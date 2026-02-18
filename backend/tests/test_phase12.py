"""
Bubby Vision — Phase 12 Tests

Tests for:
- Circuit breaker state machine (CLOSED/OPEN/HALF_OPEN)
- Circuit breaker registry (get_breaker, get_all_breaker_states)
- DataEngine _safe_call with circuit breaker
- GZip compression middleware
"""

import time
import pytest


# ════════════════════════════════════════════════
#  CIRCUIT BREAKER — STATE MACHINE
# ════════════════════════════════════════════════


class TestCircuitBreakerStates:

    def test_import(self):
        from app.utils.circuit_breaker import CircuitBreaker, CircuitState
        assert CircuitState.CLOSED is not None

    def test_starts_closed(self):
        from app.utils.circuit_breaker import CircuitBreaker, CircuitState
        cb = CircuitBreaker("test_svc_1", failure_threshold=3, recovery_timeout=1)
        assert cb.state == CircuitState.CLOSED

    def test_stays_closed_on_success(self):
        from app.utils.circuit_breaker import CircuitBreaker, CircuitState
        cb = CircuitBreaker("test_svc_2", failure_threshold=3)
        result = cb.call(lambda: "ok")
        assert result == "ok"
        assert cb.state == CircuitState.CLOSED

    def test_opens_after_threshold_failures(self):
        from app.utils.circuit_breaker import CircuitBreaker, CircuitState
        cb = CircuitBreaker("test_svc_3", failure_threshold=3, recovery_timeout=60)
        for _ in range(3):
            try:
                cb.call(lambda: (_ for _ in ()).throw(ConnectionError("fail")))
            except ConnectionError:
                pass
        assert cb.state == CircuitState.OPEN

    def test_open_circuit_raises_circuit_open_error(self):
        from app.utils.circuit_breaker import CircuitBreaker, CircuitOpenError
        cb = CircuitBreaker("test_svc_4", failure_threshold=1, recovery_timeout=60)
        try:
            cb.call(lambda: (_ for _ in ()).throw(ConnectionError("fail")))
        except ConnectionError:
            pass
        with pytest.raises(CircuitOpenError):
            cb.call(lambda: "should not run")

    def test_half_open_after_recovery_timeout(self):
        from app.utils.circuit_breaker import CircuitBreaker, CircuitState
        cb = CircuitBreaker("test_svc_5", failure_threshold=1, recovery_timeout=0.1)
        try:
            cb.call(lambda: (_ for _ in ()).throw(ConnectionError("fail")))
        except ConnectionError:
            pass
        assert cb.state == CircuitState.OPEN
        time.sleep(0.15)
        assert cb.state == CircuitState.HALF_OPEN

    def test_half_open_success_closes(self):
        from app.utils.circuit_breaker import CircuitBreaker, CircuitState
        cb = CircuitBreaker("test_svc_6", failure_threshold=1, recovery_timeout=0.1)
        try:
            cb.call(lambda: (_ for _ in ()).throw(ConnectionError("fail")))
        except ConnectionError:
            pass
        time.sleep(0.15)
        result = cb.call(lambda: "recovered")
        assert result == "recovered"
        assert cb.state == CircuitState.CLOSED

    def test_half_open_failure_reopens(self):
        from app.utils.circuit_breaker import CircuitBreaker, CircuitState
        cb = CircuitBreaker("test_svc_7", failure_threshold=1, recovery_timeout=0.1)
        try:
            cb.call(lambda: (_ for _ in ()).throw(ConnectionError("fail")))
        except ConnectionError:
            pass
        time.sleep(0.15)
        try:
            cb.call(lambda: (_ for _ in ()).throw(ConnectionError("still fail")))
        except ConnectionError:
            pass
        assert cb.state == CircuitState.OPEN

    def test_reset(self):
        from app.utils.circuit_breaker import CircuitBreaker, CircuitState
        cb = CircuitBreaker("test_svc_8", failure_threshold=1, recovery_timeout=60)
        try:
            cb.call(lambda: (_ for _ in ()).throw(ConnectionError("fail")))
        except ConnectionError:
            pass
        assert cb.state == CircuitState.OPEN
        cb.reset()
        assert cb.state == CircuitState.CLOSED

    def test_success_resets_failure_count(self):
        from app.utils.circuit_breaker import CircuitBreaker, CircuitState
        cb = CircuitBreaker("test_svc_9", failure_threshold=3)
        # 2 failures (below threshold)
        for _ in range(2):
            try:
                cb.call(lambda: (_ for _ in ()).throw(ConnectionError("fail")))
            except ConnectionError:
                pass
        # 1 success resets
        cb.call(lambda: "ok")
        assert cb._failure_count == 0
        assert cb.state == CircuitState.CLOSED


