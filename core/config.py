"""Configuration loader with cold-start caching and zero-cost SSM fallback."""
import os
from functools import lru_cache
from typing import NamedTuple


def _load_env_file() -> None:
    """Zero-dependency .env loader for local development without bloat."""
    # Check current directory and parent directory for .env
    for candidate in [os.path.join(os.getcwd(), ".env"), os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".env"))]:
        if os.path.isfile(candidate):
            try:
                with open(candidate, encoding="utf-8") as f:
                    for line in f:
                        stripped = line.strip()
                        if not stripped or stripped.startswith("#") or "=" not in stripped:
                            continue
                        k, v = stripped.split("=", 1)
                        k = k.strip()
                        v = v.strip().strip("'\"")
                        if k and k not in os.environ:
                            os.environ[k] = v
            except Exception:
                pass
            break


_load_env_file()


class Settings(NamedTuple):
    app_name: str
    stage: str
    aws_region: str
    dynamodb_table: str
    s3_bucket: str
    cognito_user_pool_id: str
    cognito_client_id: str
    allowed_email_domains: list[str]
    gemini_api_key: str
    gemini_model: str
    groq_api_key: str
    groq_model: str
    openai_api_key: str
    rate_limit_max: int
    rate_limit_window_seconds: int


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Load settings once per Lambda lifecycle."""
    allowed_domains_raw = os.getenv("ALLOWED_EMAIL_DOMAINS", "*")
    allowed_domains = (
        [d.strip().lower() for d in allowed_domains_raw.split(",") if d.strip()]
        if allowed_domains_raw != "*"
        else ["*"]
    )

    return Settings(
        app_name=os.getenv("APP_NAME", "intelliq"),
        stage=os.getenv("STAGE", "dev"),
        aws_region=os.getenv("AWS_REGION", "us-east-1"),
        dynamodb_table=os.getenv("TABLE_NAME", os.getenv("DYNAMODB_TABLE_NAME", "intelliq-db")),
        s3_bucket=os.getenv("BUCKET_NAME", os.getenv("S3_BUCKET_NAME", "intelliq-storage")),
        cognito_user_pool_id=os.getenv("COGNITO_USER_POOL_ID", ""),
        cognito_client_id=os.getenv("COGNITO_CLIENT_ID", ""),
        allowed_email_domains=allowed_domains,
        gemini_api_key=os.getenv("GEMINI_API_KEY", ""),
        gemini_model=os.getenv("GEMINI_MODEL", ""),
        groq_api_key=os.getenv("GROQ_API_KEY", ""),
        groq_model=os.getenv("GROQ_MODEL", ""),
        openai_api_key=os.getenv("OPENAI_API_KEY", ""),
        rate_limit_max=int(os.getenv("RATE_LIMIT_MAX_REQUESTS", "60")),
        rate_limit_window_seconds=int(os.getenv("RATE_LIMIT_WINDOW_SECONDS", "300")),
    )

