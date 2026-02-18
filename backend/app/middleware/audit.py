"""
Bubby Vision — Request Audit Logging

Lightweight audit trail for API requests:
- Records method, path, status, duration, timestamp
- In-memory ring buffer (last N entries) for dev
- Exposed via GET /v1/api/audit-log
"""

from __future__ import annotations

import time
from collections import deque
from datetime import datetime, timezone
from typing import Any

import structlog
from fastapi import APIRouter, Query
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

log = structlog.get_logger(__name__)


# ────────────────────────────────────────────────
# Audit Store (in-memory ring buffer)
# ────────────────────────────────────────────────

MAX_AUDIT_ENTRIES = 500

_audit_log: deque[dict[str, Any]] = deque(maxlen=MAX_AUDIT_ENTRIES)


def get_audit_entries(
    limit: int = 50,
    path_filter: str | None = None,
    method_filter: str | None = None,
) -> list[dict]:
    """Return recent audit entries, optionally filtered."""
    entries = list(_audit_log)
    if path_filter:
        entries = [e for e in entries if path_filter in e.get("path", "")]
    if method_filter:
        entries = [e for e in entries if e.get("method") == method_filter.upper()]
    return entries[-limit:]


def clear_audit_log() -> None:
    """Clear all audit entries (for testing)."""
    _audit_log.clear()


# ────────────────────────────────────────────────
# Audit Middleware
# ────────────────────────────────────────────────


_SKIP_PATHS = {"/health", "/metrics", "/openapi.json", "/docs", "/redoc"}


class AuditMiddleware(BaseHTTPMiddleware):
    """Records every API request for audit trail."""

    async def dispatch(self, request: Request, call_next) -> Response:
        path = request.url.path

        # Skip internal/infra endpoints
        if path in _SKIP_PATHS:
            return await call_next(request)

        start = time.perf_counter()
        response = await call_next(request)
        duration_ms = round((time.perf_counter() - start) * 1000, 2)

        # Extract request ID if set by upstream middleware
        request_id = response.headers.get("X-Request-ID", "")

        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "method": request.method,
            "path": path,
            "query": str(request.url.query) if request.url.query else "",
            "status": response.status_code,
            "duration_ms": duration_ms,
            "request_id": request_id,
            "client": request.client.host if request.client else "",
        }

        _audit_log.append(entry)

        return response


# ────────────────────────────────────────────────
# Audit Log Endpoint
# ────────────────────────────────────────────────

audit_router = APIRouter()


@audit_router.get("/audit-log")
async def get_audit_log(
    limit: int = Query(50, ge=1, le=500, description="Max entries to return"),
    path: str | None = Query(None, description="Filter by path substring"),
    method: str | None = Query(None, description="Filter by HTTP method"),
):
    """View recent API request audit trail."""
    entries = get_audit_entries(limit=limit, path_filter=path, method_filter=method)
    return {
        "entries": entries,
        "count": len(entries),
        "max_capacity": MAX_AUDIT_ENTRIES,
    }
