"""
Bubby Vision — Auth Dependencies

FastAPI dependency for extracting the current user from JWT tokens.
"""

from __future__ import annotations

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

import structlog

from app.auth.jwt_handler import verify_token
from app.auth.models import UserResponse
from app.db.questdb_client import get_questdb

log = structlog.get_logger(__name__)

_bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
) -> UserResponse:
    """Extract and validate the current user from a JWT Bearer token.

    Usage::

        @router.get("/me")
        async def me(user: UserResponse = Depends(get_current_user)):
            return user

    Raises:
        HTTPException 401 if token is missing, invalid, or user not found.
    """
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    payload = verify_token(credentials.credentials, expected_type="access")
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
        )

    # Look up user in database
    db = get_questdb()
    user_data = db.get_user_by_id(user_id)

    if not user_data:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )

    if not user_data.get("is_active", True):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is deactivated",
        )

    return UserResponse(
        id=user_data["id"],
        email=user_data["email"],
        display_name=user_data.get("display_name"),
        is_active=user_data.get("is_active", True),
        created_at=user_data.get("created_at"),
    )
