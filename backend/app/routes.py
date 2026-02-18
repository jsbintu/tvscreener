"""
Bubby Vision — API Routes

All HTTP endpoints. Thin layer — delegates to the DataEngine.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from app.config import get_settings
from app.engines.data_engine import DataEngine
from app.models import (
    ChatRequest,
    ChatResponse,
    FearGreedIndex,
    HealthCheck,
    OptionsChain,
    StockData,
)

# ──────────────────────────────────────────────
# Health
# ──────────────────────────────────────────────

health_router = APIRouter()


@health_router.get("/health")
async def health_check():
    """Deep application health check with dependency status and response times."""
    import time as _time
    settings = get_settings()
    services = {}

    # Check Redis
    t0 = _time.perf_counter()
    try:
        import redis as redis_lib
        r = redis_lib.from_url(settings.redis_url, socket_timeout=2)
        r.ping()
        services["redis"] = {"status": "ok", "latency_ms": round((_time.perf_counter() - t0) * 1000, 1)}
    except Exception:
        services["redis"] = {"status": "unavailable", "latency_ms": round((_time.perf_counter() - t0) * 1000, 1)}

    # Check QuestDB
    t0 = _time.perf_counter()
    try:
        import psycopg2
        conn = psycopg2.connect(settings.questdb_dsn, connect_timeout=2)
        conn.close()
        services["questdb"] = {"status": "ok", "latency_ms": round((_time.perf_counter() - t0) * 1000, 1)}
    except Exception:
        services["questdb"] = {"status": "unavailable", "latency_ms": round((_time.perf_counter() - t0) * 1000, 1)}

    # Check ChromaDB
    t0 = _time.perf_counter()
    try:
        import httpx
        resp = httpx.get(f"{settings.chromadb_url}/api/v1/heartbeat", timeout=2)
        services["chromadb"] = {
            "status": "ok" if resp.status_code == 200 else "unavailable",
            "latency_ms": round((_time.perf_counter() - t0) * 1000, 1),
        }
    except Exception:
        services["chromadb"] = {"status": "unavailable", "latency_ms": round((_time.perf_counter() - t0) * 1000, 1)}

    # Check Finnhub API key
    services["finnhub"] = {"status": "ok" if settings.finnhub_api_key else "no_api_key"}

    # Check Alpaca API key
    services["alpaca"] = {"status": "ok" if settings.alpaca_api_key else "no_api_key"}

    # ── Overall status ──
    statuses = [
        s["status"] if isinstance(s, dict) else s
        for s in services.values()
    ]
    if all(s == "ok" for s in statuses):
        overall = "ok"
    elif any(s == "unavailable" for s in statuses):
        overall = "degraded"
    else:
        overall = "ok"

    # ── Uptime ──
    from app.main import APP_START_TIME
    uptime_seconds = round(_time.monotonic() - APP_START_TIME, 1)

    return {
        "status": overall,
        "version": "1.0.0",
        "environment": settings.app_env,
        "uptime_seconds": uptime_seconds,
        "services": services,
    }


# ──────────────────────────────────────────────
# Data Routes
# ──────────────────────────────────────────────

data_router = APIRouter()

_engine = DataEngine()


@data_router.get("/stock/{ticker}", response_model=StockData)
async def get_stock(
    ticker: str,
    period: str = Query("1mo", description="Data period: 1d, 5d, 1mo, 3mo, 6mo, 1y, 2y, 5y, max"),
    interval: str = Query("1d", description="Candle interval: 1m, 5m, 15m, 30m, 1h, 1d, 1wk, 1mo"),
):
    """Fetch stock data: quote, OHLCV history, and fundamentals."""
    try:
        return _engine.get_stock(ticker, period=period, interval=interval)
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"Could not fetch data for {ticker}: {e}")


@data_router.get("/options/{ticker}", response_model=OptionsChain)
async def get_options(
    ticker: str,
    expiration: str = Query(None, description="Expiration date (YYYY-MM-DD). Omit for nearest."),
):
    """Fetch options chain with Greeks."""
    try:
        return _engine.get_options(ticker, expiration=expiration)
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Options unavailable: {e}")


@data_router.get("/sentiment/fear-greed", response_model=FearGreedIndex)
async def get_fear_greed():
    """Fetch current Fear & Greed Index."""
    try:
        return await _engine.get_fear_greed()
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Fear & Greed unavailable: {e}")


@data_router.get("/news/{ticker}")
async def get_news(
    ticker: str,
    limit: int = Query(20, ge=1, le=100),
):
    """Fetch news for a ticker from Finnhub."""
    try:
        articles = await _engine.get_news(ticker, limit=limit)
        return {"ticker": ticker, "articles": [a.model_dump() for a in articles]}
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"News unavailable: {e}")


# ──────────────────────────────────────────────
# Chat (AI Agent) Route
# ──────────────────────────────────────────────

chat_router = APIRouter()


@chat_router.post("/chat", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest):
    """Chat with Bubby Vision's multi-agent AI system.

    Routes your message to the appropriate specialist agent
    (TA, Options, Breakout, News, or Portfolio) based on intent.

    Pipeline: Input Guardrails → Supervisor → Output Guardrails → Response
    """
    from app.guardrails import apply_input_guardrails, OutputGuard, ContentSafety

    # ── Input Guardrails ──
    raw_message = request.get_last_user_message()
    sanitized_message, input_warnings = apply_input_guardrails(raw_message)

    try:
        from app.agents.supervisor import chat

        result = await chat(
            message=sanitized_message,
            conversation_id=request.conversation_id,
        )

        # ── Output Guardrails ──
        ai_response = result["message"]
        ai_response, output_warnings = OutputGuard.validate_response(ai_response)
        ai_response = ContentSafety.redact_pii(ai_response)

        all_warnings = input_warnings + output_warnings

        return ChatResponse(
            message=ai_response,
            conversation_id=result["conversation_id"],
            agent_used=result.get("agent_used"),
            tools_called=result.get("tools_called", []),
            warnings=all_warnings if all_warnings else None,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Chat error: {e}")


# ──────────────────────────────────────────────
# External Quick Links
# ──────────────────────────────────────────────

links_router = APIRouter()


@links_router.get("/links")
async def get_external_links(
    category: Optional[str] = Query(None, description="Filter by category: options, charting, screener, market"),
):
    """Get external tool links for services without APIs.

    Returns clickable links for QuantData, OptionStrat, TradingView, etc.
    """
    from app.data.quick_links import get_links
    return {"links": get_links(category)}


@links_router.get("/links/ticker/{ticker}")
async def get_ticker_links(ticker: str):
    """Get ticker-specific external links (e.g. TradingView chart for AAPL)."""
    from app.data.quick_links import get_link_for_ticker

    services = ["tradingview_chart", "tradingview_options", "tradingview_technicals", "tradingview_financials"]
    links = []
    for service in services:
        url = get_link_for_ticker(service, ticker)
        if url:
            links.append({"service": service, "url": url, "ticker": ticker.upper()})
    return {"ticker": ticker.upper(), "links": links}


# ──────────────────────────────────────────────
# Live Options (Alpaca)
# ──────────────────────────────────────────────

options_live_router = APIRouter()


@options_live_router.get("/options/{ticker}/live")
async def get_live_options(
    ticker: str,
    option_type: Optional[str] = Query(None, description="Filter: call or put"),
    expiration: Optional[str] = Query(None, description="Expiration date YYYY-MM-DD"),
    min_strike: Optional[float] = Query(None, description="Min strike price"),
    max_strike: Optional[float] = Query(None, description="Max strike price"),
    limit: int = Query(50, ge=1, le=1000, description="Max contracts"),
):
    """Fetch live options chain with Greeks from Alpaca."""
    try:
        return await _engine.get_alpaca_options_snapshot(
            ticker=ticker,
            option_type=option_type,
            expiration=expiration,
            min_strike=min_strike,
            max_strike=max_strike,
            limit=limit,
        )
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Options data unavailable: {e}")


# ──────────────────────────────────────────────
# Alpaca Market Data Routes
# ──────────────────────────────────────────────

alpaca_data_router = APIRouter()


@alpaca_data_router.get("/snapshot/{ticker}")
async def get_snapshot(ticker: str):
    """Full real-time stock snapshot: trade, quote, bars."""
    try:
        return await _engine.get_stock_snapshot(ticker)
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Snapshot unavailable: {e}")


@alpaca_data_router.get("/snapshots")
async def get_snapshots(
    symbols: str = Query(..., description="Comma-separated tickers (e.g. AAPL,TSLA,NVDA)"),
):
    """Batch real-time snapshots for multiple stocks."""
    try:
        tickers = [s.strip() for s in symbols.split(",") if s.strip()]
        return await _engine.get_multi_snapshots(tickers)
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Snapshots unavailable: {e}")


@alpaca_data_router.get("/news/market")
async def get_market_news(
    symbols: Optional[str] = Query(None, description="Comma-separated symbols to filter"),
    limit: int = Query(20, ge=1, le=50),
):
    """Market news from Alpaca, optionally filtered by symbols."""
    try:
        sym_list = [s.strip() for s in symbols.split(",") if s.strip()] if symbols else None
        return await _engine.get_alpaca_news(symbols=sym_list, limit=limit)
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"News unavailable: {e}")


@alpaca_data_router.get("/most-actives")
async def get_most_active_stocks(
    by: str = Query("volume", description="Rank by 'volume' or 'trades'"),
    top: int = Query(20, ge=1, le=100),
):
    """Most active stocks by volume or trade count."""
    try:
        return await _engine.get_most_actives(by=by, top=top)
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Screener unavailable: {e}")


@alpaca_data_router.get("/account")
async def get_account():
    """Paper trading account info: buying power, equity, margins."""
    try:
        return await _engine.get_account()
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Account unavailable: {e}")


@alpaca_data_router.get("/positions")
async def get_positions():
    """Open positions in paper trading account."""
    try:
        return await _engine.get_positions()
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Positions unavailable: {e}")


# ──────────────────────────────────────────────
# Extended Data Routes (Edgar, Finnhub, QuantData)
# ──────────────────────────────────────────────

extended_data_router = APIRouter()


@extended_data_router.get("/financials/{ticker}")
async def get_financials(ticker: str):
    """XBRL financial data from the latest 10-K filing."""
    try:
        result = _engine.get_financials(ticker)
        return {"ticker": ticker.upper(), "financials": result}
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Financials unavailable: {e}")


@extended_data_router.get("/earnings-calendar")
async def get_earnings_calendar(
    days: int = Query(7, ge=1, le=30, description="Days ahead to look"),
):
    """Upcoming earnings announcements from Finnhub."""
    try:
        return await _engine.get_earnings_calendar(days=days)
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Earnings calendar unavailable: {e}")


@extended_data_router.get("/analyst/{ticker}")
async def get_analyst_recommendations(ticker: str):
    """Analyst recommendation trends from Finnhub."""
    try:
        return await _engine.get_analyst_recommendations(ticker)
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Recommendations unavailable: {e}")


@extended_data_router.get("/insider/{ticker}")
async def get_insider_transactions(ticker: str):
    """Insider transactions from Finnhub (buys, sells, exercises)."""
    try:
        return await _engine.get_insider_transactions(ticker)
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Insider data unavailable: {e}")


@extended_data_router.get("/darkpool/{ticker}")
async def get_darkpool(
    ticker: str,
    limit: int = Query(25, ge=1, le=100),
):
    """Dark pool prints from QuantData.us."""
    try:
        return await _engine.get_darkpool(ticker, limit=limit)
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Dark pool data unavailable: {e}")


