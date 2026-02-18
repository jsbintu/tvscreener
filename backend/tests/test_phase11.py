"""
Bubby Vision — Phase 11 Tests

Tests for:
- Structlog migration (no print() in production code)
- Enhanced health check (latency, uptime, services, overall status)
- Prometheus metrics endpoint and middleware
- Startup config validation
"""

import pytest


# ════════════════════════════════════════════════
#  STRUCTLOG MIGRATION
# ════════════════════════════════════════════════


class TestStructlogMigration:

    def test_main_no_print_statements(self):
        """main.py should use structlog, not print()."""
        import app.main as module
        source = open(module.__file__).read()
        # All print() calls should be replaced with log.*
        assert "print(" not in source
        assert "structlog" in source

    def test_edgar_no_print_statements(self):
        """edgar_client.py should use structlog, not print()."""
        import app.data.edgar_client as module
        source = open(module.__file__).read()
        assert "print(" not in source
        assert "structlog" in source


# ════════════════════════════════════════════════
#  STARTUP CONFIG VALIDATION
# ════════════════════════════════════════════════


class TestStartupValidation:

    def test_validate_config_function_exists(self):
        from app.main import _validate_config
        assert callable(_validate_config)

    def test_validate_config_warns_on_empty_keys(self):
        """Should not raise; just logs warnings."""
        from app.main import _validate_config
        from app.config import Settings
        settings = Settings()
        # Should run without error even with empty keys
        _validate_config(settings)

    def test_app_start_time_defined(self):
        from app.main import APP_START_TIME
        assert isinstance(APP_START_TIME, float)
        assert APP_START_TIME > 0


# ════════════════════════════════════════════════
#  ENHANCED HEALTH CHECK
# ════════════════════════════════════════════════


class TestEnhancedHealthCheck:

    def _get_client(self):
        from fastapi.testclient import TestClient
        from app.main import create_app
        return TestClient(create_app())

    def test_health_returns_200(self):
        resp = self._get_client().get("/health")
        assert resp.status_code == 200

    def test_health_has_status_field(self):
        body = self._get_client().get("/health").json()
        assert "status" in body
        assert body["status"] in ("ok", "degraded", "critical")

    def test_health_has_uptime(self):
        body = self._get_client().get("/health").json()
        assert "uptime_seconds" in body
        assert isinstance(body["uptime_seconds"], (int, float))
        assert body["uptime_seconds"] >= 0

    def test_health_has_version(self):
        body = self._get_client().get("/health").json()
        assert body["version"] == "1.0.0"

    def test_health_has_services(self):
        body = self._get_client().get("/health").json()
        assert "services" in body
        services = body["services"]
        # Should check at least these services
        assert "redis" in services
        assert "questdb" in services
        assert "chromadb" in services
        assert "finnhub" in services
        assert "alpaca" in services

    def test_health_services_have_status(self):
        body = self._get_client().get("/health").json()
        for name, info in body["services"].items():
            if isinstance(info, dict):
                assert "status" in info, f"Service '{name}' missing status"

    def test_health_latency_fields(self):
        """Redis, QuestDB, ChromaDB should have latency_ms."""
        body = self._get_client().get("/health").json()
        for name in ("redis", "questdb", "chromadb"):
            info = body["services"][name]
            assert "latency_ms" in info, f"{name} missing latency_ms"


# ════════════════════════════════════════════════
#  PROMETHEUS METRICS
# ════════════════════════════════════════════════


class TestMetrics:

    def _get_client(self):
        from fastapi.testclient import TestClient
        from app.main import create_app
        return TestClient(create_app())

    def test_metrics_module_imports(self):
        from app.metrics import MetricsMiddleware, metrics_router, record_request
        assert callable(record_request)

    def test_metrics_endpoint_returns_text(self):
        client = self._get_client()
        # Hit a route first to generate some metrics
        client.get("/health")
        resp = client.get("/metrics")
        assert resp.status_code == 200
        assert "text/plain" in resp.headers["content-type"]

    def test_metrics_contains_counter_type(self):
        client = self._get_client()
        client.get("/health")
        body = client.get("/metrics").text
        assert "# TYPE http_requests_total counter" in body

    def test_metrics_contains_duration_type(self):
        client = self._get_client()
        client.get("/health")
        body = client.get("/metrics").text
        assert "# TYPE http_request_duration_seconds summary" in body

    def test_metrics_records_requests(self):
        client = self._get_client()
        # Hit health 3 times
        for _ in range(3):
            client.get("/health")
        body = client.get("/metrics").text
        # Should have count for /health
        assert "/health" in body

    def test_bucket_path_normalization(self):
        """Ticker segments should be bucketed as {ticker}."""
        from app.metrics import _bucket_path
        assert _bucket_path("/v1/api/stock/AAPL") == "/v1/api/stock/{ticker}"
        assert _bucket_path("/v1/api/options/TSLA") == "/v1/api/options/{ticker}"
        assert _bucket_path("/v1/api/news/NVDA") == "/v1/api/news/{ticker}"

    def test_bucket_path_preserves_static(self):
        from app.metrics import _bucket_path
        assert _bucket_path("/health") == "/health"
        assert _bucket_path("/metrics") == "/metrics"

    def test_record_request_function(self):
        from app.metrics import record_request, _request_counts
        record_request("GET", "/test/path", 200, 0.05)
        assert _request_counts[("GET", "/test/path", 200)] >= 1
