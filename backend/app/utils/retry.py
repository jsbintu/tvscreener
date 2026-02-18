"""
Bubby Vision — Retry Decorator

Exponential backoff with jitter for external API calls.
Retries only on transient errors (timeouts, connection errors,
HTTP 429/5xx). Works with both sync and async functions.
"""

from __future__ import annotations

import asyncio
import functools
import inspect
import random
import time
from typing import Any, Callable, Sequence, Type

import structlog

log = structlog.get_logger(__name__)

# Default exception types that warrant a retry
DEFAULT_RETRYABLE: tuple[Type[Exception], ...] = (
    ConnectionError,
    TimeoutError,
    OSError,
)

try:
    import httpx
    DEFAULT_RETRYABLE = DEFAULT_RETRYABLE + (httpx.TransportError,)
except ImportError:
    pass

try:
    import requests
    DEFAULT_RETRYABLE = DEFAULT_RETRYABLE + (
        requests.ConnectionError,
        requests.Timeout,
    )
except ImportError:
    pass


def with_retry(
    max_attempts: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 30.0,
    backoff_factor: float = 2.0,
    jitter: bool = True,
    retryable_exceptions: tuple[Type[Exception], ...] | None = None,
    on_retry: Callable[..., Any] | None = None,
) -> Callable:
    """Decorator that retries a function on transient failures.

    Args:
        max_attempts: Maximum number of attempts (including the first).
        base_delay: Initial delay between retries in seconds.
        max_delay: Maximum delay cap in seconds.
        backoff_factor: Multiplier for delay after each retry.
        jitter: Add randomized jitter to prevent thundering herd.
        retryable_exceptions: Exception types to retry on.
            Defaults to ConnectionError, TimeoutError, OSError + httpx/requests.
        on_retry: Optional callback(attempt, exception, delay) called before sleeping.

    Returns:
        Decorated function with retry behavior.

    Usage::

        @with_retry(max_attempts=3, base_delay=1.0)
        async def fetch_stock_data(ticker: str):
            ...

        @with_retry(max_attempts=5, retryable_exceptions=(TimeoutError,))
        def get_financials(ticker: str):
            ...
    """
    retry_on = retryable_exceptions or DEFAULT_RETRYABLE

    def decorator(func: Callable) -> Callable:
        is_async = inspect.iscoroutinefunction(func)

        @functools.wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            last_exception: Exception | None = None
            for attempt in range(1, max_attempts + 1):
                try:
                    return await func(*args, **kwargs)
                except retry_on as exc:
                    last_exception = exc
                    if attempt == max_attempts:
                        log.error(
                            "retry.exhausted",
                            func=func.__qualname__,
                            attempts=max_attempts,
                            error=str(exc),
                        )
                        raise
                    delay = _compute_delay(attempt, base_delay, max_delay, backoff_factor, jitter)
                    log.warning(
                        "retry.attempt",
                        func=func.__qualname__,
                        attempt=attempt,
                        max_attempts=max_attempts,
                        delay=round(delay, 2),
                        error=str(exc),
                    )
                    if on_retry:
                        on_retry(attempt, exc, delay)
                    await asyncio.sleep(delay)
            raise last_exception  # type: ignore[misc]

        @functools.wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            last_exception: Exception | None = None
            for attempt in range(1, max_attempts + 1):
                try:
                    return func(*args, **kwargs)
                except retry_on as exc:
                    last_exception = exc
                    if attempt == max_attempts:
                        log.error(
                            "retry.exhausted",
                            func=func.__qualname__,
                            attempts=max_attempts,
                            error=str(exc),
                        )
                        raise
                    delay = _compute_delay(attempt, base_delay, max_delay, backoff_factor, jitter)
                    log.warning(
                        "retry.attempt",
                        func=func.__qualname__,
                        attempt=attempt,
                        max_attempts=max_attempts,
                        delay=round(delay, 2),
                        error=str(exc),
                    )
                    if on_retry:
                        on_retry(attempt, exc, delay)
                    time.sleep(delay)
            raise last_exception  # type: ignore[misc]

        return async_wrapper if is_async else sync_wrapper

    return decorator


def _compute_delay(
    attempt: int,
    base_delay: float,
    max_delay: float,
    backoff_factor: float,
    jitter: bool,
) -> float:
    """Calculate delay for a given attempt with exponential backoff + jitter."""
    delay = base_delay * (backoff_factor ** (attempt - 1))
    if jitter:
        delay *= random.uniform(0.5, 1.5)
    return min(delay, max_delay)
