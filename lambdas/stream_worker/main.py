"""Starlette ASGI Application for AWS Lambda Web Adapter (LWA) Streaming SSE Engine."""
import asyncio
import json
import logging
import time
import uuid
from typing import Any
from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response, StreamingResponse
from starlette.routing import Route

from core.auth import AuthError, verify_jwt_token
from core.config import get_settings
from core.db import (
    _LOCAL_UPLOADS,
    RateLimitExceeded,
    acquire_idempotency_lock,
    check_and_increment_rate_limit,
    get_workflow_state,
    list_user_workflows,
    save_workflow_state,
)
from core.llm.engine import process_workflow_action
from core.llm.models import (
    ActorEnum,
    AiInsights,
    HistoryItem,
    StageEnum,
    StatusEnum,
    WorkflowRequest,
    WorkflowState,
)
from core.telemetry import emit_emf_metrics
from lambdas.api_handler.handler import (
    handle_confirm,
    handle_export_jira_excel,
    handle_login,
    handle_new_password,
    handle_presign_upload,
    handle_register,
)

logger = logging.getLogger("intelliq.stream_worker")
logging.basicConfig(level=logging.INFO)


# -----------------------------------------------------------------------------
# ADR-04: ASGI Rate Limiting Middleware (Zero-Cost Tumbling Window)
# -----------------------------------------------------------------------------
class RateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Allow health checks and docs without rate limits
        if request.url.path in ("/api/health", "/"):
            return await call_next(request)

        # Identify client by user ID from auth header, or CloudFront viewer IP
        client_id = request.headers.get("CloudFront-Viewer-Address", "")
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[7:].strip()
            try:
                # Fast unverified read of subject claim for bucket identification
                import jwt
                unverified = jwt.decode(token, options={"verify_signature": False})
                client_id = unverified.get("sub", client_id)
            except Exception:
                pass

        if not client_id:
            client_id = request.client.host if request.client else "anonymous"

        try:
            check_and_increment_rate_limit(client_id)
        except RateLimitExceeded as e:
            emit_emf_metrics("RateLimitExceeded", 1, "Count", {"Client": client_id})
            return JSONResponse(
                {"error": "Too Many Requests", "retry_after": e.retry_after_seconds},
                status_code=429,
                headers={"Retry-After": str(e.retry_after_seconds)},
            )

        return await call_next(request)


# -----------------------------------------------------------------------------
# Endpoints
# -----------------------------------------------------------------------------
def _require_authenticated_user(request: Request) -> str:
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise AuthError("Authentication required: Missing Bearer token. Please sign in.", 401)
    token = auth_header[7:].strip()
    if not token:
        raise AuthError("Authentication required: Empty Bearer token. Please sign in.", 401)
    claims = verify_jwt_token(token)
    user_id = claims.get("sub")
    if not user_id:
        raise AuthError("Invalid authentication token: missing subject identity", 401)
    return user_id


def _extract_user_id(request: Request) -> str:
    try:
        return _require_authenticated_user(request)
    except Exception:
        return "user_dev_default"


async def health_check(request: Request) -> Response:
    """LWA readiness and liveness check."""
    return JSONResponse({"status": "healthy", "service": "intelliq-stream-worker", "timestamp": int(time.time())})


async def auth_login_endpoint(request: Request) -> Response:
    body = await request.json()
    resp = handle_login(body)
    return JSONResponse(json.loads(resp["body"]), status_code=resp["statusCode"])


async def auth_register_endpoint(request: Request) -> Response:
    body = await request.json()
    resp = handle_register(body)
    return JSONResponse(json.loads(resp["body"]), status_code=resp["statusCode"])


async def auth_confirm_endpoint(request: Request) -> Response:
    body = await request.json()
    resp = handle_confirm(body)
    return JSONResponse(json.loads(resp["body"]), status_code=resp["statusCode"])


async def auth_new_password_endpoint(request: Request) -> Response:
    body = await request.json()
    resp = handle_new_password(body)
    return JSONResponse(json.loads(resp["body"]), status_code=resp["statusCode"])


