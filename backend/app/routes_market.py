"""
Bubby Vision — Market Data Routes

REST endpoints for all DataEngine capabilities that weren't covered by
the original routes.py. All requests flow through the DataEngine
(gaining Redis caching automatically via @cached decorators).
"""

from __future__ import annotations

import math
from typing import Any, Optional

import pandas as pd

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

import structlog

from app.engines.data_engine import DataEngine
from app.engines.options_engine import OptionsEngine
from app.engines.pattern_engine import PatternEngine
from app.engines.vision_engine import VisionEngine
from app.data.openbb_client import OpenBBClient

log = structlog.get_logger(__name__)

market_router = APIRouter()
_engine = DataEngine()
_pattern_engine = PatternEngine()
_vision_engine = VisionEngine()
_openbb = OpenBBClient()


def _sanitize_floats(obj: Any) -> Any:
    """Replace NaN/Inf float values with None for JSON compliance.

    TradingView data frequently contains NaN values that crash
    FastAPI's JSON serializer.
    """
    if isinstance(obj, float):
        if math.isnan(obj) or math.isinf(obj):
            return None
        return obj
    if isinstance(obj, dict):
        return {k: _sanitize_floats(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_sanitize_floats(v) for v in obj]
    return obj


# ──────────────────────────────────────────────
# Sentiment
# ──────────────────────────────────────────────


@market_router.get("/sentiment/{ticker}")
async def get_sentiment_bundle(ticker: str):
    """Fused sentiment from Fear & Greed + Finnhub + WSB Reddit.

    Returns market-wide sentiment plus ticker-specific social signals.
    """
    try:
        return await _engine.get_sentiment_bundle(ticker)
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Sentiment data unavailable: {e}")


# ──────────────────────────────────────────────
# SEC Filings (EDGAR)
# ──────────────────────────────────────────────


@market_router.get("/filings/{ticker}")
async def get_sec_filings(
    ticker: str,
    form_type: Optional[str] = Query(None, description="Filter by form type (e.g. 10-K, 10-Q, 8-K)"),
    limit: int = Query(10, ge=1, le=50, description="Max filings to return"),
):
    """SEC filings from EDGAR (10-K, 10-Q, 8-K, Form 4, etc.)."""
    try:
        filings = _engine.get_filings(ticker, form_type=form_type, limit=limit)
        return {
            "ticker": ticker.upper(),
            "count": len(filings),
            "filings": [f.model_dump() if hasattr(f, "model_dump") else f for f in filings],
        }
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"SEC filings unavailable: {e}")


# ──────────────────────────────────────────────
# Options Flow (QuantData)
# ──────────────────────────────────────────────


@market_router.get("/options-flow")
async def get_options_flow(
    ticker: Optional[str] = Query(None, description="Filter by ticker"),
    min_premium: int = Query(100_000, ge=0, description="Min premium in dollars"),
):
    """Live options flow — large block trades and institutional activity."""
    try:
        return await _engine.get_options_flow(ticker, min_premium=min_premium)
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Options flow unavailable: {e}")


@market_router.get("/unusual-activity")
async def get_unusual_activity(
    ticker: Optional[str] = Query(None, description="Filter by ticker"),
):
    """Unusual options activity — volume/OI anomalies."""
    try:
        return await _engine.get_unusual_activity(ticker)
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Unusual activity unavailable: {e}")


@market_router.get("/sweeps")
async def get_sweep_orders(
    ticker: Optional[str] = Query(None, description="Filter by ticker"),
):
    """Sweep orders — aggressive multi-exchange fills."""
    try:
        return await _engine.get_sweep_orders(ticker)
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Sweep data unavailable: {e}")


@market_router.get("/combined-flow")
async def get_combined_flow(
    ticker: Optional[str] = Query(None, description="Filter by ticker"),
    min_premium: int = Query(50_000, ge=0, description="Min premium in dollars"),
):
    """Combined options flow — merges QuantData (API) + OptionStrats (scraped).

    Returns separate lists for each source plus a deduplicated merged list.
    QuantData entries are preferred when duplicates are detected.
    """
    try:
        return await _engine.get_combined_flow(ticker, min_premium=min_premium)
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Combined flow unavailable: {e}")


@market_router.get("/optionstrats/iv/{ticker}")
async def get_optionstrats_iv(ticker: str):
    """OptionStrats IV surface data — current IV, per-expiration IV, IV percentile.

    Only available when OPTIONSTRATS_ENABLED=true.
    """
    try:
        result = await _engine.get_optionstrats_iv(ticker)
        if not result:
            raise HTTPException(
                status_code=404,
                detail=f"No IV data for {ticker} (OptionStrats may be disabled)",
            )
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"IV surface unavailable: {e}")


@market_router.get("/congress")
async def get_congressional_flow(
    limit: int = Query(25, ge=1, le=100, description="Max entries"),
):
    """Congressional trading activity from OptionStrats."""
    try:
        return await _engine.get_congressional_flow(limit=limit)
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Congressional flow unavailable: {e}")


# ──────────────────────────────────────────────
# Combined News (Finnhub + QuantData)
# ──────────────────────────────────────────────


@market_router.get("/news")
async def get_combined_news(
    ticker: Optional[str] = Query(None, description="Filter by ticker"),
    limit: int = Query(50, ge=1, le=200, description="Max news items"),
):
    """Combined news feed — merges Finnhub and QuantData.

    Deduplicates by headline similarity. Returns tagged entries per source.
    Note: Alpaca 'feed' is the SIP price data tier, not a news source.
    """
    try:
        return await _engine.get_combined_news(ticker=ticker, limit=limit)
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Combined news unavailable: {e}")


@market_router.get("/news/quantdata")
async def get_quantdata_news(
    ticker: Optional[str] = Query(None, description="Filter by ticker"),
    topic: Optional[str] = Query(None, description="Filter by topic"),
    limit: int = Query(50, ge=1, le=200, description="Max items"),
):
    """QuantData market news — real-time, filterable by ticker and topic."""
    try:
        return await _engine.get_quantdata_news(ticker=ticker, topic=topic, limit=limit)
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"QuantData news unavailable: {e}")


# ──────────────────────────────────────────────
# OpenBB — Bloomberg-Grade News Wire
# ──────────────────────────────────────────────


@market_router.get("/news/world")
async def get_world_news(
    topic: Optional[str] = Query(None, description="Filter by topic keyword"),
    limit: int = Query(50, ge=1, le=100, description="Max articles"),
):
    """Global market news wire — macro, geopolitical, central bank, earnings.

    This is the Bloomberg Terminal equivalent. Aggregates from multiple
    providers (benzinga, biztoc, tiingo, yfinance) with automatic
    failover to whichever provider is available.
    """
    try:
        from app.data.openbb_client import OpenBBClient
        data = OpenBBClient().get_world_news(limit=limit, topic=topic)
        if data is None:
            return {"articles": [], "source": "openbb_unavailable"}
        return data
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"World news unavailable: {e}")


@market_router.get("/news/company/{ticker}")
async def get_company_news_openbb(
    ticker: str,
    limit: int = Query(30, ge=1, le=100, description="Max articles"),
):
    """Aggregated company news from multiple OpenBB providers.

    Unlike the combined /news endpoint, this directly targets company-specific
    news from benzinga, tiingo, and yfinance, deduplicating by URL.
    """
    try:
        from app.data.openbb_client import OpenBBClient
        data = OpenBBClient().get_company_news_dedicated(ticker, limit=limit)
        if data is None:
            return {"ticker": ticker.upper(), "articles": [], "source": "openbb_unavailable"}
        return data
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Company news unavailable: {e}")


# ──────────────────────────────────────────────
# QuantData — Options Intelligence
# ──────────────────────────────────────────────


@market_router.get("/net-drift")
async def get_net_drift(
    ticker: Optional[str] = Query(None, description="Filter by ticker"),
    date: Optional[str] = Query(None, description="Date YYYY-MM-DD (default: today)"),
):
    """Net drift — cumulative call/put premium imbalance over time."""
    try:
        return await _engine.get_net_drift(ticker=ticker, date=date)
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Net drift unavailable: {e}")


@market_router.get("/net-flow")
async def get_net_flow(
    ticker: Optional[str] = Query(None, description="Filter by ticker"),
    limit: int = Query(50, ge=1, le=200, description="Max entries"),
):
    """Net flow — real-time premium flowing into calls vs puts."""
    try:
        return await _engine.get_net_flow(ticker=ticker, limit=limit)
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Net flow unavailable: {e}")


@market_router.get("/dark-flow")
async def get_dark_flow(
    ticker: Optional[str] = Query(None, description="Filter by ticker"),
    limit: int = Query(25, ge=1, le=100, description="Max entries"),
):
    """Dark flow — large off-exchange institutional activity."""
    try:
        return await _engine.get_dark_flow(ticker=ticker, limit=limit)
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Dark flow unavailable: {e}")


@market_router.get("/exposure/{ticker}")
async def get_options_exposure(
    ticker: str,
    exposure_type: str = Query("gex", description="Type: dex, gex, vex, chex"),
    expiration: Optional[str] = Query(None, description="Expiration YYYY-MM-DD"),
):
    """Options exposure — dealer positioning (Delta/Gamma/Vanna/Charm)."""
    try:
        return await _engine.get_options_exposure(
            ticker=ticker, exposure_type=exposure_type, expiration=expiration,
        )
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Options exposure unavailable: {e}")


@market_router.get("/heatmap/{ticker}")
async def get_heat_map(
    ticker: str,
    metric: str = Query("gex", description="Metric: gex, dex, vex, chex, oi, volume"),
    expiration: Optional[str] = Query(None, description="Expiration YYYY-MM-DD"),
):
    """Options heat map — 30+ metrics across strikes and expirations."""
    try:
        return await _engine.get_heat_map(
            ticker=ticker, metric=metric, expiration=expiration,
        )
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Heat map unavailable: {e}")


@market_router.get("/vol-drift/{ticker}")
async def get_volatility_drift(
    ticker: str,
    date: Optional[str] = Query(None, description="Date YYYY-MM-DD"),
):
    """Volatility drift — intraday IV evolution vs price."""
    try:
        return await _engine.get_volatility_drift(ticker=ticker, date=date)
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Vol drift unavailable: {e}")


@market_router.get("/vol-skew/{ticker}")
async def get_volatility_skew(
    ticker: str,
    expiration: Optional[str] = Query(None, description="Expiration YYYY-MM-DD"),
):
    """Volatility skew — IV shape across strikes."""
    try:
        return await _engine.get_volatility_skew(ticker=ticker, expiration=expiration)
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Vol skew unavailable: {e}")


@market_router.get("/gainers-losers")
async def get_gainers_losers(
    direction: str = Query("bullish", description="'bullish' or 'bearish'"),
    limit: int = Query(25, ge=1, le=100, description="Max entries"),
):
    """Gainers/losers ranked by bullish or bearish premium flow."""
    try:
        return await _engine.get_gainers_losers(direction=direction, limit=limit)
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Gainers/losers unavailable: {e}")


# ──────────────────────────────────────────────
# Market Clock (Alpaca)
# ──────────────────────────────────────────────


@market_router.get("/market-clock")
async def get_market_clock():
    """Is the market open? When does it open/close next?"""
    try:
        return await _engine.get_market_clock()
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Market clock unavailable: {e}")


# ──────────────────────────────────────────────
# Trending (WSB)
# ──────────────────────────────────────────────


@market_router.get("/trending")
async def get_trending_tickers():
    """WSB/Reddit trending tickers by mention count."""
    try:
        return await _engine.get_trending_tickers()
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Trending data unavailable: {e}")


@market_router.get("/wsb/{ticker}")
async def get_wsb_mentions(
    ticker: str,
    subreddit: str = Query("wallstreetbets", description="Subreddit to search"),
    limit: int = Query(25, ge=1, le=100, description="Max posts to return"),
):
    """Search for ticker mentions in WSB or other subreddits."""
    try:
        return await _engine.get_wsb_mentions(ticker, subreddit=subreddit, limit=limit)
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"WSB mentions unavailable: {e}")


# ──────────────────────────────────────────────
# TradingView
# ──────────────────────────────────────────────


@market_router.get("/tv/technical/{ticker}")
async def get_tv_technical_summary(
    ticker: str,
    exchange: str = Query("NASDAQ", description="Exchange (NASDAQ, NYSE, AMEX)"),
    interval: str = Query("1d", description="Interval: 1m, 5m, 15m, 1h, 4h, 1d, 1W, 1M"),
):
    """TradingView 26-indicator technical analysis summary.

    Returns buy/sell/neutral counts, oscillator and moving average
    breakdown, and overall recommendation.
    """
    try:
        result = await _engine.get_tv_technical_summary(ticker, exchange=exchange, interval=interval)
        return _sanitize_floats(result)
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"TV technical analysis unavailable: {e}")


@market_router.get("/ta/indicators/{ticker}")
async def get_ta_indicators(
    ticker: str,
    period: str = Query("6mo", description="History period: 1mo, 3mo, 6mo, 1y, 2y"),
    interval: str = Query("1d", description="Bar interval: 1d, 1h, 15m"),
):
    """Full TA Engine output — all computed indicators for a ticker.

    Returns all 25+ indicators: SMAs, EMAs, MACD, RSI, Stochastic,
    Bollinger, ATR, ADX, Williams %R, CCI, MFI, CMF, ROC, TSI,
    Force Index, Ultimate Oscillator, Keltner, Donchian, Aroon,
    Ichimoku, PSAR, Supertrend, Squeeze, and more.
    """
    try:
        from app.engines.ta_engine import TAEngine
        _ta = TAEngine()
        data = _engine.get_stock(ticker, period=period, interval=interval)
        indicators = _ta.compute_indicators(data.history, timeframe=interval, ticker=ticker)
        return _sanitize_floats(indicators.model_dump(mode="json"))
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"TA indicators failed: {e}")


@market_router.get("/tv/screener")
async def screen_stocks_tv(
    market: str = Query("america", description="Market: america, europe, asia"),
    min_price: Optional[float] = Query(None, description="Min stock price"),
    max_price: Optional[float] = Query(None, description="Max stock price"),
    min_volume: Optional[int] = Query(None, description="Min daily volume"),
    min_change: Optional[float] = Query(None, description="Min % change"),
    max_change: Optional[float] = Query(None, description="Max % change"),
):
    """Run a TradingView stock screener scan with custom filters."""
    kwargs = {"market": market}
    if min_price is not None:
        kwargs["min_price"] = min_price
    if max_price is not None:
        kwargs["max_price"] = max_price
    if min_volume is not None:
        kwargs["min_volume"] = min_volume
    if min_change is not None:
        kwargs["min_change"] = min_change
    if max_change is not None:
        kwargs["max_change"] = max_change

    try:
        result = await _engine.screen_stocks_tv(**kwargs)
        return _sanitize_floats(result)
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"TV screener unavailable: {e}")


@market_router.get("/tv/movers")
async def get_tv_top_movers(
    direction: str = Query("gainers", description="gainers, losers, or active"),
    limit: int = Query(15, ge=1, le=50, description="Number of stocks"),
):
    """Top gainers, losers, or most active stocks from TradingView."""
    try:
        result = await _engine.get_top_movers_tv(direction=direction, limit=limit)
        return _sanitize_floats(result)
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"TV movers unavailable: {e}")


@market_router.get("/tv/snapshot/{ticker}")
async def get_tv_snapshot(ticker: str):
    """Full TradingView data snapshot for a single ticker.

    Includes technical analysis, recommendation summary, and key metrics.
    """
    try:
        result = await _engine.get_tv_snapshot(ticker)
        if result is None:
            raise HTTPException(status_code=404, detail=f"No TradingView data for {ticker}")
        return _sanitize_floats(result)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"TV snapshot unavailable: {e}")


@market_router.get("/tv/quote/{ticker}")
async def get_tv_realtime_quote(ticker: str):
    """Real-time SIP-level quote from TradingView (paid subscription).

    Includes OHLCV, bid/ask, VWAP, extended hours, gap, volatility.
    """
    try:
        result = await _engine.get_tv_realtime_quote(ticker)
        if result is None:
            raise HTTPException(status_code=404, detail=f"No quote for {ticker}")
        return _sanitize_floats(result)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"TV quote unavailable: {e}")


