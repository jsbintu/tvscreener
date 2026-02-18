"""
Bubby Vision — FRED (Federal Reserve Economic Data) Client

Lightweight wrapper around the FRED API for macroeconomic indicators.
Free API key: https://fred.stlouisfed.org/docs/api/api_key.html

Provides GDP, unemployment, CPI, Fed Funds rate, Treasury yields,
and generic series access for any of FRED's 800,000+ data series.
"""

from __future__ import annotations

from typing import Optional

import httpx

from app.config import get_settings


_BASE_URL = "https://api.stlouisfed.org/fred"


class FREDClient:
    """Federal Reserve Economic Data API client."""

    # Common series IDs for quick access
    SERIES = {
        "gdp": "GDP",
        "unemployment": "UNRATE",
        "cpi": "CPIAUCSL",
        "fed_rate": "FEDFUNDS",
        "treasury_2y": "DGS2",
        "treasury_10y": "DGS10",
        "treasury_30y": "DGS30",
        "sp500": "SP500",
        "vix": "VIXCLS",
        "initial_claims": "ICSA",
        "housing_starts": "HOUST",
        "retail_sales": "RSXFS",
        "pce": "PCE",
        "m2_money_supply": "M2SL",
    }

    def __init__(self):
        settings = get_settings()
        self._api_key = settings.fred_api_key

    @property
    def _is_configured(self) -> bool:
        return bool(self._api_key)

    async def get_series(
        self,
        series_id: str,
        limit: int = 100,
        sort_order: str = "desc",
        frequency: Optional[str] = None,
    ) -> dict:
        """Fetch observations for any FRED series.

        Args:
            series_id: FRED series ID (e.g. 'GDP', 'UNRATE', 'CPIAUCSL').
            limit: Max observations to return.
            sort_order: 'asc' or 'desc' (default desc = most recent first).
            frequency: Optional aggregation: 'd', 'w', 'bw', 'm', 'q', 'sa', 'a'.
        """
        if not self._is_configured:
            return {"error": "FRED API key not configured"}

        params = {
            "series_id": series_id.upper(),
            "api_key": self._api_key,
            "file_type": "json",
            "limit": limit,
            "sort_order": sort_order,
        }
        if frequency:
            params["frequency"] = frequency

        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(f"{_BASE_URL}/series/observations", params=params)
            resp.raise_for_status()
            data = resp.json()

        observations = data.get("observations", [])
        return {
            "series_id": series_id.upper(),
            "count": len(observations),
            "observations": [
                {
                    "date": obs.get("date"),
                    "value": float(obs["value"]) if obs.get("value") not in (None, ".", "") else None,
                }
                for obs in observations
            ],
        }

    async def get_series_info(self, series_id: str) -> dict:
        """Fetch metadata for a FRED series (title, units, frequency, etc.)."""
        if not self._is_configured:
            return {"error": "FRED API key not configured"}

        params = {
            "series_id": series_id.upper(),
            "api_key": self._api_key,
            "file_type": "json",
        }

        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(f"{_BASE_URL}/series", params=params)
            resp.raise_for_status()
            data = resp.json()

        series_list = data.get("seriess", [])
        if not series_list:
            return {}

        s = series_list[0]
        return {
            "id": s.get("id"),
            "title": s.get("title"),
            "units": s.get("units"),
            "frequency": s.get("frequency"),
            "seasonal_adjustment": s.get("seasonal_adjustment"),
            "last_updated": s.get("last_updated"),
            "notes": s.get("notes", "")[:500],
        }

    # ── Convenience methods ──

    async def get_gdp(self, limit: int = 20) -> dict:
        """Fetch US GDP (quarterly, seasonally adjusted annual rate)."""
        return await self.get_series("GDP", limit=limit, frequency="q")

    async def get_unemployment(self, limit: int = 24) -> dict:
        """Fetch US unemployment rate (monthly)."""
        return await self.get_series("UNRATE", limit=limit, frequency="m")

    async def get_cpi(self, limit: int = 24) -> dict:
        """Fetch Consumer Price Index (monthly)."""
        return await self.get_series("CPIAUCSL", limit=limit, frequency="m")

    async def get_federal_funds_rate(self, limit: int = 24) -> dict:
        """Fetch effective federal funds rate (monthly)."""
        return await self.get_series("FEDFUNDS", limit=limit, frequency="m")

    async def get_treasury_yields(self) -> dict:
        """Fetch latest Treasury yields (2Y, 10Y, 30Y) for yield curve analysis."""
        results = {}
        for label, series_id in [("2y", "DGS2"), ("10y", "DGS10"), ("30y", "DGS30")]:
            data = await self.get_series(series_id, limit=5)
            obs = data.get("observations", [])
            # Find first non-null value (weekends/holidays may have null)
            for o in obs:
                if o.get("value") is not None:
                    results[label] = {
                        "rate": o["value"],
                        "date": o["date"],
                        "series_id": series_id,
                    }
                    break
            if label not in results:
                results[label] = {"rate": None, "date": None, "series_id": series_id}

        # Calculate spread
        if results.get("10y", {}).get("rate") and results.get("2y", {}).get("rate"):
            results["spread_10y_2y"] = round(
                results["10y"]["rate"] - results["2y"]["rate"], 3
            )
            results["yield_curve_inverted"] = results["spread_10y_2y"] < 0
        else:
            results["spread_10y_2y"] = None
            results["yield_curve_inverted"] = None

        return results

    async def get_economic_dashboard(self) -> dict:
        """Fetch a snapshot of key economic indicators.

        Returns latest values for GDP, unemployment, CPI, Fed rate,
        and Treasury yield spread.
        """
        import asyncio

        gdp, unemp, cpi, fed, yields = await asyncio.gather(
            self.get_gdp(limit=1),
            self.get_unemployment(limit=1),
            self.get_cpi(limit=1),
            self.get_federal_funds_rate(limit=1),
            self.get_treasury_yields(),
            return_exceptions=True,
        )

        def _latest(data):
            if isinstance(data, Exception) or isinstance(data, dict) and "error" in data:
                return None
            obs = data.get("observations", [])
            return obs[0] if obs else None

        return {
            "gdp": _latest(gdp),
            "unemployment": _latest(unemp),
            "cpi": _latest(cpi),
            "federal_funds_rate": _latest(fed),
            "treasury_yields": yields if not isinstance(yields, Exception) else None,
        }
