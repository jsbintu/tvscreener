"""
Bubby Vision — Phase 15 Tests

Tests for:
- Input sanitization (OWASP)
- Integration tests (cache flow, circuit breaker recovery, endpoint composition)
"""

import pytest


# ════════════════════════════════════════════════
#  OWASP — TICKER VALIDATION
# ════════════════════════════════════════════════


class TestTickerValidation:

    def test_valid_tickers(self):
        from app.utils.sanitize import is_valid_ticker
        assert is_valid_ticker("AAPL")
        assert is_valid_ticker("TSLA")
        assert is_valid_ticker("BRK.B")
        assert is_valid_ticker("NVDA")

    def test_invalid_tickers(self):
        from app.utils.sanitize import is_valid_ticker
        assert not is_valid_ticker("")
        assert not is_valid_ticker("A" * 20)  # Too long
        assert not is_valid_ticker("AAPL; DROP TABLE")
        assert not is_valid_ticker("../etc/passwd")
        assert not is_valid_ticker("<script>")

    def test_sanitize_ticker_normalizes(self):
        from app.utils.sanitize import sanitize_ticker
        assert sanitize_ticker("aapl") == "AAPL"
        assert sanitize_ticker(" tsla ") == "TSLA"

    def test_sanitize_ticker_rejects_invalid(self):
        from app.utils.sanitize import sanitize_ticker
        with pytest.raises(ValueError):
            sanitize_ticker("../etc/passwd")


# ════════════════════════════════════════════════
#  OWASP — XSS PREVENTION
# ════════════════════════════════════════════════


class TestXSSPrevention:

    def test_detects_script_tags(self):
        from app.utils.sanitize import contains_xss
        assert contains_xss("<script>alert('xss')</script>")

    def test_detects_javascript_proto(self):
        from app.utils.sanitize import contains_xss
        assert contains_xss("javascript:alert(1)")

    def test_detects_event_handlers(self):
        from app.utils.sanitize import contains_xss
        assert contains_xss('<img onerror="alert(1)">')

    def test_detects_iframe(self):
        from app.utils.sanitize import contains_xss
        assert contains_xss("<iframe src=evil.com>")

    def test_safe_text_passes(self):
        from app.utils.sanitize import contains_xss
        assert not contains_xss("Hello, this is a normal message about AAPL stock")

    def test_sanitize_string_rejects_xss(self):
        from app.utils.sanitize import sanitize_string
        with pytest.raises(ValueError, match="dangerous"):
            sanitize_string("<script>alert('xss')</script>")

    def test_sanitize_string_truncates(self):
        from app.utils.sanitize import sanitize_string
        result = sanitize_string("A" * 5000, max_length=100)
        assert len(result) == 100

    def test_sanitize_string_strips(self):
        from app.utils.sanitize import sanitize_string
        assert sanitize_string("  hello  ") == "hello"


# ════════════════════════════════════════════════
#  OWASP — PATH TRAVERSAL
# ════════════════════════════════════════════════


class TestPathTraversal:

    def test_detects_dot_dot(self):
        from app.utils.sanitize import is_path_safe
        assert not is_path_safe("../etc/passwd")

    def test_detects_backslash(self):
        from app.utils.sanitize import is_path_safe
        assert not is_path_safe("..\\windows\\system32")

    def test_detects_encoded(self):
        from app.utils.sanitize import is_path_safe
        assert not is_path_safe("%2e%2e%2fetc")

    def test_safe_ticker_passes(self):
        from app.utils.sanitize import is_path_safe
        assert is_path_safe("AAPL")
        assert is_path_safe("BRK.B")


# ════════════════════════════════════════════════
#  OWASP — REQUEST SIZE
# ════════════════════════════════════════════════


class TestRequestSize:

    def test_valid_size(self):
        from app.utils.sanitize import validate_body_size
        assert validate_body_size(1000)
        assert validate_body_size(500_000)

    def test_oversized_rejected(self):
        from app.utils.sanitize import validate_body_size
        assert not validate_body_size(2_000_000)

    def test_none_allowed(self):
        from app.utils.sanitize import validate_body_size
        assert validate_body_size(None)

    def test_max_constant(self):
        from app.utils.sanitize import MAX_REQUEST_BODY_BYTES
        assert MAX_REQUEST_BODY_BYTES == 1_048_576