@market_router.get("/tv/batch-quotes")
async def get_tv_batch_quotes(
    tickers: str = Query(..., description="Comma-separated tickers, e.g. AAPL,TSLA,MSFT"),
):
    """Batch real-time quotes for multiple tickers in one call."""
    try:
        ticker_list = [t.strip() for t in tickers.split(",") if t.strip()]
        if not ticker_list:
            raise HTTPException(status_code=400, detail="No tickers provided")
        result = await _engine.get_tv_batch_quotes(ticker_list)
        return _sanitize_floats(result)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"TV batch quotes unavailable: {e}")


@market_router.get("/tv/financials/{ticker}")
async def get_tv_financials(ticker: str):
    """Full company financials — revenue, margins, debt, FCF, valuation.

    Fills gaps that Alpaca doesn't cover: balance sheet, income statement,
    valuation ratios, cash flow metrics.
    """
    try:
        result = await _engine.get_tv_financials(ticker)
        if result is None:
            raise HTTPException(status_code=404, detail=f"No financials for {ticker}")
        return _sanitize_floats(result)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"TV financials unavailable: {e}")


@market_router.get("/tv/earnings-calendar")
async def get_tv_earnings_calendar(
    limit: int = Query(50, ge=1, le=200, description="Max results"),
    upcoming_only: bool = Query(True, description="Only future earnings"),
):
    """Upcoming earnings calendar — not available from Alpaca or QuantData."""
    try:
        result = await _engine.get_tv_earnings_calendar(
            limit=limit, upcoming_only=upcoming_only,
        )
        return _sanitize_floats(result)
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Earnings calendar unavailable: {e}")


@market_router.get("/tv/short-interest")
async def get_tv_short_interest(
    limit: int = Query(25, ge=1, le=100, description="Max results"),
):
    """Short squeeze scanner — ranked by short volume ratio.

    Not available from Alpaca or QuantData.
    """
    try:
        result = await _engine.get_tv_short_interest(limit=limit)
        return _sanitize_floats(result)
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Short interest unavailable: {e}")


@market_router.get("/tv/sector-performance")
async def get_tv_sector_performance(
    top_per_sector: int = Query(5, ge=1, le=20, description="Top stocks per sector"),
):
    """Sector performance heatmap — aggregated sector metrics with top movers."""
    try:
        result = await _engine.get_tv_sector_performance(
            top_per_sector=top_per_sector,
        )
        return _sanitize_floats(result)
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Sector performance unavailable: {e}")


# ──────────────────────────────────────────────
# OptionStrats — Expanded Scraped Data
# ──────────────────────────────────────────────

@market_router.get("/optionstrats/urls/{ticker}")
async def get_optionstrats_urls(
    ticker: str,
    strategy: Optional[str] = Query(None, description="Strategy name e.g. 'Covered Call'"),
):
    """Deep-link URLs for OptionStrats pages.

    Returns URLs for Optimizer, Builder, Flow, and all 50+ strategy builders.
    Frontend opens these in a new tab — the interactive P&L matrix is best
    used directly on OptionStrats.
    """
    try:
        return _engine.get_optionstrats_urls(ticker, strategy=strategy)
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"URL generation failed: {e}")


@market_router.get("/optionstrats/insider-flow")
async def get_insider_flow(
    ticker: Optional[str] = Query(None, description="Filter by ticker"),
    limit: int = Query(50, ge=1, le=200, description="Max results"),
):
    """SEC insider trading from OptionStrats.

    Scraped every 15 min by background Celery task and cached in Redis.
    Unique data source not available from other providers.
    """
    try:
        result = await _engine.get_insider_flow(
            ticker=ticker, limit=limit,
        )
        return _sanitize_floats(result)
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Insider flow unavailable: {e}")


@market_router.get("/optionstrats/strategy-catalog")
async def get_strategy_catalog():
    """Static catalog of 50+ options strategy types.

    Organized by skill level (Novice → Expert) and category.
    Each strategy links to its OptionStrats builder and info pages.
    """
    try:
        return _engine.get_strategy_catalog()
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Strategy catalog unavailable: {e}")


# ──────────────────────────────────────────────
# Phase 6: Enhanced Endpoints
# ──────────────────────────────────────────────


@market_router.get("/fear-greed/detailed")
async def get_fear_greed_detailed():
    """CNN Fear & Greed Index with all 7 sub-indicators."""
    try:
        result = await _engine.get_fear_greed_detailed()
        return result.model_dump(mode="json")
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"F&G detailed unavailable: {e}")


@market_router.get("/earnings/estimates/{ticker}")
async def get_earnings_estimates(ticker: str, freq: str = Query("quarterly")):
    """Forward EPS estimates from Finnhub."""
    try:
        return await _engine.get_earnings_estimates(ticker, freq)
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Earnings estimates unavailable: {e}")


@market_router.get("/price-target/{ticker}")
async def get_price_target(ticker: str):
    """Analyst price target consensus from Finnhub."""
    try:
        return await _engine.get_price_target(ticker)
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Price target unavailable: {e}")


@market_router.get("/fundamentals/{ticker}")
async def get_basic_fundamentals(ticker: str):
    """100+ fundamental metrics from Finnhub (PE, PB, ROE, margins, debt)."""
    try:
        return _sanitize_floats(await _engine.get_basic_financials(ticker))
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Fundamentals unavailable: {e}")


@market_router.get("/insider-sentiment/{ticker}")
async def get_insider_sentiment(ticker: str):
    """Aggregated insider sentiment (MSPR) from Finnhub."""
    try:
        return await _engine.get_insider_sentiment(ticker)
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Insider sentiment unavailable: {e}")


@market_router.get("/earnings/transcript/{ticker}")
async def get_earnings_transcript(
    ticker: str,
    quarter: Optional[int] = Query(None),
    year: Optional[int] = Query(None),
):
    """Earnings call transcript from Finnhub."""
    try:
        return await _engine.get_earnings_transcripts(ticker, quarter, year)
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Transcript unavailable: {e}")


@market_router.get("/financials/{ticker}/multi-year")
async def get_multi_year_financials(ticker: str, years: int = Query(5)):
    """Multi-year XBRL financials from EDGAR 10-K filings."""
    try:
        return _engine.get_multi_year_financials(ticker, years)
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Multi-year financials unavailable: {e}")


@market_router.get("/financials/{ticker}/quarterly")
async def get_quarterly_financials(ticker: str, quarters: int = Query(8)):
    """Quarterly XBRL financials from EDGAR 10-Q filings."""
    try:
        return _engine.get_quarterly_financials(ticker, quarters)
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Quarterly financials unavailable: {e}")


@market_router.get("/wsb/dd/{ticker}")
async def get_dd_posts(ticker: str, limit: int = Query(15)):
    """WSB Due Diligence (DD) tagged posts."""
    try:
        return await _engine.get_dd_posts(ticker, limit=limit)
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"DD posts unavailable: {e}")


@market_router.get("/corporate-actions/{ticker}")
async def get_corporate_actions(ticker: str):
    """Corporate actions (splits, dividends, mergers) from Alpaca."""
    try:
        return await _engine.get_corporate_actions(ticker)
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Corporate actions unavailable: {e}")


@market_router.get("/economic/{series_id}")
async def get_economic_series(series_id: str, limit: int = Query(100)):
    """Fetch any FRED economic data series by ID.

    Common series: GDP, UNRATE, CPIAUCSL, FEDFUNDS, DGS10, SP500, VIXCLS.
    """
    try:
        return await _engine.get_economic_series(series_id, limit=limit)
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Economic data unavailable: {e}")


@market_router.get("/economic/dashboard")
async def get_economic_dashboard():
    """Macro economic snapshot: GDP, unemployment, CPI, Fed rate, Treasury yields."""
    try:
        return await _engine.get_economic_dashboard()
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Economic dashboard unavailable: {e}")


@market_router.get("/treasury-yields")
async def get_treasury_yields():
    """Treasury yields (2Y, 10Y, 30Y), yield curve spread, and inversion status."""
    try:
        return await _engine.get_treasury_yields()
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Treasury yields unavailable: {e}")


# ──────────────────────────────────────────────
# Phase 7: Advanced Options Analysis
# ──────────────────────────────────────────────

_options_engine = OptionsEngine()


@market_router.post("/options/pl-profile")
async def compute_pl_profile(
    legs: list[dict],
    underlying_price: float = Query(...),
    price_range_pct: float = Query(0.20),
):
    """Compute multi-leg options P/L profile at expiration.

    Returns a P/L curve for charting plus breakevens, max profit, max loss.
    """
    try:
        return _options_engine.compute_pl_profile(legs, underlying_price, price_range_pct)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"P/L profile error: {e}")


@market_router.post("/options/probability-of-profit")
async def compute_pop(
    legs: list[dict],
    underlying_price: float = Query(...),
    sigma: float = Query(...),
    T: float = Query(...),
    r: float = Query(0.05),
):
    """Monte Carlo probability of profit for any multi-leg strategy.

    Simulates 10,000 terminal stock prices and checks if P/L > 0.
    """
    try:
        return _options_engine.probability_of_profit(legs, underlying_price, sigma, T, r)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"PoP calculation error: {e}")


@market_router.get("/options/oi-patterns/{ticker}")
async def get_oi_patterns(ticker: str, expiration: Optional[str] = Query(None)):
    """Analyze open interest patterns: put/call walls, strike concentration."""
    try:
        chain = _engine.get_options(ticker, expiration=expiration)
        return _options_engine.analyze_oi_patterns(chain)
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"OI patterns unavailable: {e}")


@market_router.get("/options/gex-detailed/{ticker}")
async def get_gex_detailed(ticker: str, expiration: Optional[str] = Query(None)):
    """Enhanced GEX with per-strike DEX (Delta Exposure) and VEX (Vanna Exposure)."""
    try:
        chain = _engine.get_options(ticker, expiration=expiration)
        return _options_engine.compute_gex_detailed(chain)
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"GEX detailed unavailable: {e}")


@market_router.post("/options/price")
async def price_option(
    S: float = Query(..., description="Current stock price"),
    K: float = Query(..., description="Strike price"),
    T: float = Query(..., description="Time to expiry in years"),
    r: float = Query(0.05, description="Risk-free rate"),
    sigma: float = Query(..., description="Implied volatility"),
    option_type: str = Query("call"),
    model: str = Query("black_scholes", description="Pricing model: black_scholes, monte_carlo, binomial, baw"),
    american: bool = Query(False, description="American exercise (binomial only)"),
):
    """Price an option using Black-Scholes, Monte Carlo, Binomial tree, or Barone-Adesi-Whaley."""
    try:
        if model == "monte_carlo":
            return _options_engine.monte_carlo_price(S, K, T, r, sigma, option_type)
        elif model == "binomial":
            return _options_engine.binomial_price(S, K, T, r, sigma, option_type, american=american)
        elif model == "baw":
            return _options_engine.barone_adesi_whaley(S, K, T, r, sigma, option_type)
        else:
            price = _options_engine.black_scholes(S, K, T, r, sigma, option_type)
            greeks = _options_engine.compute_greeks(S, K, T, r, sigma, option_type)
            return {
                "price": round(price, 4),
                "greeks": greeks.model_dump(mode="json"),
                "model": "black_scholes",
            }
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Pricing error: {e}")


# ──────────────────────────────────────────────
# Phase 7b: Advanced Options Analytics (previously orphaned methods)
# ──────────────────────────────────────────────


@market_router.get("/options/max-pain/{ticker}")
async def get_max_pain(ticker: str, expiration: Optional[str] = Query(None)):
    """Max pain strike — price where option holders lose the most."""
    try:
        chain = _engine.get_options(ticker, expiration=expiration)
        return _options_engine.compute_max_pain(chain)
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Max pain unavailable: {e}")


@market_router.get("/options/pcr/{ticker}")
async def get_pcr(ticker: str, expiration: Optional[str] = Query(None)):
    """Put/call ratio by volume and open interest."""
    try:
        chain = _engine.get_options(ticker, expiration=expiration)
        return _options_engine.put_call_ratio(chain)
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"PCR unavailable: {e}")


@market_router.get("/options/iv-analysis/{ticker}")
async def get_iv_analysis(ticker: str, expiration: Optional[str] = Query(None)):
    """Combined IV metrics: IV rank, percentile, skew, and current ATM IV.

    Computes IV Rank (52-week), IV Percentile, and IV Skew (OTM put vs call).
    """
    try:
        chain = _engine.get_options(ticker, expiration=expiration)

        # Gather IVs from chain
        call_ivs = [c.greeks.implied_volatility for c in chain.calls if c.greeks.implied_volatility]
        put_ivs = [p.greeks.implied_volatility for p in chain.puts if p.greeks.implied_volatility]
        all_ivs = call_ivs + put_ivs

        if not all_ivs:
            raise HTTPException(status_code=404, detail="No IV data available for this chain")

        current_iv = sum(all_ivs) / len(all_ivs)

        # Historical IV from price data (approximate using HV)
        import yfinance as yf
        hist = yf.Ticker(ticker).history(period="1y")
        if hist.empty:
            raise HTTPException(status_code=404, detail="No historical data for IV analysis")

        # Compute historical daily returns → annualized HV as IV proxy
        returns = hist["Close"].pct_change().dropna()
        rolling_hv = (returns.rolling(21).std() * (252 ** 0.5)).dropna().tolist()

        iv_high = max(rolling_hv) if rolling_hv else current_iv
        iv_low = min(rolling_hv) if rolling_hv else current_iv

        rank = _options_engine.iv_rank(current_iv, iv_high, iv_low)
        percentile = _options_engine.iv_percentile(current_iv, rolling_hv) if rolling_hv else 50.0

        # IV Skew: OTM put IV vs OTM call IV
        atm = chain.underlying_price
        otm_call_ivs = [c.greeks.implied_volatility for c in chain.calls
                        if c.greeks.implied_volatility and c.strike > atm * 1.02]
        otm_put_ivs = [p.greeks.implied_volatility for p in chain.puts
                       if p.greeks.implied_volatility and p.strike < atm * 0.98]

        skew = {}
        if otm_call_ivs and otm_put_ivs:
            avg_call_iv = sum(otm_call_ivs) / len(otm_call_ivs)
            avg_put_iv = sum(otm_put_ivs) / len(otm_put_ivs)
            skew = _options_engine.iv_skew(avg_call_iv, avg_put_iv)

        # ── IV Term Structure ──
        # Compute ATM IV for each available expiration
        term_structure = {}
        try:
            # Fetch chain structure for all available expirations
            import asyncio
            qt = _engine.questrade

            async def _get_chain_structure():
                return await qt.get_options_chain_structure(ticker)

            try:
                loop = asyncio.get_running_loop()
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as pool:
                    structure = pool.submit(
                        lambda: asyncio.run(_get_chain_structure())
                    ).result(timeout=10)
            except RuntimeError:
                structure = asyncio.run(_get_chain_structure())

            all_expirations = []
            for entry in structure.get("optionChain", []):
                exp_date = entry.get("expiryDate", "")
                if exp_date:
                    all_expirations.append(exp_date[:10])

            # Compute ATM IV for each expiry (cap at 8 for performance)
            expiry_ivs: list[tuple[str, float]] = []
            for exp in all_expirations[:8]:
                try:
                    exp_chain = _engine.get_options(ticker, expiration=exp)
                    exp_call_ivs = [c.greeks.implied_volatility for c in exp_chain.calls
                                    if c.greeks.implied_volatility and c.in_the_money is False]
                    exp_put_ivs = [p.greeks.implied_volatility for p in exp_chain.puts
                                   if p.greeks.implied_volatility and p.in_the_money is False]
                    exp_all = exp_call_ivs + exp_put_ivs
                    if exp_all:
                        expiry_ivs.append((exp, sum(exp_all) / len(exp_all)))
                except Exception:
                    continue  # Skip expirations that fail

            if expiry_ivs:
                term_structure = _options_engine.term_structure(expiry_ivs)
        except Exception as ts_err:
            log.warning("iv_analysis.term_structure_failed", error=str(ts_err), ticker=ticker)

        return {
            "ticker": ticker,
            "current_iv": round(current_iv, 4),
            "iv_rank": round(rank, 2),
            "iv_percentile": round(percentile, 2),
            "iv_high_52w": round(iv_high, 4),
            "iv_low_52w": round(iv_low, 4),
            "iv_skew": skew,
            "term_structure": term_structure,
            "chain_call_count": len(chain.calls),
            "chain_put_count": len(chain.puts),
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"IV analysis error: {e}")


