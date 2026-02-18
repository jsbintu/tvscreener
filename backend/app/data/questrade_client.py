"""
Bubby Vision — Questrade API Client

PRIMARY data source for real-time stock quotes, historical OHLCV candles,
options chains with exchange-computed Greeks, multi-leg strategy pricing,
symbol info, and account data.

Questrade API overview:
  - OAuth2 token-based auth (refresh token rotates on each use)
  - REST endpoints for quotes, candles, options, symbols, accounts
  - WebSocket streaming for L1 real-time push (bid/ask/last/volume)
  - Rate limits: 20 req/sec market data, 15K/hr; 30 req/sec account, 30K/hr

Requires:
  - QUESTRADE_REFRESH_TOKEN in .env (get from Questrade API settings)
  - Real-Time Streaming package ($9.95 CAD/mo) for OPRA options data
"""

from __future__ import annotations

import asyncio
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import httpx
import structlog

from app.config import get_settings
from app.models import OHLCV, OptionContract, OptionGreeks, OptionsChain, StockQuote

_log = structlog.get_logger(__name__)

# ──────────────────────────────────────────────
# Interval mapping (our strings → Questrade API names)
# ──────────────────────────────────────────────
_QT_INTERVAL_MAP = {
    "1m": "OneMinute",
    "2m": "TwoMinutes",
    "3m": "ThreeMinutes",
    "4m": "FourMinutes",
    "5m": "FiveMinutes",
    "10m": "TenMinutes",
    "15m": "FifteenMinutes",
    "20m": "TwentyMinutes",
    "30m": "HalfHour",
    "1h": "OneHour",
    "2h": "TwoHours",
    "4h": "FourHours",
    "1d": "OneDay",
    "1W": "OneWeek",
    "1M": "OneMonth",
    "1Y": "OneYear",
}


def _qt_interval(interval: str) -> str:
    """Convert our interval strings to Questrade interval names."""
    return _QT_INTERVAL_MAP.get(interval, "OneDay")


def _period_to_timedelta(period: str) -> timedelta:
    """Convert period string to timedelta for candle start date."""
    mapping = {
        "1d": timedelta(days=1),
        "5d": timedelta(days=5),
        "1mo": timedelta(days=30),
        "3mo": timedelta(days=90),
        "6mo": timedelta(days=180),
        "1y": timedelta(days=365),
        "2y": timedelta(days=730),
        "5y": timedelta(days=1825),
        "max": timedelta(days=7300),  # ~20 years
    }
    return mapping.get(period, timedelta(days=180))


# ──────────────────────────────────────────────
# Token file persistence (survives restarts)
# ──────────────────────────────────────────────
_TOKEN_FILE = Path(__file__).parent.parent.parent / ".questrade_token"


