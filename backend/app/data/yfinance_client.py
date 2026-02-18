"""
Bubby Vision — yfinance Data Client

Primary free data source for OHLCV, quotes, fundamentals, and options chains.
Wraps yfinance with our Pydantic models.
"""

from __future__ import annotations

import structlog
from datetime import datetime
from typing import Optional

import yfinance as yf

log = structlog.get_logger(__name__)

from app.models import (
    OHLCV,
    OptionContract,
    OptionGreeks,
    OptionsChain,
    StockData,
    StockQuote,
)


class YFinanceClient:
    """Wrapper around yfinance delivering typed Pydantic models."""

    def get_stock_data(
        self,
        ticker: str,
        period: str = "1mo",
        interval: str = "1d",
    ) -> StockData:
        """Fetch quote, OHLCV history, and fundamentals for a ticker."""
        try:
            return self._get_stock_data_primary(ticker, period, interval)
        except Exception as e:
            log.warning("yfinance_primary_failed_trying_openbb", ticker=ticker, error=str(e))
            try:
                from app.data.openbb_client import OpenBBClient
                fallback = OpenBBClient().get_quote_fallback(ticker)
                if fallback:
                    quote = StockQuote(
                        ticker=ticker.upper(),
                        price=fallback.get("price", 0.0),
                        change=fallback.get("change", 0.0),
                        change_pct=fallback.get("change_pct", 0.0),
                        volume=fallback.get("volume", 0),
                    )
                    return StockData(
                        ticker=ticker.upper(),
                        quote=quote,
                        history=[],
                        fundamentals={"source": "openbb_fallback"},
                    )
            except Exception as fb_e:
                log.warning("openbb_fallback_also_failed", ticker=ticker, error=str(fb_e))
            raise

    def _get_stock_data_primary(
        self,
        ticker: str,
        period: str = "1mo",
        interval: str = "1d",
    ) -> StockData:
        """Primary yfinance data fetch."""
        t = yf.Ticker(ticker)
        info = t.info or {}

        # ── Quote ──
        quote = StockQuote(
            ticker=ticker.upper(),
            price=info.get("currentPrice") or info.get("regularMarketPrice", 0.0),
            change=info.get("regularMarketChange", 0.0),
            change_pct=info.get("regularMarketChangePercent", 0.0),
            volume=info.get("regularMarketVolume", 0),
            market_cap=info.get("marketCap"),
            pe_ratio=info.get("trailingPE"),
            dividend_yield=info.get("dividendYield"),
            fifty_two_week_high=info.get("fiftyTwoWeekHigh"),
            fifty_two_week_low=info.get("fiftyTwoWeekLow"),
            avg_volume=info.get("averageVolume"),
            sector=info.get("sector"),
            industry=info.get("industry"),
        )

        # ── OHLCV History ──
        df = t.history(period=period, interval=interval)
        history = []
        for idx, row in df.iterrows():
            history.append(
                OHLCV(
                    timestamp=idx.to_pydatetime(),
                    open=round(row["Open"], 4),
                    high=round(row["High"], 4),
                    low=round(row["Low"], 4),
                    close=round(row["Close"], 4),
                    volume=int(row["Volume"]),
                )
            )

        # ── Fundamentals ──
        fundamentals = {
            "name": info.get("longName", ticker),
            "sector": info.get("sector"),
            "industry": info.get("industry"),
            "market_cap": info.get("marketCap"),
            "pe_ratio": info.get("trailingPE"),
            "forward_pe": info.get("forwardPE"),
            "peg_ratio": info.get("pegRatio"),
            "price_to_book": info.get("priceToBook"),
            "revenue": info.get("totalRevenue"),
            "earnings": info.get("netIncomeToCommon"),
            "profit_margin": info.get("profitMargins"),
            "return_on_equity": info.get("returnOnEquity"),
            "debt_to_equity": info.get("debtToEquity"),
            "free_cash_flow": info.get("freeCashflow"),
            "beta": info.get("beta"),
            "dividend_yield": info.get("dividendYield"),
            "ex_dividend_date": info.get("exDividendDate"),
            "earnings_date": info.get("earningsDate"),
        }

        return StockData(
            ticker=ticker.upper(),
            quote=quote,
            history=history,
            fundamentals=fundamentals,
        )

    def get_options_chain(
        self,
        ticker: str,
        expiration: Optional[str] = None,
    ) -> OptionsChain:
        """Fetch options chain with Greeks for a specific expiration."""
        t = yf.Ticker(ticker)
        expirations = list(t.options or [])

        if not expirations:
            return OptionsChain(
                ticker=ticker.upper(),
                underlying_price=0.0,
                expirations=[],
            )

        # Use requested expiration or nearest
        exp = expiration if expiration and expiration in expirations else expirations[0]
        chain = t.option_chain(exp)

        info = t.info or {}
        underlying = info.get("currentPrice") or info.get("regularMarketPrice", 0.0)

        calls = self._parse_contracts(chain.calls, "call", exp, underlying)
        puts = self._parse_contracts(chain.puts, "put", exp, underlying)

        return OptionsChain(
            ticker=ticker.upper(),
            underlying_price=underlying,
            expirations=expirations,
            calls=calls,
            puts=puts,
        )

    @staticmethod
    def _safe_int(val, default: int = 0) -> int:
        """Safely convert a value to int, handling NaN/None from pandas."""
        import math
        if val is None:
            return default
        try:
            f = float(val)
            if math.isnan(f) or math.isinf(f):
                return default
            return int(f)
        except (ValueError, TypeError):
            return default

    @staticmethod
    def _safe_float(val, default: float = 0.0) -> float:
        """Safely convert a value to float, handling NaN/None from pandas."""
        import math
        if val is None:
            return default
        try:
            f = float(val)
            if math.isnan(f) or math.isinf(f):
                return default
            return f
        except (ValueError, TypeError):
            return default

    def _parse_contracts(
        self, df, option_type: str, expiration: str, underlying: float
    ) -> list[OptionContract]:
        """Parse a DataFrame of option contracts into Pydantic models."""
        contracts = []
        for _, row in df.iterrows():
            strike = float(row.get("strike", 0))
            itm = (strike < underlying) if option_type == "call" else (strike > underlying)

            iv = row.get("impliedVolatility")
            greeks = OptionGreeks(
                implied_volatility=self._safe_float(iv) if iv is not None else None,
            )

            contracts.append(
                OptionContract(
                    contract_symbol=row.get("contractSymbol", ""),
                    strike=strike,
                    expiration=datetime.strptime(expiration, "%Y-%m-%d"),
                    option_type=option_type,
                    last_price=self._safe_float(row.get("lastPrice", 0)),
                    bid=self._safe_float(row.get("bid", 0)),
                    ask=self._safe_float(row.get("ask", 0)),
                    volume=self._safe_int(row.get("volume", 0)),
                    open_interest=self._safe_int(row.get("openInterest", 0)),
                    greeks=greeks,
                    in_the_money=itm,
                )
            )
        return contracts