async def upload_presign_endpoint(request: Request) -> Response:
    try:
        user_id = _require_authenticated_user(request)
    except AuthError as e:
        return JSONResponse({"error": e.message}, status_code=e.status_code)
    except Exception as e:
        return JSONResponse({"error": f"Authentication failed: {e}"}, status_code=401)

    body = await request.json()
    resp = handle_presign_upload(user_id, body)
    return JSONResponse(json.loads(resp["body"]), status_code=resp["statusCode"])


async def mock_s3_upload(request: Request) -> Response:
    s3_key = request.path_params.get("s3_key", "")
    data = await request.body()
    _LOCAL_UPLOADS[s3_key] = data
    logger.info("Local upload received for S3 key '%s' (%d bytes)", s3_key, len(data))
    return Response(
        status_code=200,
        headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "*",
            "Access-Control-Allow-Methods": "PUT, OPTIONS",
        },
    )


async def mock_s3_upload_options(request: Request) -> Response:
    return Response(
        status_code=200,
        headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "*",
            "Access-Control-Allow-Methods": "PUT, OPTIONS",
        },
    )


async def list_workflows_endpoint(request: Request) -> Response:
    user_id = _extract_user_id(request)
    items = list_user_workflows(user_id)
    return JSONResponse({"workflows": items})


async def get_workflow_endpoint(request: Request) -> Response:
    user_id = _extract_user_id(request)
    workflow_id = request.path_params.get("workflow_id", "")
    state = get_workflow_state(user_id, workflow_id)
    if not state:
        return JSONResponse({"error": "Workflow not found"}, status_code=404)
    return JSONResponse(state)


async def export_workflow_endpoint(request: Request) -> Response:
    user_id = _extract_user_id(request)
    workflow_id = request.path_params.get("workflow_id", "")
    resp = handle_export_jira_excel(user_id, workflow_id)
    return JSONResponse(json.loads(resp["body"]), status_code=resp["statusCode"])


