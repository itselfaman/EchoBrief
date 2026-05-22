"""
JWT authentication via Supabase HS256 tokens.

Supabase issues HS256 JWTs signed with the project's JWT secret.
This module validates those tokens and extracts the current user identity.

For RS256 (JWKS-based) validation, the JWKS endpoint is:
  {SUPABASE_URL}/auth/v1/.well-known/jwks.json
"""

from __future__ import annotations

from dataclasses import dataclass

from jose import JWTError, jwt
from jose.exceptions import ExpiredSignatureError

from app.config import settings
from app.core.exceptions import AuthenticationError


@dataclass(frozen=True)
class CurrentUser:
    """
    Immutable representation of the authenticated user extracted from a JWT.

    Attributes:
        user_id: Supabase auth.users UUID (the `sub` claim).
        email:   User's email address (the `email` claim).
        role:    Supabase role (typically 'authenticated').
    """

    user_id: str
    email: str
    role: str = "authenticated"


def verify_supabase_jwt(token: str) -> CurrentUser:
    """
    Validate a Supabase-issued HS256 JWT and return the authenticated user.

    Args:
        token: Raw Bearer token string (without 'Bearer ' prefix).

    Returns:
        CurrentUser with extracted identity claims.

    Raises:
        AuthenticationError: If the token is missing, expired, or invalid.
    """
    if not token:
        raise AuthenticationError("No authentication token provided.")

    try:
        payload = jwt.decode(
            token,
            settings.SUPABASE_JWT_SECRET,
            algorithms=["HS256"],
            options={
                "verify_aud": False,   # Supabase JWTs don't always include aud
                "verify_exp": True,
            },
        )
    except ExpiredSignatureError:
        raise AuthenticationError("Authentication token has expired. Please sign in again.")
    except JWTError as exc:
        raise AuthenticationError(f"Invalid authentication token: {exc}") from exc

    sub: str | None = payload.get("sub")
    email: str | None = payload.get("email")
    role: str = payload.get("role", "authenticated")

    if not sub or not email:
        raise AuthenticationError("Token is missing required identity claims (sub, email).")

    return CurrentUser(user_id=sub, email=email, role=role)


def extract_bearer_token(authorization_header: str | None) -> str:
    """
    Extract the raw JWT from an Authorization header value.

    Args:
        authorization_header: Full value of the Authorization header,
                              expected format: "Bearer <token>"

    Returns:
        The raw JWT string.

    Raises:
        AuthenticationError: If the header is missing or malformed.
    """
    if not authorization_header:
        raise AuthenticationError("Authorization header is required.")

    scheme, _, token = authorization_header.partition(" ")

    if scheme.lower() != "bearer" or not token:
        raise AuthenticationError(
            "Authorization header must use the Bearer scheme: 'Bearer <token>'."
        )

    return token
