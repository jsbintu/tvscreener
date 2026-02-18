"""
Bubby Vision — TradingView Data Client

PRIMARY data source for the platform (with paid TradingView subscription).

Three packages:
  - tradingview-screener  →  Stock scanner with 3000+ fields (real-time with subscription)
  - tradingview-ta        →  26-indicator TA summaries
  - tvDatafeed            →  Historical OHLCV bars (up to 5000 bars per request)

With a paid TradingView plan:
  - Screener returns real-time SIP-level data (OHLCV, extended hours, VWAP, bid/ask)
  - tvDatafeed provides full historical candle data across all timeframes
"""

from __future__ import annotations

import asyncio
import structlog
from typing import Optional

from tradingview_ta import TA_Handler, Interval as TAInterval
from tradingview_screener import Query, Column

from app.config import get_settings
from app.models import OHLCV

_log = structlog.get_logger(__name__)


# ──────────────────────────────────────────────
# TA Interval mapping (tradingview-ta)
# ──────────────────────────────────────────────

_INTERVAL_MAP = {
    "1m": TAInterval.INTERVAL_1_MINUTE,
    "5m": TAInterval.INTERVAL_5_MINUTES,
    "15m": TAInterval.INTERVAL_15_MINUTES,
    "30m": TAInterval.INTERVAL_30_MINUTES,
    "1h": TAInterval.INTERVAL_1_HOUR,
    "2h": TAInterval.INTERVAL_2_HOURS,
    "4h": TAInterval.INTERVAL_4_HOURS,
    "1d": TAInterval.INTERVAL_1_DAY,
    "1W": TAInterval.INTERVAL_1_WEEK,
    "1M": TAInterval.INTERVAL_1_MONTH,
}


# ──────────────────────────────────────────────
# tvDatafeed Interval mapping (historical bars)
# ──────────────────────────────────────────────

def _get_tvdf_interval(interval: str):
    """Convert our interval strings to tvDatafeed Interval enum."""
    from tvDatafeed import Interval as TvDfInterval

    return {
        "1m": TvDfInterval.in_1_minute,
        "5m": TvDfInterval.in_5_minute,
        "15m": TvDfInterval.in_15_minute,
        "30m": TvDfInterval.in_30_minute,
        "1h": TvDfInterval.in_1_hour,
        "2h": TvDfInterval.in_2_hour,
        "4h": TvDfInterval.in_4_hour,
        "1d": TvDfInterval.in_daily,
        "1W": TvDfInterval.in_weekly,
        "1wk": TvDfInterval.in_weekly,
        "1M": TvDfInterval.in_monthly,
        "1mo": TvDfInterval.in_monthly,
    }.get(interval, TvDfInterval.in_daily)


# ──────────────────────────────────────────────
# n_bars mapping (period → approximate bar count)
# ──────────────────────────────────────────────

def _period_to_n_bars(period: str, interval: str) -> int:
    """Convert period + interval into approximate number of bars to fetch."""
    _PERIOD_DAYS = {
        "1d": 1, "5d": 5, "1mo": 22, "3mo": 66, "6mo": 132,
        "1y": 252, "2y": 504, "5y": 1260, "max": 5000,
    }
    _INTERVAL_MINUTES = {
        "1m": 1, "5m": 5, "15m": 15, "30m": 30,
        "1h": 60, "2h": 120, "4h": 240,
        "1d": 390, "1W": 1950, "1wk": 1950, "1M": 8190, "1mo": 8190,
    }
    trading_days = _PERIOD_DAYS.get(period, 132)
    trading_minutes_per_day = 390
    interval_minutes = _INTERVAL_MINUTES.get(interval, 390)

    total_minutes = trading_days * trading_minutes_per_day
    n_bars = total_minutes // interval_minutes

    # Clamp to tvDatafeed's 5000-bar limit
    return min(max(n_bars, 10), 5000)


