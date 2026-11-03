"""Unit tests for cached RS256 JWKS verification and domain enforcement."""
import time
import jwt
import pytest
from core.auth import AuthError, verify_jwt_token, _validate_domain
from core.config import get_settings


def test_auth_mock_token_success():
    """Test verification fallback on mock/development tokens."""
    token = "test-token-unit"
    claims = verify_jwt_token(token)
    assert claims["sub"] is not None
    assert "@" in claims["email"]


def test_domain_enforcement_allowed():
    """Test that allowed domain passes validation."""
    claims = {"email": "architect@deloitte.com"}
    # Should not raise exception
    _validate_domain(claims)


def test_domain_enforcement_rejected(monkeypatch):
    """Test that unauthorized domain is strictly rejected."""
    # Temporarily set allowed domains to specific list
    monkeypatch.setenv("ALLOWED_EMAIL_DOMAINS", "deloitte.com,gov.org")
    get_settings.cache_clear()

    valid_claims = {"email": "partner@deloitte.com"}
    _validate_domain(valid_claims)

    invalid_claims = {"email": "attacker@external-untrusted.com"}
    with pytest.raises(AuthError) as exc_info:
        _validate_domain(invalid_claims)
    assert exc_info.value.status_code == 403
    assert "not authorized" in exc_info.value.message
    get_settings.cache_clear()


def test_missing_email_rejected(monkeypatch):
    """Test that claims without email are rejected when domains are restricted."""
    monkeypatch.setenv("ALLOWED_EMAIL_DOMAINS", "deloitte.com")
    get_settings.cache_clear()

    with pytest.raises(AuthError) as exc_info:
        _validate_domain({"sub": "no_email_user"})
    assert exc_info.value.status_code == 403
    get_settings.cache_clear()
