"""Synchronous CRUD, S3 Presigned Upload & JIRA Excel Generator Lambda Handler."""
import base64
import io
import json
import logging
import os
import time
import uuid
from typing import Any
import boto3
import jwt
import openpyxl
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from core.auth import AuthError, verify_jwt_token
from core.cognito import (
    cognito_confirm_sign_up,
    cognito_respond_new_password,
    cognito_sign_in,
    cognito_sign_up,
)
from core.config import get_settings
from core.db import (
    create_presigned_upload_url,
    get_s3_client,
    get_workflow_state,
    list_user_workflows,
    save_workflow_state,
)

logger = logging.getLogger("intelliq.api_handler")
logging.basicConfig(level=logging.INFO)


def _json_resp(status_code: int, body: dict[str, Any]) -> dict[str, Any]:
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "*",
            "Access-Control-Allow-Methods": "GET,POST,PUT,DELETE,OPTIONS",
        },
        "body": json.dumps(body),
    }


def _authenticate_request(event: dict[str, Any]) -> dict[str, Any]:
    headers = {k.lower(): v for k, v in (event.get("headers") or {}).items()}
    auth_header = headers.get("authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header[7:].strip()
        return verify_jwt_token(token)
    # Mock/dev fallback
    return {
        "sub": "user_dev_default",
        "email": "engineer@deloitte.com",
        "name": "Deloitte Lead Architect",
    }


def handle_login(body: dict[str, Any]) -> dict[str, Any]:
    """Authenticate email and password directly with AWS Cognito User Pool."""
    settings = get_settings()
    email = body.get("email", "").strip().lower()
    password = body.get("password", "")

    if not email or not password:
        return _json_resp(400, {"error": "Email and password are required"})

    if not settings.cognito_client_id:
        return _json_resp(
            400,
            {
                "error": "COGNITO_CLIENT_ID is not configured in .env. Please set your AWS Cognito User Pool Client ID."
            },
        )

    try:
        auth_res = cognito_sign_in(email, password)
        if auth_res.get("challenge") == "NEW_PASSWORD_REQUIRED":
            return _json_resp(200, {
                "challenge": "NEW_PASSWORD_REQUIRED",
                "session": auth_res["session"],
                "email": auth_res["email"],
                "message": auth_res.get("message", "Temporary password detected. You must set a new permanent password."),
            })

        claims = {}
        if auth_res.get("id_token"):
            try:
                claims = verify_jwt_token(auth_res["id_token"])
            except Exception:
                pass

        return _json_resp(200, {
            "access_token": auth_res["access_token"],
            "id_token": auth_res.get("id_token", auth_res["access_token"]),
            "refresh_token": auth_res.get("refresh_token"),
            "user": {
                "sub": claims.get("sub", auth_res["access_token"][:12]),
                "email": claims.get("email", email),
                "name": claims.get("name") or email.split("@")[0].replace(".", " ").title(),
                "role": "Lead Architect",
            },
        })
    except Exception as e:
        return _json_resp(401, {"error": str(e)})


def handle_new_password(body: dict[str, Any]) -> dict[str, Any]:
    """Respond to NEW_PASSWORD_REQUIRED challenge with a new permanent password."""
    email = body.get("email", "").strip().lower()
    new_password = body.get("new_password", "")
    session = body.get("session", "")

    if not email or not new_password or not session:
        return _json_resp(400, {"error": "Email, new_password, and challenge session are required"})

    try:
        auth_res = cognito_respond_new_password(email, new_password, session)
        claims = {}
        if auth_res.get("id_token"):
            try:
                claims = verify_jwt_token(auth_res["id_token"])
            except Exception:
                pass

        return _json_resp(200, {
            "access_token": auth_res["access_token"],
            "id_token": auth_res.get("id_token", auth_res["access_token"]),
            "refresh_token": auth_res.get("refresh_token"),
            "user": {
                "sub": claims.get("sub", auth_res["access_token"][:12]),
                "email": claims.get("email", email),
                "name": claims.get("name") or email.split("@")[0].replace(".", " ").title(),
                "role": "Lead Architect",
            },
        })
    except Exception as e:
        return _json_resp(400, {"error": str(e)})


def handle_register(body: dict[str, Any]) -> dict[str, Any]:
    """Register a new user directly in AWS Cognito User Pool."""
    settings = get_settings()
    email = body.get("email", "").strip().lower()
    password = body.get("password", "")
    name = body.get("name", "")

    if not email or not password:
        return _json_resp(400, {"error": "Email and password are required for registration"})

    if not settings.cognito_client_id:
        return _json_resp(
            400,
            {
                "error": "COGNITO_CLIENT_ID is not configured in .env. Please set your AWS Cognito User Pool Client ID."
            },
        )

    try:
        reg_res = cognito_sign_up(email, password, name)
        return _json_resp(200, reg_res)
    except Exception as e:
        return _json_resp(400, {"error": str(e)})


def handle_confirm(body: dict[str, Any]) -> dict[str, Any]:
    """Confirm user registration with verification code."""
    email = body.get("email", "").strip().lower()
    code = body.get("code", "")
    if not email or not code:
        return _json_resp(400, {"error": "Email and confirmation code are required"})
    try:
        res = cognito_confirm_sign_up(email, code)
        return _json_resp(200, res)
    except Exception as e:
        return _json_resp(400, {"error": str(e)})


def handle_presign_upload(user_id: str, body: dict[str, Any]) -> dict[str, Any]:
    """Generate S3 Presigned PUT URL for direct client upload (ADR-09 safeguard)."""
    filename = body.get("filename", "upload.txt")
    mime_type = body.get("mime_type", "application/octet-stream")
    session_id = (body.get("session_id") or body.get("workflow_id") or "default").strip().upper()
    file_ext = os.path.splitext(filename)[1].lower()
    file_uuid = uuid.uuid4().hex[:10]

    s3_key = f"uploads/{user_id}/{session_id}/{file_uuid}_{filename}"
    res = create_presigned_upload_url(s3_key=s3_key, content_type=mime_type)
    return _json_resp(200, res)


def handle_export_jira_excel(user_id: str, workflow_id: str) -> dict[str, Any]:
    """
    Generate professional JIRA-compatible Excel (.xlsx) workbook with complete
    traceability from BRD -> Epics -> User Stories -> Test Cases.
    """
    state_dict = get_workflow_state(user_id, workflow_id)
    if not state_dict:
        return _json_resp(404, {"error": "Workflow state not found"})

    wb = openpyxl.Workbook()
    # Remove default sheet
    wb.remove(wb.active)

    # Styles
    header_fill = PatternFill(start_color="000000", end_color="000000", fill_type="solid")
    header_font = Font(name="Arial", size=11, bold=True, color="FFFFFF")
    accent_fill = PatternFill(start_color="86BC25", end_color="86BC25", fill_type="solid")
    accent_font = Font(name="Arial", size=11, bold=True, color="000000")
    bold_font = Font(name="Arial", size=10, bold=True)
    body_font = Font(name="Arial", size=10)
    thin_border = Border(
        left=Side(style="thin", color="D8D8DC"),
        right=Side(style="thin", color="D8D8DC"),
        top=Side(style="thin", color="D8D8DC"),
        bottom=Side(style="thin", color="D8D8DC"),
    )

    # 1. Sheet: Executive Summary & Traceability
    ws_summary = wb.create_sheet(title="Executive Summary")
    ws_summary.append(["INTELLIQ REQUIREMENTS & TEST TRACEABILITY DOSSIER"])
    ws_summary.append(["Generated by Deloitte IntelliQ Serverless AI Platform"])
    ws_summary.append([])
    ws_summary.append(["Project Title:", state_dict.get("title", "Untitled Project")])
    ws_summary.append(["Workflow ID:", workflow_id])
    ws_summary.append(["Status:", state_dict.get("status", "completed").upper()])
    ws_summary.append(["Export Date (UTC):", time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime())])
    ws_summary.append([])

    ws_summary.append(["METRIC SUMMARY", "COUNT"])
    epics_count = len(state_dict.get("epics", []))
    stories_count = len(state_dict.get("stories", []))
    tests_count = len(state_dict.get("test_cases", []))
    ws_summary.append(["Total Epics", epics_count])
    ws_summary.append(["Total User Stories", stories_count])
    ws_summary.append(["Total JIRA Test Cases", tests_count])

    # 2. Sheet: BRD Document
    brd = state_dict.get("brd") or {}
    ws_brd = wb.create_sheet(title="BRD Overview")
    ws_brd.append(["Section", "Content"])
    ws_brd.append(["Title", brd.get("title", state_dict.get("title", ""))])
    ws_brd.append(["Executive Summary", brd.get("executive_summary", "")])
    ws_brd.append(["Business Objectives", "\n".join(f"• {obj}" for obj in brd.get("business_objectives", []))])
    ws_brd.append(["In-Scope Scope", "\n".join(f"• {item}" for item in brd.get("in_scope", []))])
    ws_brd.append(["Out-of-Scope", "\n".join(f"• {item}" for item in brd.get("out_of_scope", []))])

    # 3. Sheet: Epics (JIRA Format)
    ws_epics = wb.create_sheet(title="JIRA Epics")
    epic_headers = ["Issue Type", "Epic Key", "Summary", "Description / Value", "Priority", "Acceptance Criteria"]
    ws_epics.append(epic_headers)
    for col_idx, cell in enumerate(ws_epics[1], start=1):
        cell.fill = header_fill
        cell.font = header_font

    for ep in state_dict.get("epics", []):
        ws_epics.append([
            "Epic",
            ep.get("id"),
            ep.get("title"),
            ep.get("business_value") or ep.get("summary"),
            ep.get("priority", "HIGH"),
            "\n".join(ep.get("acceptance_criteria", [])),
        ])

    # 4. Sheet: User Stories (JIRA Format)
    ws_stories = wb.create_sheet(title="JIRA User Stories")
    story_headers = ["Issue Type", "Story Key", "Epic Link", "Summary", "As A", "I Want To", "So That", "Story Points", "Priority", "Gherkin Acceptance Criteria"]
    ws_stories.append(story_headers)
    for col_idx, cell in enumerate(ws_stories[1], start=1):
        cell.fill = header_fill
        cell.font = header_font

    for st in state_dict.get("stories", []):
        ws_stories.append([
            "Story",
            st.get("id"),
            st.get("epic_id"),
            st.get("title"),
            st.get("user_role"),
            st.get("capability"),
            st.get("benefit"),
            st.get("story_points", 3),
            st.get("priority", "MUST_HAVE"),
            "\n".join(st.get("acceptance_criteria_gherkin", [])),
        ])

    # 5. Sheet: JIRA Test Cases (Xray / Zephyr Compatible Format)
    ws_tests = wb.create_sheet(title="JIRA Test Cases")
    test_headers = [
        "Issue Type",
        "Test Key",
        "Summary",
        "Linked User Story",
        "Linked Epic",
        "Test Type",
        "Execution Priority",
        "Preconditions",
        "Step Number",
        "Action / Description",
        "Expected Result",
        "Postconditions",
    ]
    ws_tests.append(test_headers)
    for col_idx, cell in enumerate(ws_tests[1], start=1):
        cell.fill = accent_fill
        cell.font = accent_font

    for tc in state_dict.get("test_cases", []):
        steps = tc.get("steps", [])
        if not steps:
            steps = [{"step_number": 1, "action": "Execute test logic", "expected_result": "Success"}]

        for idx, step in enumerate(steps):
            if isinstance(step, str):
                step_num = idx + 1
                action = step
                expected = ""
            elif isinstance(step, dict):
                step_num = step.get("step_number", idx + 1)
                action = step.get("action", "")
                expected = step.get("expected_result", "")
            else:
                step_num = getattr(step, "step_number", idx + 1)
                action = getattr(step, "action", str(step))
                expected = getattr(step, "expected_result", "")

            ws_tests.append([
                "Test",
                tc.get("id"),
                tc.get("title"),
                tc.get("story_id"),
                tc.get("epic_id"),
                tc.get("test_type", "POSITIVE"),
                tc.get("priority", "HIGH"),
                "\n".join(tc.get("preconditions", [])) if idx == 0 else "",
                step_num,
                action,
                expected,
                tc.get("postconditions", "") if idx == 0 else "",
            ])

    # Autofit column widths across all sheets
    for sheet in wb.worksheets:
        for col in sheet.columns:
            max_len = 0
            col_letter = get_column_letter(col[0].column)
            for cell in col:
                val = str(cell.value or "")
                lines = val.split("\n")
                line_max = max(len(l) for l in lines) if lines else len(val)
                if line_max > max_len:
                    max_len = line_max
                if cell.row > 1 and sheet.title != "Executive Summary":
                    cell.font = body_font
                cell.border = thin_border
                cell.alignment = Alignment(wrap_text=True, vertical="top")
            sheet.column_dimensions[col_letter].width = min(max(max_len + 3, 12), 50)

    # Save to buffer
    output_stream = io.BytesIO()
    wb.save(output_stream)
    excel_bytes = output_stream.getvalue()

    # Save artifact to S3
    settings = get_settings()
    s3_key = f"exports/{workflow_id}/intelliq_jira_package.xlsx"
    try:
        s3 = get_s3_client()
        s3.put_object(
            Bucket=settings.s3_bucket,
            Key=s3_key,
            Body=excel_bytes,
            ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
    except Exception as e:
        logger.warning("Could not save Excel to S3: %s", e)

    # Return base64 payload and S3 key
    b64_content = base64.b64encode(excel_bytes).decode("utf-8")
    return _json_resp(200, {
        "filename": f"{state_dict.get('title', 'intelliq').lower().replace(' ', '_')}_jira_test_cases.xlsx",
        "s3_key": s3_key,
        "content_base64": b64_content,
        "size_bytes": len(excel_bytes),
        "epics_exported": epics_count,
        "stories_exported": stories_count,
        "test_cases_exported": tests_count,
    })


def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """Main routing handler for API Gateway / CloudFront."""
    raw_path = event.get("rawPath") or event.get("path") or ""
    http_method = (
        event.get("requestContext", {}).get("http", {}).get("method")
        or event.get("httpMethod")
        or "GET"
    ).upper()

    # Handle CORS preflight
    if http_method == "OPTIONS":
        return _json_resp(200, {"status": "ok"})

    # Parse body
    body = {}
    raw_body = event.get("body")
    if raw_body:
        if event.get("isBase64Encoded"):
            raw_body = base64.b64decode(raw_body).decode("utf-8")
        try:
            body = json.loads(raw_body)
        except Exception:
            body = {}

    # Health check endpoint
    if "/api/health" in raw_path:
        return _json_resp(200, {"status": "healthy", "service": "api_handler"})

    # Public Auth endpoints
    if "/api/auth/login" in raw_path and http_method == "POST":
        return handle_login(body)
    if "/api/auth/new-password" in raw_path and http_method == "POST":
        return handle_new_password(body)
    if "/api/auth/register" in raw_path and http_method == "POST":
        return handle_login(body)  # Lite mode auto-registers

    # Authenticated endpoints
    try:
        claims = _authenticate_request(event)
        user_id = claims.get("sub", "user_dev_default")
    except AuthError as e:
        return _json_resp(e.status_code, {"error": e.message})

    # Upload presign
    if "/api/upload/presign" in raw_path and http_method == "POST":
        return handle_presign_upload(user_id, body)

    # List workflows
    if raw_path.rstrip("/") == "/api/workflows" and http_method == "GET":
        items = list_user_workflows(user_id)
        return _json_resp(200, {"workflows": items})

    # Export JIRA Excel
    if "/api/workflows/" in raw_path and "/export" in raw_path and http_method == "POST":
        # Extract workflow_id
        parts = raw_path.split("/")
        wf_idx = parts.index("workflows") + 1
        workflow_id = parts[wf_idx]
        return handle_export_jira_excel(user_id, workflow_id)

    # Get single workflow
    if "/api/workflows/" in raw_path and http_method == "GET":
        parts = raw_path.split("/")
        workflow_id = parts[-1]
        state = get_workflow_state(user_id, workflow_id)
        if not state:
            return _json_resp(404, {"error": "Workflow not found"})
        return _json_resp(200, state)

    return _json_resp(404, {"error": f"Route not found: {http_method} {raw_path}"})
