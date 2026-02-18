"""
Bubby Vision — Circuit Breaker

Prevents cascading failures when external services are down.

State machine:
    CLOSED  → requests pass normally; failures are counted
    OPEN    → requests immediately fail; after cooldown, transition to HALF_OPEN
    HALF_OPEN → one probe request allowed; success → CLOSED, failure → OPEN

Usage::

    breaker = CircuitBreaker("alpaca", failure_threshold=5, recovery_timeout=30)

    try:
        result = breaker.call(lambda: alpaca_client.get_snapshot("AAPL"))
    except CircuitOpenError:
        # Service is unavailable, use fallback
        result = cached_data or {}
"""

from __future__ import annotations

import time
import threading
from enum import Enum, auto
from typing import Any, Callable, TypeVar

import structlog

log = structlog.get_logger(__name__)

T = TypeVar("T")


class CircuitState(Enum):
    CLOSED = auto()
    OPEN = auto()
    HALF_OPEN = auto()


class CircuitOpenError(Exception):
    """Raised when the circuit is open and the request is rejected."""

    def __init__(self, service: str, retry_after: float):
        self.service = service
        self.retry_after = retry_after
        super().__init__(
            f"Circuit breaker OPEN for '{service}' — retry after {retry_after:.0f}s"
        )


class CircuitBreaker:
    """Per-service circuit breaker with thread-safe state management."""

    def __init__(
        self,
        service_name: str,
        failure_threshold: int = 5,
        recovery_timeout: float = 30.0,
    ):
        """
        Args:
            service_name: Identifier for the external service.
            failure_threshold: Consecutive failures before opening circuit.
            recovery_timeout: Seconds to wait before allowing a probe request.
        """
        self.service_name = service_name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout

        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._last_failure_time: float = 0.0
        self._lock = threading.Lock()

    @property
    def state(self) -> CircuitState:
        with self._lock:
            if self._state == CircuitState.OPEN:
                elapsed = time.monotonic() - self._last_failure_time
                if elapsed >= self.recovery_timeout:
                    self._state = CircuitState.HALF_OPEN
                    log.info(
                        "circuit_breaker.half_open",
                        service=self.service_name,
                        elapsed=round(elapsed, 1),
                    )
            return self._state

    def call(self, func: Callable[[], T]) -> T:
        """Execute a function through the circuit breaker.

        Args:
            func: Zero-argument callable to execute.

        Returns:
            The result of func().

        Raises:
            CircuitOpenError: If the circuit is open.
        """
        current_state = self.state

        if current_state == CircuitState.OPEN:
            retry_after = self.recovery_timeout - (
                time.monotonic() - self._last_failure_time
            )
            raise CircuitOpenError(self.service_name, max(0, retry_after))

        try:
            result = func()
            self._on_success()
            return result
        except Exception as exc:
            self._on_failure(exc)
            raise

    def _on_success(self) -> None:
        with self._lock:
            if self._state == CircuitState.HALF_OPEN:
                log.info(
                    "circuit_breaker.closed",
                    service=self.service_name,
                    detail="probe succeeded, circuit recovered",
                )
            self._state = CircuitState.CLOSED
            self._failure_count = 0

    def _on_failure(self, exc: Exception) -> None:
        with self._lock:
            self._failure_count += 1
            self._last_failure_time = time.monotonic()

            if self._state == CircuitState.HALF_OPEN:
                self._state = CircuitState.OPEN
                log.warning(
                    "circuit_breaker.reopened",
                    service=self.service_name,
                    error=str(exc),
                )
            elif self._failure_count >= self.failure_threshold:
                self._state = CircuitState.OPEN
                log.warning(
                    "circuit_breaker.opened",
                    service=self.service_name,
                    failures=self._failure_count,
                    threshold=self.failure_threshold,
                    error=str(exc),
                )

    def reset(self) -> None:
        """Manually reset the circuit to CLOSED."""
        with self._lock:
            self._state = CircuitState.CLOSED
            self._failure_count = 0
            self._last_failure_time = 0.0
            log.info("circuit_breaker.reset", service=self.service_name)


# ────────────────────────────────────────────────
# Global Circuit Breaker Registry
# ────────────────────────────────────────────────

_breakers: dict[str, CircuitBreaker] = {}
_registry_lock = threading.Lock()


def get_breaker(
    service_name: str,
    failure_threshold: int = 5,
    recovery_timeout: float = 30.0,
) -> CircuitBreaker:
    """Get or create a circuit breaker for a service.

    Thread-safe singleton per service name.
    """
    with _registry_lock:
        if service_name not in _breakers:
            _breakers[service_name] = CircuitBreaker(
                service_name, failure_threshold, recovery_timeout
            )
        return _breakers[service_name]


def get_all_breaker_states() -> dict[str, str]:
    """Return current state of all registered circuit breakers."""
    with _registry_lock:
        return {name: cb.state.name for name, cb in _breakers.items()}