@market_router.get("/options/unusual/{ticker}")
async def get_unusual_activity_engine(
    ticker: str,
    expiration: Optional[str] = Query(None),
    threshold: float = Query(3.0, description="Volume/OI threshold"),
):
    """Engine-side unusual options activity detection (volume > threshold × OI)."""
    try:
        chain = _engine.get_options(ticker, expiration=expiration)
        return _options_engine.detect_unusual_activity(chain, volume_threshold=threshold)
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Unusual activity unavailable: {e}")


@market_router.get("/options/smart-money/{ticker}")
async def get_smart_money(ticker: str, expiration: Optional[str] = Query(None)):
    """Smart money / institutional positioning score based on OI patterns."""
    try:
        chain = _engine.get_options(ticker, expiration=expiration)
        return _options_engine.detect_smart_money(chain)
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Smart money analysis unavailable: {e}")


@market_router.post("/options/evaluate-strategy")
async def evaluate_strategy(
    strategy_type: str = Query(..., description="Strategy: long_call, bull_call_spread, iron_condor, etc."),
    legs: list[dict] = [],
    underlying_price: float = Query(...),
):
    """Evaluate an options strategy: max profit, max loss, breakevens, risk/reward."""
    try:
        return _options_engine.evaluate_strategy(strategy_type, legs, underlying_price)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Strategy evaluation error: {e}")


@market_router.post("/options/pl-at-date")
async def compute_pl_at_date(
    legs: list[dict],
    underlying_price: float = Query(...),
    target_days: int = Query(..., description="Days forward from now"),
    r: float = Query(0.05),
):
    """Compute P/L profile at a future date using Black-Scholes time-value decay."""
    try:
        return _options_engine.compute_pl_at_target_date(legs, underlying_price, target_days, r)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"P/L at date error: {e}")


@market_router.post("/options/profitable-range")
async def compute_profitable_range(
    legs: list[dict],
    underlying_price: float = Query(...),
):
    """Find min/max profitable prices for a strategy at expiration."""
    try:
        return _options_engine.profitable_price_range(legs, underlying_price)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Profitable range error: {e}")


@market_router.get("/options/higher-greeks/{ticker}")
async def get_higher_greeks(
    ticker: str,
    expiry_days: int = Query(30, ge=1, le=730),
    option_type: str = Query("call"),
    r: float = Query(0.05),
):
    """Compute 2nd and 3rd order Greeks for ATM option.

    Returns: charm, vanna, vomma, veta, color, speed, ultima, zomma.
    """
    try:
        data = _engine.get_stock(ticker)
        S = data.price
        K = S  # ATM
        T = expiry_days / 365.0
        sigma = data.implied_volatility or 0.30
        return _options_engine.compute_higher_greeks(S, K, T, r, sigma, option_type)
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Higher Greeks error: {e}")


class MertonRequest(BaseModel):
    S: float
    K: float
    T: float
    r: float = 0.05
    sigma: float = 0.30
    q: float = 0.015
    option_type: str = "call"


@market_router.post("/options/price-merton")
async def price_merton(req: MertonRequest):
    """Merton model pricing for dividend-paying stocks.

    Returns: price, delta, gamma, theta, vega, model.
    """
    try:
        return _options_engine.price_merton(req.S, req.K, req.T, req.r, req.sigma, req.q, req.option_type)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Merton pricing error: {e}")


# ──────────────────────────────────────────────
# Phase 8: Pattern Detection & Vision Analysis
# ──────────────────────────────────────────────


@market_router.get("/patterns/{ticker}")
async def get_patterns(ticker: str, period: str = Query("3mo")):
    """Scan for all candlestick and chart patterns (40+ detectors)."""
    try:
        data = _engine.get_stock(ticker, period=period, interval="1d")
        return _pattern_engine.scan_all_patterns(data.history)
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Pattern scan failed: {e}")


@market_router.get("/patterns/confluence/{ticker}")
async def get_pattern_confluence(ticker: str, period: str = Query("3mo")):
    """Patterns cross-referenced with TA indicators for conviction score."""
    try:
        from app.engines.ta_engine import TAEngine
        _ta = TAEngine()
        data = _engine.get_stock(ticker, period=period, interval="1d")
        indicators = _ta.compute_indicators(data.history, timeframe="1d", ticker=ticker)
        return _pattern_engine.pattern_confluence(data.history, indicators.model_dump(mode="json"))
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Confluence failed: {e}")


@market_router.post("/vision/analyze")
async def vision_analyze(
    image_base64: str = "",
    ticker: str = Query(""),
    context: str = Query(""),
):
    """Analyze a chart using direct data engines — or analyze user-uploaded screenshot.

    For ticker-based requests: uses ta_engine + pattern_engine + breakout_engine (NO Vision AI).
    For user-uploaded images: uses Gemini Vision for educational screenshot analysis.
    """
    try:
        if image_base64:
            # EDUCATIONAL ONLY: user uploaded their own screenshot
            import base64
            img_bytes = base64.b64decode(image_base64)
            return _vision_engine.analyze_chart(img_bytes, context=context or None)
        elif ticker:
            # DIRECT DATA: no Vision AI, use mathematical engines
            from app.engines.ta_engine import TAEngine
            from app.engines.pattern_engine import PatternEngine
            from app.engines.breakout_engine import BreakoutEngine
            _ta = TAEngine()
            _pat = PatternEngine()
            _bo = BreakoutEngine()

            data = _engine.get_stock(ticker, period="3mo", interval="1d")
            indicators = _ta.compute_indicators(data.history, timeframe="1d", ticker=ticker)
            ind = indicators.model_dump(mode="json")
            patterns = _pat.full_scan(data.history)
            confluence = _pat.pattern_confluence(data.history, ind)

            precursors = _bo.scan_precursors(data.history, indicators)
            breakout_signal = _bo.score_breakout(precursors, indicators)

            current_price = data.history[-1]["close"] if data.history else 0
            rsi = ind.get("rsi", 50)
            sma_20 = ind.get("sma_20", 0)
            sma_50 = ind.get("sma_50", 0)
            bullish = sum([
                rsi > 50 if rsi else False,
                (ind.get("macd_histogram", 0) or 0) > 0,
                current_price > (sma_20 or 0),
                current_price > (sma_50 or 0),
            ])
            trend = "bullish" if bullish >= 3 else "bearish" if bullish <= 1 else "neutral"

            return {
                "method": "direct_data",
                "ticker": ticker,
                "trend": trend,
                "indicators": ind,
                "patterns": patterns,
                "confluence": confluence,
                "breakout_signal": breakout_signal.model_dump(mode="json") if hasattr(breakout_signal, "model_dump") else breakout_signal,
            }
        else:
            raise HTTPException(status_code=400, detail="Provide image_base64 or ticker")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Analysis failed: {e}")


