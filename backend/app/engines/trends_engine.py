"""
Bubby Vision — Google Trends Engine

Fetches Google search interest data for stock tickers / company names
using the pytrends library. Identifies interest spikes that may
correlate with price movements.

pytrends is an optional dependency — install via: pip install pytrends
"""

from __future__ import annotations

import structlog

log = structlog.get_logger()

_PYTRENDS_AVAILABLE = False
try:
    from pytrends.request import TrendReq
    _PYTRENDS_AVAILABLE = True
except ImportError:
    pass


class TrendsEngine:
    """Google Trends data engine for stock-related search interest."""

    @property
    def is_available(self) -> bool:
        return _PYTRENDS_AVAILABLE

    def _ensure_pytrends(self):
        """Raise if pytrends is not installed."""
        if not _PYTRENDS_AVAILABLE:
            raise RuntimeError(
                "pytrends is not installed. Install with: pip install pytrends"
            )

    def _get_client(self) -> "TrendReq":
        """Create a pytrends client."""
        from pytrends.request import TrendReq
        return TrendReq(hl="en-US", tz=300)

    def get_search_interest(
        self,
        keyword: str,
        timeframe: str = "today 3-m",
        geo: str = "US",
    ) -> dict:
        """Fetch Google search interest over time for a keyword.

        Args:
            keyword: Search term (ticker symbol or company name).
            timeframe: Pytrends timeframe string (default 'today 3-m').
            geo: Country code (default 'US').

        Returns:
            Dict with interest_over_time data, current level, and trend.
        """
        self._ensure_pytrends()

        try:
            pt = self._get_client()
            pt.build_payload([keyword], timeframe=timeframe, geo=geo)
            df = pt.interest_over_time()

            if df.empty:
                return {"keyword": keyword, "status": "no_data", "interest": []}

            # Extract the interest column
            values = df[keyword].tolist()
            dates = [str(d.date()) for d in df.index]

            # Compute trend direction
            recent_avg = sum(values[-7:]) / max(len(values[-7:]), 1)
            prior_avg = sum(values[-30:-7]) / max(len(values[-30:-7]), 1)
            trend = (
                "rising" if recent_avg > prior_avg * 1.1
                else "falling" if recent_avg < prior_avg * 0.9
                else "stable"
            )

            # Detect spikes (>2σ above mean)
            mean_val = sum(values) / len(values)
            variance = sum((v - mean_val) ** 2 for v in values) / len(values)
            import math
            std_dev = math.sqrt(variance) if variance > 0 else 0
            spike_threshold = mean_val + 2 * std_dev

            spikes = [
                {"date": dates[i], "value": values[i]}
                for i in range(len(values))
                if values[i] > spike_threshold
            ]

            return {
                "keyword": keyword,
                "timeframe": timeframe,
                "geo": geo,
                "data_points": len(values),
                "current_interest": values[-1] if values else 0,
                "avg_interest": round(mean_val, 1),
                "max_interest": max(values),
                "trend": trend,
                "spikes": spikes[-5:],  # Last 5 spikes
                "interest_last_14": [
                    {"date": dates[i], "value": values[i]}
                    for i in range(max(0, len(values) - 14), len(values))
                ],
            }

        except Exception as e:
            log.warning("trends.search_interest_failed", keyword=keyword, error=str(e))
            return {"keyword": keyword, "status": "error", "error": str(e)}

    def get_related_queries(
        self,
        keyword: str,
        timeframe: str = "today 3-m",
        geo: str = "US",
    ) -> dict:
        """Fetch related search queries for a keyword.

        Args:
            keyword: Search term.
            timeframe: Pytrends timeframe string.
            geo: Country code.

        Returns:
            Dict with top and rising related queries.
        """
        self._ensure_pytrends()

        try:
            pt = self._get_client()
            pt.build_payload([keyword], timeframe=timeframe, geo=geo)
            related = pt.related_queries()

            result = {"keyword": keyword, "top": [], "rising": []}

            if keyword in related:
                top_df = related[keyword].get("top")
                if top_df is not None and not top_df.empty:
                    result["top"] = top_df.head(10).to_dict("records")

                rising_df = related[keyword].get("rising")
                if rising_df is not None and not rising_df.empty:
                    result["rising"] = rising_df.head(10).to_dict("records")

            return result

        except Exception as e:
            log.warning("trends.related_queries_failed", keyword=keyword, error=str(e))
            return {"keyword": keyword, "status": "error", "error": str(e)}

    def get_interest_spike(
        self,
        keyword: str,
        timeframe: str = "today 3-m",
        geo: str = "US",
    ) -> dict:
        """Check if a keyword currently has an interest spike.

        A spike is defined as current interest >2σ above the period mean.

        Args:
            keyword: Search term.
            timeframe: Pytrends timeframe string.
            geo: Country code.

        Returns:
            Dict with spike detection result.
        """
        data = self.get_search_interest(keyword, timeframe=timeframe, geo=geo)

        if data.get("status") == "error" or data.get("status") == "no_data":
            return {"keyword": keyword, "has_spike": False, "reason": data.get("status", "unknown")}

        current = data.get("current_interest", 0)
        avg = data.get("avg_interest", 0)
        max_val = data.get("max_interest", 0)

        # Calculate spike magnitude
        import math
        interest_data = data.get("interest_last_14", [])
        values = [d["value"] for d in interest_data] if interest_data else [0]
        mean_val = sum(values) / len(values) if values else 0
        variance = sum((v - mean_val) ** 2 for v in values) / len(values) if values else 0
        std_dev = math.sqrt(variance) if variance > 0 else 0

        has_spike = current > (avg + 2 * std_dev) if std_dev > 0 else current > avg * 2
        spike_magnitude = round((current - avg) / max(std_dev, 1), 2) if std_dev > 0 else 0

        return {
            "keyword": keyword,
            "has_spike": has_spike,
            "current_interest": current,
            "average_interest": round(avg, 1),
            "spike_magnitude_sigma": spike_magnitude,
            "trend": data.get("trend", "unknown"),
        }