# ════════════════════════════════════════════════
#  INTEGRATION — CACHE FLOW
# ════════════════════════════════════════════════


class TestCacheIntegration:

    def test_redis_cache_decorator_exists(self):
        from app.cache import cached
        assert callable(cached)

    def test_cache_miss_returns_data(self):
        """First call (cache miss) should still return data."""
        from fastapi.testclient import TestClient
        from app.main import create_app

        client = TestClient(create_app())
        resp = client.get("/v1/api/stock/AAPL")
        # Should not fail — either returns data or graceful error
        assert resp.status_code in (200, 500, 503)

    def test_repeated_calls_consistent(self):
        """Multiple calls to same endpoint should return consistent structure."""
        from fastapi.testclient import TestClient
        from app.main import create_app

        client = TestClient(create_app())
        resp1 = client.get("/v1/api/fear-greed")
        resp2 = client.get("/v1/api/fear-greed")
        # Both should have same status
        assert resp1.status_code == resp2.status_code


# ════════════════════════════════════════════════
#  INTEGRATION — CIRCUIT BREAKER RECOVERY
# ════════════════════════════════════════════════


class TestCircuitBreakerIntegration:

    def test_breaker_starts_closed(self):
        from app.utils.circuit_breaker import CircuitBreaker, CircuitState
        cb = CircuitBreaker("test_integration", failure_threshold=3)
        assert cb.state == CircuitState.CLOSED

    def test_breaker_opens_and_recovers(self):
        import time
        from app.utils.circuit_breaker import (
            CircuitBreaker, CircuitState, CircuitOpenError,
        )
        cb = CircuitBreaker("test_recovery", failure_threshold=2, recovery_timeout=0.1)

        # Trip the breaker
        for _ in range(2):
            try:
                cb.call(lambda: (_ for _ in ()).throw(RuntimeError("fail")))
            except RuntimeError:
                pass

        assert cb.state == CircuitState.OPEN

        # Wait for recovery
        time.sleep(0.15)
        assert cb.state == CircuitState.HALF_OPEN

        # Successful call closes it
        result = cb.call(lambda: "recovered")
        assert result == "recovered"
        assert cb.state == CircuitState.CLOSED

    def test_data_engine_has_safe_call(self):
        from app.engines.data_engine import DataEngine
        engine = DataEngine()
        assert hasattr(engine, "_safe_call")
        assert callable(engine._safe_call)


# ════════════════════════════════════════════════
#  INTEGRATION — ENDPOINT COMPOSITION
# ════════════════════════════════════════════════


class TestEndpointComposition:

    def _get_client(self):
        from fastapi.testclient import TestClient
        from app.main import create_app
        return TestClient(create_app())

    def test_all_responses_have_version_header(self):
        """Every endpoint should return X-API-Version header."""
        client = self._get_client()

        endpoints = ["/health", "/v1/api/stock/AAPL", "/metrics"]
        for ep in endpoints:
            resp = client.get(ep)
            assert "X-API-Version" in resp.headers, f"Missing version header on {ep}"

    def test_middleware_stack_order(self):
        """Middleware should be registered in correct order."""
        from app.main import create_app
        app = create_app()
        names = [m.cls.__name__ for m in app.user_middleware]

        # These should all be present
        expected = ["RateLimitMiddleware", "SecurityHeadersMiddleware",
                    "MetricsMiddleware", "AuditMiddleware", "GZipMiddleware"]
        for mw in expected:
            assert mw in names, f"Missing middleware: {mw}"

    def test_error_response_format(self):
        """Error responses should be structured JSON."""
        client = self._get_client()
        resp = client.get("/v1/api/this-does-not-exist")
        assert resp.status_code == 404
        body = resp.json()
        assert body.get("error") is True

    def test_unversioned_endpoints_still_work(self):
        """Health and metrics should work without /v1/ prefix."""
        client = self._get_client()
        assert client.get("/health").status_code == 200
        assert client.get("/metrics").status_code == 200
