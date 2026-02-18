"""
Core Route Tests

Tests for health check and external links endpoints — no external API mocking needed.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


# ──────────────────────────────────────────────
# Health Check
# ──────────────────────────────────────────────

class TestHealthRoute:
    """Tests for /health endpoint."""

    def test_health_returns_200(self):
        resp = client.get("/health")
        assert resp.status_code == 200

    def test_health_response_structure(self):
        resp = client.get("/health")
        data = resp.json()
        assert "status" in data
        assert "version" in data
        assert "services" in data
        assert "uptime_seconds" in data
        assert data["version"] == "1.0.0"

    def test_health_services_present(self):
        resp = client.get("/health")
        services = resp.json()["services"]
        # At minimum these keys should exist (services may be unavailable in test env)
        assert "redis" in services
        assert "questdb" in services


# ──────────────────────────────────────────────
# External Links
# ──────────────────────────────────────────────

class TestLinksRoutes:
    """Tests for /v1/api/links/* endpoints."""

    def test_get_all_links(self):
        resp = client.get("/v1/api/links")
        assert resp.status_code == 200
        data = resp.json()
        assert "links" in data
        assert len(data["links"]) >= 4  # We have at least 6 links defined

    def test_filter_links_by_category(self):
        resp = client.get("/v1/api/links?category=options")
        assert resp.status_code == 200
        links = resp.json()["links"]
        assert len(links) >= 2  # At least QuantData + OptionStrat + TV Options
        for link in links:
            assert link["category"] == "options"

    def test_filter_empty_category(self):
        resp = client.get("/v1/api/links?category=nonexistent")
        assert resp.status_code == 200
        assert resp.json()["links"] == []

    def test_ticker_links(self):
        resp = client.get("/v1/api/links/ticker/AAPL")
        assert resp.status_code == 200
        data = resp.json()
        assert data["ticker"] == "AAPL"
        assert len(data["links"]) >= 1
        for link in data["links"]:
            assert "service" in link
            assert "url" in link
            assert link["ticker"] == "AAPL"
            assert "AAPL" in link["url"]

    def test_ticker_links_case_insensitive(self):
        resp = client.get("/v1/api/links/ticker/aapl")
        assert resp.status_code == 200
        data = resp.json()
        assert data["ticker"] == "AAPL"
        for link in data["links"]:
            assert "AAPL" in link["url"]