@market_router.post("/vision/compare")
async def vision_compare(
    tickers: list[str],
    period: str = Query("3mo"),
):
    """Compare multiple stocks using direct data correlation (numpy corrcoef)."""
    try:
        import numpy as np
        tickers = tickers[:4]
        price_data = {}
        returns_data = {}

        for t in tickers:
            data = _engine.get_stock(t, period=period, interval="1d")
            closes = [bar["close"] for bar in data.history if bar.get("close")]
            if len(closes) >= 10:
                price_data[t] = closes
                returns_data[t] = (closes[-1] - closes[0]) / closes[0] * 100

        if len(price_data) < 2:
            raise HTTPException(status_code=400, detail="Need at least 2 tickers with data")

        min_len = min(len(v) for v in price_data.values())
        aligned = {t: v[-min_len:] for t, v in price_data.items()}
        ticker_list = list(aligned.keys())
        matrix = np.array([aligned[t] for t in ticker_list])
        corr_matrix = np.corrcoef(matrix).tolist()

        corr_values = [
            corr_matrix[i][j]
            for i in range(len(ticker_list))
            for j in range(i + 1, len(ticker_list))
        ]
        avg_corr = sum(corr_values) / max(len(corr_values), 1)
        ranked = sorted(returns_data.items(), key=lambda x: x[1], reverse=True)

        return {
            "method": "direct_data_numpy_correlation",
            "tickers": ticker_list,
            "correlation_matrix": {
                f"{ticker_list[i]}_vs_{ticker_list[j]}": round(corr_matrix[i][j], 4)
                for i in range(len(ticker_list))
                for j in range(i + 1, len(ticker_list))
            },
            "avg_correlation": round(avg_corr, 4),
            "relative_strength_ranking": [t for t, _ in ranked],
            "returns_pct": {t: round(r, 2) for t, r in returns_data.items()},
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Comparison failed: {e}")


@market_router.get("/patterns/full/{ticker}")
async def get_full_pattern_scan(ticker: str, period: str = Query("3mo")):
    """Deep-dive pattern scan: candlestick, chart, gaps, volume, fibs, trend lines, emerging."""
    try:
        data = _engine.get_stock(ticker, period=period, interval="1d")
        return _pattern_engine.full_scan(data.history)
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Full scan failed: {e}")


@market_router.get("/patterns/fibonacci/{ticker}")
async def get_fibonacci(ticker: str, period: str = Query("6mo")):
    """Fibonacci retracement and extension levels from swing analysis."""
    try:
        data = _engine.get_stock(ticker, period=period, interval="1d")
        return _pattern_engine.detect_fibonacci_levels(data.history)
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Fibonacci failed: {e}")


@market_router.get("/vision/narrate/{ticker}")
async def vision_narrate(ticker: str, period: str = Query("1mo")):
    """Candle-by-candle narration using OHLCV data + Language AI (NOT Vision)."""
    try:
        data = _engine.get_stock(ticker, period=period, interval="1d")
        bars = data.history[-10:] if len(data.history) >= 10 else data.history

        bar_descriptions = []
        for i, bar in enumerate(bars):
            o, h, l, c = bar.get("open", 0), bar.get("high", 0), bar.get("low", 0), bar.get("close", 0)
            bar_type = "bullish" if c > o else "bearish" if c < o else "doji"
            bar_descriptions.append({
                "bar_number": i + 1,
                "date": bar.get("timestamp", bar.get("date", f"bar_{i+1}")),
                "open": round(o, 2), "high": round(h, 2),
                "low": round(l, 2), "close": round(c, 2),
                "volume": bar.get("volume", 0),
                "type": bar_type,
                "change_pct": round((c - o) / o * 100, 2) if o else 0,
            })

        try:
            import json
            from langchain_google_genai import ChatGoogleGenerativeAI
            from langchain_core.messages import HumanMessage, SystemMessage
            from app.config import get_settings

            settings = get_settings()
            llm = ChatGoogleGenerativeAI(
                model="gemini-3.0-flash",
                google_api_key=settings.google_api_key,
                temperature=0.3,
                max_output_tokens=2048,
            )
            prompt = f"""Narrate the recent price action for {ticker}. OHLCV data:
{json.dumps(bar_descriptions, indent=2, default=str)}

Return as JSON with keys: ticker, candle_count_narrated, narration (array), overall_story, key_moment."""
            response = llm.invoke([
                SystemMessage(content="You are an expert technical analyst."),
                HumanMessage(content=prompt),
            ])
            from app.engines.vision_engine import VisionEngine
            return VisionEngine._parse_json(response.content)
        except Exception:
            return {"ticker": ticker, "bars": bar_descriptions, "method": "direct_data_fallback"}
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Narration failed: {e}")


@market_router.get("/vision/health/{ticker}")
async def vision_health(ticker: str, period: str = Query("3mo")):
    """Chart health report using arithmetic scoring on direct data (NOT Vision AI)."""
    try:
        from app.engines.ta_engine import TAEngine
        _ta = TAEngine()
        data = _engine.get_stock(ticker, period=period, interval="1d")
        indicators = _ta.compute_indicators(data.history, timeframe="1d", ticker=ticker)
        ind = indicators.model_dump(mode="json")

        current_price = data.history[-1]["close"] if data.history else 0
        sma_20 = ind.get("sma_20") or 0
        sma_50 = ind.get("sma_50") or 0
        sma_200 = ind.get("sma_200") or 0
        rsi = ind.get("rsi") or 50
        macd_hist = ind.get("macd_histogram") or 0

        trend_score = sum([
            25 if current_price > sma_20 else 0,
            25 if current_price > sma_50 else 0,
            25 if current_price > sma_200 else 0,
            25 if sma_20 > sma_50 else 0,
        ])
        rsi_score = 50 if 40 <= rsi <= 60 else min(100, 50 + (rsi - 60) * 1.25) if rsi > 60 else max(0, 50 - (40 - rsi) * 1.25)
        macd_score = 100 if macd_hist > 0 else max(0, 50 + macd_hist * 10)
        momentum_score = int((rsi_score + macd_score) / 2)

        volumes = [b.get("volume", 0) for b in data.history[-20:]]
        avg_vol = sum(volumes) / max(len(volumes), 1)
        rel_vol = (volumes[-1] if volumes else 0) / max(avg_vol, 1)
        volume_score = min(100, int(rel_vol * 50))

        bb_upper = ind.get("bb_upper") or current_price
        bb_lower = ind.get("bb_lower") or current_price
        bb_width = (bb_upper - bb_lower) / max(current_price, 1) * 100
        volatility_score = 80 if bb_width < 3 else 60 if bb_width < 6 else 40 if bb_width < 10 else 20

        atr = ind.get("atr") or 0
        atr_pct = (atr / max(current_price, 1)) * 100
        risk_score = 90 if atr_pct < 1.5 else 70 if atr_pct < 3 else 40 if atr_pct < 5 else 20

        overall = int((trend_score + momentum_score + volume_score + volatility_score + risk_score) / 5)
        grades = {90: "A+", 80: "A", 70: "B", 60: "C", 50: "D"}
        grade = "F"
        for threshold, g in sorted(grades.items(), reverse=True):
            if overall >= threshold:
                grade = g
                break

        return {
            "method": "direct_data_arithmetic",
            "ticker": ticker,
            "overall_health": overall,
            "grade": grade,
            "scores": {
                "trend": trend_score, "momentum": momentum_score,
                "volume": volume_score, "volatility": volatility_score,
                "risk": risk_score,
            },
            "recommendation": "buy" if overall >= 75 else "sell" if overall <= 35 else "hold" if overall >= 50 else "watch",
        }
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Health report failed: {e}")


# ──────────────────────────────────────────────
# Comprehensive Analysis (AI Data Pipeline)
# ──────────────────────────────────────────────

@market_router.get("/analysis/comprehensive/{ticker}")
async def comprehensive_analysis(
    ticker: str,
    period: str = Query("3mo"),
    interval: str = Query("1d"),
):
    """Bundle ALL engine outputs into a single response for the AI Brain button.

    Combines ta_engine indicators, pattern_engine full_scan, breakout_engine
    analysis, and multi-target TP into one comprehensive data payload.
    """
    from app.engines.ta_engine import TAEngine
    from app.engines.pattern_engine import PatternEngine
    from app.engines.breakout_engine import BreakoutEngine

    try:
        _ta = TAEngine()
        _pat = PatternEngine()
        _bo = BreakoutEngine()

        data = _engine.get_stock(ticker, period=period, interval=interval)
        bars = data.history

        # 1. Technical indicators
        indicators = _ta.compute_indicators(bars, timeframe=interval, ticker=ticker)
        ind = indicators.model_dump(mode="json")

        # 2. Pattern engine — full scan (candlestick, chart, gaps, volume, trends, fib, emerging)
        patterns = _pat.full_scan(bars)
        confluence = _pat.pattern_confluence(bars, ind)

        # 3. Breakout engine — full analysis
        precursors = _bo.scan_precursors(bars, indicators)
        breakout_signal = _bo.score_breakout(precursors, indicators)
        breakout_level = max(b.high for b in bars[-20:]) if len(bars) >= 20 else None

        # 4. Multi-target TP (if breakout level available)
        trade_targets = None
        if breakout_level and bars:
            stop = round(breakout_level * 0.97, 2)
            fib_result = None
            try:
                fib_result = _pat.detect_fibonacci_levels(bars)
                if isinstance(fib_result, dict) and fib_result.get("error"):
                    fib_result = None
            except Exception:
                pass
            trade_targets = _bo.compute_multi_targets(
                entry=breakout_level, stop=stop, bars=bars, fib_levels=fib_result,
            )

        # 5. Health score
        current_price = bars[-1].close if bars else 0
        sma_20 = ind.get("sma_20") or 0
        sma_50 = ind.get("sma_50") or 0
        sma_200 = ind.get("sma_200") or 0
        rsi = ind.get("rsi") or 50
        macd_hist = ind.get("macd_histogram") or 0

        trend_score = sum([
            25 if current_price > sma_20 else 0,
            25 if current_price > sma_50 else 0,
            25 if current_price > sma_200 else 0,
            25 if sma_20 > sma_50 else 0,
        ])
        rsi_score = 50 if 40 <= rsi <= 60 else min(100, 50 + (rsi - 60) * 1.25) if rsi > 60 else max(0, 50 - (40 - rsi) * 1.25)
        macd_score = 100 if macd_hist > 0 else max(0, 50 + macd_hist * 10)
        momentum_score = int((rsi_score + macd_score) / 2)
        health_score = int((trend_score + momentum_score) / 2)

        return {
            "ticker": ticker,
            "period": period,
            "method": "comprehensive_direct_data",
            "indicators": ind,
            "patterns": patterns,
            "confluence": confluence,
            "breakout": {
                "precursor_count": len(precursors),
                "precursors": precursors,
                "quality_score": breakout_signal.quality_score,
                "stage": breakout_signal.stage.value,
                "breakout_level": breakout_level,
            },
            "trade_targets": trade_targets,
            "health_score": health_score,
            "current_price": current_price,
        }
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Comprehensive analysis failed: {e}")


# ──────────────────────────────────────────────
# Phase 2: Morning Briefing & Trading Journal
# ──────────────────────────────────────────────

@market_router.get("/briefing/latest")
async def get_latest_briefing():
    """Return the latest morning briefing from Redis cache."""
    import json
    try:
        import redis
        from app.config import get_settings
        settings = get_settings()
        r = redis.from_url(settings.redis_url, decode_responses=True)

        raw = r.get("bubby:briefing:latest")
        if not raw:
            return {"status": "no_briefing", "message": "No briefing generated yet. Briefings run at 8:00 AM EST."}
        return json.loads(raw)
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Briefing fetch failed: {e}")


@market_router.get("/journal/latest")
async def get_latest_journal():
    """Return the latest daily trading journal from Redis cache."""
    import json
    try:
        import redis
        from app.config import get_settings
        settings = get_settings()
        r = redis.from_url(settings.redis_url, decode_responses=True)

        raw = r.get("bubby:journal:latest")
        if not raw:
            return {"status": "no_journal", "message": "No journal generated yet. Journals run at 4:30 PM EST."}
        return json.loads(raw)
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Journal fetch failed: {e}")


@market_router.get("/journal/{date}")
async def get_journal_by_date(date: str):
    """Return trading journal for a specific date (YYYY-MM-DD)."""
    import json
    try:
        import redis
        from app.config import get_settings
        settings = get_settings()
        r = redis.from_url(settings.redis_url, decode_responses=True)

        raw = r.get(f"bubby:journal:{date}")
        if not raw:
            return {"status": "not_found", "message": f"No journal found for {date}."}
        return json.loads(raw)
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Journal fetch failed: {e}")


@market_router.get("/analysis/anchored-vwap/{ticker}")
async def get_anchored_vwap_route(
    ticker: str,
    anchor_date: Optional[str] = Query(None),
    period: str = Query("6mo"),
):
    """Compute Anchored VWAP from a specific date forward with ±1σ/±2σ bands."""
    try:
        from app.engines.ta_engine import TAEngine
        from app.services.data_engine import DataEngine

        _data = DataEngine()
        _ta = TAEngine()
        data = _data.get_stock(ticker, period=period, interval="1d")

        anchor_index = 0
        if anchor_date and data.history:
            for i, bar in enumerate(data.history):
                bar_date = str(bar.timestamp)[:10] if hasattr(bar, "timestamp") else ""
                if bar_date >= anchor_date:
                    anchor_index = i
                    break

        return _ta.compute_anchored_vwap(data.history, anchor_index=anchor_index)
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Anchored VWAP failed: {e}")


@market_router.get("/analysis/market-structure/{ticker}")
async def get_market_structure_route(
    ticker: str,
    period: str = Query("3mo"),
    lookback: int = Query(5),
):
    """Classify market structure as Uptrend, Downtrend, or Range using swing analysis."""
    try:
        from app.engines.pattern_engine import PatternEngine
        from app.services.data_engine import DataEngine

        _data = DataEngine()
        _pat = PatternEngine()
        data = _data.get_stock(ticker, period=period, interval="1d")
        return _pat.detect_market_structure(data.history, lookback=lookback)
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Market structure failed: {e}")


@market_router.get("/analysis/sentiment/{ticker}")
async def get_sentiment_synthesis_route(
    ticker: str,
    period: str = Query("3mo"),
):
    """Unified sentiment synthesis: TA + patterns + news + structure → single verdict."""
    try:
        from app.agents.tools import get_sentiment_synthesis as _synth_tool
        # Unwrap the langchain tool
        result = _synth_tool.invoke({"ticker": ticker, "period": period})
        return result
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Sentiment synthesis failed: {e}")


# ──────────────────────────────────────────────
# Phase 9: Pattern Alert & Backtest Endpoints
# ──────────────────────────────────────────────

@market_router.get("/patterns/scan/{ticker}")
async def trigger_pattern_scan_route(ticker: str, period: str = Query("3mo")):
    """On-demand real-time pattern scan with new-pattern detection."""
    import json as _json

    try:
        data = _engine.get_stock(ticker, period=period, interval="1d")
        current = _pattern_engine.full_scan(data.history)

        # Check Redis for previous scan to identify NEW patterns
        prev_patterns = set()
        try:
            import redis as _redis
            from app.config import get_settings
            r = _redis.from_url(get_settings().redis_url, decode_responses=True)
            prev_raw = r.get(f"Bubby Vision:pattern_scan:{ticker}")
            if prev_raw:
                prev = _json.loads(prev_raw)
                for p in prev.get("candlestick_patterns", []) + prev.get("chart_patterns", []):
                    if isinstance(p, dict):
                        prev_patterns.add(p.get("name", ""))
            r.setex(f"Bubby Vision:pattern_scan:{ticker}", 600, _json.dumps(current, default=str))
        except Exception:
            pass

        new_patterns = []
        all_p = (
            current.get("candlestick_patterns", []) + current.get("chart_patterns", []) +
            current.get("gap_patterns", []) + current.get("volume_patterns", []) +
            current.get("trend_line_patterns", [])
        )
        for p in all_p:
            if isinstance(p, dict) and p.get("name", "") not in prev_patterns:
                new_patterns.append(p)

        current["new_patterns"] = new_patterns
        current["new_pattern_count"] = len(new_patterns)
        return current
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Pattern scan failed: {e}")


@market_router.get("/patterns/outcomes/{ticker}")
async def get_pattern_outcomes(ticker: str, period: str = Query("6mo"), lookforward: int = Query(20)):
    """Evaluate outcomes of detected patterns (success/failure/active/expired)."""
    import json as _json

    try:
        data = _engine.get_stock(ticker, period=period, interval="1d")

        # Try Redis log first
        pattern_log = []
        try:
            import redis as _redis
            from app.config import get_settings
            r = _redis.from_url(get_settings().redis_url, decode_responses=True)
            log_raw = r.get(f"Bubby Vision:pattern_log:{ticker}")
            if log_raw:
                pattern_log = _json.loads(log_raw)
        except Exception:
            pass

        if not pattern_log:
            scan = _pattern_engine.scan_all_patterns(data.history)
            pattern_log = [
                p for p in scan.get("candlestick_patterns", []) + scan.get("chart_patterns", [])
                if isinstance(p, dict) and (p.get("target") or p.get("stop_loss"))
            ]

        evaluated = _pattern_engine.evaluate_pattern_outcomes(data.history, pattern_log, lookforward)

        successes = [p for p in evaluated if p.get("outcome") == "success"]
        failures = [p for p in evaluated if p.get("outcome") == "failed"]
        active = [p for p in evaluated if p.get("outcome") == "active"]

        return {
            "ticker": ticker,
            "total_evaluated": len(evaluated),
            "successes": len(successes),
            "failures": len(failures),
            "active": len(active),
            "success_rate_pct": round(len(successes) / max(len(successes) + len(failures), 1) * 100, 1),
            "patterns": evaluated,
            "failure_alerts": failures,
        }
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Pattern outcome evaluation failed: {e}")


@market_router.get("/patterns/backtest/{ticker}")
async def backtest_patterns_route(ticker: str, period: str = Query("2y")):
    """Historical pattern backtest — per-pattern win rate, reliability score."""
    try:
        data = _engine.get_stock(ticker, period=period, interval="1d")
        return _pattern_engine.backtest_patterns(data.history)
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Pattern backtest failed: {e}")


@market_router.post("/patterns/watchlist")
async def manage_pattern_watchlist(tickers: list[str], action: str = Query("add")):
    """Add or remove tickers from the real-time pattern scan watchlist.

    Query param 'action': 'add' or 'remove'.
    """
    try:
        import redis as _redis
        from app.config import get_settings
        r = _redis.from_url(get_settings().redis_url, decode_responses=True)

        modified = 0
        for t in tickers:
            if action == "remove":
                r.srem("Bubby Vision:pattern_watchlist", t.upper())
            else:
                r.sadd("Bubby Vision:pattern_watchlist", t.upper())
            modified += 1

        current = sorted(r.smembers("Bubby Vision:pattern_watchlist"))
        return {"action": action, "modified": modified, "watchlist": current}
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Watchlist update failed: {e}")


@market_router.get("/patterns/watchlist")
async def get_pattern_watchlist():
    """Get the current pattern scan watchlist with latest scan results."""
    import json as _json

    try:
        import redis as _redis
        from app.config import get_settings
        r = _redis.from_url(get_settings().redis_url, decode_responses=True)

        tickers = sorted(r.smembers("Bubby Vision:pattern_watchlist"))
        results = {}
        for t in tickers:
            scan_raw = r.get(f"Bubby Vision:pattern_scan:{t}")
            alerts_raw = r.lrange(f"Bubby Vision:pattern_alerts:{t}", 0, 4)
            results[t] = {
                "last_scan": _json.loads(scan_raw) if scan_raw else None,
                "recent_alerts": [_json.loads(a) for a in alerts_raw],
            }

        return {"watchlist": tickers, "count": len(tickers), "results": results}
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Watchlist retrieval failed: {e}")


@market_router.get("/patterns/alerts/{ticker}")
async def get_pattern_alerts(ticker: str, limit: int = Query(20)):
    """Get recent pattern alerts for a ticker (new detections + failures)."""
    import json as _json

    try:
        import redis as _redis
        from app.config import get_settings
        r = _redis.from_url(get_settings().redis_url, decode_responses=True)

        alerts_raw = r.lrange(f"Bubby Vision:pattern_alerts:{ticker}", 0, limit - 1)
        alerts = [_json.loads(a) for a in alerts_raw]

        return {"ticker": ticker, "alerts": alerts, "count": len(alerts)}
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Alert retrieval failed: {e}")


# ──────────────────────────────────────────────
# Phase 10: Breakout Specialty Endpoints
# ──────────────────────────────────────────────

@market_router.get("/breakout/full/{ticker}")
async def full_breakout_analysis_route(ticker: str, period: str = Query("6mo")):
    """Comprehensive breakout analysis — the crown jewel.

    Returns conviction score, all 15 precursors, component scoring,
    options confirmation, institutional detection, and recommendation.
    """
    try:
        data = _engine.get_stock(ticker, period=period, interval="1d")
        from app.engines.ta_engine import TAEngine
        _ta = TAEngine()
        indicators = _ta.compute_indicators(data.history, timeframe="1d", ticker=ticker)

        options_data = None
        try:
            from app.engines.options_engine import OptionsEngine
            opts = OptionsEngine()
            gex = opts.compute_gex(ticker)
            unusual = opts.detect_unusual_activity(ticker)
            options_data = {
                "gex": gex.model_dump(mode="json") if hasattr(gex, "model_dump") else gex,
                "unusual_activity": unusual if isinstance(unusual, list) else [],
            }
        except Exception:
            pass

        from app.engines.breakout_engine import BreakoutEngine
        _bo = BreakoutEngine()
        return _bo.full_breakout_analysis(data.history, indicators, options_data)
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Breakout analysis failed: {e}")


@market_router.get("/breakout/options-confirm/{ticker}")
async def options_confirmation_route(ticker: str):
    """Options-based breakout confirmation analysis."""
    try:
        data = _engine.get_stock(ticker, period="3mo", interval="1d")
        from app.engines.ta_engine import TAEngine
        _ta = TAEngine()
        indicators = _ta.compute_indicators(data.history, timeframe="1d", ticker=ticker)

        from app.engines.breakout_engine import BreakoutEngine
        _bo = BreakoutEngine()
        precursors = _bo.scan_precursors(data.history, indicators)

        from app.engines.options_engine import OptionsEngine
        opts = OptionsEngine()
        gex = opts.compute_gex(ticker)
        unusual = opts.detect_unusual_activity(ticker)
        options_data = {
            "gex": gex.model_dump(mode="json") if hasattr(gex, "model_dump") else gex,
            "unusual_activity": unusual if isinstance(unusual, list) else [],
        }
        return _bo.options_confirmation(options_data, precursors, indicators)
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Options confirmation failed: {e}")


@market_router.get("/breakout/institutional/{ticker}")
async def institutional_tells_route(ticker: str, period: str = Query("3mo")):
    """Detect institutional accumulation/distribution signals."""
    try:
        data = _engine.get_stock(ticker, period=period, interval="1d")
        from app.engines.breakout_engine import BreakoutEngine
        _bo = BreakoutEngine()
        return _bo.detect_institutional_activity(data.history)
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Institutional detection failed: {e}")


@market_router.get("/breakout/backtest/{ticker}")
async def breakout_backtest_route(ticker: str, period: str = Query("2y")):
    """Historical breakout backtest — win rate and volume confirmation analysis."""
    try:
        data = _engine.get_stock(ticker, period=period, interval="1d")
        from app.engines.ta_engine import TAEngine
        _ta = TAEngine()
        indicators = _ta.compute_indicators(data.history, timeframe="1d", ticker=ticker)

        from app.engines.breakout_engine import BreakoutEngine
        _bo = BreakoutEngine()
        return _bo.backtest_breakouts(data.history, indicators)
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Breakout backtest failed: {e}")

@market_router.get("/chart-data/{ticker}")
async def get_chart_data(
    ticker: str,
    period: str = Query("6mo", description="1mo, 3mo, 6mo, 1y, 2y, 5y"),
    interval: str = Query("1d", description="1d, 1h, 15m, 5m"),
):
    """Return all data for the PatternChart component in one call.

    Returns candles, volume, full indicator time-series, sub-pane data
    (RSI, MACD, Stochastic), support/resistance, patterns, and fibonacci.
    """
    import math

    try:
        data = _engine.get_stock(ticker, period=period, interval=interval)
        bars = data.history
        if not bars or len(bars) < 5:
            raise HTTPException(status_code=404, detail=f"No data for {ticker}")

        # ── Convert timestamps to UNIX seconds for lightweight-charts ──
        def ts(dt) -> int:
            return int(dt.timestamp())

        closes = [b.close for b in bars]
        highs = [b.high for b in bars]
        lows = [b.low for b in bars]
        volumes = [float(b.volume) for b in bars]
        times = [ts(b.timestamp) for b in bars]

        # ── Candles ──
        candles = []
        for b in bars:
            candles.append({
                "time": ts(b.timestamp),
                "open": b.open,
                "high": b.high,
                "low": b.low,
                "close": b.close,
            })

        # ── Volume histogram ──
        volume_data = []
        for i, b in enumerate(bars):
            color = "rgba(0,200,83,0.4)" if b.close >= b.open else "rgba(255,53,71,0.4)"
            volume_data.append({"time": times[i], "value": volumes[i], "color": color})

        # ── Indicator time-series (full arrays) ──
        from app.engines.ta_engine import TAEngine
        from ta.trend import IchimokuIndicator, PSARIndicator, ADXIndicator
        from ta.volatility import AverageTrueRange
        from ta.volume import OnBalanceVolumeIndicator, MFIIndicator
        from ta.momentum import WilliamsRIndicator
        _ta = TAEngine()

        # Build a DataFrame for ta library functions
        _df = pd.DataFrame({
            "high": highs, "low": lows, "close": closes, "volume": volumes,
        })

        def safe(val):
            """Convert NaN/inf to None for JSON safety."""
            if val is None:
                return None
            try:
                if math.isnan(val) or math.isinf(val):
                    return None
                return round(val, 4)
            except (TypeError, ValueError):
                return None

        def series(values, time_list):
            """Build [{time, value}] from a list, skipping None entries."""
            return [
                {"time": t, "value": safe(v)}
                for t, v in zip(time_list, values)
                if safe(v) is not None
            ]

        sma_20 = _ta._sma(closes, 20)
        sma_50 = _ta._sma(closes, 50)
        sma_200 = _ta._sma(closes, 200)
        ema_8 = _ta._ema(closes, 8)
        ema_21 = _ta._ema(closes, 21)

        # Bollinger Bands (20, 2)
        bb_upper, bb_middle, bb_lower = [], [], []
        for i in range(len(closes)):
            if sma_20[i] is not None:
                window = closes[max(0, i - 19):i + 1]
                std = (sum((x - sma_20[i]) ** 2 for x in window) / len(window)) ** 0.5
                bb_upper.append(sma_20[i] + 2 * std)
                bb_middle.append(sma_20[i])
                bb_lower.append(sma_20[i] - 2 * std)
            else:
                bb_upper.append(None)
                bb_middle.append(None)
                bb_lower.append(None)

        # VWAP (cumulative)
        vwap_vals = []
        cum_vol = 0.0
        cum_tp_vol = 0.0
        for i in range(len(bars)):
            tp = (highs[i] + lows[i] + closes[i]) / 3.0
            cum_vol += volumes[i]
            cum_tp_vol += tp * volumes[i]
            vwap_vals.append(cum_tp_vol / cum_vol if cum_vol > 0 else None)

        # ── Ichimoku Cloud (5 components) ──
        ichimoku_tenkan, ichimoku_kijun = [None] * len(closes), [None] * len(closes)
        ichimoku_senkou_a, ichimoku_senkou_b = [None] * len(closes), [None] * len(closes)
        ichimoku_chikou = [None] * len(closes)
        if len(_df) >= 52:
            ichi = IchimokuIndicator(_df["high"], _df["low"], window1=9, window2=26, window3=52)
            ichimoku_tenkan = ichi.ichimoku_conversion_line().tolist()
            ichimoku_kijun = ichi.ichimoku_base_line().tolist()
            ichimoku_senkou_a = ichi.ichimoku_a().tolist()
            ichimoku_senkou_b = ichi.ichimoku_b().tolist()
            # Chikou = close shifted back 26 periods
            chikou_series = _df["close"].shift(-26)
            ichimoku_chikou = chikou_series.tolist()

        # ── EMA Ribbon (8 EMAs) ──
        ribbon_periods = [8, 13, 21, 34, 55, 89, 144, 233]
        ema_ribbon = {}
        for rp in ribbon_periods:
            if len(closes) >= rp:
                ema_ribbon[f"ema_{rp}"] = _ta._ema(closes, rp)
            else:
                ema_ribbon[f"ema_{rp}"] = [None] * len(closes)

        # ── Parabolic SAR ──
        psar_vals = [None] * len(closes)
        if len(_df) >= 5:
            psar_ind = PSARIndicator(_df["high"], _df["low"], _df["close"])
            psar_vals = psar_ind.psar().tolist()

        # ── ATR (14) ──
        atr_vals = [None] * len(closes)
        if len(_df) >= 14:
            atr_ind = AverageTrueRange(_df["high"], _df["low"], _df["close"], window=14)
            atr_vals = atr_ind.average_true_range().tolist()

        indicators = {
            "sma_20": series(sma_20, times),
            "sma_50": series(sma_50, times),
            "sma_200": series(sma_200, times),
            "ema_8": series(ema_8, times),
            "ema_21": series(ema_21, times),
            "bb_upper": series(bb_upper, times),
            "bb_middle": series(bb_middle, times),
            "bb_lower": series(bb_lower, times),
            "vwap": series(vwap_vals, times),
            # Ichimoku
            "ichimoku_tenkan": series(ichimoku_tenkan, times),
            "ichimoku_kijun": series(ichimoku_kijun, times),
            "ichimoku_senkou_a": series(ichimoku_senkou_a, times),
            "ichimoku_senkou_b": series(ichimoku_senkou_b, times),
            "ichimoku_chikou": series(ichimoku_chikou, times),
            # EMA Ribbon
            **{k: series(v, times) for k, v in ema_ribbon.items()},
            # Parabolic SAR
            "psar": series(psar_vals, times),
            # ATR overlay
            "atr": series(atr_vals, times),
        }

        # ── Sub-pane data (RSI, MACD, Stochastic) ──
        rsi_14 = _ta._rsi(closes, 14)

        # MACD (12, 26, 9)
        ema_12 = _ta._ema(closes, 12)
        ema_26 = _ta._ema(closes, 26)
        macd_line_vals = []
        for i in range(len(closes)):
            if ema_12[i] is not None and ema_26[i] is not None:
                macd_line_vals.append(ema_12[i] - ema_26[i])
            else:
                macd_line_vals.append(None)

        macd_valid = [v for v in macd_line_vals if v is not None]
        macd_signal_vals = [None] * len(closes)
        if len(macd_valid) >= 9:
            macd_ema = _ta._ema(macd_valid, 9)
            offset = len(closes) - len(macd_valid)
            for idx, val in enumerate(macd_ema):
                if val is not None:
                    macd_signal_vals[offset + idx] = val

        macd_hist_vals = []
        for i in range(len(closes)):
            if macd_line_vals[i] is not None and macd_signal_vals[i] is not None:
                h = macd_line_vals[i] - macd_signal_vals[i]
                color = "rgba(0,200,83,0.6)" if h >= 0 else "rgba(255,53,71,0.6)"
                macd_hist_vals.append({"time": times[i], "value": safe(h), "color": color})

        # Stochastic (14, 3, 3)
        stoch_k_vals = [None] * len(closes)
        stoch_d_vals = [None] * len(closes)
        if len(bars) >= 14:
            for i in range(13, len(bars)):
                window_highs = highs[i - 13:i + 1]
                window_lows = lows[i - 13:i + 1]
                hh = max(window_highs)
                ll = min(window_lows)
                if hh != ll:
                    stoch_k_vals[i] = ((closes[i] - ll) / (hh - ll)) * 100
                else:
                    stoch_k_vals[i] = 50.0

            # Smooth %K with 3-period SMA = %D
            k_valid = [v for v in stoch_k_vals if v is not None]
            if len(k_valid) >= 3:
                d_sma = _ta._sma(k_valid, 3)
                offset = len(closes) - len(k_valid)
                for idx, val in enumerate(d_sma):
                    if val is not None:
                        stoch_d_vals[offset + idx] = val

        # ── ADX with DI+/DI- ──
        adx_vals, adx_pos_vals, adx_neg_vals = [None] * len(closes), [None] * len(closes), [None] * len(closes)
        if len(_df) >= 28:
            adx_ind = ADXIndicator(_df["high"], _df["low"], _df["close"], window=14)
            adx_vals = adx_ind.adx().tolist()
            adx_pos_vals = adx_ind.adx_pos().tolist()
            adx_neg_vals = adx_ind.adx_neg().tolist()

        # ── OBV ──
        obv_vals = [None] * len(closes)
        if len(_df) >= 2:
            obv_ind = OnBalanceVolumeIndicator(_df["close"], _df["volume"])
            obv_vals = obv_ind.on_balance_volume().tolist()

        # ── CCI (20) ──
        cci_vals = [None] * len(closes)
        if len(_df) >= 20:
            from ta.trend import CCIIndicator
            cci_ind = CCIIndicator(_df["high"], _df["low"], _df["close"], window=20)
            cci_vals = cci_ind.cci().tolist()

        # ── Williams %R (14) ──
        williams_vals = [None] * len(closes)
        if len(_df) >= 14:
            wr_ind = WilliamsRIndicator(_df["high"], _df["low"], _df["close"], lbp=14)
            williams_vals = wr_ind.williams_r().tolist()

        # ── MFI (14) ──
        mfi_vals = [None] * len(closes)
        if len(_df) >= 14:
            mfi_ind = MFIIndicator(_df["high"], _df["low"], _df["close"], _df["volume"], window=14)
            mfi_vals = mfi_ind.money_flow_index().tolist()

        sub_panes = {
            "rsi": series(rsi_14, times),
            "macd_line": series(macd_line_vals, times),
            "macd_signal": series(macd_signal_vals, times),
            "macd_hist": [e for e in macd_hist_vals if e.get("value") is not None],
            "stoch_k": series(stoch_k_vals, times),
            "stoch_d": series(stoch_d_vals, times),
            # ADX
            "adx": series(adx_vals, times),
            "adx_pos": series(adx_pos_vals, times),
            "adx_neg": series(adx_neg_vals, times),
            # Volume
            "obv": series(obv_vals, times),
            # Momentum
            "cci": series(cci_vals, times),
            "williams": series(williams_vals, times),
            "mfi": series(mfi_vals, times),
            # Volatility
            "atr_pane": series(atr_vals, times),
        }

        # ── Support/Resistance ──
        sr = _ta.detect_support_resistance(bars)
        support = [{"price": s.price, "strength": s.strength, "type": "support"} for s in sr.support]
        resistance = [{"price": r.price, "strength": r.strength, "type": "resistance"} for r in sr.resistance]

        # ── Patterns ──
        patterns = {}
        ai_analysis = {}
        try:
            from app.engines.pattern_engine import PatternEngine
            _pe = PatternEngine()
            scan = _pe.full_scan(bars, ticker=ticker)

            # Convert pattern timestamps to UNIX seconds
            def pattern_markers(pats, key="index"):
                markers = []
                for p in pats:
                    idx = p.get(key, p.get("end_index", len(bars) - 1))
                    if isinstance(idx, int) and 0 <= idx < len(bars):
                        p["time"] = times[idx]
                    markers.append(p)
                return markers

            patterns["candlestick"] = pattern_markers(scan.get("candlestick_patterns", []))
            patterns["chart"] = pattern_markers(scan.get("chart_patterns", []), "end_index")
            patterns["gap"] = pattern_markers(scan.get("gap_patterns", []))
            patterns["volume"] = pattern_markers(scan.get("volume_patterns", []))
            patterns["emerging"] = pattern_markers(scan.get("emerging_patterns", []))

            # ── Trend lines with drawable coordinates ──
            tl_raw = scan.get("trend_line_patterns", [])
            trend_lines = []
            for tl in tl_raw:
                tl_dict = tl if isinstance(tl, dict) else tl.to_dict() if hasattr(tl, "to_dict") else {}
                bi = tl_dict.get("bar_index", len(bars) - 1)
                if 0 <= bi < len(bars):
                    tl_dict["time"] = times[bi]
                trend_lines.append(tl_dict)
            patterns["trend_lines"] = trend_lines

            # ── Pre-candle formations (1 bar from confirmation) ──
            pre_candle = scan.get("pre_candle_formations", [])
            for pc in pre_candle:
                bi = pc.get("bar_index", len(bars) - 1)
                if isinstance(bi, int) and 0 <= bi < len(bars):
                    pc["time"] = times[bi]
            patterns["pre_candle"] = pre_candle

            # ── Aged patterns with freshness tracking ──
            patterns["aged"] = scan.get("aged_patterns", [])
            patterns["aging_summary"] = scan.get("aging_summary", {})

            patterns["summary"] = {
                "total": scan.get("pattern_count", 0),
                "bullish": scan.get("bullish_count", 0),
                "bearish": scan.get("bearish_count", 0),
                "bias": scan.get("overall_bias", "neutral"),
            }

            # ── AI Analysis Narrative ── build structured reasoning log ──
            analysis_sections = []
            current_price = closes[-1] if closes else 0

            # 1. Overall assessment
            bias = scan.get("overall_bias", "neutral")
            bull = scan.get("bullish_count", 0)
            bear = scan.get("bearish_count", 0)
            total_p = scan.get("pattern_count", 0)
            analysis_sections.append({
                "title": "Overall Assessment",
                "icon": "🎯",
                "content": f"Detected {total_p} patterns: {bull} bullish, {bear} bearish. Overall bias: {bias.upper()}.",
                "severity": "high" if abs(bull - bear) > 3 else "medium",
            })

            # 2. Candlestick patterns
            cands = patterns.get("candlestick", [])
            if cands:
                items = [f"• {c.get('name', 'Unknown')} ({c.get('direction', '?')}, {int(c.get('confidence', 0) * 100)}%)"
                         for c in cands[:8]]
                analysis_sections.append({
                    "title": f"Candlestick Patterns ({len(cands)})",
                    "icon": "🕯️",
                    "content": "\n".join(items),
                    "items": [{
                        "name": c.get("name", ""),
                        "direction": c.get("direction", "neutral"),
                        "confidence": round(c.get("confidence", 0) * 100),
                        "description": c.get("description", ""),
                    } for c in cands],
                })

            # 3. Chart patterns
            charts = patterns.get("chart", [])
            if charts:
                items = [f"• {c.get('name', 'Unknown')} ({c.get('direction', '?')}, {int(c.get('confidence', 0) * 100)}%)"
                         for c in charts[:6]]
                analysis_sections.append({
                    "title": f"Chart Patterns ({len(charts)})",
                    "icon": "📐",
                    "content": "\n".join(items),
                    "items": [{
                        "name": c.get("name", ""),
                        "direction": c.get("direction", "neutral"),
                        "confidence": round(c.get("confidence", 0) * 100),
                        "description": c.get("description", ""),
                        "target": c.get("target"),
                        "stop_loss": c.get("stop_loss"),
                    } for c in charts],
                })

            # 4. Trend lines
            if trend_lines:
                items = [f"• {t.get('name', 'Trend Line')} — {t.get('description', '')}"
                         for t in trend_lines]
                analysis_sections.append({
                    "title": f"Trend Lines ({len(trend_lines)})",
                    "icon": "📈",
                    "content": "\n".join(items),
                })

            # 5. Emerging patterns
            emerging = patterns.get("emerging", [])
            if emerging:
                items = []
                for ep in emerging[:6]:
                    progress = ep.get("formation_progress", ep.get("progress", 0))
                    if isinstance(progress, float) and progress <= 1:
                        progress = int(progress * 100)
                    name = ep.get("name", ep.get("pattern_name", "Unknown"))
                    items.append(f"• {name} — {progress}% formed")
                analysis_sections.append({
                    "title": f"Emerging Patterns ({len(emerging)})",
                    "icon": "🔮",
                    "content": "\n".join(items),
                    "items": [{
                        "name": ep.get("name", ep.get("pattern_name", "")),
                        "direction": ep.get("direction", "neutral"),
                        "progress": ep.get("formation_progress", ep.get("progress", 0)),
                        "description": ep.get("description", ""),
                    } for ep in emerging],
                })

            # 6. Pre-candle setups
            if pre_candle:
                items = [f"• {pc.get('name', 'Setup')} — needs: {pc.get('confirmation_needed', '?')}, prob: {int(pc.get('probability', 0) * 100)}%"
                         for pc in pre_candle[:5]]
                analysis_sections.append({
                    "title": f"Pre-Candle Setups ({len(pre_candle)})",
                    "icon": "⏭️",
                    "content": "\n".join(items),
                    "items": [{
                        "name": pc.get("name", ""),
                        "confirmation_needed": pc.get("confirmation_needed", ""),
                        "probability": round(pc.get("probability", 0) * 100),
                    } for pc in pre_candle],
                })

            # 7. Gap analysis
            gaps = patterns.get("gap", [])
            if gaps:
                items = [f"• {g.get('name', 'Gap')} ({g.get('direction', '?')})" for g in gaps[:5]]
                analysis_sections.append({
                    "title": f"Gap Patterns ({len(gaps)})",
                    "icon": "⚡",
                    "content": "\n".join(items),
                })

            # 8. Volume analysis
            vol_pats = patterns.get("volume", [])
            if vol_pats:
                items = [f"• {v.get('name', 'Volume')} ({v.get('direction', '?')})" for v in vol_pats[:5]]
                analysis_sections.append({
                    "title": f"Volume Patterns ({len(vol_pats)})",
                    "icon": "📊",
                    "content": "\n".join(items),
                })

            # 9. Signal aging summary
            aging = patterns.get("aging_summary", {})
            if aging:
                analysis_sections.append({
                    "title": "Signal Freshness",
                    "icon": "⏱️",
                    "content": (
                        f"Fresh: {aging.get('fresh', 0)} | Active: {aging.get('active', 0)} | "
                        f"Aging: {aging.get('aging', 0)} | Stale: {aging.get('stale', 0)} | "
                        f"Invalidated: {aging.get('invalidated', 0)} | Confirmed: {aging.get('confirmed', 0)}"
                    ),
                })

            ai_analysis = {
                "ticker": ticker.upper(),
                "price": current_price,
                "timestamp": times[-1] if times else 0,
                "sections": analysis_sections,
                "bias": bias,
                "pattern_count": total_p,
            }
        except Exception:
            patterns = {
                "candlestick": [], "chart": [], "gap": [], "volume": [],
                "emerging": [], "trend_lines": [], "pre_candle": [],
                "aged": [], "aging_summary": {}, "summary": {},
            }

        # ── Fibonacci — reuse from full_scan (already computed via detect_fibonacci_levels) ──
        fibonacci = scan.get("fibonacci", {}) if "scan" in dir() else {}

        # ── Real-time enrichment from Questrade L1 ──
        realtime = {}
        try:
            realtime = await _engine.get_realtime_enrichment(ticker)
        except Exception:
            realtime = {"source": "none"}

        # Determine data source for candles
        source_map = {
            "questrade_l1": "questrade",
            "tradingview_fallback": "tradingview",
        }
        data_source = source_map.get(realtime.get("source", ""), "yfinance")

        # ── Event markers (earnings, dividends, splits) ──
        event_markers = []
        try:
            import yfinance as yf
            yf_ticker = yf.Ticker(ticker)
            # Earnings dates
            try:
                earnings = yf_ticker.earnings_dates
                if earnings is not None and len(earnings) > 0:
                    for dt in earnings.index:
                        ts_val = int(dt.timestamp())
                        # Only include dates within our bar range
                        if times[0] <= ts_val <= times[-1]:
                            event_markers.append({"time": ts_val, "type": "earnings", "label": "E"})
            except Exception:
                pass
            # Dividends
            try:
                divs = yf_ticker.dividends
                if divs is not None and len(divs) > 0:
                    for dt, amount in divs.items():
                        ts_val = int(dt.timestamp())
                        if times[0] <= ts_val <= times[-1]:
                            event_markers.append({"time": ts_val, "type": "dividend", "label": f"D ${amount:.2f}"})
            except Exception:
                pass
            # Splits
            try:
                splits = yf_ticker.splits
                if splits is not None and len(splits) > 0:
                    for dt, ratio in splits.items():
                        ts_val = int(dt.timestamp())
                        if times[0] <= ts_val <= times[-1]:
                            event_markers.append({"time": ts_val, "type": "split", "label": f"S {ratio:.0f}:1"})
            except Exception:
                pass
        except Exception:
            pass

        return {
            "ticker": ticker.upper(),
            "period": period,
            "interval": interval,
            "source": data_source,
            "candles": candles,
            "volume": volume_data,
            "indicators": indicators,
            "sub_panes": sub_panes,
            "support": support,
            "resistance": resistance,
            "patterns": patterns,
            "fibonacci": fibonacci,
            "realtime": realtime,
            "events": event_markers,
            "ai_analysis": ai_analysis,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Chart data failed: {e}")


# ──────────────────────────────────────────────
# Questrade Plus — Options P&L Calculator
# ──────────────────────────────────────────────


class PnLRequest(BaseModel):
    """Request body for options P&L calculation."""
    legs: list[dict]
    underlying_price: float
    strategy_name: str = "Custom Strategy"
    price_range_pct: float = 0.30


@market_router.post("/options/pnl", tags=["options"])
async def calculate_options_pnl(request: PnLRequest):
    """Calculate P&L curve for a multi-leg options strategy.

    Supports single legs, verticals, iron condors, straddles, strangles,
    butterflies, and any custom multi-leg combination.

    Each leg should have: option_type (call/put), strike, premium, quantity,
    and optionally: expiration, delta, gamma, theta, vega, iv.

    Returns:
        P&L curve, max profit/loss, breakevens, aggregate Greeks,
        risk/reward ratio, and probability of profit.
    """
    try:
        result = _engine.calculate_options_pnl(
            legs=request.legs,
            underlying_price=request.underlying_price,
            strategy_name=request.strategy_name,
            price_range_pct=request.price_range_pct,
        )
        return result
    except Exception as e:
        log.error("options_pnl_failed", error=str(e))
        raise HTTPException(status_code=500, detail=f"P&L calculation failed: {e}")


# ──────────────────────────────────────────────
# Questrade Plus — Portfolio Rebalancer
# ──────────────────────────────────────────────


class RebalanceRequest(BaseModel):
    """Request body for portfolio rebalancing."""
    target_allocations: list[dict] | None = None


@market_router.post("/portfolio/rebalance", tags=["account"])
async def rebalance_portfolio(request: RebalanceRequest):
    """Analyze portfolio and compute rebalancing trades.

    Without target_allocations: returns current portfolio analysis
    (holdings, sector breakdown, weights).

    With target_allocations: computes buy-only trades to reach target.
    Each allocation: { ticker, target_pct (0-100), sector (optional) }.

    Returns:
        Portfolio summary, holdings with weights, drift analysis,
        proposed trades, and sector allocation breakdown.
    """
    try:
        result = await _engine.rebalance_portfolio(
            target_allocations=request.target_allocations,
        )
        return result
    except Exception as e:
        log.error("rebalance_failed", error=str(e))
        raise HTTPException(status_code=500, detail=f"Rebalancing failed: {e}")


# ──────────────────────────────────────────────
# Questrade Plus — Market Heatmap
# ──────────────────────────────────────────────


@market_router.get("/heatmap", tags=["market-data"])
async def get_market_heatmap(
    tickers: Optional[str] = Query(
        None,
        description="Comma-separated tickers. Defaults to major S&P 500 constituents.",
    ),
):
    """Market heatmap data grouped by sector.

    Uses Questrade L1 quotes for real-time price change data.
    Enriches each stock with sector information for grouping.

    Returns:
        Sector-level metrics (avg change, volume, count) and
        stock-level data (price, change%, volume, halted status).
    """
    try:
        ticker_list = None
        if tickers:
            ticker_list = [t.strip().upper() for t in tickers.split(",") if t.strip()]

        result = await _engine.get_market_heatmap(tickers=ticker_list)
        return result
    except Exception as e:
        log.error("heatmap_failed", error=str(e))
        raise HTTPException(status_code=500, detail=f"Heatmap data failed: {e}")


# ──────────────────────────────────────────────
# Questrade Plus — Account Activities
# ──────────────────────────────────────────────


@market_router.get("/account/activities", tags=["account"])
async def get_account_activities(
    start_time: Optional[str] = Query(None, description="ISO datetime start"),
    end_time: Optional[str] = Query(None, description="ISO datetime end"),
):
    """Account transaction history — trades, dividends, deposits, fees.

    Defaults to the last 30 days if no date range specified.
    """
    try:
        return await _engine.get_account_activities(
            start_time=start_time,
            end_time=end_time,
        )
    except Exception as e:
        log.error("activities_failed", error=str(e))
        raise HTTPException(status_code=500, detail=f"Activities fetch failed: {e}")


@market_router.get("/account/executions", tags=["account"])
async def get_account_executions(
    start_time: Optional[str] = Query(None, description="ISO datetime start"),
    end_time: Optional[str] = Query(None, description="ISO datetime end"),
):
    """Trade execution (fill) history — price, quantity, commission per fill."""
    try:
        return await _engine.get_account_executions(
            start_time=start_time,
            end_time=end_time,
        )
    except Exception as e:
        log.error("executions_failed", error=str(e))
        raise HTTPException(status_code=500, detail=f"Executions fetch failed: {e}")


# ──────────────────────────────────────────────
# Questrade Plus — Order Notification Streaming
# ──────────────────────────────────────────────


@market_router.get("/account/notification-port", tags=["account"])
async def get_order_notification_port():
    """Get WebSocket port for real-time order status push notifications.

    After obtaining the port, connect via WebSocket to receive live
    order fills, status changes, and execution details.

    Returns:
        { streamPort: int } for WebSocket connection.
    """
    try:
        return await _engine.get_order_notification_port()
    except Exception as e:
        log.error("notification_port_failed", error=str(e))
        raise HTTPException(
            status_code=500,
            detail=f"Notification port request failed: {e}",
        )


# ──────────────────────────────────────────────
# Questrade Plus Phase 2 — Data Intelligence
# ──────────────────────────────────────────────


@market_router.get("/quote/enriched/{ticker}", tags=["market-data"])
async def get_enriched_quote(ticker: str):
    """Enhanced quote with L1 data + fundamentals + derived intelligence.

    Returns VWAP, averageTradeSize, tick direction, isHalted, PE, EPS,
    dividend/yield, 52-week range, market cap, sector/industry,
    plus computed metrics: 52wk_position_pct, volume_vs_avg, institutional_flag.
    """
    try:
        return await _engine.get_enriched_quote(ticker)
    except Exception as e:
        log.error("enriched_quote_failed", ticker=ticker, error=str(e))
        raise HTTPException(status_code=503, detail=f"Enriched quote unavailable: {e}")


@market_router.get("/account/dividends", tags=["account"])
async def get_dividend_calendar():
    """Upcoming dividend calendar for all portfolio holdings.

    Returns per-holding dividend info (exDate, payDate, yield, amount)
    plus projected annual and monthly income.
    """
    try:
        return await _engine.get_dividend_calendar()
    except Exception as e:
        log.error("dividend_calendar_failed", error=str(e))
        raise HTTPException(status_code=500, detail=f"Dividend calendar failed: {e}")


@market_router.get("/account/performance", tags=["account"])
async def get_portfolio_performance():
    """Comprehensive portfolio P&L: unrealized, realized, dividends, commissions.

    Combines positions (unrealized P&L) with activities (realized gains,
    dividends received, commissions paid, fees, deposits, withdrawals).
    """
    try:
        return await _engine.get_portfolio_performance()
    except Exception as e:
        log.error("performance_failed", error=str(e))
        raise HTTPException(status_code=500, detail=f"Performance data failed: {e}")


@market_router.get("/account/currency-exposure", tags=["account"])
async def get_currency_exposure():
    """Portfolio currency breakdown — CAD vs USD positions and cash.

    Groups holdings by currency with market value, allocation percentages,
    and per-currency cash/buying power from account balances.
    """
    try:
        return await _engine.get_currency_exposure()
    except Exception as e:
        log.error("currency_exposure_failed", error=str(e))
        raise HTTPException(status_code=500, detail=f"Currency exposure failed: {e}")


@market_router.get("/markets/status", tags=["market-data"])
async def get_market_status():
    """Exchange trading hours and current open/closed/pre/post status.

    Returns all Questrade-supported exchanges with their trading windows
    and computed status based on server time.
    """
    try:
        return await _engine.get_market_status()
    except Exception as e:
        log.error("market_status_failed", error=str(e))
        raise HTTPException(status_code=503, detail=f"Market status unavailable: {e}")


class OrderImpactRequest(BaseModel):
    """Request body for order impact preview."""
    ticker: str
    quantity: int
    action: str = "Buy"
    order_type: str = "Market"
    limit_price: float | None = None


@market_router.post("/order/impact", tags=["account"])
async def preview_order_impact(request: OrderImpactRequest):
    """Preview order impact before placing — estimated cost and commission.

    Simulates the order through Questrade without executing it.
    Returns estimated commissions, buying power effect, and
    maintenance excess.
    """
    try:
        return await _engine.get_order_impact_preview(
            ticker=request.ticker,
            quantity=request.quantity,
            action=request.action,
            order_type=request.order_type,
            limit_price=request.limit_price,
        )
    except Exception as e:
        log.error("order_impact_failed", error=str(e))
        raise HTTPException(status_code=500, detail=f"Order impact preview failed: {e}")


# ──────────────────────────────────────────────
# Phase 3: Growth Features
# ──────────────────────────────────────────────

@market_router.get("/analysis/volume-profile/{ticker}")
async def get_volume_profile_route(
    ticker: str,
    period: str = Query("6mo"),
    num_bins: int = Query(50),
):
    """Volume Profile — price-at-volume histogram with POC and Value Area."""
    try:
        from app.engines.ta_engine import TAEngine
        from app.engines.data_engine import DataEngine

        _data = DataEngine()
        _ta = TAEngine()
        data = _data.get_stock(ticker, period=period, interval="1d")
        return _ta.compute_volume_profile(data.history, num_bins=num_bins)
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Volume profile failed: {e}")


@market_router.get("/analysis/consolidation-zones/{ticker}")
async def get_consolidation_zones_route(
    ticker: str,
    period: str = Query("6mo"),
    atr_multiplier: float = Query(0.5),
    min_bars: int = Query(8),
):
    """Consolidation zones — tight price ranges that precede breakouts."""
    try:
        from app.engines.ta_engine import TAEngine
        from app.engines.data_engine import DataEngine

        _data = DataEngine()
        _ta = TAEngine()
        data = _data.get_stock(ticker, period=period, interval="1d")
        return _ta.detect_consolidation_zones(data.history, atr_multiplier=atr_multiplier, min_bars=min_bars)
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Consolidation zones failed: {e}")


@market_router.get("/analysis/liquidity-zones/{ticker}")
async def get_liquidity_zones_route(
    ticker: str,
    period: str = Query("6mo"),
):
    """Liquidity zones — high-volume price nodes acting as support/resistance."""
    try:
        from app.engines.ta_engine import TAEngine
        from app.engines.data_engine import DataEngine

        _data = DataEngine()
        _ta = TAEngine()
        data = _data.get_stock(ticker, period=period, interval="1d")
        return _ta.detect_liquidity_zones(data.history)
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Liquidity zones failed: {e}")


@market_router.get("/analysis/google-trends/{keyword}")
async def get_google_trends_route(
    keyword: str,
    timeframe: str = Query("today 3-m"),
):
    """Google Trends search interest for a stock or keyword."""
    try:
        from app.engines.trends_engine import TrendsEngine
        trends = TrendsEngine()
        if not trends.is_available:
            return {"error": "pytrends not installed"}
        return trends.get_search_interest(keyword, timeframe=timeframe)
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Google Trends failed: {e}")


@market_router.get("/analysis/stocktwits/{ticker}")
async def get_stocktwits_route(ticker: str):
    """StockTwits social sentiment for a ticker."""
    try:
        from app.engines.data_engine import DataEngine
        _data = DataEngine()
        return _data.get_stocktwits_sentiment(ticker)
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"StockTwits failed: {e}")


@market_router.get("/accuracy/dashboard")
async def get_accuracy_dashboard_route(
    days: int = Query(90),
):
    """Pattern prediction accuracy dashboard."""
    try:
        from app.engines.accuracy_engine import AccuracyEngine
        from app.config import get_settings
        settings = get_settings()
        engine = AccuracyEngine(redis_url=settings.redis_url)
        return engine.get_accuracy_summary(days=days)
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Accuracy dashboard failed: {e}")


@market_router.get("/accuracy/pattern/{name}")
async def get_pattern_accuracy_route(
    name: str,
    days: int = Query(90),
):
    """Accuracy stats for a specific pattern type."""
    try:
        from app.engines.accuracy_engine import AccuracyEngine
        from app.config import get_settings
        settings = get_settings()
        engine = AccuracyEngine(redis_url=settings.redis_url)
        return engine.get_pattern_accuracy(pattern_name=name, days=days)
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Pattern accuracy failed: {e}")


@market_router.get("/alerts/history")
async def get_alert_history_route(limit: int = Query(50)):
    """Recent alert dispatch history."""
    try:
        from app.engines.alert_engine import AlertEngine
        from app.config import get_settings
        settings = get_settings()
        engine = AlertEngine(redis_url=settings.redis_url)
        return {"alerts": engine.get_alert_history(limit=limit)}
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Alert history failed: {e}")


@market_router.get("/alerts/chains")
async def get_active_chains_route():
    """Get all active alert chains."""
    try:
        from app.engines.alert_chain_engine import AlertChainEngine
        from app.config import get_settings
        settings = get_settings()
        engine = AlertChainEngine(redis_url=settings.redis_url)
        return {"chains": engine.get_active_chains()}
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Alert chains failed: {e}")


@market_router.get("/alerts/chains/{ticker}")
async def get_ticker_chains_route(ticker: str):
    """Get alert chains for a specific ticker."""
    try:
        from app.engines.alert_chain_engine import AlertChainEngine
        from app.config import get_settings
        settings = get_settings()
        engine = AlertChainEngine(redis_url=settings.redis_url)
        return {"chains": engine.get_chains_for_ticker(ticker)}
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Ticker chains failed: {e}")


@market_router.get("/backtest/walk-forward/{ticker}")
async def walk_forward_backtest_route(
    ticker: str,
    strategy: str = Query("sma_crossover"),
    in_sample_pct: float = Query(0.7),
    period: str = Query("5y"),
):
    """Walk-forward backtest to detect overfitting."""
    try:
        from app.engines.backtest_engine import BacktestEngine
        engine = BacktestEngine()
        return engine.run_walk_forward(
            ticker, strategy=strategy, in_sample_pct=in_sample_pct, period=period,
        )
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Walk-forward failed: {e}")


@market_router.get("/backtest/monte-carlo/{ticker}")
async def monte_carlo_backtest_route(
    ticker: str,
    strategy: str = Query("sma_crossover"),
    n_simulations: int = Query(1000),
    period: str = Query("2y"),
):
    """Monte Carlo simulation — shuffle trade order to estimate risk."""
    try:
        from app.engines.backtest_engine import BacktestEngine
        engine = BacktestEngine()
        return engine.run_monte_carlo(
            ticker, strategy=strategy, n_simulations=n_simulations, period=period,
        )
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Monte Carlo failed: {e}")


# ──────────────────────────────────────────────
# Phase 4: Coaching, Opening Range, Ghost Charts,
#           Model Optimizer, Gamification
# ──────────────────────────────────────────────

@market_router.post("/coaching/insights")
async def coaching_insights_route(trades: list[dict]):
    """Get AI-powered trading coaching from trade history."""
    try:
        from app.engines.coaching_engine import CoachingEngine
        engine = CoachingEngine()
        return engine.get_coaching_insights(trades)
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Coaching failed: {e}")


@market_router.post("/coaching/improvement-plan")
async def improvement_plan_route(trades: list[dict], weeks: int = Query(4)):
    """Week-over-week improvement plan."""
    try:
        from app.engines.coaching_engine import CoachingEngine
        engine = CoachingEngine()
        return engine.get_improvement_plan(trades, weeks=weeks)
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Improvement plan failed: {e}")


@market_router.post("/coaching/psychology")
async def psychology_report_route(trades: list[dict]):
    """Full trading psychology report."""
    try:
        from app.engines.coaching_engine import CoachingEngine
        engine = CoachingEngine()
        return engine.get_psychology_report(trades)
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Psychology report failed: {e}")


@market_router.get("/opening-range/{ticker}")
async def capture_opening_range_route(
    ticker: str,
    minutes: int = Query(30),
):
    """Capture the opening range for a ticker."""
    try:
        from app.engines.data_engine import DataEngine
        from app.engines.opening_range_engine import OpeningRangeEngine
        data_engine = DataEngine()
        or_engine = OpeningRangeEngine()
        data = data_engine.get_stock(ticker, period="1d", interval="5m")
        return or_engine.capture_opening_range(ticker, data.history, minutes=minutes)
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Opening range failed: {e}")


@market_router.get("/opening-range/{ticker}/breakout")
async def check_or_breakout_route(
    ticker: str,
    minutes: int = Query(30),
):
    """Check if ticker has broken its opening range."""
    try:
        from app.engines.data_engine import DataEngine
        from app.engines.opening_range_engine import OpeningRangeEngine
        data_engine = DataEngine()
        or_engine = OpeningRangeEngine()
        data = data_engine.get_stock(ticker, period="1d", interval="1m")
        current_price = data.history[-1]["close"] if data.history else 0
        return or_engine.check_breakout(ticker, current_price, minutes=minutes)
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"OR breakout check failed: {e}")


