"""
Bubby Vision — Phase 9 Tests

Tests for:
- Route DataEngine wiring (routes.py no longer imports clients directly)
- Global error handlers (structured JSON responses)
- Error handler registration
"""

import pytest
from unittest.mock import patch, MagicMock


# ════════════════════════════════════════════════
#  ROUTE DATAENGINE WIRING
# ════════════════════════════════════════════════


class TestRouteDataEngineWiring:

    def test_routes_import_data_engine(self):
        """routes.py should import DataEngine, not individual clients."""
        import app.routes as routes_module
        source = open(routes_module.__file__).read()
        # Should use DataEngine
        assert "from app.engines.data_engine import DataEngine" in source
        # Should NOT import individual clients at module level
        assert "from app.data.yfinance_client import YFinanceClient" not in source
        assert "from app.data.fear_greed import FearGreedClient" not in source
        assert "from app.data.finnhub_client import FinnhubClient" not in source

    def test_routes_no_inline_client_instantiation(self):
        """No route should create an AlpacaClient() or EdgarClient() inline."""
        import app.routes as routes_module
        source = open(routes_module.__file__).read()
        assert "AlpacaClient()" not in source
        assert "EdgarClient()" not in source
        assert "QuantDataClient()" not in source
        assert "FinnhubClient()" not in source

    def test_routes_engine_instance_exists(self):
        """routes.py should have a module-level _engine."""
        from app.routes import _engine
        from app.engines.data_engine import DataEngine
        assert isinstance(_engine, DataEngine)


# ════════════════════════════════════════════════
#  ERROR HANDLERS MODULE
# ════════════════════════════════════════════════


class TestErrorHandlersModule:

    def test_imports(self):
        from app.error_handlers import register_error_handlers
        assert callable(register_error_handlers)

    def test_handlers_registered(self):
        from app.main import create_app
        app = create_app()
        # FastAPI stores exception_handlers as a dict keyed by exception class
        handler_types = list(app.exception_handlers.keys())
        # Should have at minimum: HTTPException, RequestValidationError, Exception
        assert len(handler_types) >= 3


# ════════════════════════════════════════════════
#  ERROR HANDLER BEHAVIOR
# ════════════════════════════════════════════════


class TestErrorHandlerBehavior:

    def _get_client(self):
        from fastapi.testclient import TestClient
        from app.main import create_app
        return TestClient(create_app())

    def test_404_returns_structured_json(self):
        client = self._get_client()
        resp = client.get("/v1/api/this-path-does-not-exist")
        assert resp.status_code == 404
        body = resp.json()
        assert body["error"] is True
        assert body["status_code"] == 404
        assert "detail" in body

    def test_422_returns_field_errors(self):
        """Sending invalid query params should produce structured 422."""
        client = self._get_client()
        # /api/stock/{ticker} requires a path param; hitting with bad query should 422
        # Use options endpoint that validates ge/le constraints
        resp = client.get("/v1/api/news/AAPL?limit=-5")
        assert resp.status_code == 422
        body = resp.json()
        assert body["error"] is True
        assert body["status_code"] == 422
        assert "errors" in body
        assert len(body["errors"]) >= 1

    def test_error_includes_request_id(self):
        """Error responses should include request_id from middleware."""
        client = self._get_client()
        resp = client.get("/v1/api/this-does-not-exist")
        body = resp.json()
        # request_id may be None if request logger didn't set it,
        # but the field should exist
        assert "request_id" in body


# ════════════════════════════════════════════════
#  EXISTING ROUTES STILL WORK
# ════════════════════════════════════════════════


class TestExistingRoutesIntact:

    def _get_client(self):
        from fastapi.testclient import TestClient
        from app.main import create_app
        return TestClient(create_app())

    def test_health_still_works(self):
        resp = self._get_client().get("/health")
        assert resp.status_code == 200

    def test_stock_route_accessible(self):
        """Stock route exists and responds (may be 200 or error)."""
        resp = self._get_client().get("/v1/api/stock/AAPL")
        assert resp.status_code != 404  # route exists

    def test_options_route_accessible(self):
        resp = self._get_client().get("/v1/api/options/AAPL")
        assert resp.status_code != 404

    def test_fear_greed_route_accessible(self):
        resp = self._get_client().get("/v1/api/sentiment/fear-greed")
        assert resp.status_code != 404
