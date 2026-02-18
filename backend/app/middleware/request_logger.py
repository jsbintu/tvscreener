"""
Bubby Vision — Request Logger Middleware

Structured request/response logging via structlog.  Attaches a unique
request ID header for end-to-end tracing.
"""

from __future__ import annotations

import time
import uuid

import structlog
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

log = structlog.get_logger(__name__)

# Paths to skip logging (high-frequency, low-signal)
_SKIP_PATHS = frozenset({"/health", "/favicon.ico"})


class RequestLoggerMiddleware(BaseHTTPMiddleware):
    """Log every request with method, path, status, and latency."""

    async def dispatch(self, request: Request, call_next):
        if request.url.path in _SKIP_PATHS:
            return await call_next(request)

        request_id = str(uuid.uuid4())
        start = time.perf_counter()

        # Bind request context for structured logs
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(request_id=request_id)

        log.info(
            "request.start",
            method=request.method,
            path=request.url.path,
            client=request.client.host if request.client else "unknown",
        )

        try:
            response = await call_next(request)
        except Exception:
            elapsed_ms = (time.perf_counter() - start) * 1000
            log.error(
                "request.error",
                method=request.method,
                path=request.url.path,
                latency_ms=round(elapsed_ms, 1),
            )
            raise

        elapsed_ms = (time.perf_counter() - start) * 1000

        log.info(
            "request.complete",
            method=request.method,
            path=request.url.path,
            status=response.status_code,
            latency_ms=round(elapsed_ms, 1),
        )

        response.headers["X-Request-ID"] = request_id
        return response
