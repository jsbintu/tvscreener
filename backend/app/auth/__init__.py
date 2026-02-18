"""
Bubby Vision — Auth Module

JWT-based user authentication with registration, login, and token refresh.
"""

from app.auth.dependencies import get_current_user  # noqa: F401
from app.auth.routes import auth_router  # noqa: F401

__all__ = ["auth_router", "get_current_user"]
