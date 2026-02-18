"""
Bubby Vision — Phase 6 Tests

Tests for:
- QuestDB client (offline graceful degradation)
- WebSocket module (connection manager, imports)
- Watchlist & Alerts routes (in-memory fallback)
- Module exports
"""

import pytest
from datetime import datetime, timezone


# ════════════════════════════════════════════════
#  QUESTDB CLIENT
# ════════════════════════════════════════════════


class TestQuestDBClient:

    def test_import(self):
        from app.db.questdb_client import QuestDBClient, get_questdb
        assert QuestDBClient is not None
        assert callable(get_questdb)

    def test_client_offline_graceful(self):
        """Client degrades gracefully when QuestDB is not running."""
        from app.db.questdb_client import QuestDBClient
        client = QuestDBClient()
        # Should not crash — just report unavailable
        assert client.query_ohlcv("AAPL") == []
        assert client.get_active_alerts("user1") == []
        assert client.get_watchlist("user1") == []
        assert client.insert_ohlcv("AAPL", []) == 0

    def test_ensure_tables_offline(self):
        from app.db.questdb_client import QuestDBClient
        client = QuestDBClient()
        # Should return False when QuestDB is unavailable
        result = client.ensure_tables()
        assert result is False

    def test_module_exports(self):
        from app.db import QuestDBClient, get_questdb
        assert QuestDBClient is not None
        assert callable(get_questdb)


# ════════════════════════════════════════════════
#  WEBSOCKET MODULE
# ════════════════════════════════════════════════


class TestWebSocket:

    def test_imports(self):
        from app.websocket import ws_router, manager, ConnectionManager, push_alert
        assert ws_router is not None
        assert manager is not None
        assert ConnectionManager is not None
        assert callable(push_alert)

    def test_connection_manager_init(self):
        from app.websocket import ConnectionManager
        mgr = ConnectionManager()
        assert mgr.total_connections == 0
        assert mgr.active_tickers == []

    def test_connection_manager_tracks_tickers(self):
        """Manager correctly reports empty state."""
        from app.websocket import ConnectionManager
        mgr = ConnectionManager()
        assert len(mgr.active_tickers) == 0
        assert mgr.total_connections == 0

    def test_websocket_routes_registered(self):
        """WebSocket routes are mounted in the FastAPI app."""
        from app.main import create_app
        app = create_app()
        route_paths = [r.path for r in app.routes]
        assert "/ws/stream/{ticker}" in route_paths
        assert "/ws/alerts" in route_paths


# ════════════════════════════════════════════════
#  WATCHLIST & ALERTS — IN-MEMORY FALLBACK
# ════════════════════════════════════════════════


class TestWatchlistInMemory:

    def test_add_and_get_watchlist(self):
        from app.routes_watchlist import _InMemoryStore
        store = _InMemoryStore()
        assert store.add_to_watchlist("user1", "AAPL") is True
        items = store.get_watchlist("user1")
        assert len(items) == 1
        assert items[0]["ticker"] == "AAPL"

    def test_watchlist_no_duplicates(self):
        from app.routes_watchlist import _InMemoryStore
        store = _InMemoryStore()
        assert store.add_to_watchlist("user1", "AAPL") is True
        assert store.add_to_watchlist("user1", "AAPL") is False
        assert len(store.get_watchlist("user1")) == 1

    def test_remove_from_watchlist(self):
        from app.routes_watchlist import _InMemoryStore
        store = _InMemoryStore()
        store.add_to_watchlist("user1", "TSLA")
        assert store.remove_from_watchlist("user1", "TSLA") is True
        assert len(store.get_watchlist("user1")) == 0

    def test_remove_nonexistent(self):
        from app.routes_watchlist import _InMemoryStore
        store = _InMemoryStore()
        assert store.remove_from_watchlist("user1", "NVDA") is False

    def test_alerts_crud(self):
        from app.routes_watchlist import _InMemoryStore
        store = _InMemoryStore()
        store.add_alert("user1", {
            "id": "alert-1",
            "ticker": "AAPL",
            "threshold": 200.0,
            "direction": "above",
            "active": True,
        })
        alerts = store.get_alerts("user1")
        assert len(alerts) == 1
        assert alerts[0]["ticker"] == "AAPL"

        # Remove
        assert store.remove_alert("user1", "alert-1") is True
        assert len(store.get_alerts("user1")) == 0

    def test_remove_nonexistent_alert(self):
        from app.routes_watchlist import _InMemoryStore
        store = _InMemoryStore()
        assert store.remove_alert("user1", "bogus-id") is False


# ════════════════════════════════════════════════
#  WATCHLIST API ROUTES
# ════════════════════════════════════════════════


class TestWatchlistRoutes:

    def _get_client(self):
        from fastapi.testclient import TestClient
        from app.main import create_app
        return TestClient(create_app())

    def test_get_empty_watchlist(self):
        client = self._get_client()
        resp = client.get("/v1/api/watchlist?user_id=test_empty")
        assert resp.status_code == 200
        data = resp.json()
        assert data["count"] == 0

    def test_add_to_watchlist_api(self):
        client = self._get_client()
        resp = client.post(
            "/v1/api/watchlist?user_id=test_add",
            json={"ticker": "NVDA"},
        )
        assert resp.status_code == 201
        assert resp.json()["ticker"] == "NVDA"

    def test_add_invalid_ticker(self):
        client = self._get_client()
        resp = client.post(
            "/v1/api/watchlist?user_id=test_invalid",
            json={"ticker": "TOOLONG123456"},
        )
        assert resp.status_code == 422  # Pydantic max_length validation

    def test_create_alert_api(self):
        client = self._get_client()
        resp = client.post(
            "/v1/api/alerts?user_id=test_alerts",
            json={"ticker": "TSLA", "threshold": 250.0, "direction": "above"},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["ticker"] == "TSLA"
        assert data["threshold"] == 250.0
        assert "id" in data

    def test_get_alerts_api(self):
        client = self._get_client()
        resp = client.get("/v1/api/alerts?user_id=test_get_alerts")
        assert resp.status_code == 200
        assert "alerts" in resp.json()

    def test_create_alert_invalid_direction(self):
        client = self._get_client()
        resp = client.post(
            "/v1/api/alerts?user_id=test_dir",
            json={"ticker": "AAPL", "threshold": 100.0, "direction": "sideways"},
        )
        assert resp.status_code == 422  # Pydantic validation


# ════════════════════════════════════════════════
#  DOCKER FILES EXIST
# ════════════════════════════════════════════════


class TestDeployment:

    def test_dockerfile_exists(self):
        import os
        dockerfile = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            "Dockerfile",
        )
        assert os.path.exists(dockerfile)

    def test_docker_compose_has_backend(self):
        import os
        compose_file = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            "docker-compose.yml",
        )
        with open(compose_file) as f:
            content = f.read()
        assert "backend:" in content
        assert "mp-backend" in content
        assert "depends_on:" in content


# ════════════════════════════════════════════════
#  ROUTE REGISTRATION
# ════════════════════════════════════════════════


class TestRouteRegistration:

    def test_all_routers_mounted(self):
        from app.main import create_app
        app = create_app()
        route_paths = [r.path for r in app.routes]

        # Phase 1-5 routes
        assert "/health" in route_paths
        assert "/v1/api/stock/{ticker}" in route_paths
        assert "/v1/api/chat" in route_paths

        # Phase 6 routes
        assert "/v1/api/watchlist" in route_paths
        assert "/v1/api/alerts" in route_paths
        assert "/ws/stream/{ticker}" in route_paths
        assert "/ws/alerts" in route_paths