class QuestradeClient:
    """Full Questrade API client with OAuth2 auto-refresh.

    Token lifecycle:
      1. First run: uses QUESTRADE_REFRESH_TOKEN from .env
      2. Exchanges refresh token for access_token + new refresh_token + api_server
      3. Saves new refresh_token to .questrade_token for next use
      4. Access token expires in ~30min → auto-refreshes via saved refresh_token
    """

    def __init__(self):
        settings = get_settings()
        self._refresh_token = settings.questrade_refresh_token
        self._account_id = settings.questrade_account_id
        self._is_practice = settings.questrade_is_practice

        # Token state (populated on first API call)
        self._access_token: str = ""
        self._api_server: str = ""  # e.g. "https://api01.iq.questrade.com/"
        self._token_expiry: float = 0.0  # Unix timestamp
        self._lock = asyncio.Lock()

    @property
    def _is_configured(self) -> bool:
        return bool(self._refresh_token)

    # ──────────────────────────────────────────
    # OAuth2 Token Management
    # ──────────────────────────────────────────

    async def _ensure_token(self) -> None:
        """Ensure we have a valid access token, refreshing if needed."""
        if not self._is_configured:
            raise RuntimeError("Questrade not configured: set QUESTRADE_REFRESH_TOKEN in .env")

        # Check if current token is still valid (with 60s buffer)
        if self._access_token and time.time() < (self._token_expiry - 60):
            return

        async with self._lock:
            # Double-check after acquiring lock
            if self._access_token and time.time() < (self._token_expiry - 60):
                return
            await self._refresh_access_token()

    async def _refresh_access_token(self) -> None:
        """Exchange refresh token for a new access token.

        Questrade's OAuth2 flow:
          POST https://login.questrade.com/oauth2/token?grant_type=refresh_token&refresh_token=XXX
          Response: { access_token, token_type, expires_in, refresh_token, api_server }

        The refresh_token is single-use — we save the new one for next time.
        """
        # Try saved token file first (survives restarts), fall back to .env
        refresh_token = self._load_saved_token() or self._refresh_token

        login_url = (
            "https://practicelogin.questrade.com/oauth2/token"
            if self._is_practice
            else "https://login.questrade.com/oauth2/token"
        )

        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                login_url,
                params={
                    "grant_type": "refresh_token",
                    "refresh_token": refresh_token,
                },
            )

            if resp.status_code != 200:
                _log.error(
                    "questrade.token_refresh_failed",
                    status=resp.status_code,
                    body=resp.text[:200],
                )
                raise RuntimeError(
                    f"Questrade token refresh failed ({resp.status_code}). "
                    "You may need to generate a new refresh token at "
                    "https://apphub.questrade.com/UI/UserApps.aspx"
                )

            data = resp.json()

        self._access_token = data["access_token"]
        self._api_server = data["api_server"].rstrip("/")  # Remove trailing slash
        self._token_expiry = time.time() + data.get("expires_in", 1800)
        new_refresh = data.get("refresh_token", "")

        # Save new refresh token for next use
        if new_refresh:
            self._refresh_token = new_refresh
            self._save_token(new_refresh)

        _log.info(
            "questrade.token_refreshed",
            server=self._api_server,
            expires_in=data.get("expires_in"),
        )

    def _save_token(self, token: str) -> None:
        """Persist refresh token to file."""
        try:
            _TOKEN_FILE.write_text(token.strip())
        except Exception as e:
            _log.warning("questrade.token_save_failed", error=str(e))

    def _load_saved_token(self) -> str | None:
        """Load refresh token from file."""
        try:
            if _TOKEN_FILE.exists():
                token = _TOKEN_FILE.read_text().strip()
                if token:
                    return token
        except Exception:
            pass
        return None

    # ──────────────────────────────────────────
    # HTTP Helpers
    # ──────────────────────────────────────────

    async def _get(self, path: str, params: dict | None = None) -> dict | list:
        """Authenticated GET request to the Questrade API."""
        await self._ensure_token()

        url = f"{self._api_server}/v1/{path.lstrip('/')}"
        headers = {"Authorization": f"Bearer {self._access_token}"}

        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(url, headers=headers, params=params or {})

            # If 401, try refreshing token once
            if resp.status_code == 401:
                _log.info("questrade.token_expired_mid_request", path=path)
                await self._refresh_access_token()
                headers = {"Authorization": f"Bearer {self._access_token}"}
                resp = await client.get(url, headers=headers, params=params or {})

            resp.raise_for_status()
            return resp.json()

    # ──────────────────────────────────────────
    # Symbol Lookup
    # ──────────────────────────────────────────

    async def search_symbols(self, prefix: str, offset: int = 0) -> list[dict]:
        """Search for symbols by prefix.

        Args:
            prefix: Symbol prefix to search (e.g. 'AAP' matches AAPL, AAP, etc.)
            offset: Pagination offset.

        Returns:
            List of symbol dicts with symbolId, symbol, description, exchange, etc.
        """
        data = await self._get("symbols/search", {"prefix": prefix, "offset": offset})
        return data.get("symbols", [])

    async def get_symbol(self, symbol_id: int) -> dict:
        """Get detailed info for a single symbol by ID.

        Returns exchange, sector, industry, PE, yield, 52-week range, etc.
        """
        data = await self._get(f"symbols/{symbol_id}")
        return data.get("symbols", [{}])[0]

    async def resolve_symbol_id(self, ticker: str) -> int | None:
        """Resolve a ticker string to a Questrade symbolId.

        Caches results to avoid repeated lookups.
        """
        if not hasattr(self, "_symbol_cache"):
            self._symbol_cache: dict[str, int] = {}

        ticker_upper = ticker.upper()
        if ticker_upper in self._symbol_cache:
            return self._symbol_cache[ticker_upper]

        results = await self.search_symbols(ticker_upper)
        for sym in results:
            if sym.get("symbol", "").upper() == ticker_upper:
                sid = sym["symbolId"]
                self._symbol_cache[ticker_upper] = sid
                return sid

        # Fallback: take first result if exact match not found
        if results:
            sid = results[0]["symbolId"]
            self._symbol_cache[ticker_upper] = sid
            return sid

        _log.warning("questrade.symbol_not_found", ticker=ticker)
        return None

    # ──────────────────────────────────────────
    # Stock Quotes (Level 1)
    # ──────────────────────────────────────────

    async def get_quote(self, ticker: str) -> StockQuote | None:
        """Fetch real-time Level 1 quote for a single stock.

        Returns bid, ask, last, volume, VWAP, and more.
        """
        sid = await self.resolve_symbol_id(ticker)
        if not sid:
            return None

        data = await self._get(f"markets/quotes/{sid}")
        quotes = data.get("quotes", [])
        if not quotes:
            return None

        q = quotes[0]
        return StockQuote(
            ticker=ticker.upper(),
            price=q.get("lastTradePrice") or q.get("lastTradePriceTrHrs") or 0.0,
            change=q.get("lastTradePrice", 0) - q.get("openPrice", 0) if q.get("openPrice") else 0.0,
            change_pct=(
                ((q.get("lastTradePrice", 0) - q.get("openPrice", 1)) / q.get("openPrice", 1)) * 100
                if q.get("openPrice")
                else 0.0
            ),
            volume=q.get("volume", 0),
            avg_volume=q.get("averageVol3Months"),
            fifty_two_week_high=q.get("highPrice52"),
            fifty_two_week_low=q.get("lowPrice52"),
        )

    async def get_quotes(self, tickers: list[str]) -> list[dict]:
        """Fetch real-time Level 1 quotes for multiple stocks.

        Args:
            tickers: List of ticker symbols (max ~200).

        Returns:
            List of raw quote dicts from Questrade.
        """
        symbol_ids = []
        for t in tickers:
            sid = await self.resolve_symbol_id(t)
            if sid:
                symbol_ids.append(str(sid))

        if not symbol_ids:
            return []

        data = await self._get("markets/quotes", {"ids": ",".join(symbol_ids)})
        return data.get("quotes", [])

    async def get_quote_raw(self, ticker: str) -> dict:
        """Fetch raw Level 1 quote dict with all Questrade fields.

        Includes bid, ask, lastTradePrice, volume, VWAP, openPrice, highPrice,
        lowPrice, delay, isHalted, and more.
        """
        sid = await self.resolve_symbol_id(ticker)
        if not sid:
            return {}

        data = await self._get(f"markets/quotes/{sid}")
        quotes = data.get("quotes", [])
        return quotes[0] if quotes else {}

    # ──────────────────────────────────────────
    # Historical Candles (OHLCV)
    # ──────────────────────────────────────────

    async def get_candles(
        self,
        ticker: str,
        interval: str = "1d",
        period: str = "6mo",
        start: str | None = None,
        end: str | None = None,
    ) -> list[OHLCV]:
        """Fetch historical OHLCV candles from Questrade.

        Args:
            ticker: Stock symbol (e.g. AAPL).
            interval: Candle interval (1m, 5m, 15m, 30m, 1h, 4h, 1d, 1W, 1M).
            period: Period string (1d, 5d, 1mo, 3mo, 6mo, 1y, 2y).
            start: Override start date (ISO format: 2024-01-01T00:00:00-05:00).
            end: Override end date.

        Returns:
            List of OHLCV models sorted by timestamp ascending.

        Note:
            Intraday candles (1m-30m) limited to ~45-60 days of history.
            Daily candles have deep history (years).
        """
        sid = await self.resolve_symbol_id(ticker)
        if not sid:
            _log.warning("questrade.candles_no_symbol", ticker=ticker)
            return []

        now = datetime.now()
        if not end:
            end = now.strftime("%Y-%m-%dT%H:%M:%S-05:00")
        if not start:
            delta = _period_to_timedelta(period)
            start_dt = now - delta
            start = start_dt.strftime("%Y-%m-%dT%H:%M:%S-05:00")

        qt_interval = _qt_interval(interval)

        data = await self._get(
            f"markets/candles/{sid}",
            {
                "startTime": start,
                "endTime": end,
                "interval": qt_interval,
            },
        )

        candles_raw = data.get("candles", [])
        if not candles_raw:
            _log.warning("questrade.no_candles", ticker=ticker, interval=interval, period=period)
            return []

        bars = []
        for c in candles_raw:
            try:
                ts = datetime.fromisoformat(c["start"].replace("Z", "+00:00"))
                bars.append(
                    OHLCV(
                        timestamp=ts,
                        open=round(float(c.get("open", 0)), 4),
                        high=round(float(c.get("high", 0)), 4),
                        low=round(float(c.get("low", 0)), 4),
                        close=round(float(c.get("close", 0)), 4),
                        volume=int(c.get("volume", 0)),
                    )
                )
            except (KeyError, ValueError) as e:
                _log.debug("questrade.candle_parse_error", error=str(e))
                continue

        _log.info(
            "questrade.candles_fetched",
            ticker=ticker,
            count=len(bars),
            interval=interval,
        )
        return bars

    # ──────────────────────────────────────────
    # Options Chain
    # ──────────────────────────────────────────

    async def get_options_chain_structure(self, ticker: str) -> dict:
        """Fetch options chain structure (available expirations and strike prices).

        Returns:
            Dict with optionChain list containing expiryDate, strikes, callSymbolId,
            putSymbolId for each expiration.
        """
        sid = await self.resolve_symbol_id(ticker)
        if not sid:
            return {}

        data = await self._get(f"symbols/{sid}/options")
        return data

    async def get_options_quotes(
        self,
        option_ids: list[int],
    ) -> list[dict]:
        """Fetch Level 1 option quotes with Greeks for specific option IDs.

        Each quote includes: bid, ask, lastTradePrice, volume, openInterest,
        delta, gamma, theta, vega, rho, impliedVolatility.

        Args:
            option_ids: List of Questrade option symbolIds.

        Returns:
            List of raw option quote dicts.
        """
        if not option_ids:
            return []

        # Questrade expects optionIds as a list in the request body via POST-like GET
        # Actually, it uses a filter-based approach via markets/quotes/options
        data = await self._get(
            "markets/quotes/options",
            {"optionIds": ",".join(str(i) for i in option_ids)},
        )
        return data.get("optionQuotes", [])

    async def get_options_chain(
        self,
        ticker: str,
        expiration: str | None = None,
    ) -> OptionsChain:
        """Fetch full options chain with Greeks from Questrade.

        This is the primary options endpoint — returns real exchange data
        with exchange-computed Greeks (delta, gamma, theta, vega).

        Args:
            ticker: Underlying symbol (e.g. AAPL).
            expiration: Optional expiration filter (YYYY-MM-DD). If None, uses nearest.

        Returns:
            OptionsChain with calls and puts, each having full Greeks.
        """
        sid = await self.resolve_symbol_id(ticker)
        if not sid:
            return OptionsChain(
                ticker=ticker.upper(),
                underlying_price=0.0,
                expirations=[],
            )

        # Get chain structure first
        chain_data = await self._get(f"symbols/{sid}/options")
        option_chain = chain_data.get("optionChain", [])
        if not option_chain:
            return OptionsChain(
                ticker=ticker.upper(),
                underlying_price=0.0,
                expirations=[],
            )

        # Collect all expirations
        expirations = []
        for entry in option_chain:
            exp_date = entry.get("expiryDate", "")
            if exp_date:
                # Format: "2024-02-16T00:00:00.000000-05:00" → "2024-02-16"
                expirations.append(exp_date[:10])

        # Select target expiration
        target_exp = expiration if expiration and expiration in expirations else (expirations[0] if expirations else None)
        if not target_exp:
            return OptionsChain(
                ticker=ticker.upper(),
                underlying_price=0.0,
                expirations=expirations,
            )

        # Find the chain entry for our target expiration
        target_entry = None
        for entry in option_chain:
            if entry.get("expiryDate", "")[:10] == target_exp:
                target_entry = entry
                break

        if not target_entry:
            return OptionsChain(
                ticker=ticker.upper(),
                underlying_price=0.0,
                expirations=expirations,
            )

        # Collect all option IDs from this expiration
        call_ids = []
        put_ids = []
        chain_roots = target_entry.get("chainPerRoot", [])
        for root in chain_roots:
            for row in root.get("chainPerStrikePrice", []):
                if row.get("callSymbolId"):
                    call_ids.append(row["callSymbolId"])
                if row.get("putSymbolId"):
                    put_ids.append(row["putSymbolId"])

        # Fetch quotes for all options in one request
        all_ids = call_ids + put_ids
        option_quotes = []
        # Questrade limits to ~100 IDs per request; batch if needed
        batch_size = 100
        for i in range(0, len(all_ids), batch_size):
            batch = all_ids[i : i + batch_size]
            # Use POST-style filter for options quotes
            data = await self._get(
                "markets/quotes/options",
                {
                    "filters": None,
                    "optionIds": ",".join(str(x) for x in batch),
                },
            )
            option_quotes.extend(data.get("optionQuotes", []))

        # Get underlying price
        underlying_quote = await self.get_quote_raw(ticker)
        underlying_price = underlying_quote.get("lastTradePrice", 0.0)

        # Parse into our models
        calls = []
        puts = []
        for oq in option_quotes:
            symbol = oq.get("symbol", "")
            strike = oq.get("strikePrice", 0)
            opt_type = "call" if oq.get("symbolId") in call_ids else "put"

            greeks = OptionGreeks(
                delta=oq.get("delta"),
                gamma=oq.get("gamma"),
                theta=oq.get("theta"),
                vega=oq.get("vega"),
                rho=oq.get("rho"),
                implied_volatility=oq.get("volatility"),
            )

            contract = OptionContract(
                contract_symbol=symbol,
                strike=float(strike),
                expiration=datetime.strptime(target_exp, "%Y-%m-%d"),
                option_type=opt_type,
                last_price=oq.get("lastTradePrice", 0) or 0,
                bid=oq.get("bidPrice", 0) or 0,
                ask=oq.get("askPrice", 0) or 0,
                volume=oq.get("volume", 0) or 0,
                open_interest=oq.get("openInterest", 0) or 0,
                greeks=greeks,
                in_the_money=(strike < underlying_price) if opt_type == "call" else (strike > underlying_price),
            )

            if opt_type == "call":
                calls.append(contract)
            else:
                puts.append(contract)

        _log.info(
            "questrade.options_chain_fetched",
            ticker=ticker,
            expiration=target_exp,
            calls=len(calls),
            puts=len(puts),
        )

        return OptionsChain(
            ticker=ticker.upper(),
            underlying_price=underlying_price,
            expirations=expirations,
            calls=calls,
            puts=puts,
        )

    # ──────────────────────────────────────────
    # Strategy Quotes
    # ──────────────────────────────────────────

    async def get_strategy_quotes(self, legs: list[dict]) -> dict:
        """Fetch exchange-priced quotes for multi-leg option strategies.

        Args:
            legs: List of strategy legs, each with:
                  {'symbolId': int, 'ratio': int, 'action': 'Buy'|'Sell'}

        Returns:
            Raw strategy quote dict from Questrade with bid/ask/last for the combo.
        """
        data = await self._get(
            "markets/quotes/strategies",
            {"variants": legs},
        )
        return data

    # ──────────────────────────────────────────
    # Account Data
    # ──────────────────────────────────────────

    async def get_accounts(self) -> list[dict]:
        """Fetch all accounts linked to this Questrade login."""
        data = await self._get("accounts")
        return data.get("accounts", [])

    async def get_positions(self, account_id: str | None = None) -> list[dict]:
        """Fetch open positions for an account.

        Args:
            account_id: Questrade account number. Defaults to configured account.
        """
        acct = account_id or self._account_id
        if not acct:
            return []
        data = await self._get(f"accounts/{acct}/positions")
        return data.get("positions", [])

    async def get_balances(self, account_id: str | None = None) -> dict:
        """Fetch account balances (cash, buying power, equity, etc.)."""
        acct = account_id or self._account_id
        if not acct:
            return {}
        data = await self._get(f"accounts/{acct}/balances")
        return data

    async def get_orders(
        self,
        account_id: str | None = None,
        start_time: str | None = None,
        end_time: str | None = None,
        state: str = "All",
    ) -> list[dict]:
        """Fetch order history for an account.

        Args:
            account_id: Questrade account number.
            start_time: ISO datetime for query start.
            end_time: ISO datetime for query end.
            state: Filter: 'All', 'Open', 'Closed'.
        """
        acct = account_id or self._account_id
        if not acct:
            return []

        params: dict = {"stateFilter": state}
        if start_time:
            params["startTime"] = start_time
        if end_time:
            params["endTime"] = end_time

        data = await self._get(f"accounts/{acct}/orders", params)
        return data.get("orders", [])

    async def get_executions(
        self,
        account_id: str | None = None,
        start_time: str | None = None,
        end_time: str | None = None,
    ) -> list[dict]:
        """Fetch execution (fill) history for an account."""
        acct = account_id or self._account_id
        if not acct:
            return []

        params: dict = {}
        if start_time:
            params["startTime"] = start_time
        if end_time:
            params["endTime"] = end_time

        data = await self._get(f"accounts/{acct}/executions", params)
        return data.get("executions", [])

    # ──────────────────────────────────────────
    # Market Info
    # ──────────────────────────────────────────

    async def get_markets(self) -> list[dict]:
        """Fetch list of available markets and their trading hours."""
        data = await self._get("markets")
        return data.get("markets", [])

    async def get_server_time(self) -> str:
        """Fetch current server time (useful for timezone sync)."""
        data = await self._get("time")
        return data.get("time", "")

    # ──────────────────────────────────────────
    # WebSocket Streaming Info
    # ──────────────────────────────────────────

    async def get_streaming_port(self) -> dict:
        """Get WebSocket streaming connection details.

        Questrade L1 streaming uses a WebSocket at:
          wss://{api_server}:{port}/
        After connecting, send access token to authenticate.

        Returns:
            Dict with streamPort for WebSocket connection.
        """
        await self._ensure_token()
        data = await self._get("markets/quotes", {"ids": "0", "stream": "true", "mode": "WebSocket"})
        return data

    # ──────────────────────────────────────────
    # Account Activities (Questrade Plus)
    # ──────────────────────────────────────────

    async def get_activities(
        self,
        account_id: str | None = None,
        start_time: str | None = None,
        end_time: str | None = None,
    ) -> list[dict]:
        """Fetch account activities (trades, dividends, deposits, fees, interest).

        This endpoint returns a full transaction history including:
          - Trades (buy/sell executions with commissions)
          - Dividends received
          - Deposits and withdrawals
          - Interest (margin charges, cash interest)
          - Fees (data subscription, ADR fees, etc.)

        Args:
            account_id: Questrade account number. Defaults to configured account.
            start_time: ISO datetime for query start (e.g. "2024-01-01T00:00:00-05:00").
            end_time: ISO datetime for query end.

        Returns:
            List of activity dicts, each containing:
              tradeDate, transactionDate, settlementDate, action, symbol,
              description, currency, quantity, price, grossAmount, commission,
              netAmount, type, etc.
        """
        acct = account_id or self._account_id
        if not acct:
            return []

        params: dict = {}
        if start_time:
            params["startTime"] = start_time
        if end_time:
            params["endTime"] = end_time

        # If no dates specified, default to last 30 days
        if not start_time and not end_time:
            now = datetime.now()
            params["startTime"] = (now - timedelta(days=30)).strftime(
                "%Y-%m-%dT00:00:00-05:00"
            )
            params["endTime"] = now.strftime("%Y-%m-%dT23:59:59-05:00")

        data = await self._get(f"accounts/{acct}/activities", params)
        activities = data.get("activities", [])

        _log.info(
            "questrade.activities_fetched",
            account=acct,
            count=len(activities),
        )
        return activities

    # ──────────────────────────────────────────
    # Order/Execution Notification Streaming (Questrade Plus)
    # ──────────────────────────────────────────

    async def get_notification_port(self, mode: str = "WebSocket") -> dict:
        """Request a streaming notification port for order status and execution push.

        Questrade's notification streaming delivers real-time push notifications for:
          - Order status changes (submitted, filled, partially filled, cancelled, expired)
          - Execution details (fill price, quantity, commission)

        After obtaining the port, connect via WebSocket to:
          wss://{api_server}:{port}/
        Then send the access token to authenticate and begin receiving push events.

        Args:
            mode: 'WebSocket' or 'RawSocket'. WebSocket is recommended.

        Returns:
            Dict with 'streamPort' (int) for WebSocket connection.
        """
        await self._ensure_token()
        data = await self._get("notifications", {"mode": mode})

        _log.info(
            "questrade.notification_port_obtained",
            port=data.get("streamPort"),
            mode=mode,
        )
        return data

    async def get_symbol_enriched(self, ticker: str) -> dict:
        """Fetch enriched symbol info including sector, industry, PE, dividend yield.

        Useful for portfolio rebalancing (sector allocation) and heatmap grouping.

        Returns:
            Dict with symbol, listingExchange, securityType, prevDayClosePrice,
            highPrice52, lowPrice52, averageVol3Months, pe, yield, sector,
            industry, and more.
        """
        sid = await self.resolve_symbol_id(ticker)
        if not sid:
            return {}
        return await self.get_symbol(sid)

    async def get_batch_quotes_raw(self, tickers: list[str]) -> list[dict]:
        """Fetch raw L1 quote dicts for multiple tickers in a single call.

        Returns all Questrade L1 fields: bid, ask, lastTradePrice, volume,
        VWAP, openPrice, highPrice, lowPrice, averageTradeSize, delay,
        isHalted, tick (Up/Down), and more.

        Args:
            tickers: List of ticker symbols (max ~200).

        Returns:
            List of raw quote dicts.
        """
        if not tickers:
            return []

        ids = []
        for t in tickers:
            sid = await self.resolve_symbol_id(t)
            if sid:
                ids.append(sid)

        if not ids:
            return []

        id_str = ",".join(str(i) for i in ids)
        data = await self._get(f"markets/quotes", {"ids": id_str})
        return data.get("quotes", [])

    async def get_order_impact(
        self,
        order: dict,
        account_id: str | None = None,
    ) -> dict:
        """Preview order impact before placing — estimated cost and commission.

        Questrade's order impact endpoint simulates an order without executing it.

        Args:
            order: Order dict with at minimum:
                symbolId (int), quantity (int), orderType ('Market'|'Limit'),
                timeInForce ('Day'|'GoodTillCanceled'), action ('Buy'|'Sell'),
                and optionally limitPrice, primaryRoute, etc.
            account_id: Questrade account number. Defaults to configured account.

        Returns:
            Dict with estimatedCommissions, buyingPowerEffect,
            buyingPowerResult, maintenanceExcess, etc.
        """
        acct = account_id or self._account_id
        if not acct:
            return {}

        await self._ensure_token()
        url = f"{self._api_server}/v1/accounts/{acct}/orders/impact"
        headers = {
            "Authorization": f"Bearer {self._access_token}",
            "Content-Type": "application/json",
        }

        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(url, headers=headers, json=order)

            if resp.status_code == 401:
                _log.info("questrade.token_expired_mid_request", path="orders/impact")
                await self._refresh_access_token()
                headers["Authorization"] = f"Bearer {self._access_token}"
                resp = await client.post(url, headers=headers, json=order)

            resp.raise_for_status()
            return resp.json()

    async def get_strategy_order_impact(
        self,
        strategy_order: dict,
        account_id: str | None = None,
    ) -> dict:
        """Preview multi-leg strategy order impact before placing.

        Args:
            strategy_order: Strategy order dict with:
                strategyType ('CoveredCall', 'VerticalCallSpread', etc.),
                legs: list of {symbolId, ratio, action ('Buy'|'Sell')},
                and optionally limitPrice, orderType, timeInForce.
            account_id: Questrade account number.

        Returns:
            Dict with estimatedCommissions, buyingPowerEffect, etc.
        """
        acct = account_id or self._account_id
        if not acct:
            return {}

        await self._ensure_token()
        url = f"{self._api_server}/v1/accounts/{acct}/orders/strategy/impact"
        headers = {
            "Authorization": f"Bearer {self._access_token}",
            "Content-Type": "application/json",
        }

        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(url, headers=headers, json=strategy_order)

            if resp.status_code == 401:
                await self._refresh_access_token()
                headers["Authorization"] = f"Bearer {self._access_token}"
                resp = await client.post(url, headers=headers, json=strategy_order)

            resp.raise_for_status()
            return resp.json()

