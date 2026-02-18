"""
Bubby Vision — Phase 10 Tests

Tests for:
- Retry decorator (sync + async, backoff, exhaustion)
- Security headers middleware
- Configurable CORS origins
- OpenAPI metadata enhancements
"""

import asyncio
import pytest
from unittest.mock import patch


# ════════════════════════════════════════════════
#  RETRY DECORATOR
# ════════════════════════════════════════════════


class TestRetryDecorator:

    def test_import(self):
        from app.utils.retry import with_retry
        assert callable(with_retry)

    def test_no_retry_on_success(self):
        """Function succeeds on first call — no retries."""
        from app.utils.retry import with_retry
        call_count = 0

        @with_retry(max_attempts=3, base_delay=0.01)
        def succeed():
            nonlocal call_count
            call_count += 1
            return "ok"

        result = succeed()
        assert result == "ok"
        assert call_count == 1

    def test_retry_on_connection_error(self):
        """Retries on ConnectionError, then succeeds."""
        from app.utils.retry import with_retry
        call_count = 0

        @with_retry(max_attempts=3, base_delay=0.01)
        def flaky():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ConnectionError("connection refused")
            return "recovered"

        result = flaky()
        assert result == "recovered"
        assert call_count == 3

    def test_retry_exhaustion_raises(self):
        """After max_attempts, the original exception is raised."""
        from app.utils.retry import with_retry

        @with_retry(max_attempts=2, base_delay=0.01)
        def always_fail():
            raise TimeoutError("timed out")

        with pytest.raises(TimeoutError, match="timed out"):
            always_fail()

    def test_no_retry_on_non_retryable_error(self):
        """ValueError is not retryable — should raise immediately."""
        from app.utils.retry import with_retry
        call_count = 0

        @with_retry(max_attempts=3, base_delay=0.01)
        def bad_input():
            nonlocal call_count
            call_count += 1
            raise ValueError("bad value")

        with pytest.raises(ValueError):
            bad_input()
        assert call_count == 1  # No retries

    def test_async_retry(self):
        """Async function retries work correctly."""
        from app.utils.retry import with_retry
        call_count = 0

        @with_retry(max_attempts=3, base_delay=0.01)
        async def async_flaky():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise ConnectionError("refused")
            return "async_ok"

        result = asyncio.run(async_flaky())
        assert result == "async_ok"
        assert call_count == 2

    def test_custom_retryable_exceptions(self):
        """Custom exception types can be specified."""
        from app.utils.retry import with_retry
        call_count = 0

        @with_retry(max_attempts=3, base_delay=0.01, retryable_exceptions=(ValueError,))
        def custom_retry():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise ValueError("custom")
            return "done"

        result = custom_retry()
        assert result == "done"
        assert call_count == 2

    def test_on_retry_callback(self):
        """on_retry callback is called before each retry sleep."""
        from app.utils.retry import with_retry
        retry_log = []

        def log_retry(attempt, exc, delay):
            retry_log.append((attempt, str(exc)))

        @with_retry(max_attempts=3, base_delay=0.01, on_retry=log_retry)
        def flaky():
            if len(retry_log) < 2:
                raise ConnectionError("fail")
            return "ok"

        result = flaky()
        assert result == "ok"
        assert len(retry_log) == 2

    def test_backoff_delay_computation(self):
        """Delay should increase exponentially."""
        from app.utils.retry import _compute_delay
        d1 = _compute_delay(1, base_delay=1.0, max_delay=30.0, backoff_factor=2.0, jitter=False)
        d2 = _compute_delay(2, base_delay=1.0, max_delay=30.0, backoff_factor=2.0, jitter=False)
        d3 = _compute_delay(3, base_delay=1.0, max_delay=30.0, backoff_factor=2.0, jitter=False)
        assert d1 == 1.0
        assert d2 == 2.0
        assert d3 == 4.0

    def test_max_delay_cap(self):
        """Delay should never exceed max_delay."""
        from app.utils.retry import _compute_delay
        d = _compute_delay(10, base_delay=1.0, max_delay=5.0, backoff_factor=2.0, jitter=False)
        assert d == 5.0


# ════════════════════════════════════════════════
#  SECURITY HEADERS
# ════════════════════════════════════════════════


class TestSecurityHeaders:

    def _get_client(self):
        from fastapi.testclient import TestClient
        from app.main import create_app
        return TestClient(create_app())

    def test_x_content_type_options(self):
        resp = self._get_client().get("/health")
        assert resp.headers.get("X-Content-Type-Options") == "nosniff"

    def test_x_frame_options(self):
        resp = self._get_client().get("/health")
        assert resp.headers.get("X-Frame-Options") == "DENY"

    def test_x_xss_protection(self):
        resp = self._get_client().get("/health")
        assert resp.headers.get("X-XSS-Protection") == "1; mode=block"

    def test_referrer_policy(self):
        resp = self._get_client().get("/health")
        assert resp.headers.get("Referrer-Policy") == "strict-origin-when-cross-origin"

    def test_permissions_policy(self):
        resp = self._get_client().get("/health")
        pp = resp.headers.get("Permissions-Policy", "")
        assert "camera=()" in pp
        assert "microphone=()" in pp

    def test_no_hsts_in_dev(self):
        """HSTS should NOT be set in development mode."""
        resp = self._get_client().get("/health")
        assert "Strict-Transport-Security" not in resp.headers


# ════════════════════════════════════════════════
#  CONFIGURABLE CORS
# ════════════════════════════════════════════════


class TestConfigurableCORS:

    def test_cors_origin_list_default(self):
        from app.config import Settings
        s = Settings()
        origins = s.cors_origin_list
        assert "http://localhost:3000" in origins
        assert "http://localhost:5173" in origins

    def test_cors_origin_list_custom(self):
        from app.config import Settings
        s = Settings(cors_origins="https://app.example.com, https://staging.example.com")
        origins = s.cors_origin_list
        assert len(origins) == 2
        assert "https://app.example.com" in origins

    def test_cors_origin_list_empty_filtered(self):
        from app.config import Settings
        s = Settings(cors_origins="https://a.com,,, https://b.com,")
        origins = s.cors_origin_list
        assert len(origins) == 2


# ════════════════════════════════════════════════
#  OPENAPI METADATA
# ════════════════════════════════════════════════


class TestOpenAPIMetadata:

    def _get_schema(self):
        from app.main import create_app
        app = create_app()
        return app.openapi()

    def test_contact_info(self):
        schema = self._get_schema()
        assert "contact" in schema["info"]
        assert schema["info"]["contact"]["name"] == "Bubby Vision Team"

    def test_license_info(self):
        schema = self._get_schema()
        assert "license" in schema["info"]
        assert schema["info"]["license"]["name"] == "MIT"

    def test_tag_descriptions(self):
        schema = self._get_schema()
        tags = {t["name"]: t for t in schema.get("tags", [])}
        assert "Health" in tags
        assert "description" in tags["Health"]
        assert "Data" in tags
        assert "Market Data" in tags

    def test_all_tags_have_descriptions(self):
        schema = self._get_schema()
        for tag in schema.get("tags", []):
            assert "description" in tag, f"Tag '{tag['name']}' missing description"