@market_router.get("/ghost-charts/{ticker}")
async def find_ghost_patterns_route(
    ticker: str,
    period: str = Query("3mo"),
    top_k: int = Query(5),
):
    """Find historically similar patterns for ghost chart overlay."""
    try:
        from app.engines.data_engine import DataEngine
        from app.engines.ghost_chart_engine import GhostChartEngine
        data_engine = DataEngine()
        ghost_engine = GhostChartEngine()
        data = data_engine.get_stock(ticker, period=period, interval="1d")
        return ghost_engine.find_similar_patterns(data.history, top_k=top_k)
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Ghost chart search failed: {e}")


@market_router.get("/ghost-charts/overlay/{pattern_id}")
async def ghost_overlay_route(
    pattern_id: str,
    ticker: str = Query(...),
):
    """Get scaled historical price path for chart overlay."""
    try:
        from app.engines.data_engine import DataEngine
        from app.engines.ghost_chart_engine import GhostChartEngine
        data_engine = DataEngine()
        ghost_engine = GhostChartEngine()
        data = data_engine.get_stock(ticker, period="1d", interval="1m")
        current_price = data.history[-1]["close"] if data.history else 0
        return ghost_engine.get_ghost_overlay(pattern_id, current_price)
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Ghost overlay failed: {e}")


