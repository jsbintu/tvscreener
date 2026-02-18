"""
Bubby Vision — QuantData.us API Client

Primary source for real-time options flow data, unusual activity,
institutional order detection, options exposure (Greeks), volatility
analysis, market news, and dark pool intelligence.

Endpoints covered:
  - Options flow (consolidated + trade-by-trade)
  - Unusual options activity (UOA)
  - Dark pool prints
  - Dark flow (institutional off-exchange)
  - Sweep orders
  - Net drift (cumulative call/put premium imbalance)
  - Net flow (real-time premium direction)
  - Options exposure (DEX, GEX, VEX, CHEX)
  - Options heat map (30+ metrics)
  - Volatility drift (intraday IV vs price)
  - Volatility skew (IV across strikes)
  - Market news (real-time, filterable)
  - Gainers & losers (by premium flow)

Requires API key (paid service).
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

import httpx

from app.config import get_settings


_BASE_URL = "https://api.quantdata.us/od/v2"


class QuantDataClient:
    """Wrapper around QuantData.us REST API for full options data suite."""

    def __init__(self):
        settings = get_settings()
        self._api_key = settings.quantdata_api_key
        self._headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

    @property
    def _is_configured(self) -> bool:
        return bool(self._api_key)

    async def _get(self, endpoint: str, params: dict | None = None) -> dict | list:
        """Shared GET helper with error handling."""
        if not self._is_configured:
            return []

        async with httpx.AsyncClient(headers=self._headers, timeout=15) as client:
            resp = await client.get(f"{_BASE_URL}/{endpoint}", params=params or {})
            resp.raise_for_status()
            data = resp.json()
            # QuantData wraps results in {"data": [...]} for most endpoints
            if isinstance(data, dict) and "data" in data:
                return data["data"]
            return data

    # ──────────────────────────────────────────
    # Options Flow
    # ──────────────────────────────────────────

    async def get_flow(
        self,
        ticker: Optional[str] = None,
        min_premium: int = 100_000,
        limit: int = 50,
    ) -> list[dict]:
        """Fetch live options flow data.

        Args:
            ticker: Filter by ticker (optional). None = all tickers.
            min_premium: Minimum premium in dollars (default $100K).
            limit: Max results.
        """
        params: dict = {"limit": limit}
        if ticker:
            params["symbol"] = ticker.upper()
        if min_premium:
            params["min_premium"] = min_premium

        return await self._get("flow", params)

    async def get_unusual_activity(
        self,
        ticker: Optional[str] = None,
        limit: int = 25,
    ) -> list[dict]:
        """Fetch unusual options activity (UOA).

        UOA = volume significantly exceeds average open interest.
        """
        params: dict = {"limit": limit}
        if ticker:
            params["symbol"] = ticker.upper()

        return await self._get("unusual", params)

    async def get_darkpool(
        self,
        ticker: str,
        limit: int = 25,
    ) -> list[dict]:
        """Fetch dark pool prints for a ticker."""
        params = {"symbol": ticker.upper(), "limit": limit}
        return await self._get("darkpool", params)

    async def get_sweep_orders(
        self,
        ticker: Optional[str] = None,
        limit: int = 25,
    ) -> list[dict]:
        """Fetch sweep orders (aggressive multi-exchange fills)."""
        params: dict = {"limit": limit, "order_type": "SWEEP"}
        if ticker:
            params["symbol"] = ticker.upper()

        return await self._get("flow", params)

    # ──────────────────────────────────────────
    # News
    # ──────────────────────────────────────────

    async def get_news(
        self,
        ticker: Optional[str] = None,
        topic: Optional[str] = None,
        limit: int = 50,
    ) -> list[dict]:
        """Fetch real-time market news filtered by ticker and/or topic.

        QuantData delivers curated, market-relevant news that can impact
        price, volatility, and order flow.

        Args:
            ticker: Filter by stock symbol (optional).
            topic: Filter by news topic (optional).
            limit: Max results.
        """
        params: dict = {"limit": limit}
        if ticker:
            params["symbol"] = ticker.upper()
        if topic:
            params["topic"] = topic

        return await self._get("news", params)

    # ──────────────────────────────────────────
    # Net Drift (Cumulative Premium Imbalance)
    # ──────────────────────────────────────────

    async def get_net_drift(
        self,
        ticker: Optional[str] = None,
        date: Optional[str] = None,
    ) -> dict | list:
        """Fetch net drift — cumulative premium imbalance between calls and puts.

        Measures how call vs put premium builds over time, detecting
        directional pressure beneath the surface. Tracks net premium
        and volume of all options traded.

        Args:
            ticker: Stock symbol (optional for market-wide drift).
            date: Date string 'YYYY-MM-DD' (optional, defaults to today).
        """
        params: dict = {}
        if ticker:
            params["symbol"] = ticker.upper()
        if date:
            params["date"] = date

        return await self._get("net-drift", params)

    # ──────────────────────────────────────────
    # Net Flow (Real-time Premium Direction)
    # ──────────────────────────────────────────

    async def get_net_flow(
        self,
        ticker: Optional[str] = None,
        limit: int = 50,
    ) -> list[dict]:
        """Fetch net flow — real-time options premium flowing into calls and puts.

        Used to confirm momentum, fade exhaustion, or validate breakouts.

        Args:
            ticker: Filter by ticker.
            limit: Max results.
        """
        params: dict = {"limit": limit}
        if ticker:
            params["symbol"] = ticker.upper()

        return await self._get("net-flow", params)

    # ──────────────────────────────────────────
    # Dark Flow (Institutional Off-Exchange)
    # ──────────────────────────────────────────

    async def get_dark_flow(
        self,
        ticker: Optional[str] = None,
        limit: int = 25,
    ) -> list[dict]:
        """Fetch dark flow — large off-exchange and institutional equity activity.

        Surfaces hidden positioning and potential smart-money intent.
        Different from dark pool prints: dark flow aggregates and
        highlights significance.

        Args:
            ticker: Filter by ticker.
            limit: Max results.
        """
        params: dict = {"limit": limit}
        if ticker:
            params["symbol"] = ticker.upper()

        return await self._get("dark-flow", params)

    # ──────────────────────────────────────────
    # Options Exposure (Greeks — DEX/GEX/VEX/CHEX)
    # ──────────────────────────────────────────

    async def get_options_exposure(
        self,
        ticker: str,
        exposure_type: str = "gex",
        expiration: Optional[str] = None,
    ) -> dict | list:
        """Fetch options exposure data — dealer positioning across strikes.

        Visualizes Delta (DEX), Gamma (GEX), Vanna (VEX), and Charm (CHEX)
        exposure. Available real-time and historically.

        Args:
            ticker: Stock symbol (required).
            exposure_type: One of 'dex', 'gex', 'vex', 'chex'.
            expiration: Optional expiration date filter 'YYYY-MM-DD'.
        """
        params: dict = {
            "symbol": ticker.upper(),
            "type": exposure_type.lower(),
        }
        if expiration:
            params["expiration"] = expiration

        return await self._get("exposure", params)

    # ──────────────────────────────────────────
    # Options Heat Map (30+ Metrics)
    # ──────────────────────────────────────────

    async def get_heat_map(
        self,
        ticker: str,
        metric: str = "gex",
        expiration: Optional[str] = None,
    ) -> dict | list:
        """Fetch options heat map — 30+ metrics across strikes and expirations.

        Explore GEX, DEX, VEX, CHEX, and more. Real-time and historical
        snapshots with flexible filters.

        Args:
            ticker: Stock symbol (required).
            metric: Metric type (gex, dex, vex, chex, oi, volume, etc.).
            expiration: Optional expiration date filter.
        """
        params: dict = {
            "symbol": ticker.upper(),
            "metric": metric.lower(),
        }
        if expiration:
            params["expiration"] = expiration

        return await self._get("heatmap", params)

    # ──────────────────────────────────────────
    # Volatility Drift (Intraday IV vs Price)
    # ──────────────────────────────────────────

    async def get_volatility_drift(
        self,
        ticker: str,
        date: Optional[str] = None,
    ) -> dict | list:
        """Fetch volatility drift — how IV evolves intraday relative to price.

        Helps identify vol expansion, compression, and regime shifts.

        Args:
            ticker: Stock symbol.
            date: Date string 'YYYY-MM-DD' (optional).
        """
        params: dict = {"symbol": ticker.upper()}
        if date:
            params["date"] = date

        return await self._get("volatility-drift", params)

    # ──────────────────────────────────────────
    # Volatility Skew (IV Across Strikes)
    # ──────────────────────────────────────────

    async def get_volatility_skew(
        self,
        ticker: str,
        expiration: Optional[str] = None,
    ) -> dict | list:
        """Fetch volatility skew — IV shape and movement across strikes.

        Reveals where the options market is pricing asymmetric risk.

        Args:
            ticker: Stock symbol.
            expiration: Optional expiration date.
        """
        params: dict = {"symbol": ticker.upper()}
        if expiration:
            params["expiration"] = expiration

        return await self._get("volatility-skew", params)

    # ──────────────────────────────────────────
    # Gainers & Losers (Premium Flow Rankings)
    # ──────────────────────────────────────────

    async def get_gainers_losers(
        self,
        direction: str = "bullish",
        limit: int = 25,
    ) -> list[dict]:
        """Fetch gainers/losers ranked by bullish or bearish premium.

        Quickly identify where capital is flowing and which names
        are driving market sentiment.

        Args:
            direction: 'bullish' or 'bearish'.
            limit: Max results.
        """
        params: dict = {
            "direction": direction.lower(),
            "limit": limit,
        }
        return await self._get("gainers-losers", params)
