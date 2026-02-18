"""
Bubby Vision — Authentication Middleware

Validates Bearer tokens (JWT or API key) and X-API-Key headers.
Supports dual authentication: JWT-based user auth AND legacy API key auth.
Bypasses auth in development mode and for public paths.
"""

from __future__ import annotations

import secrets

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

import structlog

from app.config import get_settings

log = structlog.get_logger(__name__)

# Paths that never require authentication
_PUBLIC_PATHS = frozenset({
    "/health",
    "/docs",
    "/redoc",
    "/openapi.json",
    "/favicon.ico",
})

# Prefixes that never require authentication
_PUBLIC_PREFIXES = (
    "/ws/",           # WebSocket endpoints handle auth differently
    "/v1/api/auth/",  # Auth endpoints (register, login, refresh) are public
)


class AuthMiddleware(BaseHTTPMiddleware):
    """Dual authentication middleware: JWT + API key.

    Checks for a valid credential in either:
    - ``Authorization: Bearer <jwt_or_api_key>`` header
    - ``X-API-Key: <key>`` header

    Behavior:
    - Skips auth for public paths (/health, /docs, /openapi.json)
    - Skips auth for WebSocket paths (/ws/*) and auth paths (/v1/api/auth/*)
    - In development mode (``app_env == 'development'``), all requests pass
    - In production, tries JWT verification first, falls back to API key match
    """

    async def dispatch(self, request: Request, call_next):
        settings = get_settings()
        path = request.url.path

        # Always allow public paths
        if path in _PUBLIC_PATHS:
            return await call_next(request)

        # Always allow public prefixes (WebSocket, auth)
        for prefix in _PUBLIC_PREFIXES:
            if path.startswith(prefix):
                return await call_next(request)

        # Development mode — bypass auth
        if not settings.is_production:
            return await call_next(request)

        # Extract credential
        credential = self._extract_key(request)

        if not credential:
            log.warning("auth.missing_key", path=path, method=request.method)
            return JSONResponse(
                status_code=401,
                content={
                    "detail": "Authentication required. Provide a JWT or API key via "
                              "'Authorization: Bearer <token>' or 'X-API-Key: <key>' header."
                },
            )

        # Try JWT verification first
        try:
            from app.auth.jwt_handler import verify_token
            payload = verify_token(credential, expected_type="access")
            if payload:
                # Valid JWT — attach user_id to request state
                request.state.user_id = payload.get("sub")
                request.state.auth_method = "jwt"
                return await call_next(request)
        except Exception:
            pass  # Not a JWT, try API key

        # Fall back to API key validation (constant-time comparison)
        if secrets.compare_digest(credential, settings.app_secret_key):
            request.state.auth_method = "api_key"
            return await call_next(request)

        log.warning("auth.invalid_credential", path=path, method=request.method)
        return JSONResponse(
            status_code=401,
            content={"detail": "Invalid authentication credential."},
        )

    @staticmethod
    def _extract_key(request: Request) -> str | None:
        """Extract credential from Authorization or X-API-Key header."""
        # Try Authorization: Bearer <token>
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            return auth_header[7:].strip()

        # Try X-API-Key
        api_key = request.headers.get("X-API-Key", "").strip()
        if api_key:
            return api_key

        return None