@market_router.get("/optimizer/report")
async def optimization_report_route():
    """Get model optimizer report with threshold recommendations."""
    try:
        from app.engines.optimizer_engine import OptimizerEngine
        engine = OptimizerEngine()
        return engine.get_optimization_report()
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Optimization report failed: {e}")


@market_router.get("/gamification/streaks")
async def streak_data_route():
    """Get current and best win/loss streaks."""
    try:
        from app.engines.accuracy_engine import AccuracyEngine
        from app.config import get_settings
        settings = get_settings()
        engine = AccuracyEngine(redis_url=settings.redis_url)
        return engine.get_streak_data()
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Streak data failed: {e}")


@market_router.get("/gamification/leaderboard")
async def leaderboard_stats_route():
    """Get gamification leaderboard stats: badges, trends, R:R."""
    try:
        from app.engines.accuracy_engine import AccuracyEngine
        from app.config import get_settings
        settings = get_settings()
        engine = AccuracyEngine(redis_url=settings.redis_url)
        return engine.get_leaderboard_stats()
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Leaderboard failed: {e}")


# ════════════════════════════════════════════════════════
# Tier 2 — Advanced Analytics
# AVWAP · Volume Profile · Consolidation · Liquidity · Market Structure
# Correlation Matrix · Multi-Target TP
# ════════════════════════════════════════════════════════

