"""
Phase 3 Tests — Alpaca Data Expansion, Quick Links, TradingView Integration

Tests the new Alpaca market data endpoints (snapshots, news, screener, account),
external quick links module, and TradingView tools.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


# ──────────────────────────────────────────────
# Quick Links Module
# ──────────────────────────────────────────────

class TestQuickLinks:
    def test_get_all_links(self):
        from app.data.quick_links import get_links
        links = get_links()
        assert len(links) >= 6
        assert all("name" in l and "url" in l and "category" in l for l in links)

    def test_filter_by_category(self):
        from app.data.quick_links import get_links
        options_links = get_links("options")
        assert len(options_links) >= 3
        assert all(l["category"] == "options" for l in options_links)

    def test_get_link_for_ticker(self):
        from app.data.quick_links import get_link_for_ticker
        url = get_link_for_ticker("tradingview_chart", "AAPL")
        assert "AAPL" in url
        assert "tradingview.com/chart" in url

    def test_get_link_unknown_service(self):
        from app.data.quick_links import get_link_for_ticker
        url = get_link_for_ticker("nonexistent_service", "AAPL")
        assert url is None


# ──────────────────────────────────────────────
# Quick Links API Endpoints
# ──────────────────────────────────────────────

class TestLinksEndpoints:
    def test_get_links(self):
        resp = client.get("/v1/api/links")
        assert resp.status_code == 200
        data = resp.json()
        # Response may be a list or a dict wrapper
        links = data if isinstance(data, list) else data.get("links", data)
        assert len(links) >= 6

    def test_get_links_filter(self):
        resp = client.get("/v1/api/links?category=options")
        assert resp.status_code == 200
        data = resp.json()
        links = data if isinstance(data, list) else data.get("links", data)
        assert all(l["category"] == "options" for l in links)

    def test_get_ticker_links(self):
        resp = client.get("/v1/api/links/ticker/AAPL")
        assert resp.status_code == 200
        data = resp.json()
        assert data["ticker"] == "AAPL"
        links = data["links"]
        assert isinstance(links, list)
        assert len(links) > 0
        services = [l["service"] for l in links]
        assert "tradingview_chart" in services


# ──────────────────────────────────────────────
# Alpaca Client — Unit Tests
# ──────────────────────────────────────────────

class TestAlpacaClientConfig:
    def test_client_creation(self):
        from app.data.alpaca_client import AlpacaClient
        c = AlpacaClient()
        assert hasattr(c, "_api_key")
        assert hasattr(c, "_secret_key")
        assert hasattr(c, "_is_paper")
        assert hasattr(c, "_headers")

    def test_is_configured_property(self):
        from app.data.alpaca_client import AlpacaClient
        c = AlpacaClient()
        # Property should return bool
        assert isinstance(c._is_configured, bool)


# ──────────────────────────────────────────────
# Alpaca Data — Integration Tests (require API key)
# ──────────────────────────────────────────────

class TestAlpacaStockSnapshot:
    @pytest.mark.slow
    def test_stock_snapshot(self):
        import asyncio
        from app.data.alpaca_client import AlpacaClient
        c = AlpacaClient()
        if not c._is_configured:
            pytest.skip("Alpaca not configured")
        result = asyncio.run(c.get_stock_snapshot("AAPL"))
        assert "ticker" in result
        assert result["ticker"] == "AAPL"
        assert "latest_trade" in result
        assert "latest_quote" in result
        assert "daily_bar" in result
        assert "prev_daily_bar" in result
        assert result["latest_trade"]["price"] is not None

    @pytest.mark.slow
    def test_multi_snapshots(self):
        import asyncio
        from app.data.alpaca_client import AlpacaClient
        c = AlpacaClient()
        if not c._is_configured:
            pytest.skip("Alpaca not configured")
        result = asyncio.run(c.get_multi_snapshots(["AAPL", "TSLA", "NVDA"]))
        assert "snapshots" in result
        assert result["count"] == 3
        for sym in ["AAPL", "TSLA", "NVDA"]:
            assert sym in result["snapshots"]
            snap = result["snapshots"][sym]
            assert snap["price"] > 0
            assert "change_pct" in snap

    @pytest.mark.slow
    def test_latest_trade(self):
        import asyncio
        from app.data.alpaca_client import AlpacaClient
        c = AlpacaClient()
        if not c._is_configured:
            pytest.skip("Alpaca not configured")
        result = asyncio.run(c.get_latest_trade("AAPL"))
        assert result["ticker"] == "AAPL"
        assert result["price"] is not None
        assert result["size"] is not None


class TestAlpacaNews:
    @pytest.mark.slow
    def test_get_news_general(self):
        import asyncio
        from app.data.alpaca_client import AlpacaClient
        c = AlpacaClient()
        if not c._is_configured:
            pytest.skip("Alpaca not configured")
        articles = asyncio.run(c.get_news(limit=5))
        assert isinstance(articles, list)
        assert len(articles) > 0
        assert "headline" in articles[0]
        assert "source" in articles[0]

    @pytest.mark.slow
    def test_get_news_filtered(self):
        import asyncio
        from app.data.alpaca_client import AlpacaClient
        c = AlpacaClient()
        if not c._is_configured:
            pytest.skip("Alpaca not configured")
        articles = asyncio.run(c.get_news(["AAPL"], limit=3))
        assert isinstance(articles, list)
        assert len(articles) > 0


class TestAlpacaScreener:
    @pytest.mark.slow
    def test_most_actives_volume(self):
        import asyncio
        from app.data.alpaca_client import AlpacaClient
        c = AlpacaClient()
        if not c._is_configured:
            pytest.skip("Alpaca not configured")
        actives = asyncio.run(c.get_most_actives(by="volume", top=5))
        assert isinstance(actives, list)
        assert len(actives) == 5
        assert "symbol" in actives[0]
        assert "volume" in actives[0]

    @pytest.mark.slow
    def test_most_actives_trades(self):
        import asyncio
        from app.data.alpaca_client import AlpacaClient
        c = AlpacaClient()
        if not c._is_configured:
            pytest.skip("Alpaca not configured")
        actives = asyncio.run(c.get_most_actives(by="trades", top=3))
        assert len(actives) == 3


class TestAlpacaAccount:
    @pytest.mark.slow
    def test_get_account(self):
        import asyncio
        from app.data.alpaca_client import AlpacaClient
        c = AlpacaClient()
        if not c._is_configured:
            pytest.skip("Alpaca not configured")
        acct = asyncio.run(c.get_account())
        assert "equity" in acct
        assert "cash" in acct
        assert "buying_power" in acct
        assert "status" in acct
        assert acct["equity"] >= 0

    @pytest.mark.slow
    def test_get_positions(self):
        import asyncio
        from app.data.alpaca_client import AlpacaClient
        c = AlpacaClient()
        if not c._is_configured:
            pytest.skip("Alpaca not configured")
        positions = asyncio.run(c.get_positions())
        assert isinstance(positions, list)


class TestAlpacaOptions:
    @pytest.mark.slow
    def test_options_snapshot(self):
        import asyncio
        from app.data.alpaca_client import AlpacaClient
        c = AlpacaClient()
        if not c._is_configured:
            pytest.skip("Alpaca not configured")
        result = asyncio.run(c.get_options_snapshot("AAPL", limit=5))
        assert "total_contracts" in result
        assert "contracts" in result

    @pytest.mark.slow
    def test_options_chain_filtered(self):
        import asyncio
        from app.data.alpaca_client import AlpacaClient
        c = AlpacaClient()
        if not c._is_configured:
            pytest.skip("Alpaca not configured")
        result = asyncio.run(c.get_options_chain_alpaca("AAPL", option_type="call", limit=3))
        assert "total_contracts" in result


# ──────────────────────────────────────────────
# Alpaca API Endpoints
# ──────────────────────────────────────────────

class TestAlpacaApiEndpoints:
    @pytest.mark.slow
    def test_snapshot_endpoint(self):
        resp = client.get("/v1/api/snapshot/AAPL")
        assert resp.status_code in (200, 503)
        if resp.status_code == 200:
            data = resp.json()
            # May return error dict if not configured
            if "error" not in data:
                assert data["ticker"] == "AAPL"

    @pytest.mark.slow
    def test_snapshots_endpoint(self):
        resp = client.get("/v1/api/snapshots?symbols=AAPL,TSLA")
        assert resp.status_code in (200, 503)
        if resp.status_code == 200:
            data = resp.json()
            if "error" not in data:
                assert "snapshots" in data

    @pytest.mark.slow
    def test_news_endpoint(self):
        resp = client.get("/v1/api/news/market?limit=3")
        assert resp.status_code in (200, 503)

    @pytest.mark.slow
    def test_most_actives_endpoint(self):
        resp = client.get("/v1/api/most-actives?by=volume&top=5")
        assert resp.status_code in (200, 503)

    @pytest.mark.slow
    def test_account_endpoint(self):
        resp = client.get("/v1/api/account")
        assert resp.status_code in (200, 503)

    @pytest.mark.slow
    def test_positions_endpoint(self):
        resp = client.get("/v1/api/positions")
        assert resp.status_code in (200, 503)

    @pytest.mark.slow
    def test_live_options_endpoint(self):
        resp = client.get("/v1/api/options/AAPL/live?limit=3")
        assert resp.status_code in (200, 503)


# ──────────────────────────────────────────────
# TradingView Client — Integration Tests
# ──────────────────────────────────────────────

class TestTradingViewClient:
    @pytest.mark.slow
    def test_technical_summary(self):
        import asyncio
        from app.data.tradingview_client import TradingViewClient
        tv = TradingViewClient()
        result = asyncio.run(tv.get_technical_summary("AAPL"))
        assert "ticker" in result
        assert "summary" in result
        assert result["summary"]["recommendation"] in [
            "STRONG_BUY", "BUY", "NEUTRAL", "SELL", "STRONG_SELL"
        ]

    @pytest.mark.slow
    def test_screen_stocks(self):
        import asyncio
        from app.data.tradingview_client import TradingViewClient
        tv = TradingViewClient()
        result = asyncio.run(tv.screen_stocks(limit=5))
        assert isinstance(result, list)
        assert len(result) > 0

    @pytest.mark.slow
    def test_top_movers(self):
        import asyncio
        from app.data.tradingview_client import TradingViewClient
        tv = TradingViewClient()
        result = asyncio.run(tv.get_top_movers(direction="gainers", limit=5))
        assert isinstance(result, list)
        assert len(result) > 0


# ──────────────────────────────────────────────
# Extended Data API Endpoints
# ──────────────────────────────────────────────

class TestExtendedDataEndpoints:
    @pytest.mark.slow
    def test_financials_endpoint(self):
        resp = client.get("/v1/api/financials/AAPL")
        assert resp.status_code in (200, 503)
        if resp.status_code == 200:
            data = resp.json()
            assert data["ticker"] == "AAPL"

    @pytest.mark.slow
    def test_earnings_calendar_endpoint(self):
        resp = client.get("/v1/api/earnings-calendar?days=7")
        assert resp.status_code in (200, 503)

    @pytest.mark.slow
    def test_analyst_endpoint(self):
        resp = client.get("/v1/api/analyst/AAPL")
        assert resp.status_code in (200, 503)

    @pytest.mark.slow
    def test_insider_endpoint(self):
        resp = client.get("/v1/api/insider/AAPL")
        assert resp.status_code in (200, 503)

    @pytest.mark.slow
    def test_darkpool_endpoint(self):
        resp = client.get("/v1/api/darkpool/AAPL?limit=5")
        assert resp.status_code in (200, 503)