class TradingViewClient:
    """TradingView data access — PRIMARY data source for the platform.

    Three data pipelines:
      1. tvDatafeed      → Historical OHLCV candle bars (paid plan)
      2. tradingview-screener → Real-time SIP quotes, screener, fundamentals
      3. tradingview-ta  → 26-indicator technical analysis summaries

    All methods are async-safe via asyncio.to_thread() since the
    underlying packages are synchronous.
    """

    def __init__(self):
        self._tv_session = None  # Lazy-initialized tvDatafeed session

    def _get_tv_session(self):
        """Lazy-initialize tvDatafeed session with TradingView credentials."""
        if self._tv_session is not None:
            return self._tv_session

        from tvDatafeed import TvDatafeed

        settings = get_settings()
        username = settings.tradingview_username
        password = settings.tradingview_password

        if username and password:
            self._tv_session = TvDatafeed(username=username, password=password)
            _log.info("tv.session_authenticated", username=username)
        else:
            # Without credentials: limited data access
            self._tv_session = TvDatafeed()
            _log.warning("tv.session_anonymous", msg="No TradingView credentials — limited data")

        return self._tv_session

    # ──────────────────────────────────────────
    # Historical OHLCV Bars (tvDatafeed)
    # ──────────────────────────────────────────

    async def get_historical_bars(
        self,
        ticker: str,
        exchange: str = "NASDAQ",
        interval: str = "1d",
        period: str = "6mo",
        n_bars: Optional[int] = None,
    ) -> list[OHLCV]:
        """Fetch historical OHLCV bars from TradingView via tvDatafeed.

        Uses our paid TradingView subscription for full SIP-quality data.
        Supports all timeframes from 1-minute to monthly.

        Args:
            ticker: Stock symbol (e.g. AAPL).
            exchange: Exchange name (NASDAQ, NYSE, AMEX).
            interval: Candle interval (1m, 5m, 15m, 30m, 1h, 4h, 1d, 1W, 1M).
            period: Period string (1d, 5d, 1mo, 3mo, 6mo, 1y, 2y, 5y, max).
            n_bars: Override — exact number of bars to fetch (max 5000).

        Returns:
            List of OHLCV models sorted by timestamp ascending.
        """

        def _fetch():
            tv = self._get_tv_session()
            tvdf_interval = _get_tvdf_interval(interval)
            bar_count = n_bars or _period_to_n_bars(period, interval)

            df = tv.get_hist(
                symbol=ticker.upper(),
                exchange=exchange.upper(),
                interval=tvdf_interval,
                n_bars=bar_count,
            )

            if df is None or df.empty:
                _log.warning("tv.no_bars", ticker=ticker, exchange=exchange, interval=interval)
                return []

            bars = []
            for idx, row in df.iterrows():
                bars.append(
                    OHLCV(
                        timestamp=idx.to_pydatetime(),
                        open=round(float(row["open"]), 4),
                        high=round(float(row["high"]), 4),
                        low=round(float(row["low"]), 4),
                        close=round(float(row["close"]), 4),
                        volume=int(row["volume"]),
                    )
                )

            _log.info("tv.bars_fetched", ticker=ticker, count=len(bars), interval=interval)
            return bars

        return await asyncio.to_thread(_fetch)

    # ──────────────────────────────────────────
    # Technical Analysis
    # ──────────────────────────────────────────

    async def get_technical_summary(
        self,
        ticker: str,
        exchange: str = "NASDAQ",
        screener: str = "america",
        interval: str = "1d",
    ) -> dict:
        """Fetch TradingView's 26-indicator technical analysis summary.

        Returns oscillator and moving average signals with an overall
        recommendation (STRONG_BUY / BUY / NEUTRAL / SELL / STRONG_SELL).

        Args:
            ticker: Stock symbol (e.g. AAPL, TSLA).
            exchange: Exchange name (NASDAQ, NYSE, AMEX, etc.).
            screener: Market screener (america, forex, crypto, etc.).
            interval: Candle interval (1m, 5m, 15m, 30m, 1h, 4h, 1d, 1W, 1M).
        """
        ta_interval = _INTERVAL_MAP.get(interval, TAInterval.INTERVAL_1_DAY)

        def _fetch():
            handler = TA_Handler(
                symbol=ticker.upper(),
                exchange=exchange.upper(),
                screener=screener.lower(),
                interval=ta_interval,
            )
            analysis = handler.get_analysis()
            return {
                "ticker": ticker.upper(),
                "exchange": exchange.upper(),
                "interval": interval,
                "summary": {
                    "recommendation": analysis.summary.get("RECOMMENDATION", "NEUTRAL"),
                    "buy": analysis.summary.get("BUY", 0),
                    "sell": analysis.summary.get("SELL", 0),
                    "neutral": analysis.summary.get("NEUTRAL", 0),
                },
                "oscillators": {
                    "recommendation": analysis.oscillators.get("RECOMMENDATION", "NEUTRAL"),
                    "buy": analysis.oscillators.get("BUY", 0),
                    "sell": analysis.oscillators.get("SELL", 0),
                    "neutral": analysis.oscillators.get("NEUTRAL", 0),
                    "compute": analysis.oscillators.get("COMPUTE", {}),
                },
                "moving_averages": {
                    "recommendation": analysis.moving_averages.get("RECOMMENDATION", "NEUTRAL"),
                    "buy": analysis.moving_averages.get("BUY", 0),
                    "sell": analysis.moving_averages.get("SELL", 0),
                    "neutral": analysis.moving_averages.get("NEUTRAL", 0),
                    "compute": analysis.moving_averages.get("COMPUTE", {}),
                },
                "indicators": analysis.indicators or {},
            }

        return await asyncio.to_thread(_fetch)

    # ──────────────────────────────────────────
    # Stock Screener
    # ──────────────────────────────────────────

    async def screen_stocks(
        self,
        min_price: Optional[float] = None,
        max_price: Optional[float] = None,
        min_volume: Optional[int] = None,
        min_market_cap: Optional[float] = None,
        min_change_pct: Optional[float] = None,
        max_change_pct: Optional[float] = None,
        sort_by: str = "market_cap_basic",
        ascending: bool = False,
        limit: int = 25,
    ) -> list[dict]:
        """Run a TradingView stock screener scan with custom filters.

        Returns a list of stock dicts with key fields.

        Args:
            min_price: Minimum stock price filter.
            max_price: Maximum stock price filter.
            min_volume: Minimum daily volume filter.
            min_market_cap: Minimum market cap filter (in dollars).
            min_change_pct: Minimum % change filter.
            max_change_pct: Maximum % change filter.
            sort_by: Column to sort by (default: market_cap_basic).
            ascending: Sort direction (default: descending).
            limit: Max results to return.
        """

        def _fetch():
            query = (
                Query()
                .select(
                    "name",
                    "close",
                    "change",
                    "change_abs",
                    "volume",
                    "market_cap_basic",
                    "price_earnings_ttm",
                    "sector",
                    "industry",
                    "Recommend.All",
                    "RSI",
                    "MACD.macd",
                    "ADX",
                    "ATR",
                    "Perf.W",
                    "Perf.1M",
                    "Perf.3M",
                    "relative_volume_10d_calc",
                    "average_volume_10d_calc",
                    "SMA20",
                    "SMA50",
                    "SMA200",
                    "BB.upper",
                    "BB.lower",
                    "Volatility.D",
                )
                .set_markets("america")
                .order_by(sort_by, ascending)
                .limit(limit)
            )

            # Apply filters
            if min_price is not None:
                query = query.where(Column("close") >= min_price)
            if max_price is not None:
                query = query.where(Column("close") <= max_price)
            if min_volume is not None:
                query = query.where(Column("volume") >= min_volume)
            if min_market_cap is not None:
                query = query.where(Column("market_cap_basic") >= min_market_cap)
            if min_change_pct is not None:
                query = query.where(Column("change") >= min_change_pct)
            if max_change_pct is not None:
                query = query.where(Column("change") <= max_change_pct)

            # Filter out non-stock types
            query = query.where(Column("is_primary") == True)  # noqa: E712

            count, rows = query.get_scanner_data()
            results = []
            for _, row in rows.iterrows():
                results.append({
                    "ticker": row.get("ticker", ""),
                    "name": row.get("name", ""),
                    "close": row.get("close"),
                    "change_pct": row.get("change"),
                    "change_abs": row.get("change_abs"),
                    "volume": row.get("volume"),
                    "market_cap": row.get("market_cap_basic"),
                    "pe_ratio": row.get("price_earnings_ttm"),
                    "sector": row.get("sector"),
                    "industry": row.get("industry"),
                    "tv_recommendation": row.get("Recommend.All"),
                    "rsi": row.get("RSI"),
                    "macd": row.get("MACD.macd"),
                    "adx": row.get("ADX"),
                    "atr": row.get("ATR"),
                    "perf_1w": row.get("Perf.W"),
                    "perf_1m": row.get("Perf.1M"),
                    "perf_3m": row.get("Perf.3M"),
                    "relative_volume": row.get("relative_volume_10d_calc"),
                    "avg_volume_10d": row.get("average_volume_10d_calc"),
                    "sma_20": row.get("SMA20"),
                    "sma_50": row.get("SMA50"),
                    "sma_200": row.get("SMA200"),
                    "bb_upper": row.get("BB.upper"),
                    "bb_lower": row.get("BB.lower"),
                    "volatility_d": row.get("Volatility.D"),
                })
            return results

        return await asyncio.to_thread(_fetch)

    # ──────────────────────────────────────────
    # Top Movers
    # ──────────────────────────────────────────

    async def get_top_movers(
        self,
        direction: str = "gainers",
        limit: int = 15,
    ) -> list[dict]:
        """Get top gainers, losers, or most active stocks.

        Args:
            direction: One of 'gainers', 'losers', 'active'.
            limit: Max results.
        """

        def _fetch():
            query = (
                Query()
                .select(
                    "name",
                    "close",
                    "change",
                    "change_abs",
                    "volume",
                    "market_cap_basic",
                    "Recommend.All",
                    "RSI",
                )
                .set_markets("america")
                .where(Column("is_primary") == True)  # noqa: E712
                .where(Column("market_cap_basic") >= 1_000_000_000)  # $1B+ only
                .limit(limit)
            )

            if direction == "gainers":
                query = query.order_by("change", ascending=False)
            elif direction == "losers":
                query = query.order_by("change", ascending=True)
            else:  # active
                query = query.order_by("volume", ascending=False)

            count, rows = query.get_scanner_data()
            results = []
            for _, row in rows.iterrows():
                results.append({
                    "ticker": row.get("ticker", ""),
                    "name": row.get("name", ""),
                    "close": row.get("close"),
                    "change_pct": row.get("change"),
                    "change_abs": row.get("change_abs"),
                    "volume": row.get("volume"),
                    "market_cap": row.get("market_cap_basic"),
                    "tv_recommendation": row.get("Recommend.All"),
                    "rsi": row.get("RSI"),
                })
            return results

        return await asyncio.to_thread(_fetch)

    # ──────────────────────────────────────────
    # Single Ticker Snapshot
    # ──────────────────────────────────────────

    async def get_snapshot(
        self,
        ticker: str,
    ) -> Optional[dict]:
        """Get a full data snapshot for a single ticker from TradingView.

        Combines screener data (fundamentals + technicals) for one stock.

        Args:
            ticker: Stock symbol (e.g. AAPL). Format: EXCHANGE:SYMBOL or just SYMBOL.
        """

        def _fetch():
            # Normalize ticker for query
            if ":" not in ticker:
                search_ticker = ticker.upper()
            else:
                search_ticker = ticker.upper()

            query = (
                Query()
                .select(
                    "name",
                    "description",
                    "close",
                    "open",
                    "high",
                    "low",
                    "change",
                    "change_abs",
                    "volume",
                    "average_volume_10d_calc",
                    "relative_volume_10d_calc",
                    "market_cap_basic",
                    "price_earnings_ttm",
                    "earnings_per_share_basic_ttm",
                    "dividend_yield_recent",
                    "sector",
                    "industry",
                    "Recommend.All",
                    "Recommend.MA",
                    "Recommend.Other",
                    "RSI",
                    "RSI[1]",
                    "MACD.macd",
                    "MACD.signal",
                    "ADX",
                    "ATR",
                    "CCI20",
                    "Stoch.K",
                    "Stoch.D",
                    "SMA20",
                    "SMA50",
                    "SMA200",
                    "EMA20",
                    "EMA50",
                    "EMA200",
                    "BB.upper",
                    "BB.lower",
                    "Pivot.M.Classic.R1",
                    "Pivot.M.Classic.S1",
                    "Perf.W",
                    "Perf.1M",
                    "Perf.3M",
                    "Perf.6M",
                    "Perf.YTD",
                    "Perf.Y",
                    "Volatility.D",
                    "Volatility.W",
                    "Volatility.M",
                    "52 Week High",
                    "52 Week Low",
                    "beta_1_year",
                    "gap",
                    "Pre-market Close",
                    "after_hours_close",
                )
                .set_markets("america")
                .where(Column("name") == search_ticker)
                .limit(1)
            )

            count, rows = query.get_scanner_data()
            if rows.empty:
                return None

            row = rows.iloc[0]
            return {
                "ticker": row.get("ticker", ticker.upper()),
                "name": row.get("name", ""),
                "description": row.get("description", ""),
                "price": {
                    "close": row.get("close"),
                    "open": row.get("open"),
                    "high": row.get("high"),
                    "low": row.get("low"),
                    "change_pct": row.get("change"),
                    "change_abs": row.get("change_abs"),
                    "gap": row.get("gap"),
                    "premarket": row.get("Pre-market Close"),
                    "after_hours": row.get("after_hours_close"),
                },
                "volume": {
                    "current": row.get("volume"),
                    "avg_10d": row.get("average_volume_10d_calc"),
                    "relative": row.get("relative_volume_10d_calc"),
                },
                "fundamentals": {
                    "market_cap": row.get("market_cap_basic"),
                    "pe_ratio": row.get("price_earnings_ttm"),
                    "eps": row.get("earnings_per_share_basic_ttm"),
                    "dividend_yield": row.get("dividend_yield_recent"),
                    "sector": row.get("sector"),
                    "industry": row.get("industry"),
                    "beta": row.get("beta_1_year"),
                    "52w_high": row.get("52 Week High"),
                    "52w_low": row.get("52 Week Low"),
                },
                "technicals": {
                    "recommendation": row.get("Recommend.All"),
                    "ma_recommendation": row.get("Recommend.MA"),
                    "oscillator_recommendation": row.get("Recommend.Other"),
                    "rsi": row.get("RSI"),
                    "rsi_prev": row.get("RSI[1]"),
                    "macd": row.get("MACD.macd"),
                    "macd_signal": row.get("MACD.signal"),
                    "adx": row.get("ADX"),
                    "atr": row.get("ATR"),
                    "cci": row.get("CCI20"),
                    "stoch_k": row.get("Stoch.K"),
                    "stoch_d": row.get("Stoch.D"),
                },
                "moving_averages": {
                    "sma_20": row.get("SMA20"),
                    "sma_50": row.get("SMA50"),
                    "sma_200": row.get("SMA200"),
                    "ema_20": row.get("EMA20"),
                    "ema_50": row.get("EMA50"),
                    "ema_200": row.get("EMA200"),
                    "bb_upper": row.get("BB.upper"),
                    "bb_lower": row.get("BB.lower"),
                },
                "pivots": {
                    "r1_monthly": row.get("Pivot.M.Classic.R1"),
                    "s1_monthly": row.get("Pivot.M.Classic.S1"),
                },
                "performance": {
                    "1w": row.get("Perf.W"),
                    "1m": row.get("Perf.1M"),
                    "3m": row.get("Perf.3M"),
                    "6m": row.get("Perf.6M"),
                    "ytd": row.get("Perf.YTD"),
                    "1y": row.get("Perf.Y"),
                },
                "volatility": {
                    "daily": row.get("Volatility.D"),
                    "weekly": row.get("Volatility.W"),
                    "monthly": row.get("Volatility.M"),
                },
            }

        return await asyncio.to_thread(_fetch)

    # ────────────────────────────────────────
    # Real-Time SIP Quote (paid subscription)
    # ────────────────────────────────────────

    async def get_realtime_quote(self, ticker: str) -> Optional[dict]:
        """Get a real-time SIP-level quote from TradingView.

        With a paid TradingView subscription this returns true real-time
        OHLCV, VWAP, bid/ask, extended hours, and intraday metrics.

        Args:
            ticker: Stock symbol (e.g. AAPL).
        """

        def _fetch():
            query = (
                Query()
                .select(
                    "name",
                    "close",
                    "open",
                    "high",
                    "low",
                    "volume",
                    "change",
                    "change_abs",
                    "bid",
                    "ask",
                    "VWAP",
                    "average_volume_10d_calc",
                    "relative_volume_10d_calc",
                    "Pre-market Close",
                    "premarket_change",
                    "premarket_volume",
                    "after_hours_close",
                    "postmarket_change",
                    "postmarket_volume",
                    "update_mode",
                    "exchange",
                    "type",
                    "High.All",
                    "Low.All",
                    "52 Week High",
                    "52 Week Low",
                    "gap",
                    "Volatility.D",
                )
                .set_markets("america")
                .where(Column("name") == ticker.upper())
                .limit(1)
            )

            count, rows = query.get_scanner_data()
            if rows.empty:
                return None

            row = rows.iloc[0]
            return {
                "ticker": row.get("ticker", ticker.upper()),
                "name": row.get("name", ""),
                "source": "tradingview_sip",
                "realtime": True,
                "price": row.get("close"),
                "open": row.get("open"),
                "high": row.get("high"),
                "low": row.get("low"),
                "volume": row.get("volume"),
                "change_pct": row.get("change"),
                "change_abs": row.get("change_abs"),
                "bid": row.get("bid"),
                "ask": row.get("ask"),
                "vwap": row.get("VWAP"),
                "gap": row.get("gap"),
                "volatility_d": row.get("Volatility.D"),
                "volume_avg_10d": row.get("average_volume_10d_calc"),
                "relative_volume": row.get("relative_volume_10d_calc"),
                "extended_hours": {
                    "premarket_price": row.get("Pre-market Close"),
                    "premarket_change": row.get("premarket_change"),
                    "premarket_volume": row.get("premarket_volume"),
                    "afterhours_price": row.get("after_hours_close"),
                    "afterhours_change": row.get("postmarket_change"),
                    "afterhours_volume": row.get("postmarket_volume"),
                },
                "range": {
                    "52w_high": row.get("52 Week High"),
                    "52w_low": row.get("52 Week Low"),
                    "all_time_high": row.get("High.All"),
                    "all_time_low": row.get("Low.All"),
                },
                "exchange": row.get("exchange"),
                "update_mode": row.get("update_mode"),
            }

        return await asyncio.to_thread(_fetch)

    # ────────────────────────────────────────
    # Batch Multi-Ticker Quotes
    # ────────────────────────────────────────

    async def get_batch_quotes(self, tickers: list[str]) -> list[dict]:
        """Get real-time quotes for multiple tickers in a single call.

        More efficient than calling get_realtime_quote() per ticker.
        Uses the screener's OR filter to fetch all tickers at once.

        Args:
            tickers: List of stock symbols (e.g. ['AAPL', 'TSLA', 'MSFT']).
        """

        def _fetch():
            query = (
                Query()
                .select(
                    "name",
                    "close",
                    "open",
                    "high",
                    "low",
                    "volume",
                    "change",
                    "change_abs",
                    "VWAP",
                    "average_volume_10d_calc",
                    "relative_volume_10d_calc",
                    "market_cap_basic",
                    "Pre-market Close",
                    "after_hours_close",
                    "Recommend.All",
                    "RSI",
                    "gap",
                )
                .set_markets("america")
                .where(Column("name").isin([t.upper() for t in tickers]))
                .limit(len(tickers))
            )

            count, rows = query.get_scanner_data()
            results = []
            for _, row in rows.iterrows():
                results.append({
                    "ticker": row.get("ticker", ""),
                    "name": row.get("name", ""),
                    "price": row.get("close"),
                    "open": row.get("open"),
                    "high": row.get("high"),
                    "low": row.get("low"),
                    "volume": row.get("volume"),
                    "change_pct": row.get("change"),
                    "change_abs": row.get("change_abs"),
                    "vwap": row.get("VWAP"),
                    "volume_avg_10d": row.get("average_volume_10d_calc"),
                    "relative_volume": row.get("relative_volume_10d_calc"),
                    "market_cap": row.get("market_cap_basic"),
                    "premarket": row.get("Pre-market Close"),
                    "afterhours": row.get("after_hours_close"),
                    "recommendation": row.get("Recommend.All"),
                    "rsi": row.get("RSI"),
                    "gap": row.get("gap"),
                    "source": "tradingview_sip",
                })
            return results

        return await asyncio.to_thread(_fetch)

    # ────────────────────────────────────────
    # Financials (Revenue, Income, Margins, Debt)
    # ────────────────────────────────────────

    async def get_financials(self, ticker: str) -> Optional[dict]:
        """Get key financial data for a ticker from TradingView.

        Covers revenue, net income, margins, debt, cash flow, and
        valuation ratios — fills gaps that Alpaca doesn’t provide.

        Args:
            ticker: Stock symbol.
        """

        def _fetch():
            query = (
                Query()
                .select(
                    "name",
                    "market_cap_basic",
                    "price_earnings_ttm",
                    "price_sales_current",
                    "price_book_fq",
                    "price_free_cash_flow_ttm",
                    "earnings_per_share_basic_ttm",
                    "earnings_per_share_diluted_ttm",
                    "dividend_yield_recent",
                    "dividends_per_share_fq",
                    "revenue_per_share_ttm",
                    "total_revenue_ttm",
                    "net_income_ttm",
                    "gross_margin_ttm",
                    "operating_margin_ttm",
                    "net_margin_ttm",
                    "return_on_equity_ttm",
                    "return_on_assets_ttm",
                    "return_on_invested_capital_ttm",
                    "total_debt_fq",
                    "total_current_assets_fq",
                    "total_current_liabilities_fq",
                    "current_ratio_fq",
                    "quick_ratio_fq",
                    "debt_to_equity_fq",
                    "free_cash_flow_ttm",
                    "cash_and_short_term_investments_fq",
                    "book_value_per_share_fq",
                    "enterprise_value_fq",
                    "float_shares_outstanding",
                    "number_of_employees",
                    "beta_1_year",
                )
                .set_markets("america")
                .where(Column("name") == ticker.upper())
                .limit(1)
            )

            count, rows = query.get_scanner_data()
            if rows.empty:
                return None

            row = rows.iloc[0]
            return {
                "ticker": row.get("ticker", ticker.upper()),
                "name": row.get("name", ""),
                "source": "tradingview",
                "valuation": {
                    "market_cap": row.get("market_cap_basic"),
                    "enterprise_value": row.get("enterprise_value_fq"),
                    "pe_ratio": row.get("price_earnings_ttm"),
                    "ps_ratio": row.get("price_sales_current"),
                    "pb_ratio": row.get("price_book_fq"),
                    "price_to_fcf": row.get("price_free_cash_flow_ttm"),
                },
                "earnings": {
                    "eps_basic": row.get("earnings_per_share_basic_ttm"),
                    "eps_diluted": row.get("earnings_per_share_diluted_ttm"),
                    "revenue_per_share": row.get("revenue_per_share_ttm"),
                },
                "income": {
                    "total_revenue": row.get("total_revenue_ttm"),
                    "net_income": row.get("net_income_ttm"),
                    "free_cash_flow": row.get("free_cash_flow_ttm"),
                },
                "margins": {
                    "gross_margin": row.get("gross_margin_ttm"),
                    "operating_margin": row.get("operating_margin_ttm"),
                    "net_margin": row.get("net_margin_ttm"),
                },
                "returns": {
                    "roe": row.get("return_on_equity_ttm"),
                    "roa": row.get("return_on_assets_ttm"),
                    "roic": row.get("return_on_invested_capital_ttm"),
                },
                "balance_sheet": {
                    "total_debt": row.get("total_debt_fq"),
                    "current_assets": row.get("total_current_assets_fq"),
                    "current_liabilities": row.get("total_current_liabilities_fq"),
                    "current_ratio": row.get("current_ratio_fq"),
                    "quick_ratio": row.get("quick_ratio_fq"),
                    "debt_to_equity": row.get("debt_to_equity_fq"),
                    "cash_and_equivalents": row.get("cash_and_short_term_investments_fq"),
                    "book_value_per_share": row.get("book_value_per_share_fq"),
                },
                "dividends": {
                    "yield": row.get("dividend_yield_recent"),
                    "per_share": row.get("dividends_per_share_fq"),
                },
                "shares": {
                    "float": row.get("float_shares_outstanding"),
                    "employees": row.get("number_of_employees"),
                    "beta": row.get("beta_1_year"),
                },
            }

        return await asyncio.to_thread(_fetch)

    # ────────────────────────────────────────
    # Earnings Calendar
    # ────────────────────────────────────────

    async def get_earnings_calendar(
        self,
        limit: int = 50,
        upcoming_only: bool = True,
    ) -> list[dict]:
        """Get upcoming earnings dates for stocks.

        Scans for companies with upcoming earnings release dates.
        Fills a gap — Alpaca doesn’t provide an earnings calendar.

        Args:
            limit: Max results.
            upcoming_only: If True, only return future earnings dates.
        """

        def _fetch():
            import time

            query = (
                Query()
                .select(
                    "name",
                    "close",
                    "change",
                    "volume",
                    "market_cap_basic",
                    "earnings_release_date",
                    "earnings_release_next_date",
                    "earnings_per_share_forecast_next_fq",
                    "earnings_per_share_basic_ttm",
                    "price_earnings_ttm",
                    "sector",
                )
                .set_markets("america")
                .where(Column("is_primary") == True)  # noqa: E712
                .where(Column("market_cap_basic") >= 1_000_000_000)  # $1B+
            )

            if upcoming_only:
                # Filter for stocks with upcoming earnings date
                # TradingView stores these as Unix timestamps
                now_ts = int(time.time())
                query = query.where(
                    Column("earnings_release_next_date") >= now_ts
                )
                query = query.order_by("earnings_release_next_date", ascending=True)
            else:
                query = query.order_by("earnings_release_date", ascending=False)

            query = query.limit(limit)
            count, rows = query.get_scanner_data()

            results = []
            for _, row in rows.iterrows():
                results.append({
                    "ticker": row.get("ticker", ""),
                    "name": row.get("name", ""),
                    "price": row.get("close"),
                    "change_pct": row.get("change"),
                    "volume": row.get("volume"),
                    "market_cap": row.get("market_cap_basic"),
                    "earnings_date": row.get("earnings_release_date"),
                    "next_earnings_date": row.get("earnings_release_next_date"),
                    "eps_forecast_next": row.get("earnings_per_share_forecast_next_fq"),
                    "eps_ttm": row.get("earnings_per_share_basic_ttm"),
                    "pe_ratio": row.get("price_earnings_ttm"),
                    "sector": row.get("sector"),
                    "source": "tradingview",
                })
            return results

        return await asyncio.to_thread(_fetch)

    # ────────────────────────────────────────
    # Short Interest
    # ────────────────────────────────────────

    async def get_short_interest(
        self,
        limit: int = 25,
        min_short_pct: float = 10.0,
    ) -> list[dict]:
        """Get stocks with highest short interest.

        Short squeeze scanner — neither Alpaca nor QuantData provide this.

        Args:
            limit: Max results.
            min_short_pct: Minimum short volume % to include.
        """

        def _fetch():
            query = (
                Query()
                .select(
                    "name",
                    "close",
                    "change",
                    "volume",
                    "market_cap_basic",
                    "float_shares_outstanding",
                    "total_shares_outstanding",
                    "short_volume",
                    "short_volume_ratio",
                    "relative_volume_10d_calc",
                    "Recommend.All",
                    "sector",
                )
                .set_markets("america")
                .where(Column("is_primary") == True)  # noqa: E712
                .where(Column("market_cap_basic") >= 100_000_000)  # $100M+
                .order_by("short_volume_ratio", ascending=False)
                .limit(limit)
            )

            count, rows = query.get_scanner_data()
            results = []
            for _, row in rows.iterrows():
                results.append({
                    "ticker": row.get("ticker", ""),
                    "name": row.get("name", ""),
                    "price": row.get("close"),
                    "change_pct": row.get("change"),
                    "volume": row.get("volume"),
                    "market_cap": row.get("market_cap_basic"),
                    "float_shares": row.get("float_shares_outstanding"),
                    "total_shares": row.get("total_shares_outstanding"),
                    "short_volume": row.get("short_volume"),
                    "short_ratio": row.get("short_volume_ratio"),
                    "relative_volume": row.get("relative_volume_10d_calc"),
                    "recommendation": row.get("Recommend.All"),
                    "sector": row.get("sector"),
                    "source": "tradingview",
                })
            return results

        return await asyncio.to_thread(_fetch)

    # ────────────────────────────────────────
    # Sector Performance Heatmap
    # ────────────────────────────────────────

    async def get_sector_performance(
        self,
        top_per_sector: int = 5,
    ) -> dict:
        """Get sector-level performance aggregation.

        Returns top performers per sector with aggregated metrics.
        Fills the gap of TradingView’s Market Map / sector rotation data.

        Args:
            top_per_sector: How many top stocks per sector to include.
        """

        def _fetch():
            query = (
                Query()
                .select(
                    "name",
                    "close",
                    "change",
                    "volume",
                    "market_cap_basic",
                    "sector",
                    "industry",
                    "Perf.W",
                    "Perf.1M",
                    "Perf.3M",
                    "relative_volume_10d_calc",
                )
                .set_markets("america")
                .where(Column("is_primary") == True)  # noqa: E712
                .where(Column("market_cap_basic") >= 10_000_000_000)  # $10B+
                .order_by("market_cap_basic", ascending=False)
                .limit(200)
            )

            count, rows = query.get_scanner_data()

            # Group by sector
            sectors = {}
            for _, row in rows.iterrows():
                sector = row.get("sector", "Unknown")
                if sector not in sectors:
                    sectors[sector] = {
                        "stocks": [],
                        "total_market_cap": 0,
                        "avg_change": 0,
                        "count": 0,
                    }

                sectors[sector]["stocks"].append({
                    "ticker": row.get("ticker", ""),
                    "name": row.get("name", ""),
                    "price": row.get("close"),
                    "change_pct": row.get("change"),
                    "volume": row.get("volume"),
                    "market_cap": row.get("market_cap_basic"),
                    "industry": row.get("industry"),
                    "perf_1w": row.get("Perf.W"),
                    "perf_1m": row.get("Perf.1M"),
                    "perf_3m": row.get("Perf.3M"),
                    "relative_volume": row.get("relative_volume_10d_calc"),
                })
                sectors[sector]["total_market_cap"] += (row.get("market_cap_basic") or 0)
                sectors[sector]["avg_change"] += (row.get("change") or 0)
                sectors[sector]["count"] += 1

            # Calculate averages and trim to top_per_sector
            for sector_name, data in sectors.items():
                if data["count"] > 0:
                    data["avg_change"] = round(data["avg_change"] / data["count"], 4)
                # Sort by change and keep top performers
                data["stocks"] = sorted(
                    data["stocks"],
                    key=lambda x: x.get("change_pct") or 0,
                    reverse=True,
                )[:top_per_sector]

            return {
                "sectors": sectors,
                "source": "tradingview",
            }

        return await asyncio.to_thread(_fetch)
