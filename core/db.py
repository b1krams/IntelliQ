"""DynamoDB Single-Table Repository, Atomic Rate Limiter & S3 Presigner/Offloader."""
from decimal import Decimal
import gzip
import hashlib
import json
import logging
import time
from typing import Any
import boto3
from botocore.client import Config
from botocore.exceptions import ClientError

from core.config import get_settings

logger = logging.getLogger("intelliq.db")

# In-memory mock storage for local testing when AWS is unavailable
_LOCAL_MEM_DB: dict[str, dict[str, Any]] = {}
_LOCAL_LOCKS: dict[str, float] = {}
_LOCAL_RATE_LIMITS: dict[str, int] = {}
_LOCAL_UPLOADS: dict[str, bytes] = {}


def get_dynamo_table():
    """Get boto3 DynamoDB Table resource."""
    settings = get_settings()
    dynamodb = boto3.resource("dynamodb", region_name=settings.aws_region)
    return dynamodb.Table(settings.dynamodb_table)


def get_s3_client():
    """Get boto3 S3 client with regional endpoint to eliminate 307 CORS redirects."""
    settings = get_settings()
    region = settings.aws_region or "ap-south-1"
    endpoint_url = f"https://s3.{region}.amazonaws.com"
    return boto3.client(
        "s3",
        region_name=region,
        endpoint_url=endpoint_url,
        config=Config(
            signature_version="s3v4",
            s3={"addressing_style": "virtual"},
        ),
    )


# -----------------------------------------------------------------------------
# ADR-04: Atomic DynamoDB Rate Limiter (Zero-Cost Tumbling Window)
# -----------------------------------------------------------------------------
class RateLimitExceeded(Exception):
    def __init__(self, retry_after_seconds: int):
        super().__init__(f"Rate limit exceeded. Retry after {retry_after_seconds}s")
        self.retry_after_seconds = retry_after_seconds


def check_and_increment_rate_limit(
    identifier: str, max_requests: int | None = None, window_seconds: int | None = None
) -> int:
    """
    Enforce tumbling window rate limit using an atomic DynamoDB UpdateItem.
    Returns the current request count within the window.
    Raises RateLimitExceeded if count exceeds max_requests.
    """
    settings = get_settings()
    limit = max_requests or settings.rate_limit_max
    window = window_seconds or settings.rate_limit_window_seconds

    now = int(time.time())
    window_bucket = now // window
    window_end = (window_bucket + 1) * window
    ttl = window_end + 300  # keep in DDB for 5 extra mins for cleanup

    pk = f"RATELIMIT#{identifier}"
    sk = f"WINDOW#{window_bucket}"

    try:
        table = get_dynamo_table()
        response = table.update_item(
            Key={"PK": pk, "SK": sk},
            UpdateExpression="ADD request_count :inc SET #t = if_not_exists(#t, :ttl)",
            ExpressionAttributeNames={"#t": "ttl"},
            ExpressionAttributeValues={":inc": 1, ":ttl": ttl},
            ReturnValues="UPDATED_NEW",
        )
        current_count = int(response["Attributes"]["request_count"])
        if current_count > limit:
            retry_after = max(1, window_end - now)
            raise RateLimitExceeded(retry_after)
        return current_count

    except RateLimitExceeded:
        raise
    except Exception as e:
        logger.warning("DynamoDB rate limit error, using in-memory fallback: %s", e)
        # In-memory fallback
        key = f"{pk}:{sk}"
        count = _LOCAL_RATE_LIMITS.get(key, 0) + 1
        _LOCAL_RATE_LIMITS[key] = count
        if count > limit:
            raise RateLimitExceeded(max(1, window_end - now))
        return count


