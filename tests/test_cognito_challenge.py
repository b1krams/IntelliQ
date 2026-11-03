"""Unit test for Cognito NEW_PASSWORD_REQUIRED (force change password) workflow."""
from unittest.mock import MagicMock, patch
import pytest
from core.cognito import cognito_respond_new_password, cognito_sign_in
from lambdas.api_handler.handler import handle_login, handle_new_password


def test_cognito_sign_in_new_password_required_challenge():
    """Verify that initiate_auth returning NEW_PASSWORD_REQUIRED is formatted correctly."""
    mock_boto_client = MagicMock()
    mock_boto_client.initiate_auth.return_value = {
        "ChallengeName": "NEW_PASSWORD_REQUIRED",
        "Session": "session_test_token_xyz_123",
        "ChallengeParameters": {"USER_ID_FOR_SRP": "user@deloitte.com"},
    }

    with patch("core.cognito.get_cognito_client", return_value=mock_boto_client):
        res = cognito_sign_in("user@deloitte.com", "TempPassword123!")

    assert res["challenge"] == "NEW_PASSWORD_REQUIRED"
    assert res["session"] == "session_test_token_xyz_123"
    assert res["email"] == "user@deloitte.com"


def test_handle_login_returns_challenge():
    """Verify handle_login returns HTTP 200 with challenge details."""
    with patch(
        "lambdas.api_handler.handler.cognito_sign_in",
        return_value={
            "challenge": "NEW_PASSWORD_REQUIRED",
            "session": "session_abc",
            "email": "user@deloitte.com",
            "message": "Temporary password detected.",
        },
    ):
        resp = handle_login({"email": "user@deloitte.com", "password": "TempPassword123!"})

    assert resp["statusCode"] == 200
    import json
    body = json.loads(resp["body"])
    assert body["challenge"] == "NEW_PASSWORD_REQUIRED"
    assert body["session"] == "session_abc"


def test_handle_new_password_success():
    """Verify handle_new_password returns JWT session upon successful response."""
    with patch(
        "lambdas.api_handler.handler.cognito_respond_new_password",
        return_value={
            "access_token": "acc_tok_123",
            "id_token": "id_tok_123",
            "refresh_token": "ref_tok_123",
            "expires_in": 3600,
        },
    ):
        resp = handle_new_password({
            "email": "user@deloitte.com",
            "new_password": "NewPermanentPassword123!",
            "session": "session_abc",
        })

    assert resp["statusCode"] == 200
    import json
    body = json.loads(resp["body"])
    assert body["access_token"] == "acc_tok_123"
    assert body["user"]["email"] == "user@deloitte.com"

