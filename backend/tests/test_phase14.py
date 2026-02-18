"""
Bubby Vision — Phase 14 Tests

Tests for:
- WebSocket authentication (dev bypass, api_key query param)
- Audit logging middleware
- Audit log endpoint
"""

import pytest


# ════════════════════════════════════════════════
#  WEBSOCKET AUTHENTICATION
# ════════════════════════════════════════════════


class TestWebSocketAuth:

    def test_ws_authenticate_function_exists(self):
        from app.websocket import _ws_authenticate
        assert callable(_ws_authenticate)

    def test_price_stream_accepts_api_key_param(self):
        """The price_stream endpoint should accept api_key query param."""
        import inspect
        from app.websocket import price_stream
        sig = inspect.signature(price_stream)
        assert "api_key" in sig.parameters

    def test_alert_stream_accepts_api_key_param(self):
        """The alert_stream endpoint should accept api_key query param."""
        import inspect
        from app.websocket import alert_stream
        sig = inspect.signature(alert_stream)
        assert "api_key" in sig.parameters

    def test_dev_mode_bypasses_auth(self):
        """In dev mode, WS connections should work without api_key."""
        from fastapi.testclient import TestClient
        from app.main import create_app

        app = create_app()
        client = TestClient(app)

        # Connect without api_key — should work in dev mode
        with client.websocket_connect("/ws/alerts") as ws:
            ws.send_text("close")

    def test_dev_mode_price_stream(self):
        """Price stream should accept connections in dev mode."""
        from fastapi.testclient import TestClient
        from app.main import create_app

        app = create_app()
        client = TestClient(app)

        with client.websocket_connect("/ws/stream/AAPL") as ws:
            ws.send_text("close")

    def test_connection_manager_import(self):
        from app.websocket import ConnectionManager, manager
        assert isinstance(manager, ConnectionManager)

    def test_connection_manager_tracks_connections(self):
        from app.websocket import ConnectionManager
        mgr = ConnectionManager()
        assert mgr.total_connections == 0
        assert mgr.active_tickers == []


# ════════════════════════════════════════════════
#  AUDIT MIDDLEWARE
# ════════════════════════════════════════════════


class TestAuditMiddleware:

    def _get_client(self):
        from fastapi.testclient import TestClient
        from app.main import create_app
        from app.middleware.audit import clear_audit_log
        clear_audit_log()
        return TestClient(create_app())

    def test_audit_middleware_registered(self):
        from app.main import create_app
        app = create_app()
        middleware_cls_names = [m.cls.__name__ for m in app.user_middleware]
        assert "AuditMiddleware" in middleware_cls_names

    def test_audit_records_requests(self):
        from app.middleware.audit import get_audit_entries, clear_audit_log
        clear_audit_log()

        client = self._get_client()
        client.get("/v1/api/stock/AAPL")

        entries = get_audit_entries()
        assert len(entries) >= 1
        latest = entries[-1]
        assert latest["method"] == "GET"
        assert "/v1/api/stock/AAPL" in latest["path"]
        assert "status" in latest
        assert "duration_ms" in latest
        assert "timestamp" in latest

    def test_audit_skips_health(self):
        from app.middleware.audit import get_audit_entries, clear_audit_log
        clear_audit_log()

        client = self._get_client()
        client.get("/health")

        entries = get_audit_entries()
        health_entries = [e for e in entries if e["path"] == "/health"]
        assert len(health_entries) == 0

    def test_audit_skips_metrics(self):
        from app.middleware.audit import get_audit_entries, clear_audit_log
        clear_audit_log()

        client = self._get_client()
        client.get("/metrics")

        entries = get_audit_entries()
        metrics_entries = [e for e in entries if e["path"] == "/metrics"]
        assert len(metrics_entries) == 0

    def test_audit_ring_buffer_max(self):
        from app.middleware.audit import MAX_AUDIT_ENTRIES
        assert MAX_AUDIT_ENTRIES == 500


# ════════════════════════════════════════════════
#  AUDIT LOG ENDPOINT
# ════════════════════════════════════════════════


class TestAuditLogEndpoint:

    def _get_client(self):
        from fastapi.testclient import TestClient
        from app.main import create_app
        from app.middleware.audit import clear_audit_log
        clear_audit_log()
        return TestClient(create_app())

    def test_audit_log_route_exists(self):
        from app.main import create_app
        app = create_app()
        paths = [route.path for route in app.routes]
        assert "/v1/api/audit-log" in paths

    def test_audit_log_returns_json(self):
        client = self._get_client()
        resp = client.get("/v1/api/audit-log")
        assert resp.status_code == 200
        data = resp.json()
        assert "entries" in data
        assert "count" in data
        assert "max_capacity" in data

    def test_audit_log_limit_param(self):
        client = self._get_client()
        # Make a few requests first
        client.get("/v1/api/stock/AAPL")
        client.get("/v1/api/stock/TSLA")

        resp = client.get("/v1/api/audit-log?limit=1")
        data = resp.json()
        assert data["count"] <= 1

    def test_audit_log_path_filter(self):
        client = self._get_client()
        client.get("/v1/api/stock/AAPL")
        client.get("/v1/api/audit-log")

        resp = client.get("/v1/api/audit-log?path=stock")
        data = resp.json()
        for entry in data["entries"]:
            assert "stock" in entry["path"]

    def test_audit_log_method_filter(self):
        client = self._get_client()
        resp = client.get("/v1/api/audit-log?method=POST")
        data = resp.json()
        for entry in data["entries"]:
            assert entry["method"] == "POST"
