"""
Bubby Vision — Data Engine

Orchestrates data fetching, normalization, caching, and storage.
This is the single entry point for all data operations — agents call
the engine, never the data clients directly.

Data Source Hierarchy:
  Tier 1 (PRIMARY): Questrade (Real-Time Streaming) — L1 stock quotes,
                    historical OHLCV candles, options chains with exchange Greeks,
                    strategy quotes, account data, WebSocket streaming
  Tier 2 (SUPPLEMENT): TradingView — TA summaries, screening, financials, sector data
  Tier 3 (FALLBACK): yfinance — OHLCV + fundamentals when Questrade unavailable
  Tier 4 (SCRAPED): OptionStrats — complex flow, IV surface, congressional flow
  Supplements: Finnhub (news/sentiment), EDGAR (filings), FRED (economic),
               Alpaca (market clock/calendar only)
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from app.cache import cached, TTL_STOCK, TTL_OPTIONS, TTL_FINANCIALS, TTL_INSIDER
from app.data.yfinance_client import YFinanceClient
from app.data.fear_greed import FearGreedClient
from app.data.finnhub_client import FinnhubClient
from app.data.edgar_client import EdgarClient
from app.data.alpaca_client import AlpacaClient
from app.data.wsb_client import WSBClient
from app.data.quantdata_client import QuantDataClient
from app.data.screener_client import ScreenerClient
from app.data.tradingview_client import TradingViewClient
from app.data.optionstrats_scraper import OptionStratsScraper
from app.data.questrade_client import QuestradeClient
from app.data.fred_client import FREDClient
from app.engines.backtest_engine import BacktestEngine
from app.engines.options_engine import OptionsEngine
from app.engines.local_options_analytics import LocalOptionsAnalytics
from app.utils.circuit_breaker import get_breaker, CircuitOpenError
from app.models import (
    FearGreedIndex,
    FearGreedDetailed,
    FilingData,
    NewsItem,
    OHLCV,
    OptionsChain,
    StockData,
    StockQuote,
)

import structlog

_log = structlog.get_logger(__name__)


class DataEngine:
    """Central data orchestrator.

    Provides a unified API for all data operations. Handles:
    - Multi-source fetching
    - Data normalization
    - Caching (via Redis, per-endpoint TTLs)
    - Storage (via QuestDB)
    - Circuit breaker protection for external services
    """

    def __init__(self):
        self.questrade = QuestradeClient()      # PRIMARY — L1 quotes, candles, options
        self.yfinance = YFinanceClient()          # FALLBACK — OHLCV + fundamentals
        self.tradingview = TradingViewClient()    # SUPPLEMENT — TA, screening, financials
        self.fear_greed = FearGreedClient()
        self.finnhub = FinnhubClient()
        self.edgar = EdgarClient()
        self.alpaca = AlpacaClient()              # UTILITY — market clock/calendar only
        self.wsb = WSBClient()
        self.quantdata = QuantDataClient()
        self.screener = ScreenerClient()
        self.optionstrats = OptionStratsScraper()
        self.fred = FREDClient()
        self.backtest = BacktestEngine()
        self.options_engine = OptionsEngine()
        self.local_analytics = LocalOptionsAnalytics(
            yfinance=self.yfinance,
            options_engine=self.options_engine,
        )

        # Per-client circuit breakers
        self._breakers = {
            "questrade": get_breaker("questrade"),
            "yfinance": get_breaker("yfinance"),
            "finnhub": get_breaker("finnhub"),
            "alpaca": get_breaker("alpaca"),
            "edgar": get_breaker("edgar"),
            "wsb": get_breaker("wsb"),
            "quantdata": get_breaker("quantdata"),
            "tradingview": get_breaker("tradingview"),
            "fear_greed": get_breaker("fear_greed"),
            "optionstrats": get_breaker("optionstrats"),
            "fred": get_breaker("fred"),
        }

    def _safe_call(self, service: str, func, fallback=None):
        """Execute a function through the circuit breaker with fallback.

        Args:
            service: Name of the external service (key in self._breakers).
            func: Zero-argument callable to execute.
            fallback: Value to return if circuit is open.

        Returns:
            Result of func() or fallback if circuit is open.
        """
        breaker = self._breakers.get(service)
        if not breaker:
            return func()
        try:
            return breaker.call(func)
        except CircuitOpenError:
            _log.warning(
                "data_engine.circuit_open",
                service=service,
                fallback_type=type(fallback).__name__,
            )
            return fallback

    # ── Exchange Auto-Detection ──

    _EXCHANGE_MAP: dict[str, str] = {}

    def _detect_exchange(self, ticker: str) -> str:
        """Auto-detect exchange for a ticker using TradingView screener."""
        if ticker.upper() in self._EXCHANGE_MAP:
            return self._EXCHANGE_MAP[ticker.upper()]

        try:
            from tradingview_screener import Query, Column

            def _lookup():
                count, rows = (
                    Query()
                    .select("exchange")
                    .set_markets("america")
                    .where(Column("name") == ticker.upper())
                    .limit(1)
                    .get_scanner_data()
                )
                if not rows.empty:
                    return rows.iloc[0].get("exchange", "NASDAQ")
                return "NASDAQ"

            import asyncio
            try:
                loop = asyncio.get_running_loop()
                # If inside event loop, run in thread
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as pool:
                    exchange = pool.submit(_lookup).result(timeout=5)
            except RuntimeError:
                exchange = _lookup()

            self._EXCHANGE_MAP[ticker.upper()] = exchange
            return exchange
        except Exception:
            return "NASDAQ"

    # ── Stock Data ──

    @cached(ttl=TTL_STOCK, prefix="stock")
    def get_stock(
        self,
        ticker: str,
        period: str = "1mo",
        interval: str = "1d",
    ) -> StockData:
        """Fetch comprehensive stock data.

        Primary: Questrade (Real-Time Streaming) for OHLCV candle history.
        Fallback: yfinance if Questrade is unavailable.

        Quote and fundamentals always come from yfinance (richer data).
        """
        # Always get quote + fundamentals from yfinance (it's the richest source)
        yf_data = self._safe_call(
            "yfinance",
            lambda: self.yfinance.get_stock_data(ticker, period=period, interval=interval),
            fallback=None,
        )

        # Try Questrade for OHLCV bars (primary)
        qt_bars = None
        try:
            import asyncio

            async def _fetch_qt():
                return await self.questrade.get_candles(
                    ticker=ticker,
                    interval=interval,
                    period=period,
                )

            try:
                loop = asyncio.get_running_loop()
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as pool:
                    qt_bars = pool.submit(
                        lambda: asyncio.run(_fetch_qt())
                    ).result(timeout=15)
            except RuntimeError:
                qt_bars = asyncio.run(_fetch_qt())

            if qt_bars:
                _log.info(
                    "data_engine.questrade_bars_primary",
                    ticker=ticker,
                    count=len(qt_bars),
                    interval=interval,
                    source="questrade",
                )
        except Exception as e:
            _log.warning(
                "data_engine.questrade_bars_failed",
                ticker=ticker,
                error=str(e),
                msg="Falling back to yfinance for OHLCV",
            )

        # If yfinance failed entirely, create a minimal StockData
        if yf_data is None:
            yf_data = StockData(
                ticker=ticker.upper(),
                quote=StockQuote(
                    ticker=ticker.upper(),
                    price=0.0,
                    change=0.0,
                    change_pct=0.0,
                    volume=0,
                ),
                history=[],
                fundamentals={},
            )

        # Replace yfinance history with Questrade bars if available
        if qt_bars and len(qt_bars) > 0:
            yf_data.history = qt_bars
        elif not yf_data.history:
            _log.warning(
                "data_engine.no_bars_anywhere",
                ticker=ticker,
                msg="Both Questrade and yfinance returned empty history",
            )

        return yf_data

    async def get_realtime_enrichment(self, ticker: str) -> dict:
        """Fetch real-time L1 enrichment from Questrade.

        Returns bid/ask, last price, volume, VWAP, 52-week range — data
        that supplements the historical bars for a complete chart experience.
        Fallback: TradingView screener if Questrade unavailable.
        """
        try:
            quote = await self.questrade.get_quote_raw(ticker)
            if quote:
                return {
                    "source": "questrade_l1",
                    "bid": quote.get("bidPrice"),
                    "ask": quote.get("askPrice"),
                    "last": quote.get("lastTradePrice"),
                    "volume": quote.get("volume"),
                    "vwap": quote.get("VWAP"),
                    "open": quote.get("openPrice"),
                    "high": quote.get("highPrice"),
                    "low": quote.get("lowPrice"),
                    "high_52": quote.get("highPrice52"),
                    "low_52": quote.get("lowPrice52"),
                    "avg_volume_3mo": quote.get("averageVol3Months"),
                    "is_halted": quote.get("isHalted"),
                    "delay": quote.get("delay", 0),
                }
        except Exception as e:
            _log.warning("data_engine.questrade_enrichment_failed", ticker=ticker, error=str(e))

        # Fallback to TradingView
        try:
            tv_quote = await self.tradingview.get_realtime_quote(ticker)
            if tv_quote:
                return {
                    "source": "tradingview_fallback",
                    "bid": tv_quote.get("bid"),
                    "ask": tv_quote.get("ask"),
                    "vwap": tv_quote.get("vwap"),
                    "gap": tv_quote.get("gap"),
                    "volatility_d": tv_quote.get("volatility_d"),
                    "relative_volume": tv_quote.get("relative_volume"),
                    "extended_hours": tv_quote.get("extended_hours", {}),
                }
        except Exception:
            pass

        return {"source": "none", "error": "Real-time enrichment unavailable"}

    @cached(ttl=TTL_OPTIONS, prefix="options")
    def get_options(
        self,
        ticker: str,
        expiration: Optional[str] = None,
    ) -> OptionsChain:
        """Fetch options chain with exchange-computed Greeks.

        Primary: Questrade (real-time OPRA with delta, gamma, theta, vega).
        Fallback: yfinance (delayed, IV only).
        """
        try:
            import asyncio

            async def _fetch_qt_opts():
                return await self.questrade.get_options_chain(ticker, expiration=expiration)

            try:
                loop = asyncio.get_running_loop()
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as pool:
                    chain = pool.submit(
                        lambda: asyncio.run(_fetch_qt_opts())
                    ).result(timeout=15)
            except RuntimeError:
                chain = asyncio.run(_fetch_qt_opts())

            if chain and (chain.calls or chain.puts):
                _log.info(
                    "data_engine.questrade_options_primary",
                    ticker=ticker,
                    calls=len(chain.calls) if chain.calls else 0,
                    puts=len(chain.puts) if chain.puts else 0,
                )
                return chain
        except Exception as e:
            _log.warning(
                "data_engine.questrade_options_failed",
                ticker=ticker,
                error=str(e),
                msg="Falling back to yfinance for options",
            )

        return self.yfinance.get_options_chain(ticker, expiration=expiration)

    # ── Sentiment ──

    async def get_fear_greed(self) -> FearGreedIndex:
        """Fetch CNN Fear & Greed Index."""
        return await self.fear_greed.get_current()

    async def get_sentiment_bundle(self, ticker: str) -> dict:
        """Fetch fused sentiment from multiple sources.

        Combines:
        - CNN Fear & Greed Index (market-wide)
        - Finnhub social sentiment (ticker-specific)
        - WSB Reddit sentiment (ticker-specific)
        """
        fear_greed = None
        finnhub_sentiment = {}
        wsb_sentiment = {}

        try:
            fear_greed = await self.fear_greed.get_current()
        except Exception:
            pass

        try:
            finnhub_sentiment = await self.finnhub.get_sentiment(ticker)
        except Exception:
            pass

        try:
            wsb_sentiment = await self.wsb.get_sentiment_summary(ticker)
        except Exception:
            pass

        return {
            "ticker": ticker.upper(),
            "fear_greed": fear_greed.model_dump() if fear_greed else None,
            "finnhub": finnhub_sentiment,
            "wsb": wsb_sentiment,
            "timestamp": datetime.utcnow().isoformat(),
        }

    # ── News ──

    async def get_news(self, ticker: str, limit: int = 20) -> list[NewsItem]:
        """Fetch company news from Finnhub."""
        return await self.finnhub.get_company_news(ticker, limit=limit)

    # ── SEC Filings ──

    @cached(ttl=TTL_FINANCIALS, prefix="filings")
    def get_filings(
        self,
        ticker: str,
        form_type: Optional[str] = None,
        limit: int = 10,
    ) -> list[FilingData]:
        """Fetch SEC filings from EDGAR."""
        return self.edgar.get_company_filings(ticker, form_type=form_type, limit=limit)

    @cached(ttl=TTL_INSIDER, prefix="insider")
    def get_insider_trades(self, ticker: str, limit: int = 20) -> list[FilingData]:
        """Fetch insider trading activity (Form 4)."""
        return self.edgar.get_insider_trades(ticker, limit=limit)

    @cached(ttl=TTL_FINANCIALS, prefix="financials")
    def get_financials(self, ticker: str) -> dict:
        """Fetch XBRL financial data from latest 10-K."""
        return self.edgar.get_financials(ticker)

    # ── Options Flow ──

    async def get_options_flow(
        self,
        ticker: Optional[str] = None,
        min_premium: int = 100_000,
    ) -> list[dict]:
        """Fetch live options flow from QuantData."""
        return await self.quantdata.get_flow(ticker, min_premium=min_premium)

    async def get_unusual_activity(self, ticker: Optional[str] = None) -> list[dict]:
        """Unusual options activity — local yFinance computation, QuantData fallback."""
        if ticker:
            try:
                result = await self.local_analytics.compute_unusual_activity(ticker)
                if result:
                    return result
            except Exception as exc:
                _log.debug("data_engine.local_unusual_fallback", error=str(exc))
        # Market-wide UOA or local failure → QuantData fallback (returns [] if unconfigured)
        return await self.quantdata.get_unusual_activity(ticker)

    async def get_sweep_orders(self, ticker: Optional[str] = None) -> list[dict]:
        """Fetch sweep orders."""
        return await self.quantdata.get_sweep_orders(ticker)

    # ── Market Data ──

    async def get_market_clock(self) -> dict:
        """Is the market open? When does it open/close next?"""
        return await self.alpaca.get_market_clock()

    async def get_earnings_calendar(self, days: int = 7) -> list[dict]:
        """Upcoming earnings dates."""
        return await self.finnhub.get_earnings_calendar()

    async def get_analyst_recommendations(self, ticker: str) -> list[dict]:
        """Analyst buy/sell/hold recommendations."""
        return await self.finnhub.get_recommendation_trends(ticker)

    async def get_trending_tickers(self) -> dict[str, int]:
        """WSB trending tickers by mention count."""
        return await self.wsb.get_trending_tickers()

    # ── TradingView ──

    async def get_tv_technical_summary(
        self,
        ticker: str,
        exchange: str = "NASDAQ",
        interval: str = "1d",
    ) -> dict:
        """TradingView 26-indicator technical analysis summary."""
        return await self.tradingview.get_technical_summary(
            ticker, exchange=exchange, interval=interval,
        )

    async def screen_stocks_tv(self, **kwargs) -> list[dict]:
        """Run a TradingView stock screener scan."""
        return await self.tradingview.screen_stocks(**kwargs)

    async def get_top_movers_tv(
        self,
        direction: str = "gainers",
        limit: int = 15,
    ) -> list[dict]:
        """Top gainers, losers, or most active from TradingView."""
        return await self.tradingview.get_top_movers(direction=direction, limit=limit)

    async def get_tv_snapshot(self, ticker: str) -> dict | None:
        """Full TradingView data snapshot for a single ticker."""
        return await self.tradingview.get_snapshot(ticker)

    # ── Finnhub Extended ──

    async def get_insider_transactions(self, ticker: str) -> list[dict]:
        """Insider transactions from Finnhub (buys, sells, exercises)."""
        return await self.finnhub.get_insider_transactions(ticker)

    # ── QuantData Extended ──

    async def get_darkpool(self, ticker: str, limit: int = 25) -> list[dict]:
        """Dark pool prints for a ticker from QuantData."""
        return await self.quantdata.get_darkpool(ticker, limit=limit)

    # ── WSB Extended ──

    async def get_wsb_mentions(
        self,
        ticker: str,
        subreddit: str = "wallstreetbets",
        limit: int = 25,
    ) -> list[dict]:
        """Search for ticker mentions in a subreddit."""
        return await self.wsb.get_mentions(ticker, subreddit=subreddit, limit=limit)

    # ── Questrade Options (PRIMARY) ──

    async def get_questrade_options(
        self,
        ticker: str,
        expiration: str | None = None,
    ) -> OptionsChain:
        """Fetch live options chain with exchange Greeks from Questrade."""
        return await self.questrade.get_options_chain(
            ticker=ticker,
            expiration=expiration,
        )

    # ── Alpaca Options (LEGACY — kept for backwards compatibility) ──

    async def get_alpaca_options_snapshot(
        self,
        ticker: str,
        option_type: str | None = None,
        expiration: str | None = None,
        min_strike: float | None = None,
        max_strike: float | None = None,
        limit: int = 50,
    ) -> dict:
        """Fetch live options chain with Greeks from Alpaca (legacy).

        DEPRECATED: Use get_questrade_options() for real exchange data.
        Kept for backwards compatibility with existing routes.
        """
        return await self.alpaca.get_options_chain_alpaca(
            ticker=ticker,
            option_type=option_type,
            expiration=expiration,
            min_strike=min_strike,
            max_strike=max_strike,
            limit=limit,
        )

    # ── Real-Time Market Data (Questrade PRIMARY) ──

    async def get_stock_snapshot(self, ticker: str) -> dict:
        """Full real-time L1 snapshot from Questrade."""
        return await self.questrade.get_quote_raw(ticker)

    async def get_multi_snapshots(self, tickers: list[str]) -> list[dict]:
        """Batch real-time L1 snapshots from Questrade."""
        return await self.questrade.get_quotes(tickers)

    async def get_latest_trade(self, ticker: str) -> dict:
        """Latest trade from Questrade L1 quote."""
        return await self.questrade.get_quote_raw(ticker)

    async def get_alpaca_news(
        self,
        symbols: list[str] | None = None,
        limit: int = 20,
    ) -> list[dict]:
        """Market news from Alpaca, optionally filtered by symbols."""
        return await self.alpaca.get_news(symbols=symbols, limit=limit)

    async def get_most_actives(
        self,
        by: str = "volume",
        top: int = 20,
    ) -> list[dict]:
        """Most active stocks by volume or trade count (Alpaca screener)."""
        return await self.alpaca.get_most_actives(by=by, top=top)

    async def get_account(self) -> dict:
        """Real account info from Questrade: buying power, equity, positions."""
        try:
            accounts = await self.questrade.get_accounts()
            if accounts:
                acct = accounts[0]
                balances = await self.questrade.get_balances(acct.get("number"))
                return {"account": acct, "balances": balances}
        except Exception as e:
            _log.warning("data_engine.questrade_account_failed", error=str(e))
        # Fallback to Alpaca paper account
        return await self.alpaca.get_account()

    async def get_positions(self) -> list[dict]:
        """Open positions from Questrade."""
        try:
            return await self.questrade.get_positions()
        except Exception as e:
            _log.warning("data_engine.questrade_positions_failed", error=str(e))
        return await self.alpaca.get_positions()

    # ── Questrade Plus Features ──

    async def get_account_activities(
        self,
        start_time: str | None = None,
        end_time: str | None = None,
    ) -> list[dict]:
        """Fetch account transaction history from Questrade.

        Returns trades, dividends, deposits, withdrawals, fees, and interest.
        """
        return await self.questrade.get_activities(
            start_time=start_time,
            end_time=end_time,
        )

    async def get_account_executions(
        self,
        start_time: str | None = None,
        end_time: str | None = None,
    ) -> list[dict]:
        """Fetch trade execution (fill) history from Questrade."""
        return await self.questrade.get_executions(
            start_time=start_time,
            end_time=end_time,
        )

    def calculate_options_pnl(
        self,
        legs: list[dict],
        underlying_price: float,
        strategy_name: str = "Custom Strategy",
        price_range_pct: float = 0.30,
    ) -> dict:
        """Calculate P&L curve for a multi-leg options strategy.

        Args:
            legs: List of leg dicts with keys: option_type, strike, premium,
                  quantity, expiration, delta, gamma, theta, vega, iv.
            underlying_price: Current underlying stock price.
            strategy_name: Human-readable strategy label.
            price_range_pct: Price range for the curve (0.30 = ±30%).

        Returns:
            Dict with pnl_curve, max_profit, max_loss, breakevens,
            position Greeks, risk/reward ratio, and probability of profit.
        """
        from app.engines.pnl_calculator import PnLCalculator, OptionLeg

        calc = PnLCalculator()
        option_legs = [
            OptionLeg(
                option_type=leg.get("option_type", "call"),
                strike=float(leg.get("strike", 0)),
                premium=float(leg.get("premium", 0)),
                quantity=int(leg.get("quantity", 1)),
                expiration=leg.get("expiration", ""),
                delta=float(leg.get("delta", 0)),
                gamma=float(leg.get("gamma", 0)),
                theta=float(leg.get("theta", 0)),
                vega=float(leg.get("vega", 0)),
                iv=float(leg.get("iv", 0)),
            )
            for leg in legs
        ]

        result = calc.calculate_pnl(
            legs=option_legs,
            underlying_price=underlying_price,
            price_range_pct=price_range_pct,
            strategy_name=strategy_name,
        )
        return result.to_dict()

    async def rebalance_portfolio(
        self,
        target_allocations: list[dict] | None = None,
    ) -> dict:
        """Analyze portfolio and compute rebalancing trades.

        If target_allocations is None, returns current portfolio analysis.
        If provided, computes buy-only trades to reach target allocation.

        Args:
            target_allocations: List of dicts with ticker, target_pct, sector.
        """
        from app.engines.rebalancer import PortfolioRebalancer, TargetAllocation

        rebalancer = PortfolioRebalancer(questrade_client=self.questrade)

        positions = await self.questrade.get_positions()
        balances = await self.questrade.get_balances()

        targets = None
        if target_allocations:
            targets = [
                TargetAllocation(
                    ticker=t.get("ticker", ""),
                    target_pct=float(t.get("target_pct", 0)),
                    sector=t.get("sector", ""),
                )
                for t in target_allocations
            ]

        result = await rebalancer.analyze_portfolio(
            positions=positions,
            balances=balances,
            target_allocations=targets,
        )
        return result.to_dict()

    async def get_market_heatmap(
        self,
        tickers: list[str] | None = None,
    ) -> dict:
        """Generate market heatmap data using Questrade L1 quotes.

        If tickers not provided, uses a default list of major S&P 500 constituents
        grouped by sector for a broad market view.

        Returns sector-level and stock-level performance data.
        """
        # Default: major S&P 500 constituents by sector
        if not tickers:
            tickers = [
                # Technology
                "AAPL", "MSFT", "NVDA", "GOOGL", "META", "AVGO", "ORCL", "CRM",
                # Healthcare
                "UNH", "JNJ", "LLY", "PFE", "ABBV", "MRK", "TMO", "ABT",
                # Financials
                "BRK.B", "JPM", "V", "MA", "BAC", "WFC", "GS", "MS",
                # Consumer Discretionary
                "AMZN", "TSLA", "HD", "MCD", "NKE", "SBUX", "TGT", "LOW",
                # Energy
                "XOM", "CVX", "COP", "SLB", "EOG", "PSX",
                # Industrials
                "CAT", "GE", "UNP", "HON", "RTX", "BA",
                # Consumer Staples
                "PG", "KO", "PEP", "COST", "WMT", "PM",
                # Communications
                "DIS", "NFLX", "CMCSA", "T", "VZ",
                # Utilities
                "NEE", "DUK", "SO", "D",
                # Real Estate
                "AMT", "PLD", "CCI", "SPG",
            ]

        # Fetch batch quotes from Questrade
        raw_quotes = await self.questrade.get_quotes(tickers)

        # Enrich with sector info and build heatmap
        stocks = []
        sector_map: dict[str, list[dict]] = {}

        for q in raw_quotes:
            symbol = q.get("symbol", "")
            last = q.get("lastTradePrice", 0) or 0
            prev_close = q.get("prevDayClosePrice") or last
            change_pct = ((last - prev_close) / prev_close * 100) if prev_close else 0

            stock_data = {
                "ticker": symbol,
                "price": last,
                "change_pct": round(change_pct, 2),
                "volume": q.get("volume", 0),
                "high": q.get("highPrice", 0),
                "low": q.get("lowPrice", 0),
                "is_halted": q.get("isHalted", False),
            }
            stocks.append(stock_data)

            # Try to get sector from symbol info
            try:
                info = await self.questrade.get_symbol_enriched(symbol)
                sector = info.get("industrySector", "Other") or "Other"
            except Exception:
                sector = "Other"

            stock_data["sector"] = sector
            if sector not in sector_map:
                sector_map[sector] = []
            sector_map[sector].append(stock_data)

        # Calculate sector-level metrics
        sectors = {}
        for sector_name, sector_stocks in sector_map.items():
            avg_change = (
                sum(s["change_pct"] for s in sector_stocks) / len(sector_stocks)
                if sector_stocks
                else 0
            )
            total_volume = sum(s.get("volume", 0) for s in sector_stocks)
            sectors[sector_name] = {
                "avg_change_pct": round(avg_change, 2),
                "total_volume": total_volume,
                "stock_count": len(sector_stocks),
                "stocks": sector_stocks,
            }

        return {
            "source": "questrade",
            "total_stocks": len(stocks),
            "sectors": sectors,
            "stocks": stocks,
        }

    async def get_order_notification_port(self) -> dict:
        """Get WebSocket notification port for real-time order status streaming."""
        return await self.questrade.get_notification_port()

    # ── Questrade Plus Phase 2 — Data Intelligence ──

    async def get_enriched_quote(self, ticker: str) -> dict:
        """Enhanced L1 quote merged with fundamental symbol data.

        Combines real-time L1 quote (VWAP, averageTradeSize, tick, isHalted)
        with symbol fundamentals (PE, EPS, dividend, yield, 52wk range,
        market cap, sector, industry).

        Also computes derived metrics:
          - 52wk_position_pct: where price sits in 52-week range (0-100)
          - volume_vs_avg: ratio of current volume to 3-month average
          - institutional_flag: true if averageTradeSize > 500 shares

        Returns:
            Combined dict with all L1 and symbol fields plus derived metrics.
        """
        from datetime import datetime

        # Fetch both in parallel
        import asyncio
        raw_quote, symbol_info = await asyncio.gather(
            self.questrade.get_quote_raw(ticker),
            self.questrade.get_symbol_enriched(ticker),
        )

        if not raw_quote and not symbol_info:
            return {}

        # Build enriched response
        last_price = raw_quote.get("lastTradePrice", 0) or 0
        high52 = symbol_info.get("highPrice52", 0) or 0
        low52 = symbol_info.get("lowPrice52", 0) or 0
        avg_vol_3m = symbol_info.get("averageVol3Months", 0) or 0
        avg_vol_20d = symbol_info.get("averageVol20Days", 0) or 0
        current_vol = raw_quote.get("volume", 0) or 0
        avg_trade_size = raw_quote.get("averageTradeSize", 0) or 0
        outstanding_shares = symbol_info.get("outstandingShares", 0) or 0

        # Derived metrics
        range_52 = high52 - low52
        position_52wk = (
            round(((last_price - low52) / range_52) * 100, 1)
            if range_52 > 0 else 50.0
        )
        vol_vs_avg = (
            round(current_vol / avg_vol_3m, 2)
            if avg_vol_3m > 0 else 0.0
        )
        market_cap = (
            round(last_price * outstanding_shares, 2)
            if outstanding_shares > 0 else None
        )

        return {
            "ticker": ticker.upper(),
            "source": "questrade",
            "timestamp": datetime.now().isoformat(),

            # L1 Quote Data
            "last_price": last_price,
            "bid": raw_quote.get("bidPrice"),
            "ask": raw_quote.get("askPrice"),
            "bid_size": raw_quote.get("bidSize"),
            "ask_size": raw_quote.get("askSize"),
            "open": raw_quote.get("openPrice"),
            "high": raw_quote.get("highPrice"),
            "low": raw_quote.get("lowPrice"),
            "volume": current_vol,
            "vwap": raw_quote.get("VWAP"),
            "average_trade_size": avg_trade_size,
            "tick": raw_quote.get("tick"),  # "Up" or "Down"
            "is_halted": raw_quote.get("isHalted", False),
            "delay": raw_quote.get("delay", 0),

            # Fundamentals
            "pe": symbol_info.get("pe"),
            "eps": symbol_info.get("eps"),
            "dividend": symbol_info.get("dividend"),
            "yield_pct": symbol_info.get("yield"),
            "ex_date": symbol_info.get("exDate"),
            "pay_date": symbol_info.get("payDate"),
            "market_cap": market_cap,
            "outstanding_shares": outstanding_shares,
            "currency": symbol_info.get("currency"),
            "listing_exchange": symbol_info.get("listingExchange"),
            "security_type": symbol_info.get("securityType"),
            "has_options": symbol_info.get("hasOptions", False),

            # Sector
            "sector": symbol_info.get("industrySector"),
            "industry_group": symbol_info.get("industryGroup"),
            "industry_subgroup": symbol_info.get("industrySubgroup"),

            # Range Data
            "high_52wk": high52,
            "low_52wk": low52,
            "prev_close": symbol_info.get("prevDayClosePrice"),
            "avg_volume_3m": avg_vol_3m,
            "avg_volume_20d": avg_vol_20d,

            # Derived Intelligence
            "position_52wk_pct": position_52wk,
            "volume_vs_avg": vol_vs_avg,
            "institutional_flag": avg_trade_size > 500,
        }

    async def get_dividend_calendar(self) -> dict:
        """Upcoming dividends for all holdings in the portfolio.

        Fetches positions → enriches each with symbol data → extracts
        dividend info (exDate, payDate, yield, dividend amount) → sorts
        by next ex-date.

        Returns:
            List of dividend events with projected annual income.
        """
        import asyncio
        from datetime import datetime

        positions = await self.questrade.get_positions()
        if not positions:
            return {"holdings_with_dividends": [], "total_projected_annual_income": 0}

        dividend_records = []
        for pos in positions:
            ticker = pos.get("symbol", "")
            qty = pos.get("openQuantity", 0)
            if not ticker or qty <= 0:
                continue

            try:
                info = await self.questrade.get_symbol_enriched(ticker)
            except Exception:
                continue

            dividend_amt = info.get("dividend", 0) or 0
            yield_pct = info.get("yield", 0) or 0
            ex_date = info.get("exDate")
            pay_date = info.get("payDate")

            if dividend_amt > 0 or yield_pct > 0:
                current_price = pos.get("currentPrice", 0) or 0
                market_value = pos.get("currentMarketValue", 0) or (current_price * qty)
                annual_income = dividend_amt * qty * 4  # Assume quarterly

                dividend_records.append({
                    "ticker": ticker,
                    "quantity": qty,
                    "current_price": current_price,
                    "market_value": round(market_value, 2),
                    "dividend_per_share": dividend_amt,
                    "yield_pct": round(yield_pct, 2),
                    "ex_date": ex_date,
                    "pay_date": pay_date,
                    "projected_annual_income": round(annual_income, 2),
                    "projected_quarterly_income": round(annual_income / 4, 2),
                    "currency": info.get("currency", "USD"),
                })

        # Sort by ex_date (soonest first), putting None dates last
        dividend_records.sort(
            key=lambda d: d["ex_date"] or "9999-12-31"
        )

        total_annual = sum(d["projected_annual_income"] for d in dividend_records)

        return {
            "holdings_with_dividends": dividend_records,
            "total_holdings": len(dividend_records),
            "total_projected_annual_income": round(total_annual, 2),
            "total_projected_monthly_income": round(total_annual / 12, 2),
            "generated_at": datetime.now().isoformat(),
        }

    async def get_portfolio_performance(self) -> dict:
        """Comprehensive portfolio P&L: unrealized, realized, dividends, commissions.

        Combines:
          - Positions → unrealized P&L
          - Activities (type=Trades) → realized gains/losses
          - Activities (type=Dividends) → dividend income
          - Activities (commissions) → total trading costs

        Returns:
            Full performance breakdown with totals and per-position detail.
        """
        import asyncio
        from datetime import datetime, timedelta

        # Fetch positions and recent activities in parallel
        positions, activities = await asyncio.gather(
            self.questrade.get_positions(),
            self.questrade.get_activities(),
        )

        # ── Unrealized P&L (from positions)
        unrealized_pnl = 0.0
        position_details = []
        for pos in positions:
            ticker = pos.get("symbol", "")
            qty = pos.get("openQuantity", 0)
            avg_cost = pos.get("averageEntryPrice", 0) or 0
            current_price = pos.get("currentPrice", 0) or 0
            current_value = pos.get("currentMarketValue", 0) or (current_price * qty)
            cost_basis = avg_cost * qty
            pnl = current_value - cost_basis
            pnl_pct = (pnl / cost_basis * 100) if cost_basis > 0 else 0

            unrealized_pnl += pnl
            position_details.append({
                "ticker": ticker,
                "quantity": qty,
                "avg_cost": round(avg_cost, 4),
                "current_price": round(current_price, 2),
                "cost_basis": round(cost_basis, 2),
                "market_value": round(current_value, 2),
                "unrealized_pnl": round(pnl, 2),
                "unrealized_pnl_pct": round(pnl_pct, 2),
            })

        # ── Realized P&L + Dividends + Commissions (from activities)
        realized_pnl = 0.0
        total_dividends = 0.0
        total_commissions = 0.0
        total_fees = 0.0
        total_deposits = 0.0
        total_withdrawals = 0.0

        for act in activities:
            act_type = (act.get("type", "") or "").lower()
            net_amount = act.get("netAmount", 0) or 0
            commission = abs(act.get("commission", 0) or 0)

            if act_type == "trades":
                realized_pnl += net_amount
                total_commissions += commission
            elif act_type == "dividends":
                total_dividends += net_amount
            elif act_type == "fees":
                total_fees += abs(net_amount)
            elif act_type == "deposits":
                total_deposits += net_amount
            elif act_type == "withdrawals":
                total_withdrawals += abs(net_amount)

        net_performance = unrealized_pnl + realized_pnl + total_dividends - total_commissions - total_fees

        return {
            "summary": {
                "total_unrealized_pnl": round(unrealized_pnl, 2),
                "total_realized_pnl": round(realized_pnl, 2),
                "total_dividends": round(total_dividends, 2),
                "total_commissions": round(total_commissions, 2),
                "total_fees": round(total_fees, 2),
                "net_performance": round(net_performance, 2),
                "total_deposits": round(total_deposits, 2),
                "total_withdrawals": round(total_withdrawals, 2),
            },
            "positions": position_details,
            "position_count": len(position_details),
            "activity_count": len(activities),
            "generated_at": datetime.now().isoformat(),
        }

    async def get_currency_exposure(self) -> dict:
        """Portfolio currency breakdown — CAD vs USD (and any other).

        Groups all positions by currency and calculates total market value,
        percentage allocation, and per-position breakdown per currency.

        Returns:
            Currency-level aggregation with totals and percentages.
        """
        import asyncio
        from datetime import datetime

        positions = await self.questrade.get_positions()
        balances = await self.questrade.get_balances()

        currency_map: dict[str, list[dict]] = {}
        total_value = 0.0

        for pos in positions:
            ticker = pos.get("symbol", "")
            qty = pos.get("openQuantity", 0)
            current_price = pos.get("currentPrice", 0) or 0
            market_value = pos.get("currentMarketValue", 0) or (current_price * qty)

            # Get currency from symbol info
            try:
                info = await self.questrade.get_symbol_enriched(ticker)
                currency = info.get("currency", "USD")
            except Exception:
                currency = "USD"

            if currency not in currency_map:
                currency_map[currency] = []

            currency_map[currency].append({
                "ticker": ticker,
                "quantity": qty,
                "market_value": round(market_value, 2),
                "current_price": round(current_price, 2),
            })
            total_value += market_value

        # Build currency summary
        currencies = {}
        for curr, holdings in currency_map.items():
            curr_total = sum(h["market_value"] for h in holdings)
            currencies[curr] = {
                "total_market_value": round(curr_total, 2),
                "allocation_pct": round((curr_total / total_value * 100) if total_value > 0 else 0, 2),
                "position_count": len(holdings),
                "positions": holdings,
            }

        # Extract cash balances by currency
        cash_by_currency = {}
        for bal_group in balances.get("perCurrencyBalances", []):
            curr = bal_group.get("currency", "USD")
            cash_by_currency[curr] = {
                "cash": bal_group.get("cash", 0),
                "buying_power": bal_group.get("buyingPower", 0),
                "total_equity": bal_group.get("totalEquity", 0),
            }

        return {
            "total_portfolio_value": round(total_value, 2),
            "currencies": currencies,
            "cash_balances": cash_by_currency,
            "generated_at": datetime.now().isoformat(),
        }

    async def get_market_status(self) -> dict:
        """Trading hours and open/closed status for all exchanges.

        Enriches the markets endpoint with current-time comparison to
        determine if each exchange is currently in pre-market, regular
        trading, after-hours, or closed.

        Returns:
            List of markets with status, hours, and next transition time.
        """
        from datetime import datetime
        import pytz

        markets = await self.questrade.get_markets()
        server_time = await self.questrade.get_server_time()

        now_str = server_time.get("time", "")
        try:
            now = datetime.fromisoformat(now_str.replace("Z", "+00:00"))
        except Exception:
            now = datetime.now(pytz.utc)

        enriched_markets = []
        for mkt in markets:
            name = mkt.get("name", "")

            # Parse trading hours
            extended_start = mkt.get("extendedStartTime", "")
            start_time = mkt.get("startTime", "")
            end_time = mkt.get("endTime", "")
            extended_end = mkt.get("extendedEndTime", "")

            # Determine status
            status = "closed"
            try:
                def parse_time(t: str) -> datetime | None:
                    if not t:
                        return None
                    try:
                        return datetime.fromisoformat(t.replace("Z", "+00:00"))
                    except Exception:
                        return None

                ext_start = parse_time(extended_start)
                reg_start = parse_time(start_time)
                reg_end = parse_time(end_time)
                ext_end = parse_time(extended_end)

                if reg_start and reg_end and reg_start <= now <= reg_end:
                    status = "open"
                elif ext_start and reg_start and ext_start <= now < reg_start:
                    status = "pre_market"
                elif reg_end and ext_end and reg_end < now <= ext_end:
                    status = "after_hours"
            except Exception:
                pass

            enriched_markets.append({
                "name": name,
                "status": status,
                "exchange_id": mkt.get("exchangeId"),
                "default_trading_venue": mkt.get("defaultTradingVenue"),
                "extended_start_time": extended_start,
                "start_time": start_time,
                "end_time": end_time,
                "extended_end_time": extended_end,
                "snap_quotes_limit": mkt.get("snapQuotesLimit"),
            })

        return {
            "server_time": now_str,
            "markets": enriched_markets,
            "generated_at": datetime.now().isoformat(),
        }

    async def get_order_impact_preview(
        self,
        ticker: str,
        quantity: int,
        action: str = "Buy",
        order_type: str = "Market",
        limit_price: float | None = None,
    ) -> dict:
        """Preview the impact of a single-leg order before placing.

        Resolves ticker → symbolId, then calls Questrade's order impact
        endpoint for estimated commissions, buying power effect, etc.

        Args:
            ticker: Symbol to preview (e.g. 'AAPL').
            quantity: Number of shares.
            action: 'Buy' or 'Sell'.
            order_type: 'Market', 'Limit', 'StopLimit', etc.
            limit_price: Required for Limit/StopLimit orders.

        Returns:
            Impact preview with estimated cost and commission.
        """
        sid = await self.questrade.resolve_symbol_id(ticker)
        if not sid:
            return {"error": f"Symbol not found: {ticker}"}

        order = {
            "symbolId": sid,
            "quantity": quantity,
            "orderType": order_type,
            "timeInForce": "Day",
            "action": action,
        }
        if limit_price is not None:
            order["limitPrice"] = limit_price

        try:
            impact = await self.questrade.get_order_impact(order)
            return {
                "ticker": ticker.upper(),
                "action": action,
                "quantity": quantity,
                "order_type": order_type,
                "limit_price": limit_price,
                "impact": impact,
            }
        except Exception as e:
            return {
                "ticker": ticker.upper(),
                "error": str(e),
            }



    async def get_optionstrats_flow(
        self,
        ticker: Optional[str] = None,
        min_premium: int = 50_000,
        limit: int = 50,
    ) -> list[dict]:
        """Scraped options flow from OptionStrats.

        Provides complex strategy classification (spreads, condors, etc.)
        that QuantData does not offer.
        """
        try:
            return await self._safe_call(
                "optionstrats",
                lambda: self.optionstrats.get_flow(
                    ticker=ticker, min_premium=min_premium, limit=limit,
                ),
                fallback=[],
            )
        except Exception as exc:
            _log.warning("data_engine.optionstrats_flow_error", error=str(exc))
            return []

    async def get_optionstrats_iv(self, ticker: str) -> dict:
        """Scraped IV surface data from OptionStrats.

        Provides per-expiration IV adjustments and IV history
        that Alpaca's indicative Greeks don't cover.
        """
        try:
            return await self._safe_call(
                "optionstrats",
                lambda: self.optionstrats.get_iv_surface(ticker),
                fallback={},
            )
        except Exception as exc:
            _log.warning("data_engine.optionstrats_iv_error", error=str(exc), ticker=ticker)
            return {}

    async def get_congressional_flow(self, limit: int = 25) -> list[dict]:
        """Congressional trading activity from OptionStrats."""
        try:
            return await self._safe_call(
                "optionstrats",
                lambda: self.optionstrats.get_congressional_flow(limit=limit),
                fallback=[],
            )
        except Exception as exc:
            _log.warning("data_engine.congress_flow_error", error=str(exc))
            return []

    # ── QuantData Extended (News, Drift, Exposure, Vol) ──

    async def get_quantdata_news(
        self,
        ticker: Optional[str] = None,
        topic: Optional[str] = None,
        limit: int = 50,
    ) -> list[dict]:
        """Market news from QuantData — real-time, filterable by ticker/topic."""
        try:
            return await self._safe_call(
                "quantdata",
                lambda: self.quantdata.get_news(ticker=ticker, topic=topic, limit=limit),
                fallback=[],
            )
        except Exception as exc:
            _log.warning("data_engine.quantdata_news_error", error=str(exc))
            return []

    async def get_net_drift(
        self,
        ticker: Optional[str] = None,
        date: Optional[str] = None,
    ) -> dict | list:
        """Net drift — call/put premium imbalance (local yFinance proxy)."""
        if ticker:
            try:
                result = await self.local_analytics.compute_net_flow_proxy(ticker)
                if result and result.get("net_premium", 0) != 0:
                    return result
            except Exception as exc:
                _log.debug("data_engine.local_net_drift_fallback", error=str(exc))
        return await self._safe_call(
            "quantdata",
            lambda: self.quantdata.get_net_drift(ticker=ticker, date=date),
            fallback=[],
        )

    async def get_net_flow(
        self,
        ticker: Optional[str] = None,
        limit: int = 50,
    ) -> list[dict]:
        """Net flow — call vs put premium (local yFinance proxy)."""
        if ticker:
            try:
                result = await self.local_analytics.compute_net_flow_proxy(ticker, limit=limit)
                if result and result.get("top_contracts"):
                    return result.get("top_contracts", [])  # type: ignore[return-value]
            except Exception as exc:
                _log.debug("data_engine.local_net_flow_fallback", error=str(exc))
        return await self._safe_call(
            "quantdata",
            lambda: self.quantdata.get_net_flow(ticker=ticker, limit=limit),
            fallback=[],
        )

    async def get_dark_flow(
        self,
        ticker: Optional[str] = None,
        limit: int = 25,
    ) -> list[dict]:
        """Dark flow — large off-exchange institutional activity."""
        return await self._safe_call(
            "quantdata",
            lambda: self.quantdata.get_dark_flow(ticker=ticker, limit=limit),
            fallback=[],
        )

    async def get_options_exposure(
        self,
        ticker: str,
        exposure_type: str = "gex",
        expiration: Optional[str] = None,
    ) -> dict | list:
        """Options exposure — dealer positioning (local yFinance computation)."""
        try:
            result = await self.local_analytics.compute_gex_exposure(
                ticker=ticker, exposure_type=exposure_type, expiration=expiration,
            )
            if result and result.get("data"):
                return result
        except Exception as exc:
            _log.debug("data_engine.local_exposure_fallback", error=str(exc))
        return await self._safe_call(
            "quantdata",
            lambda: self.quantdata.get_options_exposure(
                ticker=ticker, exposure_type=exposure_type, expiration=expiration,
            ),
            fallback=[],
        )

    async def get_heat_map(
        self,
        ticker: str,
        metric: str = "gex",
        expiration: Optional[str] = None,
    ) -> dict | list:
        """Options heat map — strike × expiry grid (local yFinance computation)."""
        try:
            result = await self.local_analytics.compute_options_heatmap(
                ticker=ticker, metric=metric, expiration=expiration,
            )
            if result and result.get("grid"):
                return result
        except Exception as exc:
            _log.debug("data_engine.local_heatmap_fallback", error=str(exc))
        return await self._safe_call(
            "quantdata",
            lambda: self.quantdata.get_heat_map(
                ticker=ticker, metric=metric, expiration=expiration,
            ),
            fallback=[],
        )

    async def get_volatility_drift(
        self,
        ticker: str,
        date: Optional[str] = None,
    ) -> dict | list:
        """Volatility drift — IV term structure (local yFinance computation)."""
        try:
            result = await self.local_analytics.compute_vol_surface(ticker, date=date)
            if result and result.get("term_structure"):
                return result
        except Exception as exc:
            _log.debug("data_engine.local_vol_drift_fallback", error=str(exc))
        return await self._safe_call(
            "quantdata",
            lambda: self.quantdata.get_volatility_drift(ticker=ticker, date=date),
            fallback=[],
        )

    async def get_volatility_skew(
        self,
        ticker: str,
        expiration: Optional[str] = None,
    ) -> dict | list:
        """Volatility skew — IV across strikes (local yFinance computation)."""
        try:
            result = await self.local_analytics.compute_vol_skew(
                ticker=ticker, expiration=expiration,
            )
            if result and result.get("skew"):
                return result
        except Exception as exc:
            _log.debug("data_engine.local_vol_skew_fallback", error=str(exc))
        return await self._safe_call(
            "quantdata",
            lambda: self.quantdata.get_volatility_skew(
                ticker=ticker, expiration=expiration,
            ),
            fallback=[],
        )

    async def get_gainers_losers(
        self,
        direction: str = "bullish",
        limit: int = 25,
    ) -> list[dict]:
        """Gainers/losers by options premium (local yFinance computation)."""
        try:
            result = await self.local_analytics.compute_gainers_losers(
                direction=direction, limit=limit,
            )
            if result:
                return result
        except Exception as exc:
            _log.debug("data_engine.local_gainers_losers_fallback", error=str(exc))
        return await self._safe_call(
            "quantdata",
            lambda: self.quantdata.get_gainers_losers(
                direction=direction, limit=limit,
            ),
            fallback=[],
        )

    # ── Combined News (Alpaca + Finnhub + QuantData) ──

    async def get_combined_news(
        self,
        ticker: Optional[str] = None,
        limit: int = 50,
    ) -> dict:
        """Merge news from available news sources into one unified feed.

        Sources:
          1. Finnhub — company + general market news
          2. QuantData — real-time market-relevant news
          3. OpenBB — multi-provider aggregated news (benzinga, biztoc, tiingo, yfinance)

        Note: Alpaca 'feed' is the SIP price data tier, not a news source.
        Deduplicates by headline similarity and returns tagged entries.
        """
        import asyncio

        # Fetch from all news sources in parallel
        finnhub_task = self._safe_call(
            "finnhub",
            lambda: self.finnhub.get_company_news(ticker) if ticker else [],
            fallback=[],
        )
        # QuantData news removed — no API key configured.
        # Finnhub + OpenBB provide sufficient coverage.
        async def _no_quantdata_news():
            return []
        quantdata_task = _no_quantdata_news()

        # OpenBB news — run synchronously in executor to avoid blocking
        async def _openbb_news():
            try:
                from app.data.openbb_client import OpenBBClient
                obc = OpenBBClient()
                if ticker:
                    data = obc.get_company_news_dedicated(ticker, limit=limit)
                else:
                    data = obc.get_world_news(limit=limit)
                if data and data.get("articles"):
                    return data["articles"]
            except Exception as e:
                log.debug("openbb_news_in_combined_skip", error=str(e))
            return []

        finnhub_news, qd_news, openbb_news = await asyncio.gather(
            finnhub_task, quantdata_task, _openbb_news(),
        )

        # Tag all entries with their source
        for n in finnhub_news:
            n["source"] = n.get("source", "finnhub")
        for n in qd_news:
            n["source"] = n.get("source", "quantdata")
        for n in openbb_news:
            n["source"] = n.get("source", "openbb")

        # Simple dedup by headline (lowercase, stripped)
        # QuantData first — tends to be most real-time
        # then OpenBB — multi-provider, richest
        # then Finnhub — solid baseline
        seen_headlines = set()
        merged = []
        for entry in [*qd_news, *openbb_news, *finnhub_news]:
            headline = entry.get("headline", entry.get("title", "")).lower().strip()
            if headline and headline not in seen_headlines:
                seen_headlines.add(headline)
                merged.append(entry)

        return {
            "news": merged[:limit],
            "sources": {
                "finnhub": len(finnhub_news),
                "quantdata": len(qd_news),
                "openbb": len(openbb_news),
                "merged_total": len(merged),
            },
        }

    # ── Combined / Merged Sources ──

    async def get_combined_flow(
        self,
        ticker: Optional[str] = None,
        min_premium: int = 50_000,
    ) -> dict:
        """Merge options flow from QuantData + OptionStrats.

        Deduplicates by contract symbol + timestamp proximity (within 5s).
        QuantData entries are preferred when duplicates are detected
        because they come from a proper API with exact timestamps.

        Returns:
            Dict with 'quantdata_flow', 'optionstrats_flow', 'merged' lists,
            and 'sources' metadata.
        """
        import asyncio

        qd_task = self.get_options_flow(ticker=ticker, min_premium=min_premium)
        os_task = self.get_optionstrats_flow(
            ticker=ticker, min_premium=min_premium,
        )

        qd_flow, os_flow = await asyncio.gather(qd_task, os_task)

        # Tag source
        for entry in qd_flow:
            entry["source"] = entry.get("source", "quantdata")
        for entry in os_flow:
            entry["source"] = entry.get("source", "optionstrats")

        # Merge with QuantData priority (API > scraper)
        merged = list(qd_flow)  # QuantData first
        qd_symbols = {
            (e.get("contract_symbol", ""), e.get("symbol", ""))
            for e in qd_flow
        }

        for entry in os_flow:
            key = (entry.get("contract_symbol", ""), entry.get("ticker", ""))
            if key not in qd_symbols:
                merged.append(entry)

        return {
            "quantdata_flow": qd_flow,
            "optionstrats_flow": os_flow,
            "merged": merged,
            "sources": {
                "quantdata": len(qd_flow),
                "optionstrats": len(os_flow),
                "merged_total": len(merged),
            },
        }

    # ── TradingView — SIP-Level Real-Time Data ──

    async def get_tv_realtime_quote(
        self,
        ticker: str,
    ) -> Optional[dict]:
        """Real-time SIP-level quote from TradingView (paid subscription).

        Includes OHLCV, bid/ask, VWAP, extended hours, and price ranges.
        """
        return await self._safe_call(
            "tradingview",
            lambda: self.tradingview.get_realtime_quote(ticker=ticker),
            fallback=None,
        )

    async def get_tv_batch_quotes(
        self,
        tickers: list[str],
    ) -> list[dict]:
        """Batch real-time quotes for multiple tickers in one call."""
        return await self._safe_call(
            "tradingview",
            lambda: self.tradingview.get_batch_quotes(tickers=tickers),
            fallback=[],
        )

    async def get_tv_financials(
        self,
        ticker: str,
    ) -> Optional[dict]:
        """Full financials — revenue, margins, debt, FCF, valuation ratios.

        Fills gaps that Alpaca doesn't provide.
        """
        return await self._safe_call(
            "tradingview",
            lambda: self.tradingview.get_financials(ticker=ticker),
            fallback=None,
        )

    async def get_tv_earnings_calendar(
        self,
        limit: int = 50,
        upcoming_only: bool = True,
    ) -> list[dict]:
        """Upcoming earnings dates — not available from Alpaca or QuantData."""
        return await self._safe_call(
            "tradingview",
            lambda: self.tradingview.get_earnings_calendar(
                limit=limit, upcoming_only=upcoming_only,
            ),
            fallback=[],
        )

    async def get_tv_short_interest(
        self,
        limit: int = 25,
    ) -> list[dict]:
        """Short squeeze scanner — not available from Alpaca or QuantData."""
        return await self._safe_call(
            "tradingview",
            lambda: self.tradingview.get_short_interest(limit=limit),
            fallback=[],
        )

    async def get_tv_sector_performance(
        self,
        top_per_sector: int = 5,
    ) -> dict:
        """Sector-level aggregated performance with top movers per sector."""
        return await self._safe_call(
            "tradingview",
            lambda: self.tradingview.get_sector_performance(
                top_per_sector=top_per_sector,
            ),
            fallback={"sectors": {}, "source": "tradingview"},
        )

    # ── OptionStrats — iframe URLs + Scraped Insider Data ──

    def get_optionstrats_urls(
        self,
        ticker: str,
        strategy: Optional[str] = None,
    ) -> dict:
        """Deep-link URLs for OptionStrats pages.

        Frontend embeds these via iframe or opens in new tab.
        Includes Optimizer, Builder, info pages, and all flow tabs.
        """
        return self.optionstrats.get_optionstrats_urls(
            ticker=ticker, strategy=strategy,
        )

    async def get_insider_flow(
        self,
        ticker: Optional[str] = None,
        limit: int = 50,
    ) -> list[dict]:
        """SEC insider trading from OptionStrats.

        Unique data source — scraped every 15 min by Celery, cached in Redis.
        LLM reads from cache for near-zero latency.
        """
        return await self._safe_call(
            "optionstrats",
            lambda: self.optionstrats.get_insider_flow(
                ticker=ticker, limit=limit,
            ),
            fallback=[],
        )

    def get_strategy_catalog(self) -> dict:
        """Static catalog of 50+ options strategy types by skill level."""
        from app.data.optionstrats_scraper import STRATEGY_CATALOG
        return STRATEGY_CATALOG

    # ──────────────────────────────────────────────
    # Phase 6: Enhanced Data Access
    # ──────────────────────────────────────────────

    async def get_fear_greed_detailed(self) -> FearGreedDetailed:
        """F&G with all 7 sub-indicators."""
        return await self._safe_call(
            "fear_greed",
            lambda: self.fear_greed.get_detailed(),
            fallback=FearGreedDetailed(value=50, label="neutral"),
        )

    async def get_earnings_estimates(self, ticker: str, freq: str = "quarterly") -> list[dict]:
        """Forward EPS estimates from Finnhub."""
        return await self._safe_call(
            "finnhub",
            lambda: self.finnhub.get_earnings_estimates(ticker, freq),
            fallback=[],
        )

    async def get_price_target(self, ticker: str) -> dict:
        """Analyst price target consensus."""
        return await self._safe_call(
            "finnhub",
            lambda: self.finnhub.get_price_target(ticker),
            fallback={},
        )

    async def get_basic_financials(self, ticker: str) -> dict:
        """100+ fundamental metrics from Finnhub."""
        return await self._safe_call(
            "finnhub",
            lambda: self.finnhub.get_basic_financials(ticker),
            fallback={},
        )

    async def get_insider_sentiment(self, ticker: str) -> dict:
        """Monthly insider purchase sentiment ratio from Finnhub."""
        return await self._safe_call(
            "finnhub",
            lambda: self.finnhub.get_insider_sentiment(ticker),
            fallback={},
        )

    async def get_earnings_transcripts(
        self,
        ticker: str,
        quarter: Optional[int] = None,
        year: Optional[int] = None,
    ) -> dict:
        """Earnings call transcripts from Finnhub."""
        return await self._safe_call(
            "finnhub",
            lambda: self.finnhub.get_earnings_transcripts(ticker, quarter, year),
            fallback={},
        )

    def get_multi_year_financials(self, ticker: str, years: int = 5) -> list[dict]:
        """Multi-year XBRL financials from EDGAR 10-K filings."""
        try:
            return self.edgar.get_multi_year_financials(ticker, years)
        except Exception as e:
            _log.warning("data_engine.multi_year_error", ticker=ticker, error=str(e))
            return []

    def get_quarterly_financials(self, ticker: str, quarters: int = 8) -> list[dict]:
        """Quarterly XBRL financials from EDGAR 10-Q filings."""
        try:
            return self.edgar.get_quarterly_financials(ticker, quarters)
        except Exception as e:
            _log.warning("data_engine.quarterly_error", ticker=ticker, error=str(e))
            return []

    async def get_dd_posts(
        self,
        ticker: str,
        subreddit: str = "wallstreetbets",
        limit: int = 15,
    ) -> list[dict]:
        """WSB Due Diligence tagged posts."""
        return await self._safe_call(
            "wsb",
            lambda: self.wsb.get_dd_posts(ticker, subreddit, limit),
            fallback=[],
        )

    async def get_quality_mentions(
        self,
        ticker: str,
        min_score: int = 50,
        min_comments: int = 10,
    ) -> list[dict]:
        """High-quality WSB mentions filtered by score/engagement."""
        return await self._safe_call(
            "wsb",
            lambda: self.wsb.get_quality_mentions(
                ticker, min_score=min_score, min_comments=min_comments,
            ),
            fallback=[],
        )

    async def get_corporate_actions(
        self,
        ticker: str,
        types: Optional[list[str]] = None,
    ) -> list[dict]:
        """Corporate actions (splits, dividends, mergers) from Alpaca."""
        return await self._safe_call(
            "alpaca",
            lambda: self.alpaca.get_corporate_actions(ticker, types=types),
            fallback=[],
        )

    async def get_economic_series(self, series_id: str, limit: int = 100) -> dict:
        """FRED economic data series."""
        return await self._safe_call(
            "fred",
            lambda: self.fred.get_series(series_id, limit=limit),
            fallback={"error": "FRED unavailable"},
        )

    async def get_treasury_yields(self) -> dict:
        """Treasury yields (2Y, 10Y, 30Y) and yield curve spread."""
        return await self._safe_call(
            "fred",
            lambda: self.fred.get_treasury_yields(),
            fallback={},
        )

    async def get_economic_dashboard(self) -> dict:
        """Macro snapshot: GDP, unemployment, CPI, Fed rate, yields."""
        return await self._safe_call(
            "fred",
            lambda: self.fred.get_economic_dashboard(),
            fallback={},
        )

    def run_backtest(
        self,
        strategy: str,
        ticker: str,
        period: str = "2y",
        **kwargs,
    ) -> dict:
        """Run a backtest strategy via VectorBT.

        Strategies: 'sma_crossover', 'rsi', 'macd', 'compare'
        """
        if not self.backtest.is_available:
            return {"error": "VectorBT not installed. Install with: pip install .[backtest]"}

        try:
            if strategy == "sma_crossover":
                result = self.backtest.run_sma_crossover(
                    ticker,
                    fast=kwargs.get("fast", 10),
                    slow=kwargs.get("slow", 50),
                    period=period,
                )
            elif strategy == "rsi":
                result = self.backtest.run_rsi_strategy(
                    ticker,
                    rsi_window=kwargs.get("rsi_window", 14),
                    overbought=kwargs.get("overbought", 70),
                    oversold=kwargs.get("oversold", 30),
                    period=period,
                )
            elif strategy == "macd":
                result = self.backtest.run_macd_strategy(
                    ticker,
                    fast=kwargs.get("fast", 12),
                    slow=kwargs.get("slow", 26),
                    signal=kwargs.get("signal", 9),
                    period=period,
                )
            elif strategy == "compare":
                results = self.backtest.compare_strategies(ticker, period=period)
                return {"strategies": [r.model_dump() for r in results]}
            else:
                return {"error": f"Unknown strategy: {strategy}"}

            return result.model_dump()
        except Exception as e:
            _log.warning("data_engine.backtest_error", strategy=strategy, error=str(e))
            return {"error": str(e)}

    # ── Phase 3: StockTwits Sentiment ──

    def get_stocktwits_sentiment(self, ticker: str) -> dict:
        """Fetch StockTwits social sentiment for a ticker.

        Uses the free StockTwits API (200 req/hr).
        Returns bullish/bearish message counts and trending status.

        Args:
            ticker: Stock ticker symbol (e.g. 'AAPL').

        Returns:
            Dict with sentiment breakdown, message count, and trending flag.
        """
        import requests

        url = f"https://api.stocktwits.com/api/2/streams/symbol/{ticker.upper()}.json"

        try:
            resp = requests.get(url, timeout=10, headers={"User-Agent": "BubbyVision/1.0"})
            resp.raise_for_status()
            data = resp.json()

            symbol_info = data.get("symbol", {})
            messages = data.get("messages", [])

            bullish = 0
            bearish = 0
            total = len(messages)

            for msg in messages:
                sentiment = msg.get("entities", {}).get("sentiment", {})
                if sentiment:
                    basic = sentiment.get("basic", "")
                    if basic == "Bullish":
                        bullish += 1
                    elif basic == "Bearish":
                        bearish += 1

            # Compute sentiment ratio
            total_sentiment = bullish + bearish
            bullish_pct = round(bullish / total_sentiment * 100, 1) if total_sentiment > 0 else 50.0
            bearish_pct = round(bearish / total_sentiment * 100, 1) if total_sentiment > 0 else 50.0

            return {
                "ticker": ticker.upper(),
                "source": "stocktwits",
                "total_messages": total,
                "bullish_count": bullish,
                "bearish_count": bearish,
                "bullish_pct": bullish_pct,
                "bearish_pct": bearish_pct,
                "sentiment": (
                    "bullish" if bullish_pct > 60
                    else "bearish" if bearish_pct > 60
                    else "neutral"
                ),
                "trending": symbol_info.get("is_following", False),
                "watchlist_count": symbol_info.get("watchlist_count", 0),
            }

        except Exception as e:
            _log.warning("data_engine.stocktwits_error", ticker=ticker, error=str(e))
            return {
                "ticker": ticker.upper(),
                "source": "stocktwits",
                "status": "error",
                "error": str(e),
            }

