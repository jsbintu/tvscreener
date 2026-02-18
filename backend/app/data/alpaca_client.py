"""
Bubby Vision — Alpaca Markets Data Client

Provides real-time / historical market data and market calendar via Alpaca API.
Paper trading mode by default.

Free tier: IEX feed (~8-10% market volume).
Algo Trader Plus ($99/mo): Full SIP feed (100% market coverage).
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional

import httpx

from app.config import get_settings
from app.models import OHLCV, StockQuote


_DATA_URL = "https://data.alpaca.markets/v2"
_PAPER_URL = "https://paper-api.alpaca.markets/v2"


class AlpacaClient:
    """Wrapper around Alpaca Markets API."""

    def __init__(self):
        settings = get_settings()
        self._api_key = settings.alpaca_api_key
        self._secret_key = settings.alpaca_secret_key
        self._is_paper = settings.alpaca_paper
        self._feed = settings.alpaca_feed  # 'iex' (free), 'sip' (paid), 'delayed_sip'
        self._options_feed = "opra" if self._feed == "sip" else "indicative"
        self._headers = {
            "APCA-API-KEY-ID": self._api_key,
            "APCA-API-SECRET-KEY": self._secret_key,
        }

    @property
    def _is_configured(self) -> bool:
        return bool(self._api_key and self._secret_key)

    async def get_latest_quote(self, ticker: str) -> Optional[StockQuote]:
        """Fetch latest quote for a ticker."""
        if not self._is_configured:
            return None

        async with httpx.AsyncClient(headers=self._headers, timeout=10) as client:
            resp = await client.get(
                f"{_DATA_URL}/stocks/{ticker.upper()}/quotes/latest",
            )
            resp.raise_for_status()
            data = resp.json()

        quote_data = data.get("quote", {})
        return StockQuote(
            ticker=ticker.upper(),
            price=(quote_data.get("ap", 0) + quote_data.get("bp", 0)) / 2,  # midpoint
            change=0.0,
            change_pct=0.0,
            volume=0,
        )

    async def get_bars(
        self,
        ticker: str,
        timeframe: str = "1Day",
        limit: int = 100,
        start: Optional[str] = None,
    ) -> list[OHLCV]:
        """Fetch historical bars."""
        if not self._is_configured:
            return []

        params = {
            "timeframe": timeframe,
            "limit": limit,
        }
        if start:
            params["start"] = start

        async with httpx.AsyncClient(headers=self._headers, timeout=10) as client:
            resp = await client.get(
                f"{_DATA_URL}/stocks/{ticker.upper()}/bars",
                params=params,
            )
            resp.raise_for_status()
            data = resp.json()

        bars = []
        for bar in data.get("bars", []):
            bars.append(
                OHLCV(
                    timestamp=datetime.fromisoformat(bar["t"].replace("Z", "+00:00")),
                    open=bar["o"],
                    high=bar["h"],
                    low=bar["l"],
                    close=bar["c"],
                    volume=bar["v"],
                )
            )
        return bars

    async def get_market_calendar(
        self,
        days_ahead: int = 30,
    ) -> list[dict]:
        """Fetch market calendar (trading days, early close, etc.)."""
        if not self._is_configured:
            return []

        base = _PAPER_URL if self._is_paper else "https://api.alpaca.markets/v2"
        start = datetime.utcnow().strftime("%Y-%m-%d")
        end = (datetime.utcnow() + timedelta(days=days_ahead)).strftime("%Y-%m-%d")

        async with httpx.AsyncClient(headers=self._headers, timeout=10) as client:
            resp = await client.get(
                f"{base}/calendar",
                params={"start": start, "end": end},
            )
            resp.raise_for_status()
            return resp.json()

    async def get_market_clock(self) -> dict:
        """Fetch current market status (open/closed, next open/close times)."""
        if not self._is_configured:
            return {"error": "Alpaca API not configured"}

        base = _PAPER_URL if self._is_paper else "https://api.alpaca.markets/v2"

        async with httpx.AsyncClient(headers=self._headers, timeout=10) as client:
            resp = await client.get(f"{base}/clock")
            resp.raise_for_status()
            return resp.json()

    # ── Options Data (v1beta1) ──

    async def get_options_snapshot(
        self,
        ticker: str,
        feed: Optional[str] = None,
        option_type: Optional[str] = None,
        expiration_date: Optional[str] = None,
        expiration_date_gte: Optional[str] = None,
        expiration_date_lte: Optional[str] = None,
        strike_price_gte: Optional[float] = None,
        strike_price_lte: Optional[float] = None,
        limit: int = 100,
    ) -> dict:
        """Fetch full options chain snapshot with Greeks from Alpaca.

        Returns latest trade, latest quote, and Greeks (delta, gamma,
        theta, vega, rho) for each contract.

        Args:
            ticker: Underlying symbol (e.g. AAPL, SPY).
            feed: Data feed — 'indicative' (free) or 'opra' (paid).
            option_type: Filter by 'call' or 'put'.
            expiration_date: Exact expiration (YYYY-MM-DD).
            expiration_date_gte: Expiration on or after (YYYY-MM-DD).
            expiration_date_lte: Expiration on or before (YYYY-MM-DD).
            strike_price_gte: Minimum strike price.
            strike_price_lte: Maximum strike price.
            limit: Max contracts to return (up to 1000).
        """
        if not self._is_configured:
            return {"error": "Alpaca API not configured"}

        params: dict = {"feed": feed or self._options_feed, "limit": min(limit, 1000)}
        if option_type:
            params["type"] = option_type
        if expiration_date:
            params["expiration_date"] = expiration_date
        if expiration_date_gte:
            params["expiration_date_gte"] = expiration_date_gte
        if expiration_date_lte:
            params["expiration_date_lte"] = expiration_date_lte
        if strike_price_gte is not None:
            params["strike_price_gte"] = str(strike_price_gte)
        if strike_price_lte is not None:
            params["strike_price_lte"] = str(strike_price_lte)

        url = f"https://data.alpaca.markets/v1beta1/options/snapshots/{ticker.upper()}"

        all_snapshots = {}
        page_token = None

        async with httpx.AsyncClient(headers=self._headers, timeout=15) as client:
            while True:
                if page_token:
                    params["page_token"] = page_token

                resp = await client.get(url, params=params)
                resp.raise_for_status()
                data = resp.json()

                snapshots = data.get("snapshots", {})
                all_snapshots.update(snapshots)

                page_token = data.get("next_page_token")
                if not page_token or len(all_snapshots) >= limit:
                    break

        # Parse into a cleaner format
        contracts = []
        for symbol, snap in all_snapshots.items():
            latest_quote = snap.get("latestQuote", {})
            latest_trade = snap.get("latestTrade", {})
            greeks = snap.get("greeks", {})

            contracts.append({
                "contract_symbol": symbol,
                "bid": latest_quote.get("bp", 0),
                "ask": latest_quote.get("ap", 0),
                "bid_size": latest_quote.get("bs", 0),
                "ask_size": latest_quote.get("as", 0),
                "last_price": latest_trade.get("p", 0),
                "last_size": latest_trade.get("s", 0),
                "last_timestamp": latest_trade.get("t", ""),
                "greeks": {
                    "delta": greeks.get("delta"),
                    "gamma": greeks.get("gamma"),
                    "theta": greeks.get("theta"),
                    "vega": greeks.get("vega"),
                    "rho": greeks.get("rho"),
                    "implied_volatility": greeks.get("implied_volatility"),
                },
                "implied_volatility": snap.get("impliedVolatility"),
            })

        return {
            "ticker": ticker.upper(),
            "total_contracts": len(contracts),
            "feed": feed,
            "contracts": contracts,
        }

    async def get_options_quotes(
        self,
        symbols: list[str],
        feed: Optional[str] = None,
    ) -> dict:
        """Fetch latest option quotes for specific contract symbols.

        Args:
            symbols: List of OCC contract symbols (max 100).
            feed: Data feed — 'indicative' (free) or 'opra' (paid).
        """
        if not self._is_configured:
            return {"error": "Alpaca API not configured"}

        params = {
            "symbols": ",".join(symbols[:100]),
            "feed": feed or self._options_feed,
        }

        async with httpx.AsyncClient(headers=self._headers, timeout=10) as client:
            resp = await client.get(
                "https://data.alpaca.markets/v1beta1/options/quotes/latest",
                params=params,
            )
            resp.raise_for_status()
            return resp.json()

    async def get_options_chain_alpaca(
        self,
        ticker: str,
        option_type: Optional[str] = None,
        expiration: Optional[str] = None,
        min_strike: Optional[float] = None,
        max_strike: Optional[float] = None,
        limit: int = 50,
    ) -> dict:
        """Convenience wrapper for filtered options chain.

        Args:
            ticker: Underlying symbol.
            option_type: 'call' or 'put'.
            expiration: Exact expiration date (YYYY-MM-DD).
            min_strike: Minimum strike price.
            max_strike: Maximum strike price.
            limit: Max contracts.
        """
        return await self.get_options_snapshot(
            ticker=ticker,
            option_type=option_type,
            expiration_date=expiration,
            strike_price_gte=min_strike,
            strike_price_lte=max_strike,
            limit=limit,
        )

    # ── Stock Snapshots ──

    async def get_stock_snapshot(self, ticker: str, feed: Optional[str] = None) -> dict:
        """Fetch full real-time snapshot for a single stock.

        Returns latest trade, latest quote, minute bar, daily bar,
        and previous daily bar — the most comprehensive single-ticker view.

        Args:
            ticker: Stock symbol (e.g. AAPL).
            feed: Data feed — 'sip' (all exchanges), 'iex' (free), 'delayed_sip'.
        """
        if not self._is_configured:
            return {"error": "Alpaca API not configured"}

        async with httpx.AsyncClient(headers=self._headers, timeout=10) as client:
            resp = await client.get(
                f"{_DATA_URL}/stocks/{ticker.upper()}/snapshot",
                params={"feed": feed or self._feed},
            )
            resp.raise_for_status()
            data = resp.json()

        latest_trade = data.get("latestTrade", {})
        latest_quote = data.get("latestQuote", {})
        minute_bar = data.get("minuteBar", {})
        daily_bar = data.get("dailyBar", {})
        prev_daily = data.get("prevDailyBar", {})

        return {
            "ticker": ticker.upper(),
            "latest_trade": {
                "price": latest_trade.get("p"),
                "size": latest_trade.get("s"),
                "exchange": latest_trade.get("x"),
                "timestamp": latest_trade.get("t"),
                "conditions": latest_trade.get("c", []),
            },
            "latest_quote": {
                "bid": latest_quote.get("bp"),
                "ask": latest_quote.get("ap"),
                "bid_size": latest_quote.get("bs"),
                "ask_size": latest_quote.get("as"),
                "timestamp": latest_quote.get("t"),
            },
            "minute_bar": {
                "open": minute_bar.get("o"),
                "high": minute_bar.get("h"),
                "low": minute_bar.get("l"),
                "close": minute_bar.get("c"),
                "volume": minute_bar.get("v"),
                "timestamp": minute_bar.get("t"),
                "vwap": minute_bar.get("vw"),
            },
            "daily_bar": {
                "open": daily_bar.get("o"),
                "high": daily_bar.get("h"),
                "low": daily_bar.get("l"),
                "close": daily_bar.get("c"),
                "volume": daily_bar.get("v"),
                "timestamp": daily_bar.get("t"),
                "vwap": daily_bar.get("vw"),
            },
            "prev_daily_bar": {
                "open": prev_daily.get("o"),
                "high": prev_daily.get("h"),
                "low": prev_daily.get("l"),
                "close": prev_daily.get("c"),
                "volume": prev_daily.get("v"),
                "timestamp": prev_daily.get("t"),
                "vwap": prev_daily.get("vw"),
            },
        }

    async def get_multi_snapshots(
        self,
        tickers: list[str],
        feed: Optional[str] = None,
    ) -> dict:
        """Fetch snapshots for multiple stocks in one request.

        Returns the same data as get_stock_snapshot but for up to 200 tickers.

        Args:
            tickers: List of stock symbols (max ~200).
            feed: Data feed — 'sip', 'iex', or 'delayed_sip'.
        """
        if not self._is_configured:
            return {"error": "Alpaca API not configured"}

        symbols = ",".join([t.upper() for t in tickers[:200]])

        async with httpx.AsyncClient(headers=self._headers, timeout=15) as client:
            resp = await client.get(
                f"{_DATA_URL}/stocks/snapshots",
                params={"symbols": symbols, "feed": feed or self._feed},
            )
            resp.raise_for_status()
            raw = resp.json()

        results = {}
        for sym, data in raw.items():
            lt = data.get("latestTrade", {})
            lq = data.get("latestQuote", {})
            db = data.get("dailyBar", {})
            pd = data.get("prevDailyBar", {})

            # Compute change from prev close
            prev_close = pd.get("c", 0)
            current = lt.get("p", 0)
            change = current - prev_close if prev_close else 0
            change_pct = (change / prev_close * 100) if prev_close else 0

            results[sym] = {
                "price": current,
                "bid": lq.get("bp"),
                "ask": lq.get("ap"),
                "volume": db.get("v"),
                "vwap": db.get("vw"),
                "high": db.get("h"),
                "low": db.get("l"),
                "open": db.get("o"),
                "prev_close": prev_close,
                "change": round(change, 4),
                "change_pct": round(change_pct, 4),
                "timestamp": lt.get("t"),
            }

        return {"snapshots": results, "count": len(results)}

    async def get_latest_trade(self, ticker: str, feed: Optional[str] = None) -> dict:
        """Fetch the most recent trade for a stock.

        Returns exact price, size, exchange, timestamp, and trade conditions.

        Args:
            ticker: Stock symbol.
            feed: Data feed.
        """
        if not self._is_configured:
            return {"error": "Alpaca API not configured"}

        async with httpx.AsyncClient(headers=self._headers, timeout=10) as client:
            resp = await client.get(
                f"{_DATA_URL}/stocks/{ticker.upper()}/trades/latest",
                params={"feed": feed or self._feed},
            )
            resp.raise_for_status()
            data = resp.json()

        trade = data.get("trade", {})
        return {
            "ticker": ticker.upper(),
            "price": trade.get("p"),
            "size": trade.get("s"),
            "exchange": trade.get("x"),
            "timestamp": trade.get("t"),
            "conditions": trade.get("c", []),
            "id": trade.get("i"),
        }

    # ── News ──

    async def get_news(
        self,
        symbols: list[str] | None = None,
        limit: int = 20,
        sort: str = "desc",
    ) -> list[dict]:
        """Fetch market news from Alpaca.

        Can filter by symbols or return general market news.

        Args:
            symbols: Optional list of symbols to filter (e.g. ['AAPL', 'TSLA']).
            limit: Max articles (up to 50).
            sort: Sort order — 'desc' (newest first) or 'asc'.
        """
        if not self._is_configured:
            return []

        params: dict = {"limit": min(limit, 50), "sort": sort}
        if symbols:
            params["symbols"] = ",".join([s.upper() for s in symbols])

        async with httpx.AsyncClient(headers=self._headers, timeout=10) as client:
            resp = await client.get(
                "https://data.alpaca.markets/v1beta1/news",
                params=params,
            )
            resp.raise_for_status()
            data = resp.json()

        articles = []
        for article in data.get("news", []):
            articles.append({
                "id": article.get("id"),
                "headline": article.get("headline"),
                "summary": article.get("summary", ""),
                "author": article.get("author", ""),
                "source": article.get("source", ""),
                "url": article.get("url", ""),
                "symbols": article.get("symbols", []),
                "created_at": article.get("created_at", ""),
                "updated_at": article.get("updated_at", ""),
                "images": [
                    {"url": img.get("url"), "size": img.get("size")}
                    for img in article.get("images", [])
                ],
            })
        return articles

    # ── Screener ──

    async def get_most_actives(
        self,
        by: str = "volume",
        top: int = 20,
    ) -> list[dict]:
        """Fetch most active stocks from Alpaca's screener.

        Args:
            by: Rank by 'volume' or 'trades'.
            top: Number of top stocks (max 100).
        """
        if not self._is_configured:
            return []

        async with httpx.AsyncClient(headers=self._headers, timeout=10) as client:
            resp = await client.get(
                "https://data.alpaca.markets/v1beta1/screener/stocks/most-actives",
                params={"by": by, "top": min(top, 100)},
            )
            resp.raise_for_status()
            data = resp.json()

        results = []
        for stock in data.get("most_actives", []):
            results.append({
                "symbol": stock.get("symbol"),
                "volume": stock.get("volume"),
                "trade_count": stock.get("trade_count"),
            })
        return results

    # ── Account ──

    async def get_account(self) -> dict:
        """Fetch paper trading account info.

        Returns buying power, portfolio value, cash, positions count, etc.
        """
        if not self._is_configured:
            return {"error": "Alpaca API not configured"}

        base = _PAPER_URL if self._is_paper else "https://api.alpaca.markets/v2"

        async with httpx.AsyncClient(headers=self._headers, timeout=10) as client:
            resp = await client.get(f"{base}/account")
            resp.raise_for_status()
            acct = resp.json()

        return {
            "account_id": acct.get("id"),
            "status": acct.get("status"),
            "currency": acct.get("currency"),
            "buying_power": float(acct.get("buying_power", 0)),
            "cash": float(acct.get("cash", 0)),
            "portfolio_value": float(acct.get("portfolio_value", 0)),
            "equity": float(acct.get("equity", 0)),
            "long_market_value": float(acct.get("long_market_value", 0)),
            "short_market_value": float(acct.get("short_market_value", 0)),
            "initial_margin": float(acct.get("initial_margin", 0)),
            "maintenance_margin": float(acct.get("maintenance_margin", 0)),
            "last_equity": float(acct.get("last_equity", 0)),
            "daytrade_count": int(acct.get("daytrade_count", 0)),
            "daytrading_buying_power": float(acct.get("daytrading_buying_power", 0)),
            "pattern_day_trader": acct.get("pattern_day_trader", False),
            "trading_blocked": acct.get("trading_blocked", False),
            "account_blocked": acct.get("account_blocked", False),
            "created_at": acct.get("created_at"),
        }

    async def get_positions(self) -> list[dict]:
        """Fetch all open positions in the paper trading account."""
        if not self._is_configured:
            return []

        base = _PAPER_URL if self._is_paper else "https://api.alpaca.markets/v2"

        async with httpx.AsyncClient(headers=self._headers, timeout=10) as client:
            resp = await client.get(f"{base}/positions")
            resp.raise_for_status()
            positions = resp.json()

        results = []
        for pos in positions:
            results.append({
                "symbol": pos.get("symbol"),
                "qty": float(pos.get("qty", 0)),
                "side": pos.get("side"),
                "market_value": float(pos.get("market_value", 0)),
                "cost_basis": float(pos.get("cost_basis", 0)),
                "unrealized_pl": float(pos.get("unrealized_pl", 0)),
                "unrealized_plpc": float(pos.get("unrealized_plpc", 0)),
                "current_price": float(pos.get("current_price", 0)),
                "avg_entry_price": float(pos.get("avg_entry_price", 0)),
                "change_today": float(pos.get("change_today", 0)),
            })
        return results

    # ── Phase 6 additions ──

    async def get_corporate_actions(
        self,
        ticker: str,
        types: Optional[list[str]] = None,
        start: Optional[str] = None,
        end: Optional[str] = None,
    ) -> list[dict]:
        """Fetch corporate actions (splits, dividends, mergers, spinoffs).

        Args:
            ticker: Stock ticker symbol.
            types: Filter by action type: 'dividend', 'split', 'merger', 'spinoff'.
            start: Start date (YYYY-MM-DD). Default: 1 year ago.
            end: End date (YYYY-MM-DD). Default: today.
        """
        if not self._is_configured:
            return []

        from datetime import datetime, timedelta

        if not start:
            start = (datetime.utcnow() - timedelta(days=365)).strftime("%Y-%m-%d")
        if not end:
            end = datetime.utcnow().strftime("%Y-%m-%d")

        params = {
            "symbols": ticker.upper(),
            "since": start,
            "until": end,
        }
        if types:
            params["types"] = ",".join(types)

        async with httpx.AsyncClient(headers=self._headers, timeout=10) as client:
            resp = await client.get(
                f"{_DATA_URL}/v1beta1/corporate-actions",
                params=params,
            )
            resp.raise_for_status()
            data = resp.json()

        results = []
        for action_type, actions in data.items():
            if not isinstance(actions, list):
                continue
            for action in actions:
                results.append({
                    "type": action_type,
                    "symbol": action.get("symbol", ticker.upper()),
                    "ex_date": action.get("ex_date"),
                    "record_date": action.get("record_date"),
                    "payable_date": action.get("payable_date"),
                    **{k: v for k, v in action.items() if k not in ("symbol",)},
                })
        return results