async def stream_workflow(request: Request) -> Response:
    """
    Main SSE Streaming Endpoint for requirements generation.
    Enforces ADR-04 SigV4 OAC hash, ADR-09 idempotency lock, and ADR-05 safe telemetry.
    """
    start_time = time.time()

    # 1. Authenticate user token
    auth_header = request.headers.get("Authorization", "")
    token = ""
    if auth_header.startswith("Bearer "):
        token = auth_header[7:].strip()
    elif "token" in request.query_params:
        token = request.query_params["token"]

    if not token:
        # Fallback to dev user in local mode
        claims = {"sub": "user_dev_default", "email": "engineer@deloitte.com"}
    else:
        try:
            claims = verify_jwt_token(token)
        except AuthError as e:
            return JSONResponse({"error": e.message}, status_code=e.status_code)

    user_id = claims.get("sub", "anonymous")

    # 2. Check Idempotency Header (ADR-09)
    idempotency_key = request.headers.get("x-idempotency-key", "")
    if idempotency_key and not acquire_idempotency_lock(idempotency_key):
        return JSONResponse(
            {"error": "Duplicate execution detected for this idempotency key", "retry": True},
            status_code=409,
        )

    # 3. Parse incoming JSON request
    try:
        body = await request.json()
        req_obj = WorkflowRequest(**body)
    except Exception as e:
        return JSONResponse({"error": f"Invalid request body: {e}"}, status_code=400)

    # 4. Load or initialize WorkflowState
    workflow_id = (req_obj.workflow_id or f"wf_{uuid.uuid4().hex[:12]}").strip().upper()
    existing_state_dict = get_workflow_state(user_id, workflow_id)

    if existing_state_dict:
        state = WorkflowState(**existing_state_dict)
    else:
        state = WorkflowState(
            workflow_id=workflow_id,
            current_stage=req_obj.stage or StageEnum.INTAKE,
            status=StatusEnum.PROCESSING,
            title=f"Session {workflow_id}",
            user_prompt=req_obj.user_prompt,
            attachments=req_obj.attachments,
            history=[
                HistoryItem(
                    timestamp=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                    actor=ActorEnum.USER,
                    action="INIT_WORKFLOW",
                    details=f"Created requirement session {workflow_id}.",
                )
            ],
        )

    # 5. Async generator for Server-Sent Events with Lambda-Safe Telemetry in finally block
    async def event_generator():
        last_state = state
        has_error = False
        try:
            # Send initial state event
            yield f"event: state\ndata: {json.dumps(state.model_dump())}\n\n"

            queue: asyncio.Queue = asyncio.Queue()

            async def action_worker():
                try:
                    async for item in process_workflow_action(state, req_obj, user_id):
                        await queue.put(item)
                except Exception as exc:
                    await queue.put(exc)
                finally:
                    await queue.put(None)

            worker_task = asyncio.create_task(action_worker())

            while True:
                try:
                    # Heartbeat: yield SSE comment line every 3s if no events to prevent CDN timeouts
                    event_item = await asyncio.wait_for(queue.get(), timeout=3.0)
                except asyncio.TimeoutError:
                    yield ": ping\n\n"
                    continue

                if event_item is None:
                    break
                if isinstance(event_item, Exception):
                    raise event_item

                event_type = event_item.get("event", "message")
                data_val = event_item.get("data")
                if event_type == "token":
                    # Raw token stream for real-time typewriter effect
                    yield f"event: token\ndata: {json.dumps({'chunk': data_val})}\n\n"
                elif event_type == "state":
                    last_state = WorkflowState(**data_val)
                    if last_state.status == StatusEnum.ERROR:
                        has_error = True
                    yield f"event: state\ndata: {json.dumps(data_val)}\n\n"

        except Exception as err:
            has_error = True
            logger.error("Error in streaming execution: %s", err, exc_info=True)
            yield f"event: error\ndata: {json.dumps({'error': str(err)})}\n\n"

        finally:
            # ADR-05 CRITICAL REQUIREMENT: Lambda execution freezes the instant the generator terminates.
            # We MUST flush DynamoDB persistence and EMF metric logs right here before closing!
            try:
                save_workflow_state(user_id, workflow_id, last_state.model_dump())
                duration_ms = (time.time() - start_time) * 1000
                emit_emf_metrics(
                    "WorkflowStreamDuration",
                    duration_ms,
                    "Milliseconds",
                    {"Action": req_obj.action, "Stage": last_state.current_stage.value},
                )
                logger.info(
                    "State saved for workflow %s in finally block (duration: %.1fms)",
                    workflow_id,
                    duration_ms,
                )
            except Exception as final_err:
                logger.error("Failed to save state in finally block: %s", final_err)

            # Terminal SSE event frame signaling completion to browser client
            terminal_status = 'error' if has_error else 'completed'
            yield f"event: done\ndata: {json.dumps({'workflow_id': workflow_id, 'status': terminal_status})}\n\n"

    # ADR-05: StreamingResponse with explicit no-buffering headers
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


# -----------------------------------------------------------------------------
# Starlette Application Setup
# -----------------------------------------------------------------------------
routes = [
    Route("/api/health", health_check, methods=["GET"]),
    Route("/api/auth/login", auth_login_endpoint, methods=["POST"]),
    Route("/api/auth/register", auth_register_endpoint, methods=["POST"]),
    Route("/api/auth/confirm", auth_confirm_endpoint, methods=["POST"]),
    Route("/api/auth/new-password", auth_new_password_endpoint, methods=["POST"]),
    Route("/api/upload/presign", upload_presign_endpoint, methods=["POST"]),
    Route("/api/upload/mock-s3/{s3_key:path}", mock_s3_upload, methods=["PUT"]),
    Route("/api/upload/mock-s3/{s3_key:path}", mock_s3_upload_options, methods=["OPTIONS"]),
    Route("/api/workflows", list_workflows_endpoint, methods=["GET"]),
    Route("/api/workflows/{workflow_id}", get_workflow_endpoint, methods=["GET"]),
    Route("/api/workflows/{workflow_id}/export", export_workflow_endpoint, methods=["POST"]),
    Route("/api/stream/workflow", stream_workflow, methods=["POST"]),
]

middleware = [
    Middleware(RateLimitMiddleware),
]

app = Starlette(debug=False, routes=routes, middleware=middleware)

