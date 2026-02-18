"""
Bubby Vision — CNN Fear & Greed Index Client

Fetches the Fear & Greed Index from CNN's public API.
Headline score plus all 7 sub-indicators.
No API key required. MIT-compatible.
"""

from __future__ import annotations

import httpx

from app.models import FearGreedIndex, FearGreedDetailed, SubIndicator, Sentiment


_FEAR_GREED_URL = "https://production.dataviz.cnn.io/index/fearandgreed/graphdata"

# Sub-indicator keys in the CNN JSON response
_SUB_KEYS = [
    ("market_momentum_sp500", "Market Momentum (S&P 500)"),
    ("stock_price_strength", "Stock Price Strength"),
    ("stock_price_breadth", "Stock Price Breadth"),
    ("put_call_options", "Put/Call Options"),
    ("market_volatility_vix", "Market Volatility (VIX)"),
    ("junk_bond_demand", "Junk Bond Demand"),
    ("safe_haven_demand", "Safe Haven Demand"),
]


def _classify(value: int) -> Sentiment:
    """Map numeric score to sentiment label."""
    if value <= 20:
        return Sentiment.EXTREME_FEAR
    elif value <= 40:
        return Sentiment.FEAR
    elif value <= 60:
        return Sentiment.NEUTRAL
    elif value <= 80:
        return Sentiment.GREED
    else:
        return Sentiment.EXTREME_GREED


def _classify_label(value: float) -> str:
    """Map sub-indicator score to human-readable label."""
    v = int(round(value))
    if v <= 20:
        return "Extreme Fear"
    elif v <= 40:
        return "Fear"
    elif v <= 60:
        return "Neutral"
    elif v <= 80:
        return "Greed"
    else:
        return "Extreme Greed"


class FearGreedClient:
    """Fetches the CNN Fear & Greed Index."""

    def __init__(self):
        self._headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }

    async def _fetch_raw(self) -> dict:
        """Fetch the raw CNN Fear & Greed JSON response."""
        async with httpx.AsyncClient(headers=self._headers, timeout=10) as client:
            resp = await client.get(_FEAR_GREED_URL)
            resp.raise_for_status()
            return resp.json()

    async def get_current(self) -> FearGreedIndex:
        """Fetch the current Fear & Greed Index value."""
        data = await self._fetch_raw()

        fg = data.get("fear_and_greed", {})
        score = int(round(fg.get("score", 50)))
        previous = fg.get("previous_close")
        one_week = fg.get("previous_1_week")
        one_month = fg.get("previous_1_month")
        one_year = fg.get("previous_1_year")

        return FearGreedIndex(
            value=score,
            label=_classify(score),
            previous_close=int(round(previous)) if previous else None,
            one_week_ago=int(round(one_week)) if one_week else None,
            one_month_ago=int(round(one_month)) if one_month else None,
            one_year_ago=int(round(one_year)) if one_year else None,
        )

    async def get_detailed(self) -> FearGreedDetailed:
        """Fetch F&G headline score plus all 7 sub-indicators.

        Sub-indicators:
          1. Market Momentum (S&P 500 vs 125-day MA)
          2. Stock Price Strength (52-week highs vs lows)
          3. Stock Price Breadth (advancing vs declining volume)
          4. Put/Call Options (5-day average P/C ratio)
          5. Market Volatility (VIX vs 50-day MA)
          6. Junk Bond Demand (yield spread: junk vs investment-grade)
          7. Safe Haven Demand (stocks vs bonds 20-day performance)
        """
        data = await self._fetch_raw()

        fg = data.get("fear_and_greed", {})
        score = int(round(fg.get("score", 50)))
        previous = fg.get("previous_close")
        one_week = fg.get("previous_1_week")
        one_month = fg.get("previous_1_month")
        one_year = fg.get("previous_1_year")

        # Parse sub-indicators
        subs: list[SubIndicator] = []
        for key, display_name in _SUB_KEYS:
            sub_data = data.get(key, {})
            sub_score = sub_data.get("score")
            if sub_score is not None:
                subs.append(SubIndicator(
                    name=display_name,
                    value=round(float(sub_score), 1),
                    rating=sub_data.get("rating", _classify_label(float(sub_score))),
                ))

        return FearGreedDetailed(
            value=score,
            label=_classify(score),
            previous_close=int(round(previous)) if previous else None,
            one_week_ago=int(round(one_week)) if one_week else None,
            one_month_ago=int(round(one_month)) if one_month else None,
            one_year_ago=int(round(one_year)) if one_year else None,
            sub_indicators=subs,
        )

