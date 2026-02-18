"""
Bubby Vision — Auth Routes

JWT authentication endpoints: register, login, refresh, and profile.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from passlib.context import CryptContext

import structlog

from app.auth.dependencies import get_current_user
from app.auth.jwt_handler import create_access_token, create_refresh_token, verify_token
from app.auth.models import (
    ChangePasswordRequest,
    LoginRequest,
    RefreshRequest,
    RegisterRequest,
    TokenResponse,
    UpdateProfileRequest,
    UserResponse,
)
from app.config import get_settings
from app.db.questdb_client import get_questdb

log = structlog.get_logger(__name__)

auth_router = APIRouter(prefix="/auth", tags=["Authentication"])

# Password hashing context
_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def _hash_password(password: str) -> str:
    """Hash a plaintext password with bcrypt."""
    return _pwd_context.hash(password)


def _verify_password(plain: str, hashed: str) -> bool:
    """Verify a plaintext password against its hash."""
    return _pwd_context.verify(plain, hashed)


@auth_router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(body: RegisterRequest):
    """Register a new user account.

    Creates the user, hashes the password, and returns JWT tokens.
    """
    db = get_questdb()

    # Check if email already exists
    existing = db.get_user_by_email(body.email)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists",
        )

    # Create user
    user_id = str(uuid.uuid4())
    hashed = _hash_password(body.password)

    db.insert_user(
        user_id=user_id,
        email=body.email,
        hashed_password=hashed,
        display_name=body.display_name,
    )

    log.info("auth.registered", user_id=user_id, email=body.email)

    settings = get_settings()
    return TokenResponse(
        access_token=create_access_token(user_id),
        refresh_token=create_refresh_token(user_id),
        expires_in=settings.jwt_access_expiry_minutes * 60,
    )


@auth_router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest):
    """Authenticate with email and password, receive JWT tokens."""
    db = get_questdb()
    user = db.get_user_by_email(body.email)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    if not _verify_password(body.password, user["hashed_password"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    if not user.get("is_active", True):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is deactivated",
        )

    log.info("auth.login", user_id=user["id"], email=body.email)

    settings = get_settings()
    return TokenResponse(
        access_token=create_access_token(user["id"]),
        refresh_token=create_refresh_token(user["id"]),
        expires_in=settings.jwt_access_expiry_minutes * 60,
    )


@auth_router.post("/refresh", response_model=TokenResponse)
async def refresh(body: RefreshRequest):
    """Exchange a valid refresh token for a new access/refresh token pair."""
    payload = verify_token(body.refresh_token, expected_type="refresh")

    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        )

    user_id = payload["sub"]

    # Verify user still exists and is active
    db = get_questdb()
    user = db.get_user_by_id(user_id)

    if not user or not user.get("is_active", True):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or deactivated",
        )

    settings = get_settings()
    return TokenResponse(
        access_token=create_access_token(user_id),
        refresh_token=create_refresh_token(user_id),
        expires_in=settings.jwt_access_expiry_minutes * 60,
    )


@auth_router.get("/me", response_model=UserResponse)
async def get_profile(user: UserResponse = Depends(get_current_user)):
    """Get the current authenticated user's profile."""
    return user


@auth_router.patch("/profile", response_model=UserResponse)
async def update_profile(
    body: UpdateProfileRequest,
    user: UserResponse = Depends(get_current_user),
):
    """Update the current user's profile (display name)."""
    db = get_questdb()

    if body.display_name is not None:
        ok = db.update_user_display_name(user.id, body.display_name)
        if not ok:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to update profile",
            )

    # Re-fetch updated user
    updated = db.get_user_by_id(user.id)
    if not updated:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    log.info("auth.profile_updated", user_id=user.id)

    return UserResponse(
        id=updated["id"],
        email=updated["email"],
        display_name=updated.get("display_name"),
        is_active=updated.get("is_active", True),
        created_at=updated.get("created_at"),
    )


@auth_router.put("/password")
async def change_password(
    body: ChangePasswordRequest,
    user: UserResponse = Depends(get_current_user),
):
    """Change the current user's password."""
    db = get_questdb()
    full_user = db.get_user_by_id(user.id)

    if not full_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    # Verify current password
    if not _verify_password(body.current_password, full_user["hashed_password"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Current password is incorrect",
        )

    # Hash and store new password
    new_hashed = _hash_password(body.new_password)
    ok = db.update_user_password(user.id, new_hashed)
    if not ok:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update password",
        )

    log.info("auth.password_changed", user_id=user.id)
    return {"message": "Password changed successfully"}
