"""
Watchlist & Alert Route Tests

Tests all CRUD operations for the watchlist and price alert endpoints
using the in-memory fallback store (no QuestDB needed).
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


# ──────────────────────────────────────────────
# Watchlist CRUD
# ──────────────────────────────────────────────

class TestWatchlistRoutes:
    """Tests for /v1/api/watchlist/* endpoints."""

    def test_get_empty_watchlist(self):
        # Fresh user has empty watchlist
        resp = client.get("/v1/api/watchlist?user_id=test_wl_fresh")
        assert resp.status_code == 200
        data = resp.json()
        assert data["count"] == 0
        assert data["watchlist"] == []

    def test_add_ticker(self):
        resp = client.post(
            "/v1/api/watchlist?user_id=test_wl_crud",
            json={"ticker": "AAPL"},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["ticker"] == "AAPL"
        assert "message" in data

    def test_get_after_add(self):
        # Should now contain the ticker we added
        resp = client.get("/v1/api/watchlist?user_id=test_wl_crud")
        assert resp.status_code == 200
        data = resp.json()
        tickers = [item["ticker"] for item in data["watchlist"]]
        assert "AAPL" in tickers
        assert data["count"] >= 1

    def test_add_duplicate_returns_409(self):
        resp = client.post(
            "/v1/api/watchlist?user_id=test_wl_crud",
            json={"ticker": "AAPL"},
        )
        assert resp.status_code == 409

    def test_remove_ticker(self):
        resp = client.delete("/v1/api/watchlist/AAPL?user_id=test_wl_crud")
        assert resp.status_code == 200
        data = resp.json()
        assert data["ticker"] == "AAPL"
        assert "message" in data

    def test_remove_nonexistent_returns_404(self):
        resp = client.delete("/v1/api/watchlist/ZZZZZZ?user_id=test_wl_crud")
        assert resp.status_code == 404


# ──────────────────────────────────────────────
# Alert CRUD
# ──────────────────────────────────────────────

class TestAlertRoutes:
    """Tests for /v1/api/alerts/* endpoints."""

    def test_create_alert(self):
        resp = client.post(
            "/v1/api/alerts?user_id=test_alert_crud",
            json={"ticker": "TSLA", "threshold": 250.0, "direction": "above"},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["ticker"] == "TSLA"
        assert data["threshold"] == 250.0
        assert data["direction"] == "above"
        assert "id" in data

    def test_get_alerts(self):
        resp = client.get("/v1/api/alerts?user_id=test_alert_crud")
        assert resp.status_code == 200
        data = resp.json()
        assert data["count"] >= 1
        assert data["alerts"][0]["ticker"] == "TSLA"

    def test_delete_alert(self):
        # First, get the alert id
        resp = client.get("/v1/api/alerts?user_id=test_alert_crud")
        alert_id = resp.json()["alerts"][0]["id"]

        # Delete it
        resp = client.delete(f"/v1/api/alerts/{alert_id}?user_id=test_alert_crud")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == alert_id
        assert "message" in data

    def test_create_alert_invalid_direction(self):
        resp = client.post(
            "/v1/api/alerts?user_id=test_alert_crud",
            json={"ticker": "AAPL", "threshold": 200.0, "direction": "sideways"},
        )
        assert resp.status_code == 422  # Pydantic validation error
