"""
Bubby Vision — Phase 13 Tests

Tests for:
- API versioning (/v1/api/ prefix)
- X-API-Version response header
- PaginatedResponse model
- Path bucketing with /v1/api/ prefix
"""

import pytest


# ════════════════════════════════════════════════
#  API VERSIONING
# ════════════════════════════════════════════════


class TestAPIVersioning:

    def _get_client(self):
        from fastapi.testclient import TestClient
        from app.main import create_app
        return TestClient(create_app())

    def _get_paths(self):
        from app.main import create_app
        app = create_app()
        return [route.path for route in app.routes]

    def test_v1_prefix_on_stock(self):
        assert "/v1/api/stock/{ticker}" in self._get_paths()

    def test_v1_prefix_on_options(self):
        assert "/v1/api/options/{ticker}" in self._get_paths()

    def test_v1_prefix_on_chat(self):
        assert "/v1/api/chat" in self._get_paths()

    def test_v1_prefix_on_watchlist(self):
        assert "/v1/api/watchlist" in self._get_paths()

    def test_v1_prefix_on_alerts(self):
        assert "/v1/api/alerts" in self._get_paths()

    def test_v1_prefix_on_sentiment(self):
        assert "/v1/api/sentiment/{ticker}" in self._get_paths()

    def test_v1_prefix_on_tv(self):
        assert "/v1/api/tv/technical/{ticker}" in self._get_paths()

    def test_health_not_versioned(self):
        """Health check should NOT have /v1/ prefix."""
        paths = self._get_paths()
        assert "/health" in paths

    def test_metrics_not_versioned(self):
        """Metrics endpoint should NOT have /v1/ prefix."""
        paths = self._get_paths()
        assert "/metrics" in paths

    def test_websocket_not_versioned(self):
        """WebSocket should NOT have /v1/ prefix."""
        paths = self._get_paths()
        assert "/ws/stream/{ticker}" in paths
        assert "/ws/alerts" in paths

    def test_stock_accessible_via_v1(self):
        client = self._get_client()
        resp = client.get("/v1/api/stock/AAPL")
        # Route exists (may return data or error, but not 404)
        assert resp.status_code != 404

    def test_old_api_path_returns_404(self):
        """Old /api/ paths (without /v1/) should 404."""
        client = self._get_client()
        resp = client.get("/api/stock/AAPL")
        assert resp.status_code in (404, 307)  # Not Found or redirect


# ════════════════════════════════════════════════
#  X-API-VERSION HEADER
# ════════════════════════════════════════════════


class TestAPIVersionHeader:

    def _get_client(self):
        from fastapi.testclient import TestClient
        from app.main import create_app
        return TestClient(create_app())

    def test_version_header_on_health(self):
        resp = self._get_client().get("/health")
        assert resp.headers.get("X-API-Version") == "v1"

    def test_version_header_on_metrics(self):
        resp = self._get_client().get("/metrics")
        assert resp.headers.get("X-API-Version") == "v1"

    def test_version_header_on_data_endpoint(self):
        resp = self._get_client().get("/v1/api/stock/AAPL")
        assert resp.headers.get("X-API-Version") == "v1"


# ════════════════════════════════════════════════
#  PAGINATED RESPONSE MODEL
# ════════════════════════════════════════════════


class TestPaginatedResponse:

    def test_model_import(self):
        from app.models import PaginatedResponse
        assert PaginatedResponse is not None

    def test_default_values(self):
        from app.models import PaginatedResponse
        resp = PaginatedResponse()
        assert resp.data == []
        assert resp.page == 1
        assert resp.per_page == 20
        assert resp.total == 0
        assert resp.has_more is False

    def test_with_data(self):
        from app.models import PaginatedResponse
        resp = PaginatedResponse(
            data=[{"ticker": "AAPL"}, {"ticker": "TSLA"}],
            page=1,
            per_page=10,
            total=25,
            has_more=True,
        )
        assert len(resp.data) == 2
        assert resp.total == 25
        assert resp.has_more is True

    def test_validation_page_must_be_positive(self):
        from app.models import PaginatedResponse
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            PaginatedResponse(page=0)

    def test_validation_per_page_max(self):
        from app.models import PaginatedResponse
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            PaginatedResponse(per_page=101)

    def test_serialization(self):
        from app.models import PaginatedResponse
        resp = PaginatedResponse(data=[1, 2, 3], total=3)
        d = resp.model_dump()
        assert d["data"] == [1, 2, 3]
        assert "page" in d
        assert "has_more" in d


# ════════════════════════════════════════════════
#  METRICS PATH BUCKETING (updated for /v1/api/)
# ════════════════════════════════════════════════


class TestMetricsPathBucketingV1:

    def test_bucket_v1_stock(self):
        from app.metrics import _bucket_path
        assert _bucket_path("/v1/api/stock/AAPL") == "/v1/api/stock/{ticker}"

    def test_bucket_v1_options(self):
        from app.metrics import _bucket_path
        assert _bucket_path("/v1/api/options/TSLA") == "/v1/api/options/{ticker}"

    def test_bucket_v1_news(self):
        from app.metrics import _bucket_path
        assert _bucket_path("/v1/api/news/NVDA") == "/v1/api/news/{ticker}"

    def test_bucket_health_unchanged(self):
        from app.metrics import _bucket_path
        assert _bucket_path("/health") == "/health"

    def test_bucket_metrics_unchanged(self):
        from app.metrics import _bucket_path
        assert _bucket_path("/metrics") == "/metrics"
