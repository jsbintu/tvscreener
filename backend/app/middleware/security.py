"""
Bubby Vision — Security Headers Middleware

Adds security headers to every HTTP response:
- X-Content-Type-Options: nosniff
- X-Frame-Options: DENY
- X-XSS-Protection: 1; mode=block
- Referrer-Policy: strict-origin-when-cross-origin
- Permissions-Policy: restrict browser features
- Strict-Transport-Security (production only)
"""

from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.config import get_settings


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Injects security headers into every response."""

    # Headers applied to ALL environments
    COMMON_HEADERS: dict[str, str] = {
        "X-Content-Type-Options": "nosniff",
        "X-Frame-Options": "DENY",
        "X-XSS-Protection": "1; mode=block",
        "Referrer-Policy": "strict-origin-when-cross-origin",
        "Permissions-Policy": (
            "camera=(), microphone=(), geolocation=(), "
            "payment=(), usb=(), magnetometer=(), gyroscope=()"
        ),
    }

    # Applied only in production
    PRODUCTION_HEADERS: dict[str, str] = {
        "Strict-Transport-Security": "max-age=31536000; includeSubDomains; preload",
    }

    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)

        # Apply common security headers
        for header, value in self.COMMON_HEADERS.items():
            response.headers[header] = value

        # HSTS only in production
        settings = get_settings()
        if settings.is_production:
            for header, value in self.PRODUCTION_HEADERS.items():
                response.headers[header] = value

        return response
