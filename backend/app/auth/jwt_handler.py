"""
Bubby Vision — JWT Token Handler

Creates and verifies JWT access and refresh tokens using python-jose.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt

import structlog

from app.config import get_settings

log = structlog.get_logger(__name__)


def create_access_token(user_id: str) -> str:
    """Create a short-lived access token.

    Args:
        user_id: The user's unique identifier.

    Returns:
        Encoded JWT string.
    """
    settings = get_settings()
    expires = datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_access_expiry_minutes)

    payload = {
        "sub": user_id,
        "exp": expires,
        "type": "access",
        "iat": datetime.now(timezone.utc),
    }

    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def create_refresh_token(user_id: str) -> str:
    """Create a long-lived refresh token.

    Args:
        user_id: The user's unique identifier.

    Returns:
        Encoded JWT string.
    """
    settings = get_settings()
    expires = datetime.now(timezone.utc) + timedelta(days=settings.jwt_refresh_expiry_days)

    payload = {
        "sub": user_id,
        "exp": expires,
        "type": "refresh",
        "iat": datetime.now(timezone.utc),
    }

    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def verify_token(token: str, expected_type: str = "access") -> dict | None:
    """Verify and decode a JWT token.

    Args:
        token: The JWT string to verify.
        expected_type: Expected token type ("access" or "refresh").

    Returns:
        Decoded payload dict if valid, None otherwise.
    """
    settings = get_settings()

    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )

        # Verify token type
        if payload.get("type") != expected_type:
            log.warning("jwt.wrong_type", expected=expected_type, got=payload.get("type"))
            return None

        return payload

    except JWTError as exc:
        log.warning("jwt.verification_failed", error=str(exc))
        return None