# ════════════════════════════════════════════════
#  CIRCUIT BREAKER — REGISTRY
# ════════════════════════════════════════════════


class TestCircuitBreakerRegistry:

    def test_get_breaker_returns_same_instance(self):
        from app.utils.circuit_breaker import get_breaker
        b1 = get_breaker("registry_test_1")
        b2 = get_breaker("registry_test_1")
        assert b1 is b2

    def test_get_breaker_different_services(self):
        from app.utils.circuit_breaker import get_breaker
        b1 = get_breaker("registry_test_2")
        b2 = get_breaker("registry_test_3")
        assert b1 is not b2

    def test_get_all_breaker_states(self):
        from app.utils.circuit_breaker import get_breaker, get_all_breaker_states
        get_breaker("registry_test_4")
        states = get_all_breaker_states()
        assert "registry_test_4" in states
        assert states["registry_test_4"] == "CLOSED"


# ════════════════════════════════════════════════
#  DATA ENGINE — SAFE CALL
# ════════════════════════════════════════════════


class TestDataEngineSafeCall:

    def test_safe_call_exists(self):
        from app.engines.data_engine import DataEngine
        engine = DataEngine()
        assert hasattr(engine, "_safe_call")

    def test_safe_call_passes_through(self):
        from app.engines.data_engine import DataEngine
        engine = DataEngine()
        result = engine._safe_call("yfinance", lambda: "data")
        assert result == "data"

    def test_safe_call_returns_fallback_on_open_circuit(self):
        from app.engines.data_engine import DataEngine
        engine = DataEngine()
        breaker = engine._breakers["yfinance"]
        # Force circuit open
        breaker._failure_count = breaker.failure_threshold
        breaker._state = __import__("app.utils.circuit_breaker", fromlist=["CircuitState"]).CircuitState.OPEN
        breaker._last_failure_time = __import__("time").monotonic()

        result = engine._safe_call("yfinance", lambda: "should not run", fallback={"cached": True})
        assert result == {"cached": True}
        # Cleanup
        breaker.reset()

    def test_breakers_initialized(self):
        from app.engines.data_engine import DataEngine
        engine = DataEngine()
        assert "yfinance" in engine._breakers
        assert "finnhub" in engine._breakers
        assert "alpaca" in engine._breakers
        assert "edgar" in engine._breakers
        assert "tradingview" in engine._breakers


# ════════════════════════════════════════════════
#  GZIP COMPRESSION
# ════════════════════════════════════════════════


class TestGZipCompression:

    def _get_client(self):
        from fastapi.testclient import TestClient
        from app.main import create_app
        return TestClient(create_app())

    def test_gzip_middleware_registered(self):
        """App should have GZipMiddleware in its middleware stack."""
        from app.main import create_app
        app = create_app()
        middleware_cls_names = [m.cls.__name__ for m in app.user_middleware]
        assert "GZipMiddleware" in middleware_cls_names

    def test_health_response_is_valid_json_with_gzip(self):
        """Health response should still be valid JSON even when compressed."""
        client = self._get_client()
        resp = client.get("/health", headers={"Accept-Encoding": "gzip"})
        assert resp.status_code == 200
        # TestClient transparently decompresses, so json() should work
        data = resp.json()
        assert "status" in data

    def test_accepts_gzip_encoding(self):
        """Client that accepts gzip should get a valid response."""
        client = self._get_client()
        resp = client.get("/health", headers={"Accept-Encoding": "gzip"})
        assert resp.status_code == 200