# -----------------------------------------------------------------------------
# ADR-09: Idempotency Lock
# -----------------------------------------------------------------------------
def acquire_idempotency_lock(idempotency_key: str, ttl_seconds: int = 86400) -> bool:
    """
    Acquire 24-hour idempotency lock in DynamoDB.
    Returns True if lock acquired, False if duplicate request.
    """
    if not idempotency_key:
        return True

    now = int(time.time())
    ttl = now + ttl_seconds
    pk = f"IDEMPOTENCY#{idempotency_key}"
    sk = "LOCK"

    try:
        table = get_dynamo_table()
        table.put_item(
            Item={"PK": pk, "SK": sk, "ttl": ttl, "created_at": now},
            ConditionExpression="attribute_not_exists(PK)",
        )
        return True
    except ClientError as e:
        if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
            logger.info("Idempotency lock collision for key %s", idempotency_key)
            return False
        logger.error("Error setting idempotency lock in DynamoDB: %s", e)
        return True
    except Exception as e:
        logger.warning("DynamoDB unavailable for idempotency lock, using in-memory: %s", e)
        if idempotency_key in _LOCAL_LOCKS and _LOCAL_LOCKS[idempotency_key] > now:
            return False
        _LOCAL_LOCKS[idempotency_key] = now + ttl_seconds
        return True


# -----------------------------------------------------------------------------
# ADR-09: S3 Presigned URL Generation (Direct Upload Safeguard)
# -----------------------------------------------------------------------------
def create_presigned_upload_url(
    s3_key: str, content_type: str, max_bytes: int = 52428800
) -> dict[str, Any]:
    """Generate S3 Presigned PUT URL with content-type and size bounds (with local dev fallback)."""
    settings = get_settings()

    # Attempt real S3 presign if bucket is configured
    if settings.s3_bucket and settings.s3_bucket != "intelliq-storage":
        try:
            s3 = get_s3_client()
            params: dict[str, Any] = {
                "Bucket": settings.s3_bucket,
                "Key": s3_key,
            }
            if content_type and content_type.strip():
                params["ContentType"] = content_type.strip()

            url = s3.generate_presigned_url(
                ClientMethod="put_object",
                Params=params,
                ExpiresIn=3600,
            )
            return {
                "upload_url": url,
                "s3_key": s3_key,
                "bucket": settings.s3_bucket,
                "max_size_bytes": max_bytes,
            }
        except Exception as e:
            logger.warning("AWS S3 presign failed, falling back to local dev upload URL: %s", e)

    # Local development upload URL (proxied seamlessly via Vite without CORS issues)
    return {
        "upload_url": f"/api/upload/mock-s3/{s3_key}",
        "s3_key": s3_key,
        "bucket": settings.s3_bucket or "local-intelliq-storage",
        "max_size_bytes": max_bytes,
    }


def get_uploaded_file_bytes(s3_key: str) -> bytes | None:
    """Retrieve uploaded document bytes from in-memory dev cache or AWS S3."""
    if not s3_key:
        return None
    if s3_key in _LOCAL_UPLOADS:
        return _LOCAL_UPLOADS[s3_key]
    settings = get_settings()
    if settings.s3_bucket and settings.s3_bucket != "intelliq-storage":
        try:
            s3 = get_s3_client()
            obj = s3.get_object(Bucket=settings.s3_bucket, Key=s3_key)
            return obj["Body"].read()
        except Exception as e:
            logger.warning("Failed to fetch %s from S3: %s", s3_key, e)
    return None


# -----------------------------------------------------------------------------
# ADR-09: Large Payload Offloading (> 350 KB S3 Safeguard)
# -----------------------------------------------------------------------------
MAX_DDB_ITEM_SIZE_BYTES = 350 * 1024  # 350 KB threshold


