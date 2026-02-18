"""
Phase 1 Tests — Data Clients & API Endpoints

Tests the core data pipeline: yfinance wrapper, Pydantic model validation,
and FastAPI endpoint responses.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models import (
    OHLCV,
    BreakoutStage,
    FearGreedIndex,
    HealthCheck,
    OptionContract,
    OptionsChain,
    Sentiment,
    SignalStrength,
    StockData,
    StockQuote,
    TimeFrame,
)


# ──────────────────────────────────────────────
# FastAPI Client
# ──────────────────────────────────────────────

client = TestClient(app)


# ──────────────────────────────────────────────
# Health Endpoint
# ──────────────────────────────────────────────

class TestHealthEndpoint:
    def test_health_returns_200(self):
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] in ("ok", "degraded")
        assert data["version"] == "1.0.0"
        assert "services" in data
        assert "uptime_seconds" in data

    def test_health_response_model(self):
        resp = client.get("/health")
        data = resp.json()
        assert "status" in data
        assert "services" in data


# ──────────────────────────────────────────────
# Pydantic Model Validation
# ──────────────────────────────────────────────

class TestPydanticModels:
    def test_stock_quote_creation(self):
        quote = StockQuote(
            ticker="AAPL",
            price=192.50,
            change=2.30,
            change_pct=1.21,
            volume=50_000_000,
        )
        assert quote.ticker == "AAPL"
        assert quote.price == 192.50

    def test_ohlcv_creation(self):
        from datetime import datetime
        bar = OHLCV(
            timestamp=datetime.utcnow(),
            open=190.0,
            high=195.0,
            low=189.0,
            close=193.0,
            volume=45_000_000,
        )
        assert bar.close == 193.0

    def test_fear_greed_validation(self):
        fg = FearGreedIndex(value=75, label=Sentiment.GREED)
        assert fg.value == 75
        assert fg.label == Sentiment.GREED

    def test_fear_greed_out_of_range(self):
        with pytest.raises(Exception):
            FearGreedIndex(value=150, label=Sentiment.EXTREME_GREED)

    def test_timeframe_enum(self):
        assert TimeFrame.D1.value == "1d"
        assert TimeFrame.H1.value == "1h"

    def test_signal_strength_enum(self):
        assert SignalStrength.STRONG_BUY.value == "strong_buy"

    def test_breakout_stage_enum(self):
        assert BreakoutStage.PRE_BREAKOUT.value == "pre_breakout"

    def test_options_chain_empty(self):
        chain = OptionsChain(
            ticker="AAPL",
            underlying_price=192.50,
        )
        assert chain.calls == []
        assert chain.puts == []

    def test_option_contract(self):
        from datetime import datetime
        contract = OptionContract(
            contract_symbol="AAPL250221C00195000",
            strike=195.0,
            expiration=datetime(2025, 2, 21),
            option_type="call",
            last_price=3.50,
            bid=3.40,
            ask=3.60,
            volume=1500,
            open_interest=8000,
        )
        assert contract.strike == 195.0
        assert contract.option_type == "call"


# ──────────────────────────────────────────────
# yfinance Client
# ──────────────────────────────────────────────

class TestYFinanceClient:
    """Integration tests — require internet access."""

    @pytest.mark.slow
    def test_get_stock_data(self):
        from app.data.yfinance_client import YFinanceClient
        client = YFinanceClient()
        data = client.get_stock_data("AAPL", period="5d", interval="1d")
        assert isinstance(data, StockData)
        assert data.ticker == "AAPL"
        assert data.quote.price > 0
        assert len(data.history) > 0

    @pytest.mark.slow
    def test_get_options_chain(self):
        from app.data.yfinance_client import YFinanceClient
        client = YFinanceClient()
        chain = client.get_options_chain("AAPL")
        assert isinstance(chain, OptionsChain)
        assert chain.ticker == "AAPL"
        assert len(chain.expirations) > 0


# ──────────────────────────────────────────────
# Stock API Endpoint
# ──────────────────────────────────────────────

class TestStockEndpoint:
    @pytest.mark.slow
    def test_get_stock(self):
        resp = client.get("/v1/api/stock/AAPL?period=5d&interval=1d")
        assert resp.status_code == 200
        data = resp.json()
        assert data["ticker"] == "AAPL"
        assert "quote" in data
        assert "history" in data

    def test_invalid_ticker(self):
        resp = client.get("/v1/api/stock/ZZZZZZZ?period=1d&interval=1d")
        # Either 404 or empty data
        assert resp.status_code in (200, 404)