from app.engines.ta_engine import TAEngine

_ta_engine = TAEngine()


@market_router.get("/analysis/avwap/{ticker}")
async def get_anchored_vwap(
    ticker: str,
    anchor_index: int = Query(0, description="Bar index to anchor VWAP from"),
    period: str = Query("6mo", description="Data period"),
):
    """Compute Anchored VWAP with ±1σ / ±2σ bands."""
    try:
        bars = await _engine.get_ohlcv(ticker, period=period)
        result = _ta_engine.compute_anchored_vwap(bars, anchor_index=anchor_index)
        return _sanitize_floats(result)
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"AVWAP failed: {e}")


@market_router.get("/analysis/volume-profile/{ticker}")
async def get_volume_profile(
    ticker: str,
    num_bins: int = Query(50, ge=10, le=200),
    period: str = Query("6mo"),
):
    """Compute Volume Profile with POC, Value Area, and high-volume nodes."""
    try:
        bars = await _engine.get_ohlcv(ticker, period=period)
        result = _ta_engine.compute_volume_profile(bars, num_bins=num_bins)
        return _sanitize_floats(result)
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Volume profile failed: {e}")


@market_router.get("/analysis/consolidation/{ticker}")
async def get_consolidation_zones(
    ticker: str,
    atr_multiplier: float = Query(0.5, ge=0.1, le=2.0),
    min_bars: int = Query(8, ge=3, le=50),
    period: str = Query("6mo"),
):
    """Detect consolidation zones (tight price ranges)."""
    try:
        bars = await _engine.get_ohlcv(ticker, period=period)
        result = _ta_engine.detect_consolidation_zones(
            bars, atr_multiplier=atr_multiplier, min_bars=min_bars
        )
        return _sanitize_floats(result)
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Consolidation zones failed: {e}")


@market_router.get("/analysis/liquidity/{ticker}")
async def get_liquidity_zones(
    ticker: str,
    num_bins: int = Query(30, ge=10, le=100),
    threshold_pct: float = Query(80, ge=50, le=99),
    period: str = Query("6mo"),
):
    """Detect liquidity zones — high-volume price nodes acting as S/R."""
    try:
        bars = await _engine.get_ohlcv(ticker, period=period)
        result = _ta_engine.detect_liquidity_zones(
            bars, num_bins=num_bins, threshold_pct=threshold_pct
        )
        return _sanitize_floats(result)
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Liquidity zones failed: {e}")


@market_router.get("/analysis/market-structure/{ticker}")
async def get_market_structure(
    ticker: str,
    period: str = Query("6mo"),
):
    """Detect market structure: trend direction, swing highs/lows, BOS/CHoCH."""
    try:
        bars = await _engine.get_ohlcv(ticker, period=period)
        result = _pattern_engine.detect_market_structure(bars)
        return _sanitize_floats(result)
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Market structure failed: {e}")


class CorrelationRequest(BaseModel):
    tickers: list[str]
    period: str = "6mo"


@market_router.post("/analysis/correlation")
async def compute_correlation_matrix(req: CorrelationRequest):
    """Compute pairwise Pearson correlation matrix across tickers."""
    try:
        import numpy as np

        if len(req.tickers) < 2:
            raise HTTPException(status_code=400, detail="Need at least 2 tickers")
        if len(req.tickers) > 20:
            raise HTTPException(status_code=400, detail="Max 20 tickers")

        # Fetch close prices for each ticker
        close_arrays: dict[str, list[float]] = {}
        for t in req.tickers:
            bars = await _engine.get_ohlcv(t, period=req.period)
            close_arrays[t] = [b.close for b in bars if b.close is not None]

        # Align lengths to minimum
        min_len = min(len(v) for v in close_arrays.values())
        if min_len < 20:
            raise HTTPException(status_code=400, detail="Not enough data for correlation")

        matrix_data = np.array([close_arrays[t][-min_len:] for t in req.tickers])
        corr = np.corrcoef(matrix_data)

        tickers = req.tickers
        result = {
            "tickers": tickers,
            "matrix": {
                tickers[i]: {
                    tickers[j]: round(float(corr[i][j]), 4)
                    for j in range(len(tickers))
                }
                for i in range(len(tickers))
            },
            "pairs": [],
        }
        # Top correlated/anti-correlated pairs
        for i in range(len(tickers)):
            for j in range(i + 1, len(tickers)):
                result["pairs"].append({
                    "pair": f"{tickers[i]}/{tickers[j]}",
                    "correlation": round(float(corr[i][j]), 4),
                })
        result["pairs"].sort(key=lambda x: abs(x["correlation"]), reverse=True)
        return _sanitize_floats(result)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Correlation failed: {e}")


