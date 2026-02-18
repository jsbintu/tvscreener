"""
Bubby Vision — Redis Caching Layer

Decorator-based caching with configurable TTLs. Falls back to
pass-through when Redis is unavailable (no crashes, just cache misses).
"""

from __future__ import annotations

import functools
import hashlib
import json
import time
from typing import Any, Callable, Optional

import structlog

from app.config import get_settings

log = structlog.get_logger(__name__)


# ──────────────────────────────────────────────
# Redis Cache Client
# ──────────────────────────────────────────────


class RedisCache:
    """Thin Redis wrapper with JSON serialization and graceful degradation."""

    def __init__(self, url: Optional[str] = None):
        self._url = url or get_settings().redis_url
        self._client = None
        self._available = False
        self._connect()

    def _connect(self):
        try:
            import redis as redis_lib
            self._client = redis_lib.from_url(
                self._url,
                decode_responses=True,
                socket_timeout=2,
                socket_connect_timeout=2,
            )
            self._client.ping()
            self._available = True
            log.info("cache.connected", url=self._url)
        except Exception as exc:
            log.warning("cache.unavailable", error=str(exc))
            self._available = False

    @property
    def available(self) -> bool:
        return self._available

    def get(self, key: str) -> Optional[Any]:
        """Get a cached value. Returns None on miss or error."""
        if not self._available:
            return None
        try:
            raw = self._client.get(key)
            if raw is None:
                return None
            return json.loads(raw)
        except Exception:
            return None

    def set(self, key: str, value: Any, ttl: int = 300) -> bool:
        """Cache a value with TTL in seconds."""
        if not self._available:
            return False
        try:
            serialized = json.dumps(value, default=str)
            self._client.setex(key, ttl, serialized)
            return True
        except Exception:
            return False

    def delete(self, key: str) -> bool:
        """Delete a cached key."""
        if not self._available:
            return False
        try:
            self._client.delete(key)
            return True
        except Exception:
            return False

    def clear_prefix(self, prefix: str) -> int:
        """Delete all keys matching a prefix. Returns count deleted."""
        if not self._available:
            return 0
        try:
            keys = self._client.keys(f"{prefix}:*")
            if keys:
                return self._client.delete(*keys)
            return 0
        except Exception:
            return 0

    def stats(self) -> dict:
        """Get basic cache stats."""
        if not self._available:
            return {"available": False}
        try:
            info = self._client.info("stats")
            return {
                "available": True,
                "hits": info.get("keyspace_hits", 0),
                "misses": info.get("keyspace_misses", 0),
                "keys": self._client.dbsize(),
            }
        except Exception:
            return {"available": False}


# ──────────────────────────────────────────────
# Default TTLs (seconds)
# ──────────────────────────────────────────────


TTL_STOCK = 15          # 15 seconds — price data (near-real-time)
TTL_OPTIONS = 30        # 30 seconds — options chains
TTL_FEAR_GREED = 300    # 5 minutes — sentiment
TTL_NEWS = 120          # 2 minutes — news articles
TTL_TRENDING = 180      # 3 minutes — trending tickers
TTL_SCREENER = 60       # 1 minute — screener results
TTL_FINANCIALS = 3600   # 1 hour — SEC financials
TTL_INSIDER = 600       # 10 minutes — insider trades
TTL_MOVERS = 60         # 1 minute — top movers


# ──────────────────────────────────────────────
# @cached Decorator
# ──────────────────────────────────────────────


def _make_cache_key(prefix: str, args: tuple, kwargs: dict) -> str:
    """Build a deterministic cache key from function arguments."""
    parts = [prefix]
    for a in args:
        parts.append(str(a))
    for k, v in sorted(kwargs.items()):
        parts.append(f"{k}={v}")
    raw = ":".join(parts)
    # Hash long keys to keep Redis key length reasonable
    if len(raw) > 128:
        raw = prefix + ":" + hashlib.md5(raw.encode()).hexdigest()
    return f"mp:{raw}"


def cached(ttl: int = 300, prefix: str = "data"):
    """Decorator that caches function return values in Redis.

    Usage::

        @cached(ttl=60, prefix="stock")
        def get_stock(self, ticker, period="1mo"):
            ...

    - Skips `self` when building cache keys.
    - Falls through on Redis errors (function always executes).
    - Works with both sync and async functions.
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            cache = get_cache()

            # Skip `self` for methods
            cache_args = args[1:] if args and hasattr(args[0], '__class__') else args
            key = _make_cache_key(f"{prefix}:{func.__name__}", cache_args, kwargs)

            # Try cache first
            hit = cache.get(key)
            if hit is not None:
                log.debug("cache.hit", key=key)
                return hit

            # Execute function
            result = func(*args, **kwargs)

            # Cache the result (best-effort)
            if result is not None:
                # Convert Pydantic models to dicts for JSON serialization
                serializable = result
                if hasattr(result, "model_dump"):
                    serializable = result.model_dump()
                elif hasattr(result, "__dict__") and not isinstance(result, (dict, list, str, int, float)):
                    serializable = result.__dict__

                cache.set(key, serializable, ttl=ttl)
                log.debug("cache.set", key=key, ttl=ttl)

            return result

        return wrapper
    return decorator


# ──────────────────────────────────────────────
# Singleton
# ──────────────────────────────────────────────

_cache: Optional[RedisCache] = None


def get_cache() -> RedisCache:
    """Get or create the Redis cache singleton."""
    global _cache
    if _cache is None:
        _cache = RedisCache()
    return _cache
