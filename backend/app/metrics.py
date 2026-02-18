"""
Bubby Vision — Prometheus-Compatible Metrics

Lightweight metrics collection and exposition:
- http_requests_total{method, path, status} — request counter
- http_request_duration_seconds{method, path} — response time histogram
- GET /metrics — text/plain Prometheus exposition format
"""

from __future__ import annotations

import time
from collections import defaultdict
from typing import Any

from fastapi import APIRouter
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import PlainTextResponse, Response

# ────────────────────────────────────────────────
# In-Memory Metric Store
# ────────────────────────────────────────────────

_request_counts: dict[tuple[str, str, int], int] = defaultdict(int)
_request_durations: dict[tuple[str, str], list[float]] = defaultdict(list)

# Max stored durations per path to prevent memory leak
_MAX_DURATION_SAMPLES = 1000


def _bucket_path(path: str) -> str:
    """Normalize paths for metric grouping.

    Replaces variable path segments (tickers, IDs) with {param}
    to avoid cardinality explosion.
    """
    parts = path.strip("/").split("/")
    normalized = []
    for i, part in enumerate(parts):
        # Skip version and api prefix segments
        if part in ("v1", "api"):
            normalized.append(part)
            continue
        # Known variable segments: anything after /stock/, /options/, etc.
        if i > 0 and normalized and normalized[-1] in (
            "stock", "options", "sentiment", "filings", "news",
            "analyst", "insider", "darkpool", "snapshot", "wsb",
            "technical",
        ):
            normalized.append("{ticker}")
            continue
        normalized.append(part)
    return "/" + "/".join(normalized) if normalized else path


def record_request(method: str, path: str, status_code: int, duration: float) -> None:
    """Record a single request's metrics."""
    bucket = _bucket_path(path)
    _request_counts[(method, bucket, status_code)] += 1

    durations = _request_durations[(method, bucket)]
    durations.append(duration)
    # Trim to prevent unbounded growth
    if len(durations) > _MAX_DURATION_SAMPLES:
        _request_durations[(method, bucket)] = durations[-_MAX_DURATION_SAMPLES:]


# ────────────────────────────────────────────────
# Metrics Collection Middleware
# ────────────────────────────────────────────────


class MetricsMiddleware(BaseHTTPMiddleware):
    """Collects per-request metrics for Prometheus exposition."""

    async def dispatch(self, request: Request, call_next) -> Response:
        # Skip metrics endpoint itself to avoid self-referential noise
        if request.url.path == "/metrics":
            return await call_next(request)

        start = time.perf_counter()
        response = await call_next(request)
        duration = time.perf_counter() - start

        record_request(
            method=request.method,
            path=str(request.url.path),
            status_code=response.status_code,
            duration=duration,
        )

        return response


# ────────────────────────────────────────────────
# Prometheus Exposition Endpoint
# ────────────────────────────────────────────────

metrics_router = APIRouter()


def _format_prometheus() -> str:
    """Format metrics in Prometheus text exposition format."""
    lines: list[str] = []

    # ── Request Count ──
    lines.append("# HELP http_requests_total Total HTTP requests processed.")
    lines.append("# TYPE http_requests_total counter")
    for (method, path, status), count in sorted(_request_counts.items()):
        lines.append(
            f'http_requests_total{{method="{method}",path="{path}",status="{status}"}} {count}'
        )

    # ── Request Duration ──
    lines.append("")
    lines.append("# HELP http_request_duration_seconds HTTP request duration in seconds.")
    lines.append("# TYPE http_request_duration_seconds summary")
    for (method, path), durations in sorted(_request_durations.items()):
        if not durations:
            continue
        total = sum(durations)
        count = len(durations)
        sorted_d = sorted(durations)
        p50 = sorted_d[int(count * 0.5)] if count else 0
        p95 = sorted_d[int(count * 0.95)] if count else 0
        p99 = sorted_d[min(int(count * 0.99), count - 1)] if count else 0

        label = f'method="{method}",path="{path}"'
        lines.append(f'http_request_duration_seconds{{{label},quantile="0.5"}} {p50:.6f}')
        lines.append(f'http_request_duration_seconds{{{label},quantile="0.95"}} {p95:.6f}')
        lines.append(f'http_request_duration_seconds{{{label},quantile="0.99"}} {p99:.6f}')
        lines.append(f"http_request_duration_seconds_sum{{{label}}} {total:.6f}")
        lines.append(f"http_request_duration_seconds_count{{{label}}} {count}")

    lines.append("")
    return "\n".join(lines)


@metrics_router.get("/metrics", include_in_schema=False)
async def get_metrics():
    """Prometheus-compatible metrics endpoint."""
    return PlainTextResponse(
        content=_format_prometheus(),
        media_type="text/plain; version=0.0.4; charset=utf-8",
    )