@market_router.get("/analysis/multi-target/{ticker}")
async def get_multi_target_tp(
    ticker: str,
    direction: str = Query("bullish", regex="^(bullish|bearish)$"),
    period: str = Query("6mo"),
):
    """Compute multi-target take-profit levels (TP1/TP2/TP3) with Fibonacci extensions."""
    try:
        bars = await _engine.get_ohlcv(ticker, period=period)
        if not bars or len(bars) < 20:
            raise HTTPException(status_code=400, detail="Not enough data")

        closes = [b.close for b in bars if b.close]
        highs = [b.high for b in bars if b.high]
        lows = [b.low for b in bars if b.low]
        current = closes[-1]

        recent_high = max(highs[-50:]) if len(highs) >= 50 else max(highs)
        recent_low = min(lows[-50:]) if len(lows) >= 50 else min(lows)
        swing_range = recent_high - recent_low

        # Fibonacci extension levels
        fib_levels = [0.618, 1.0, 1.618, 2.618]

        if direction == "bullish":
            targets = [
                {"level": "TP1", "price": round(current + swing_range * fib_levels[0], 2),
                 "fib": f"{fib_levels[0]:.3f}", "probability": 75},
                {"level": "TP2", "price": round(current + swing_range * fib_levels[1], 2),
                 "fib": f"{fib_levels[1]:.3f}", "probability": 55},
                {"level": "TP3", "price": round(current + swing_range * fib_levels[2], 2),
                 "fib": f"{fib_levels[2]:.3f}", "probability": 30},
            ]
            stop = round(current - swing_range * 0.382, 2)
        else:
            targets = [
                {"level": "TP1", "price": round(current - swing_range * fib_levels[0], 2),
                 "fib": f"{fib_levels[0]:.3f}", "probability": 75},
                {"level": "TP2", "price": round(current - swing_range * fib_levels[1], 2),
                 "fib": f"{fib_levels[1]:.3f}", "probability": 55},
                {"level": "TP3", "price": round(current - swing_range * fib_levels[2], 2),
                 "fib": f"{fib_levels[2]:.3f}", "probability": 30},
            ]
            stop = round(current + swing_range * 0.382, 2)

        # R:R ratios
        for t in targets:
            risk = abs(current - stop)
            reward = abs(t["price"] - current)
            t["rr_ratio"] = round(reward / risk, 2) if risk > 0 else 0

        return {
            "ticker": ticker,
            "current_price": current,
            "direction": direction,
            "swing_range": round(swing_range, 2),
            "targets": targets,
            "stop_loss": stop,
            "recent_high": round(recent_high, 2),
            "recent_low": round(recent_low, 2),
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Multi-target TP failed: {e}")


# ──────────────────────────────────────────────
# Accuracy Dashboard
# ──────────────────────────────────────────────

@market_router.get("/accuracy/dashboard")
async def get_accuracy_dashboard(days: int = Query(90, ge=1, le=365)):
    """Full accuracy dashboard with pattern breakdown and calibration."""
    try:
        from app.engines.accuracy_engine import AccuracyEngine
        engine = AccuracyEngine()
        return _sanitize_floats(engine.get_accuracy_summary(days=days))
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Accuracy dashboard failed: {e}")


@market_router.get("/accuracy/pattern/{name}")
async def get_pattern_accuracy(name: str, days: int = Query(90, ge=1, le=365)):
    """Accuracy stats for a specific pattern."""
    try:
        from app.engines.accuracy_engine import AccuracyEngine
        engine = AccuracyEngine()
        return _sanitize_floats(engine.get_pattern_accuracy(pattern_name=name, days=days))
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Pattern accuracy failed: {e}")


@market_router.get("/accuracy/calibration")
async def get_confidence_calibration(days: int = Query(90, ge=1, le=365)):
    """Confidence calibration — predicted vs actual success rate."""
    try:
        from app.engines.accuracy_engine import AccuracyEngine
        engine = AccuracyEngine()
        return _sanitize_floats(engine.get_confidence_calibration(days=days))
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Calibration failed: {e}")


# ──────────────────────────────────────────────
# Backtesting — Walk-Forward & Monte Carlo
# ──────────────────────────────────────────────

@market_router.get("/backtest/walk-forward/{ticker}")
async def run_walk_forward(
    ticker: str,
    strategy: str = Query("sma_crossover"),
    in_sample_pct: float = Query(0.7, ge=0.5, le=0.9),
    period: str = Query("5y"),
):
    """Walk-forward backtest with in-sample/out-of-sample validation."""
    try:
        from app.engines.backtest_engine import BacktestEngine
        engine = BacktestEngine()
        if not engine.is_available():
            raise HTTPException(status_code=503, detail="VectorBT not installed — run: pip install .[backtest]")
        result = engine.run_walk_forward(
            ticker=ticker, strategy=strategy,
            in_sample_pct=in_sample_pct, period=period,
        )
        return _sanitize_floats(result)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Walk-forward failed: {e}")


@market_router.get("/backtest/monte-carlo/{ticker}")
async def run_monte_carlo(
    ticker: str,
    strategy: str = Query("sma_crossover"),
    n_simulations: int = Query(1000, ge=100, le=10000),
    period: str = Query("2y"),
):
    """Monte Carlo simulation — trade shuffle for drawdown confidence."""
    try:
        from app.engines.backtest_engine import BacktestEngine
        engine = BacktestEngine()
        if not engine.is_available():
            raise HTTPException(status_code=503, detail="VectorBT not installed — run: pip install .[backtest]")
        result = engine.run_monte_carlo(
            ticker=ticker, strategy=strategy,
            n_simulations=n_simulations, period=period,
        )
        return _sanitize_floats(result)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Monte Carlo failed: {e}")


# ──────────────────────────────────────────────
# Alert Chains
# ──────────────────────────────────────────────

@market_router.get("/alerts/history")
async def get_alert_history(limit: int = Query(50, ge=1, le=200)):
    """Recent alert history across all chains."""
    try:
        from app.engines.alert_chain_engine import AlertChainEngine
        engine = AlertChainEngine()
        chains = engine.get_active_chains()
        # Flatten triggered alerts from chains into a feed
        history: list[dict] = []
        for chain in chains:
            for alert in chain.get("alerts", []):
                if alert.get("triggered"):
                    history.append({**alert, "chain_id": chain.get("id"), "ticker": chain.get("ticker")})
        history.sort(key=lambda x: x.get("triggered_at", ""), reverse=True)
        return history[:limit]
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Alert history failed: {e}")


@market_router.get("/alerts/chains")
async def get_active_chains():
    """All active alert chains."""
    try:
        from app.engines.alert_chain_engine import AlertChainEngine
        engine = AlertChainEngine()
        return engine.get_active_chains()
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Active chains failed: {e}")


@market_router.get("/alerts/chains/{ticker}")
async def get_ticker_chains(ticker: str):
    """Alert chains for a specific ticker."""
    try:
        from app.engines.alert_chain_engine import AlertChainEngine
        engine = AlertChainEngine()
        return engine.get_chains_for_ticker(ticker)
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Ticker chains failed: {e}")


# ──────────────────────────────────────────────
# Correlation Matrix
# ──────────────────────────────────────────────

@market_router.post("/analysis/correlation")
async def get_correlation_matrix(body: dict):
    """Cross-ticker correlation matrix using numpy."""
    try:
        import numpy as np

        tickers = body.get("tickers", [])
        period = body.get("period", "6mo")

        if len(tickers) < 2:
            raise HTTPException(status_code=400, detail="Need at least 2 tickers")

        # Fetch close prices for each ticker
        close_arrays = []
        valid_tickers = []
        for t in tickers[:10]:  # Cap at 10 tickers
            try:
                data = _engine.get_stock(t, period=period, interval="1d")
                close = data.history["Close"].dropna().values
                close_arrays.append(close)
                valid_tickers.append(t)
            except Exception:
                continue

        if len(valid_tickers) < 2:
            raise HTTPException(status_code=400, detail="Need at least 2 valid tickers with data")

        # Align to shortest length
        min_len = min(len(c) for c in close_arrays)
        aligned = [c[-min_len:] for c in close_arrays]

        # Compute correlation matrix
        matrix = np.corrcoef(aligned)

        # Build response
        pairs = []
        for i in range(len(valid_tickers)):
            for j in range(i + 1, len(valid_tickers)):
                val = float(matrix[i][j])
                pairs.append({
                    "ticker_a": valid_tickers[i],
                    "ticker_b": valid_tickers[j],
                    "correlation": round(val, 4),
                    "strength": "strong" if abs(val) > 0.7 else "moderate" if abs(val) > 0.4 else "weak",
                })

        return _sanitize_floats({
            "tickers": valid_tickers,
            "matrix": [[round(float(v), 4) for v in row] for row in matrix],
            "pairs": sorted(pairs, key=lambda p: abs(p["correlation"]), reverse=True),
            "data_points": min_len,
        })
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Correlation failed: {e}")


# ──────────────────────────────────────────────
# Social Volume Spikes
# ──────────────────────────────────────────────

@market_router.get("/analysis/social-volume/{ticker}")
async def get_social_volume(ticker: str):
    """Social volume spike detection using Finnhub social sentiment data."""
    try:
        from app.data.finnhub_client import FinnhubClient
        import numpy as np

        fh = FinnhubClient()
        data = await fh.get_sentiment(ticker)

        reddit = data.get("reddit", [])
        twitter = data.get("twitter", [])

        def compute_spike(entries: list[dict], source_name: str) -> dict:
            if not entries or len(entries) < 3:
                return {"source": source_name, "data_points": 0, "spike": False}

            mentions = [e.get("mention", 0) for e in entries]
            scores = [e.get("positiveMention", 0) - e.get("negativeMention", 0) for e in entries]

            mean = float(np.mean(mentions))
            std = float(np.std(mentions)) if len(mentions) > 1 else 0
            latest = mentions[-1] if mentions else 0
            z_score = (latest - mean) / std if std > 0 else 0

            return {
                "source": source_name,
                "data_points": len(entries),
                "latest_mentions": latest,
                "mean_mentions": round(mean, 1),
                "std_dev": round(std, 1),
                "z_score": round(z_score, 2),
                "spike": z_score > 2.0,
                "spike_severity": "extreme" if z_score > 3 else "high" if z_score > 2 else "normal",
                "latest_score": scores[-1] if scores else 0,
                "sentiment_trend": "positive" if sum(scores[-3:]) > 0 else "negative" if sum(scores[-3:]) < 0 else "neutral",
            }

        reddit_spike = compute_spike(reddit, "Reddit")
        twitter_spike = compute_spike(twitter, "Twitter")
        any_spike = reddit_spike.get("spike", False) or twitter_spike.get("spike", False)

        return {
            "ticker": ticker.upper(),
            "spike_detected": any_spike,
            "reddit": reddit_spike,
            "twitter": twitter_spike,
        }
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Social volume failed: {e}")


# ──────────────────────────────────────────────────────────────
# 58. Pattern Outcome Accuracy (QuestDB)
# ──────────────────────────────────────────────────────────────

@market_router.get("/analysis/pattern-accuracy")
async def pattern_accuracy(
    pattern: str = Query(None, description="Filter by pattern name"),
    ticker: str = Query(None, description="Filter by ticker"),
):
    """Query pattern outcome accuracy from QuestDB.

    Returns aggregate win/loss rates across all tracked patterns,
    with per-pattern breakdowns.
    """
    try:
        from app.engines.outcome_tracker import get_outcome_tracker
        tracker = get_outcome_tracker()
        return tracker.query_accuracy(pattern_name=pattern, ticker=ticker)
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Accuracy query failed: {e}")


@market_router.get("/analysis/pattern-outcomes/recent")
async def recent_pattern_outcomes(limit: int = Query(50, ge=1, le=200)):
    """Get the most recent pattern outcome evaluations."""
    try:
        from app.engines.outcome_tracker import get_outcome_tracker
        tracker = get_outcome_tracker()
        return {"outcomes": tracker.query_recent(limit=limit)}
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Recent outcomes failed: {e}")


# ──────────────────────────────────────────────────────────────
# 59. Position Risk Overlay
# ──────────────────────────────────────────────────────────────

@market_router.post("/account/positions/risk")
async def position_risk_overlay(positions: list[dict] = None, account_size: float = Query(100000)):
    """Overlay risk_engine calculations on current positions.

    Accepts a list of positions and computes:
    - Per-position risk ($ at risk, % of account)
    - Portfolio heat (total open risk)
    - Trailing stops based on current ATR
    - Trade quality scores

    Each position dict should have: ticker, shares, entry_price, stop_price.
    """
    if not positions:
        return {"error": "No positions provided", "positions": []}

    try:
        from app.engines.risk_engine import RiskEngine
        from app.engines.ta_engine import TAEngine

        risk = RiskEngine()
        ta = TAEngine()
        enriched = []

        for pos in positions:
            ticker = pos.get("ticker", "")
            entry = pos.get("entry_price", 0)
            stop = pos.get("stop_price", 0)
            shares = pos.get("shares", 0)

            # Get current ATR for trailing stop
            atr = 0.0
            current_price = entry
            try:
                data = _engine.get_stock(ticker, period="1mo", interval="1d")
                if data and data.history:
                    indicators = ta.compute_indicators(data.history, timeframe="1d", ticker=ticker)
                    ind = indicators.model_dump(mode="json")
                    atr = ind.get("atr") or 0.0
                    current_price = data.history[-1].get("close", entry)
            except Exception:
                pass

            # Position sizing validation
            position_result = risk.compute_position_size(
                account_size=account_size,
                entry_price=entry,
                stop_price=stop if stop else entry * 0.95,
                target_price=pos.get("target_price"),
                risk_pct=0.01,
            )

            # Trailing stop
            trailing = risk.trailing_stop(
                entry_price=entry,
                current_price=current_price,
                atr=atr if atr > 0 else current_price * 0.02,
            ) if current_price > 0 else {}

            # Dollar risk
            risk_per_share = abs(entry - stop) if stop else entry * 0.05
            dollar_risk = risk_per_share * shares
            pct_of_account = round(dollar_risk / max(account_size, 1) * 100, 2)

            # Unrealized P&L
            unrealized_pnl = round((current_price - entry) * shares, 2)
            unrealized_pct = round((current_price - entry) / max(entry, 0.01) * 100, 2)

            enriched.append({
                "ticker": ticker.upper(),
                "shares": shares,
                "entry_price": entry,
                "stop_price": stop,
                "current_price": round(current_price, 2),
                "atr": round(atr, 2),
                "trailing_stop": trailing,
                "dollar_risk": round(dollar_risk, 2),
                "pct_of_account": pct_of_account,
                "unrealized_pnl": unrealized_pnl,
                "unrealized_pct": unrealized_pct,
                "position_sizing": position_result.model_dump(mode="json") if hasattr(position_result, "model_dump") else position_result,
            })

        # Portfolio heat
        portfolio_heat = risk.portfolio_heat(positions, account_size)

        return {
            "account_size": account_size,
            "positions": enriched,
            "portfolio_heat": portfolio_heat,
            "total_positions": len(enriched),
        }
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Position risk failed: {e}")


# ──────────────────────────────────────────────────────────────
# 60. Exit Analysis
# ──────────────────────────────────────────────────────────────

@market_router.get("/analysis/exit-analysis/{ticker}")
async def exit_analysis(ticker: str, period: str = Query("1mo")):
    """Analyze open positions for exit signals.

    Checks current price against pattern targets and stop levels,
    and generates an AI narrative exit summary.
    """
    try:
        import json as _json

        r = None
        try:
            import redis as _redis
            from app.config import get_settings
            r = _redis.from_url(get_settings().redis_url, decode_responses=True)
        except Exception:
            pass

        # Fetch current price data
        data = _engine.get_stock(ticker, period=period, interval="1d")
        if not data or not data.history:
            raise HTTPException(status_code=404, detail=f"No data for {ticker}")

        current_price = data.history[-1].get("close", 0)

        # Get active pattern log for this ticker
        active_patterns = []
        if r:
            log_key = f"Bubby Vision:pattern_log:{ticker.upper()}"
            log_raw = r.get(log_key)
            if log_raw:
                try:
                    active_patterns = _json.loads(log_raw)
                except _json.JSONDecodeError:
                    pass

        # Evaluate each active pattern against current price
        exit_signals = []
        for p in active_patterns:
            target = p.get("target", 0)
            stop = p.get("stop_loss", 0)
            entry = p.get("entry_price", current_price)
            direction = p.get("direction", "bullish")

            signal = {
                "pattern": p.get("name"),
                "direction": direction,
                "detected_at": p.get("detected_at"),
                "entry_price": entry,
                "target": target,
                "stop_loss": stop,
                "current_price": round(current_price, 2),
            }

            if direction == "bullish":
                if target and current_price >= target:
                    signal["verdict"] = "TARGET_HIT"
                    signal["pnl_pct"] = round((current_price - entry) / max(entry, 0.01) * 100, 2)
                elif stop and current_price <= stop:
                    signal["verdict"] = "STOP_TRIGGERED"
                    signal["pnl_pct"] = round((current_price - entry) / max(entry, 0.01) * 100, 2)
                else:
                    signal["verdict"] = "HOLD"
                    signal["distance_to_target_pct"] = round((target - current_price) / max(current_price, 0.01) * 100, 2) if target else None
                    signal["distance_to_stop_pct"] = round((current_price - stop) / max(current_price, 0.01) * 100, 2) if stop else None
            else:  # bearish
                if target and current_price <= target:
                    signal["verdict"] = "TARGET_HIT"
                    signal["pnl_pct"] = round((entry - current_price) / max(entry, 0.01) * 100, 2)
                elif stop and current_price >= stop:
                    signal["verdict"] = "STOP_TRIGGERED"
                    signal["pnl_pct"] = round((entry - current_price) / max(entry, 0.01) * 100, 2)
                else:
                    signal["verdict"] = "HOLD"
                    signal["distance_to_target_pct"] = round((current_price - target) / max(current_price, 0.01) * 100, 2) if target else None
                    signal["distance_to_stop_pct"] = round((stop - current_price) / max(current_price, 0.01) * 100, 2) if stop else None

            exit_signals.append(signal)

        # Generate AI narrative if there are actionable signals
        narrative = None
        actionable = [s for s in exit_signals if s.get("verdict") != "HOLD"]
        if actionable:
            try:
                from langchain_google_genai import ChatGoogleGenerativeAI
                from langchain_core.messages import HumanMessage, SystemMessage
                from app.config import get_settings

                settings = get_settings()
                llm = ChatGoogleGenerativeAI(
                    model="gemini-3.0-flash",
                    google_api_key=settings.google_api_key,
                    temperature=0.3,
                    max_output_tokens=512,
                )
                prompt = f"""Generate a brief exit analysis for {ticker} at ${current_price:.2f}.
Actionable signals: {_json.dumps(actionable, default=str)}
Keep it concise (2-3 sentences). Focus on the action and reasoning."""

                response = llm.invoke([
                    SystemMessage(content="You are an expert position management advisor."),
                    HumanMessage(content=prompt),
                ])
                narrative = response.content
            except Exception:
                narrative = None

        return {
            "ticker": ticker.upper(),
            "current_price": round(current_price, 2),
            "active_patterns": len(active_patterns),
            "exit_signals": exit_signals,
            "actionable_count": len(actionable),
            "narrative": narrative,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Exit analysis failed: {e}")


# ──────────────────────────────────────────────
# Phase 9: OpenBB Enhanced Data
# ──────────────────────────────────────────────


@market_router.get("/institutional/{ticker}", tags=["openbb"])
async def get_institutional_ownership(
    ticker: str,
    limit: int = Query(20, ge=1, le=100, description="Max holders to return"),
):
    """Institutional ownership (13F holders) from SEC filings via OpenBB."""
    data = _openbb.get_institutional_ownership(ticker, limit=limit)
    if data is None:
        raise HTTPException(
            status_code=503,
            detail="OpenBB SDK not available or institutional data unavailable",
        )
    return _sanitize_floats(data)


@market_router.get("/economic-calendar", tags=["openbb"])
async def get_economic_calendar(
    days_ahead: int = Query(7, ge=1, le=30, description="Days to look ahead"),
):
    """Upcoming US economic events (GDP, CPI, FOMC, NFP) via OpenBB."""
    data = _openbb.get_economic_calendar(days_ahead=days_ahead)
    if data is None:
        raise HTTPException(
            status_code=503,
            detail="OpenBB SDK not available or calendar data unavailable",
        )
    return _sanitize_floats(data)


@market_router.get("/dividends/{ticker}", tags=["openbb"])
async def get_dividend_history(
    ticker: str,
    limit: int = Query(20, ge=1, le=100, description="Max dividend records"),
):
    """Historical dividend payments for a ticker via OpenBB."""
    data = _openbb.get_dividend_history(ticker, limit=limit)
    if data is None:
        raise HTTPException(
            status_code=503,
            detail="OpenBB SDK not available or dividend data unavailable",
        )
    return _sanitize_floats(data)


@market_router.get("/etf-holdings/{ticker}", tags=["openbb"])
async def get_etf_holdings(
    ticker: str,
    limit: int = Query(25, ge=1, le=100, description="Max holdings to return"),
):
    """Top holdings of an ETF by weight via OpenBB."""
    data = _openbb.get_etf_holdings(ticker, limit=limit)
    if data is None:
        raise HTTPException(
            status_code=503,
            detail="OpenBB SDK not available or ETF data unavailable",
        )
    return _sanitize_floats(data)


@market_router.get("/analyst-estimates/{ticker}", tags=["openbb"])
async def get_analyst_estimates(ticker: str):
    """Forward revenue and EPS consensus estimates via OpenBB."""
    data = _openbb.get_analyst_estimates(ticker)
    if data is None:
        raise HTTPException(
            status_code=503,
            detail="OpenBB SDK not available or estimate data unavailable",
        )
    return _sanitize_floats(data)


@market_router.get("/openbb-health", tags=["openbb"])
async def get_openbb_health():
    """OpenBB SDK status and availability check."""
    return _openbb.get_status()