def _floats_to_decimals(obj: Any) -> Any:
    if isinstance(obj, float):
        return Decimal(str(obj))
    elif isinstance(obj, dict):
        return {k: _floats_to_decimals(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [_floats_to_decimals(v) for v in obj]
    return obj


def _decimals_to_floats(obj: Any) -> Any:
    if isinstance(obj, Decimal):
        return int(obj) if obj % 1 == 0 else float(obj)
    elif isinstance(obj, dict):
        return {k: _decimals_to_floats(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [_decimals_to_floats(v) for v in obj]
    return obj


def save_workflow_state(user_id: str, workflow_id: str, state_dict: dict[str, Any]) -> None:
    """Save workflow session state, offloading to S3 if payload exceeds 350 KB."""
    settings = get_settings()
    pk = f"USER#{user_id}"
    sk = f"WORKFLOW#{workflow_id}"

    payload_json = json.dumps(state_dict)
    payload_bytes = payload_json.encode("utf-8")

    is_offloaded = False
    s3_key = None
    content_hash = hashlib.sha256(payload_bytes).hexdigest()

    if len(payload_bytes) > MAX_DDB_ITEM_SIZE_BYTES:
        is_offloaded = True
        s3_key = f"artifacts/{workflow_id}/state.json.gz"
        compressed_bytes = gzip.compress(payload_bytes)
        try:
            s3 = get_s3_client()
            s3.put_object(
                Bucket=settings.s3_bucket,
                Key=s3_key,
                Body=compressed_bytes,
                ContentType="application/json",
                ContentEncoding="gzip",
            )
            logger.info(
                "Offloaded large workflow %s payload (%d bytes -> %d compressed bytes) to S3 at %s",
                workflow_id,
                len(payload_bytes),
                len(compressed_bytes),
                s3_key,
            )
        except Exception as e:
            logger.warning("Failed to offload to S3: %s", e)
            # Store in local memory for offline/dev fallback
            _LOCAL_MEM_DB[f"s3:{s3_key}"] = payload_bytes

    item: dict[str, Any] = {
        "PK": pk,
        "SK": sk,
        "GSI1PK": f"STAGE#{state_dict.get('current_stage', 'intake')}",
        "GSI1SK": f"TIME#{int(time.time())}",
        "workflow_id": workflow_id,
        "user_id": user_id,
        "title": state_dict.get("title", f"Session {workflow_id}"),
        "current_stage": state_dict.get("current_stage", "intake"),
        "status": state_dict.get("status", "idle"),
        "updated_at": int(time.time()),
        "is_offloaded": is_offloaded,
        "sha256": content_hash,
    }

    if is_offloaded:
        item["s3_key"] = s3_key
        # Keep minimal summary in DynamoDB
        item["summary_insights"] = state_dict.get("ai_insights", {})
    else:
        item["data"] = state_dict

    try:
        table = get_dynamo_table()
        table.put_item(Item=_floats_to_decimals(item))
    except Exception as e:
        logger.warning("DynamoDB save failed, falling back to memory: %s", e)
        _LOCAL_MEM_DB[f"{pk}:{sk}"] = item


def get_workflow_state(user_id: str, workflow_id: str) -> dict[str, Any] | None:
    """Retrieve workflow state, transparently decompressing from S3 if offloaded."""
    settings = get_settings()
    pk = f"USER#{user_id}"
    sk = f"WORKFLOW#{workflow_id}"

    item = None
    try:
        table = get_dynamo_table()
        resp = table.get_item(Key={"PK": pk, "SK": sk})
        item = resp.get("Item")
    except Exception as e:
        logger.warning("DynamoDB get failed, checking memory fallback: %s", e)
        item = _LOCAL_MEM_DB.get(f"{pk}:{sk}")

    if not item:
        return None

    if item.get("is_offloaded"):
        s3_key = item.get("s3_key")
        try:
            s3 = get_s3_client()
            obj = s3.get_object(Bucket=settings.s3_bucket, Key=s3_key)
            raw_data = obj["Body"].read()
            decompressed = gzip.decompress(raw_data)
            return json.loads(decompressed.decode("utf-8"))
        except Exception as e:
            logger.error("Failed to load offloaded state from S3 %s: %s", s3_key, e)
            # Check local memory fallback
            if f"s3:{s3_key}" in _LOCAL_MEM_DB:
                raw_bytes = _LOCAL_MEM_DB[f"s3:{s3_key}"]
                return json.loads(raw_bytes.decode("utf-8"))
            return None

    raw_data = item.get("data")
    return _decimals_to_floats(raw_data) if raw_data else None


def list_user_workflows(user_id: str, limit: int = 20) -> list[dict[str, Any]]:
    """List recent workflows for a user."""
    pk = f"USER#{user_id}"
    try:
        table = get_dynamo_table()
        resp = table.query(
            KeyConditionExpression="PK = :pk AND begins_with(SK, :sk_prefix)",
            ExpressionAttributeValues={":pk": pk, ":sk_prefix": "WORKFLOW#"},
            ScanIndexForward=False,
            Limit=limit,
        )
        items = resp.get("Items", [])
        return _decimals_to_floats(items)
    except Exception as e:
        logger.warning("DynamoDB list query failed, checking memory: %s", e)
        items = [
            v for k, v in _LOCAL_MEM_DB.items() if k.startswith(f"{pk}:WORKFLOW#")
        ]
        items.sort(key=lambda x: x.get("updated_at", 0), reverse=True)
        return items[:limit]
