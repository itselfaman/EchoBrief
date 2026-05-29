"""
JWT authentication via Supabase — JWKS / ES256.

Root cause of the startup error:
  The original code hard-coded algorithms=["HS256"] and used the static
  SUPABASE_JWT_SECRET as a symmetric key. However, this Supabase project
  issues access tokens signed with ES256 (ECDSA P-256), not HS256.

  Evidence — JWKS endpoint response:
    GET https://mlvbodeurnudfbukfdgk.supabase.co/auth/v1/.well-known/jwks.json
    → { "keys": [{ "alg": "ES256", "kty": "EC", "kid": "831ca911-..." }] }

  Every authenticated request was failing with:
    JWTError: The specified alg value is not allowed

Fix:
  - Fetch the project's JWKS endpoint on first use (cached for 1 hour).
  - Find the matching public key by `kid` from the token header.
  - Decode using ES256 with that public key.
  - Fall back to HS256 with SUPABASE_JWT_SECRET for tokens that still use it,
    so we handle any tokens the project may have issued before the key rotation.
"""

from __future__ import annotations

import threading
import time
import urllib.request
import json
from dataclasses import dataclass
from typing import Any

from jose import JWTError, jwt
from jose.exceptions import ExpiredSignatureError

from app.config import settings
from app.core.exceptions import AuthenticationError


# ── JWKS Cache ────────────────────────────────────────────────────────────────

_JWKS_CACHE: dict[str, Any] = {}         # kid → public key dict (JWK)
_JWKS_FETCHED_AT: float = 0.0
_JWKS_TTL: float = 3600.0                # refresh JWKS every hour
_JWKS_LOCK = threading.Lock()

_JWKS_URL = f"{settings.SUPABASE_URL}/auth/v1/.well-known/jwks.json"


def _fetch_jwks() -> dict[str, Any]:
    """Fetch the Supabase JWKS and index keys by kid."""
    with urllib.request.urlopen(_JWKS_URL, timeout=10) as resp:
        data = json.loads(resp.read())
    return {key["kid"]: key for key in data.get("keys", [])}


def _get_jwks() -> dict[str, Any]:
    """Return a cached JWKS dict, refreshing if older than TTL."""
    global _JWKS_CACHE, _JWKS_FETCHED_AT
    with _JWKS_LOCK:
        if time.monotonic() - _JWKS_FETCHED_AT > _JWKS_TTL or not _JWKS_CACHE:
            _JWKS_CACHE = _fetch_jwks()
            _JWKS_FETCHED_AT = time.monotonic()
    return _JWKS_CACHE


# ── Data Model ────────────────────────────────────────────────────────────────

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


# ── Token Validation ──────────────────────────────────────────────────────────

def verify_supabase_jwt(token: str) -> CurrentUser:
    """
    Validate a Supabase-issued JWT and return the authenticated user.

    Strategy:
    1. Peek at the token header to read `alg` and `kid`.
    2. If alg == ES256  → verify with the matching JWKS public key.
    3. If alg == HS256  → verify with the static SUPABASE_JWT_SECRET.
    4. Any other alg    → reject.
    """
    if not token:
        raise AuthenticationError("No authentication token provided.")

    # ── Peek at the unverified header ─────────────────────────────────────────
    try:
        header = jwt.get_unverified_header(token)
    except JWTError as exc:
        raise AuthenticationError(f"Malformed token header: {exc}") from exc

    alg = header.get("alg", "")
    kid = header.get("kid")

    # ── Decode based on the token's own algorithm ─────────────────────────────
    try:
        if alg == "ES256":
            payload = _decode_es256(token, kid)
        elif alg == "HS256":
            payload = _decode_hs256(token)
        else:
            raise AuthenticationError(
                f"Unsupported token algorithm '{alg}'. "
                "Expected ES256 (JWKS) or HS256."
            )
    except ExpiredSignatureError:
        raise AuthenticationError("Authentication token has expired. Please sign in again.")
    except JWTError as exc:
        raise AuthenticationError(f"Invalid authentication token: {exc}") from exc

    # ── Extract identity claims ───────────────────────────────────────────────
    sub: str | None = payload.get("sub")
    email: str | None = payload.get("email")
    role: str = payload.get("role", "authenticated")

    if not sub or not email:
        raise AuthenticationError(
            "Token is missing required identity claims (sub, email)."
        )

    return CurrentUser(user_id=sub, email=email, role=role)


def _decode_es256(token: str, kid: str | None) -> dict:
    """Decode an ES256-signed JWT using the project's JWKS public key."""
    jwks = _get_jwks()

    if not jwks:
        raise AuthenticationError(
            "JWKS endpoint returned no keys. Cannot verify ES256 token."
        )

    # Select the key by kid, or use the first key if kid is absent
    if kid and kid in jwks:
        public_key = jwks[kid]
    elif len(jwks) == 1:
        public_key = next(iter(jwks.values()))
    else:
        # kid not found — try refreshing the cache once (key rotation)
        global _JWKS_FETCHED_AT
        with _JWKS_LOCK:
            _JWKS_FETCHED_AT = 0.0   # force refresh on next call
        jwks = _get_jwks()
        public_key = jwks.get(kid) or next(iter(jwks.values()), None)
        if public_key is None:
            raise AuthenticationError(
                f"No JWKS key found for kid='{kid}'. "
                "The signing key may have been rotated."
            )

    return jwt.decode(
        token,
        public_key,
        algorithms=["ES256"],
        options={"verify_aud": False, "verify_exp": True},
    )


def _decode_hs256(token: str) -> dict:
    """Decode an HS256-signed JWT using the static SUPABASE_JWT_SECRET."""
    return jwt.decode(
        token,
        settings.SUPABASE_JWT_SECRET,
        algorithms=["HS256"],
        options={"verify_aud": False, "verify_exp": True},
    )


# ── Header Extraction ─────────────────────────────────────────────────────────

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
