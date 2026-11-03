"""Direct AWS Cognito Identity Provider Integration (Zero IAM Credential Overhead).

Uses unsigned public Cognito API calls so local development connects directly to
live AWS Cognito User Pools without requiring active AWS SSO / IAM credentials.
"""
import logging
from typing import Any
import boto3
from botocore import UNSIGNED
from botocore.config import Config
from botocore.exceptions import ClientError

from core.config import get_settings

logger = logging.getLogger("intelliq.cognito")


def get_cognito_client():
    """Create unsigned boto3 client for public Cognito User Pool calls."""
    settings = get_settings()
    region = settings.aws_region or "ap-south-1"
    return boto3.client(
        "cognito-idp",
        region_name=region,
        config=Config(signature_version=UNSIGNED),
    )


def cognito_sign_in(email: str, password: str) -> dict[str, Any]:
    """Authenticate email and password directly against AWS Cognito User Pool."""
    settings = get_settings()
    clean_email = email.strip().lower()

    if not settings.cognito_client_id:
        raise ValueError(
            "COGNITO_CLIENT_ID is not configured in .env. "
            "Please provide your Cognito User Pool App Client ID."
        )

    client = get_cognito_client()
    try:
        resp = client.initiate_auth(
            ClientId=settings.cognito_client_id,
            AuthFlow="USER_PASSWORD_AUTH",
            AuthParameters={
                "USERNAME": clean_email,
                "PASSWORD": password,
            },
        )
        challenge_name = resp.get("ChallengeName")
        if challenge_name == "NEW_PASSWORD_REQUIRED":
            return {
                "challenge": "NEW_PASSWORD_REQUIRED",
                "session": resp.get("Session"),
                "email": clean_email,
                "message": "Temporary password detected. You must set a new permanent password.",
            }

        auth_result = resp.get("AuthenticationResult", {})
        return {
            "access_token": auth_result.get("AccessToken"),
            "id_token": auth_result.get("IdToken"),
            "refresh_token": auth_result.get("RefreshToken"),
            "expires_in": auth_result.get("ExpiresIn", 3600),
            "token_type": auth_result.get("TokenType", "Bearer"),
        }
    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code", "AuthError")
        error_msg = e.response.get("Error", {}).get("Message", str(e))
        logger.warning("Cognito initiate_auth failed (%s): %s", error_code, error_msg)
        raise RuntimeError(f"Cognito Login Error ({error_code}): {error_msg}") from e


def cognito_sign_up(email: str, password: str, name: str | None = None) -> dict[str, Any]:
    """Register a new user in AWS Cognito User Pool."""
    settings = get_settings()
    clean_email = email.strip().lower()

    if not settings.cognito_client_id:
        raise ValueError(
            "COGNITO_CLIENT_ID is not configured in .env. "
            "Please provide your Cognito User Pool App Client ID."
        )

    user_attrs = [{"Name": "email", "Value": clean_email}]
    if name:
        user_attrs.append({"Name": "name", "Value": name})

    client = get_cognito_client()
    try:
        resp = client.sign_up(
            ClientId=settings.cognito_client_id,
            Username=clean_email,
            Password=password,
            UserAttributes=user_attrs,
        )
        return {
            "user_confirmed": resp.get("UserConfirmed", False),
            "user_sub": resp.get("UserSub"),
            "code_delivery_details": resp.get("CodeDeliveryDetails", {}),
            "message": "User registered successfully in AWS Cognito.",
        }
    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code", "SignUpError")
        error_msg = e.response.get("Error", {}).get("Message", str(e))
        logger.warning("Cognito sign_up failed (%s): %s", error_code, error_msg)
        raise RuntimeError(f"Cognito SignUp Error ({error_code}): {error_msg}") from e


def cognito_confirm_sign_up(email: str, confirmation_code: str) -> dict[str, Any]:
    """Confirm user registration with verification code."""
    settings = get_settings()
    clean_email = email.strip().lower()

    if not settings.cognito_client_id:
        raise ValueError("COGNITO_CLIENT_ID is not configured in .env.")

    client = get_cognito_client()
    try:
        client.confirm_sign_up(
            ClientId=settings.cognito_client_id,
            Username=clean_email,
            ConfirmationCode=confirmation_code.strip(),
        )
        return {"status": "confirmed", "message": "User confirmed successfully."}
    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code", "ConfirmError")
        error_msg = e.response.get("Error", {}).get("Message", str(e))
        raise RuntimeError(f"Cognito Confirm Error ({error_code}): {error_msg}") from e


def cognito_respond_new_password(
    email: str, new_password: str, session: str
) -> dict[str, Any]:
    """Respond to NEW_PASSWORD_REQUIRED challenge when user logs in with temporary password."""
    settings = get_settings()
    clean_email = email.strip().lower()

    if not settings.cognito_client_id:
        raise ValueError("COGNITO_CLIENT_ID is not configured in .env.")

    client = get_cognito_client()
    try:
        resp = client.respond_to_auth_challenge(
            ClientId=settings.cognito_client_id,
            ChallengeName="NEW_PASSWORD_REQUIRED",
            Session=session,
            ChallengeResponses={
                "USERNAME": clean_email,
                "NEW_PASSWORD": new_password,
            },
        )
        auth_result = resp.get("AuthenticationResult", {})
        if not auth_result:
            raise RuntimeError("Cognito did not return tokens after password change.")

        return {
            "access_token": auth_result.get("AccessToken"),
            "id_token": auth_result.get("IdToken"),
            "refresh_token": auth_result.get("RefreshToken"),
            "expires_in": auth_result.get("ExpiresIn", 3600),
            "token_type": auth_result.get("TokenType", "Bearer"),
        }
    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code", "ChallengeError")
        error_msg = e.response.get("Error", {}).get("Message", str(e))
        logger.warning("Cognito respond_to_auth_challenge failed (%s): %s", error_code, error_msg)
        raise RuntimeError(f"Cognito Force Change Password Error ({error_code}): {error_msg}") from e

