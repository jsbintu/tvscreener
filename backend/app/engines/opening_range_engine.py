"""
Bubby Vision — Opening Range Engine

Captures and monitors opening range breakouts for intraday trading.
Tracks the high/low of the first N minutes after market open and
detects breakouts in real-time.
"""

from __future__ import annotations

import json
from datetime import datetime, time as dtime, timedelta
from typing import Optional

import structlog

log = structlog.get_logger(__name__)

# US market open (Eastern Time)
MARKET_OPEN = dtime(9, 30)


class OpeningRangeEngine:
    """Track opening ranges and detect breakouts."""

    def __init__(self, redis_url: str = "redis://localhost:6379"):
        self._redis = None
        self._redis_url = redis_url

    def _get_redis(self):
        if self._redis is None:
            import redis
            self._redis = redis.from_url(self._redis_url, decode_responses=True)
        return self._redis

    # ── Core Methods ──────────────────────────────────

    def capture_opening_range(
        self,
        ticker: str,
        bars: list[dict],
        minutes: int = 30,
    ) -> dict:
        """Capture the opening range from intraday bars.

        Records the high and low of the first N minutes after market open.

        Args:
            ticker: Stock ticker.
            bars: Intraday OHLCV bars (1min or 5min).
            minutes: Opening range window (15, 30, or 60 minutes).

        Returns:
            Dict with range_high, range_low, range_size, and status.
        """
        if not bars:
            return {"error": "No bar data provided."}

        # Filter bars within the opening range window
        or_bars = []
        for bar in bars:
            ts = self._parse_bar_time(bar)
            if ts is None:
                continue
            bar_time = ts.time()
            or_end = dtime(
                MARKET_OPEN.hour + (minutes // 60),
                MARKET_OPEN.minute + (minutes % 60),
            )
            if MARKET_OPEN <= bar_time <= or_end:
                or_bars.append(bar)

        if not or_bars:
            return {
                "ticker": ticker.upper(),
                "status": "no_data",
                "message": f"No bars found in {minutes}-minute opening range window.",
            }

        range_high = max(b.get("high", b.get("close", 0)) for b in or_bars)
        range_low = min(b.get("low", b.get("close", 0)) for b in or_bars)
        range_size = range_high - range_low
        open_price = or_bars[0].get("open", or_bars[0].get("close", 0))
        mid = (range_high + range_low) / 2

        result = {
            "ticker": ticker.upper(),
            "minutes": minutes,
            "range_high": round(range_high, 4),
            "range_low": round(range_low, 4),
            "range_size": round(range_size, 4),
            "range_size_pct": round(range_size / max(open_price, 0.01) * 100, 2),
            "midpoint": round(mid, 4),
            "open_price": round(open_price, 4),
            "bars_in_range": len(or_bars),
            "status": "captured",
        }

        # Cache in Redis
        try:
            r = self._get_redis()
            today = datetime.utcnow().strftime("%Y-%m-%d")
            key = f"or:{ticker.upper()}:{today}:{minutes}"
            r.setex(key, 86400, json.dumps(result))  # Expire after 24 hours
        except Exception as e:
            log.warning("or_cache_failed", error=str(e))

        return result

    def check_breakout(
        self,
        ticker: str,
        current_price: float,
        minutes: int = 30,
    ) -> dict:
        """Check if current price has broken the opening range.

        Args:
            ticker: Stock ticker.
            current_price: Current market price.
            minutes: Opening range window used.

        Returns:
            Dict with breakout direction, distance, and quality.
        """
        # Fetch cached opening range
        try:
            r = self._get_redis()
            today = datetime.utcnow().strftime("%Y-%m-%d")
            key = f"or:{ticker.upper()}:{today}:{minutes}"
            cached = r.get(key)
            if not cached:
                return {
                    "ticker": ticker.upper(),
                    "status": "no_range",
                    "message": "No opening range captured for today.",
                }
            or_data = json.loads(cached)
        except Exception as e:
            return {"error": f"Failed to retrieve opening range: {e}"}

        range_high = or_data["range_high"]
        range_low = or_data["range_low"]
        range_size = or_data["range_size"]

        if current_price > range_high:
            direction = "bullish_breakout"
            distance = current_price - range_high
            target_1 = range_high + range_size  # 1x range extension
            target_2 = range_high + range_size * 1.5  # 1.5x range extension
            stop = range_high  # Re-enter range = stop
        elif current_price < range_low:
            direction = "bearish_breakout"
            distance = range_low - current_price
            target_1 = range_low - range_size
            target_2 = range_low - range_size * 1.5
            stop = range_low
        else:
            direction = "inside_range"
            distance = 0
            # Calculate proximity to edges
            dist_to_high = range_high - current_price
            dist_to_low = current_price - range_low
            target_1 = range_high if dist_to_high < dist_to_low else range_low
            target_2 = None
            stop = None

        # Quality assessment
        if direction != "inside_range" and range_size > 0:
            breakout_strength = distance / range_size
            quality = (
                "strong" if breakout_strength > 0.5
                else "moderate" if breakout_strength > 0.2
                else "weak"
            )
        else:
            breakout_strength = 0
            quality = "pending"

        return {
            "ticker": ticker.upper(),
            "current_price": round(current_price, 4),
            "opening_range": or_data,
            "direction": direction,
            "distance_from_range": round(distance, 4),
            "breakout_strength": round(breakout_strength, 2) if range_size > 0 else 0,
            "quality": quality,
            "targets": {
                "target_1": round(target_1, 4) if target_1 else None,
                "target_2": round(target_2, 4) if target_2 else None,
                "stop": round(stop, 4) if stop else None,
            },
        }

    def get_or_summary(self, tickers: list[str], minutes: int = 30) -> dict:
        """Get opening range summary for multiple tickers.

        Args:
            tickers: List of ticker symbols.
            minutes: Opening range window.

        Returns:
            Dict with opening range data for each ticker.
        """
        try:
            r = self._get_redis()
            today = datetime.utcnow().strftime("%Y-%m-%d")
            results = {}

            for ticker in tickers:
                key = f"or:{ticker.upper()}:{today}:{minutes}"
                cached = r.get(key)
                if cached:
                    results[ticker.upper()] = json.loads(cached)

            return {
                "date": today,
                "minutes": minutes,
                "tickers_with_data": len(results),
                "ranges": results,
            }
        except Exception as e:
            return {"error": f"Failed to retrieve OR summary: {e}"}

    # ── Helpers ───────────────────────────────────────

    @staticmethod
    def _parse_bar_time(bar: dict) -> Optional[datetime]:
        """Parse bar timestamp."""
        ts = bar.get("timestamp") or bar.get("date") or bar.get("time")
        if ts is None:
            return None
        if isinstance(ts, datetime):
            return ts
        try:
            return datetime.fromisoformat(str(ts).replace("Z", "+00:00").replace("+00:00", ""))
        except (ValueError, TypeError):
            return None
