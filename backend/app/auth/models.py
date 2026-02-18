"""
Bubby Vision — Auth Models

Pydantic schemas for authentication requests and responses.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, Field


# ── Request Schemas ──

class RegisterRequest(BaseModel):
    """User registration request."""
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)
    display_name: Optional[str] = Field(None, max_length=100)


class LoginRequest(BaseModel):
    """User login request."""
    email: EmailStr
    password: str


class UpdateProfileRequest(BaseModel):
    """Profile update request."""
    display_name: Optional[str] = Field(None, max_length=100)


class ChangePasswordRequest(BaseModel):
    """Password change request."""
    current_password: str
    new_password: str = Field(..., min_length=8, max_length=128)


# ── Response Schemas ──

class TokenResponse(BaseModel):
    """JWT token pair response."""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int  # seconds


class RefreshRequest(BaseModel):
    """Token refresh request."""
    refresh_token: str


class UserResponse(BaseModel):
    """Public user profile response."""
    id: str
    email: str
    display_name: Optional[str] = None
    is_active: bool = True
    created_at: Optional[datetime] = None


# ── Internal Models ──

class TokenPayload(BaseModel):
    """Decoded JWT payload."""
    sub: str  # user_id
    exp: int  # expiry timestamp
    type: str  # "access" or "refresh"
