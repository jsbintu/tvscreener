"""
Bubby Vision — Rate Limiter Middleware

Token-bucket rate limiter using Redis (falls back to in-process dict
if Redis is unavailable).  Applied as Starlette middleware.
"""

from __future__ import annotations

import time
from collections import defaultdict
from typing import Optional

import structlog
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

log = structlog.get_logger(__name__)


class _InMemoryBucket:
    """Simple in-process token bucket (fallback when Redis is down)."""

    def __init__(self):
        self._buckets: dict[str, dict] = defaultdict(
            lambda: {"tokens": 0.0, "last": 0.0}
        )

    def is_allowed(self, key: str, max_tokens: int, refill_rate: float) -> bool:
        now = time.monotonic()
        bucket = self._buckets[key]

        if bucket["last"] == 0.0:
            bucket["tokens"] = float(max_tokens)
            bucket["last"] = now

        elapsed = now - bucket["last"]
        bucket["tokens"] = min(max_tokens, bucket["tokens"] + elapsed * refill_rate)
        bucket["last"] = now

        if bucket["tokens"] >= 1.0:
            bucket["tokens"] -= 1.0
            return True
        return False


class _RedisBucket:
    """Token bucket backed by Redis for multi-process deployments."""

    def __init__(self, redis_url: str):
        self._redis = None
        try:
            import redis as _redis
            self._redis = _redis.from_url(
                redis_url,
                decode_responses=True,
                socket_timeout=3,
                socket_connect_timeout=3,
            )
            self._redis.ping()
            log.info("rate_limiter.redis_connected", url=redis_url)
        except Exception as exc:
            log.warning("rate_limiter.redis_unavailable", error=str(exc))
            self._redis = None

    @property
    def available(self) -> bool:
        return self._redis is not None

    def is_allowed(self, key: str, max_tokens: int, refill_rate: float) -> bool:
        if not self._redis:
            return True  # fail-open

        pipe_key = f"ratelimit:{key}"
        try:
            now = time.time()
            pipe = self._redis.pipeline()
            pipe.hgetall(pipe_key)
            results = pipe.execute()
            data = results[0]

            tokens = float(data.get("tokens", max_tokens))
            last = float(data.get("last", now))

            elapsed = now - last
            tokens = min(max_tokens, tokens + elapsed * refill_rate)

            if tokens >= 1.0:
                tokens -= 1.0
                self._redis.hset(pipe_key, mapping={"tokens": tokens, "last": now})
                self._redis.expire(pipe_key, 120)
                return True

            self._redis.hset(pipe_key, mapping={"tokens": tokens, "last": now})
            self._redis.expire(pipe_key, 120)
            return False
        except Exception as exc:
            log.warning("rate_limiter.redis_error", error=str(exc))
            return True  # fail-open


class RateLimitMiddleware(BaseHTTPMiddleware):
    """ASGI middleware enforcing per-IP rate limits.

    Args:
        app: The Starlette/FastAPI application.
        max_requests: Maximum burst size (tokens).
        window_seconds: Refill window in seconds.
        redis_url: Optional Redis URL for distributed limiting.
    """

    def __init__(
        self,
        app,
        max_requests: int = 60,
        window_seconds: int = 60,
        redis_url: Optional[str] = None,
    ):
        super().__init__(app)
        self.max_tokens = max_requests
        self.refill_rate = max_requests / window_seconds

        self._redis_bucket: Optional[_RedisBucket] = None
        if redis_url:
            self._redis_bucket = _RedisBucket(redis_url)

        self._mem_bucket = _InMemoryBucket()

    def _get_client_ip(self, request: Request) -> str:
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            return forwarded.split(",")[0].strip()
        return request.client.host if request.client else "unknown"

    async def dispatch(self, request: Request, call_next):
        # Skip rate limiting for health checks
        if request.url.path == "/health":
            return await call_next(request)

        client_ip = self._get_client_ip(request)

        # Try Redis first, fall back to in-memory
        if self._redis_bucket and self._redis_bucket.available:
            allowed = self._redis_bucket.is_allowed(
                client_ip, self.max_tokens, self.refill_rate
            )
        else:
            allowed = self._mem_bucket.is_allowed(
                client_ip, self.max_tokens, self.refill_rate
            )

        if not allowed:
            retry_after = int(1.0 / self.refill_rate) + 1
            log.warning(
                "rate_limit.exceeded",
                client_ip=client_ip,
                path=request.url.path,
            )
            return JSONResponse(
                status_code=429,
                content={"detail": "Too many requests. Please try again later."},
                headers={"Retry-After": str(retry_after)},
            )

        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(self.max_tokens)
        return response
