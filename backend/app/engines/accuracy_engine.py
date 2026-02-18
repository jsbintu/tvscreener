"""
Bubby Vision — Accuracy Engine

Queries pattern outcome history from Redis logs to compute
accuracy metrics, confidence calibration, and dashboard data.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from typing import Optional

import structlog

log = structlog.get_logger()


class AccuracyEngine:
    """Pattern prediction accuracy tracker and dashboard."""

    def __init__(self, redis_url: Optional[str] = None):
        self._redis = None
        if redis_url:
            try:
                import redis
                self._redis = redis.from_url(redis_url, decode_responses=True)
            except Exception as e:
                log.warning("accuracy_engine.redis_init_failed", error=str(e))

    def record_outcome(
        self,
        ticker: str,
        pattern_name: str,
        direction: str,
        predicted_confidence: float,
        actual_result: str,
        entry_price: float,
        exit_price: float,
        timeframe: str = "1d",
        bars_held: int = 0,
    ) -> dict:
        """Record a pattern outcome for accuracy tracking.

        Args:
            ticker: Stock ticker.
            pattern_name: Pattern that generated the signal.
            direction: 'bullish' or 'bearish'.
            predicted_confidence: Confidence at prediction time (0-1).
            actual_result: 'win', 'loss', or 'scratch'.
            entry_price: Entry price.
            exit_price: Exit price.
            timeframe: Chart timeframe.
            bars_held: Number of bars position was held.

        Returns:
            Dict with recorded outcome.
        """
        outcome = {
            "ticker": ticker.upper(),
            "pattern_name": pattern_name,
            "direction": direction,
            "predicted_confidence": round(predicted_confidence, 3),
            "actual_result": actual_result,
            "entry_price": round(entry_price, 4),
            "exit_price": round(exit_price, 4),
            "pnl_pct": round((exit_price - entry_price) / max(entry_price, 0.01) * 100, 2),
            "timeframe": timeframe,
            "bars_held": bars_held,
            "recorded_at": datetime.now().isoformat(),
        }

        if self._redis:
            self._redis.lpush("accuracy:outcomes", json.dumps(outcome))
            self._redis.ltrim("accuracy:outcomes", 0, 9999)  # Keep last 10K

        return outcome

    def _get_outcomes(self, days: int = 90) -> list[dict]:
        """Get outcomes within the specified time window."""
        if not self._redis:
            return []

        raw = self._redis.lrange("accuracy:outcomes", 0, -1)
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()

        outcomes = []
        for r in raw:
            o = json.loads(r)
            if o.get("recorded_at", "") >= cutoff:
                outcomes.append(o)

        return outcomes

    def get_pattern_accuracy(
        self,
        pattern_name: Optional[str] = None,
        days: int = 90,
    ) -> dict:
        """Get accuracy statistics by pattern type.

        Args:
            pattern_name: Filter to specific pattern (None = all).
            days: Lookback period in days.

        Returns:
            Dict with win rate, avg PnL, and per-pattern breakdown.
        """
        outcomes = self._get_outcomes(days)

        if pattern_name:
            outcomes = [o for o in outcomes if o["pattern_name"] == pattern_name]

        if not outcomes:
            return {"total_outcomes": 0, "message": "No outcomes recorded yet."}

        wins = [o for o in outcomes if o["actual_result"] == "win"]
        losses = [o for o in outcomes if o["actual_result"] == "loss"]
        total = len(outcomes)

        # Per-pattern breakdown
        pattern_stats = {}
        for o in outcomes:
            pn = o["pattern_name"]
            if pn not in pattern_stats:
                pattern_stats[pn] = {"wins": 0, "losses": 0, "scratches": 0, "total_pnl": 0}
            if o["actual_result"] == "win":
                pattern_stats[pn]["wins"] += 1
            elif o["actual_result"] == "loss":
                pattern_stats[pn]["losses"] += 1
            else:
                pattern_stats[pn]["scratches"] += 1
            pattern_stats[pn]["total_pnl"] += o.get("pnl_pct", 0)

        # Compute win rates
        for pn, stats in pattern_stats.items():
            total_trades = stats["wins"] + stats["losses"]
            stats["win_rate"] = round(stats["wins"] / total_trades * 100, 1) if total_trades > 0 else 0
            stats["avg_pnl"] = round(stats["total_pnl"] / (total_trades or 1), 2)

        # Sort by win rate descending
        sorted_patterns = sorted(
            pattern_stats.items(),
            key=lambda x: x[1]["win_rate"],
            reverse=True,
        )

        return {
            "days": days,
            "total_outcomes": total,
            "overall_win_rate": round(len(wins) / max(len(wins) + len(losses), 1) * 100, 1),
            "avg_pnl_pct": round(sum(o.get("pnl_pct", 0) for o in outcomes) / total, 2),
            "total_wins": len(wins),
            "total_losses": len(losses),
            "best_pattern": sorted_patterns[0][0] if sorted_patterns else None,
            "worst_pattern": sorted_patterns[-1][0] if sorted_patterns else None,
            "patterns": dict(sorted_patterns),
        }

    def get_timeframe_accuracy(self, timeframe: str = "1d", days: int = 90) -> dict:
        """Get accuracy broken down by timeframe.

        Args:
            timeframe: Filter to specific timeframe.
            days: Lookback period.

        Returns:
            Dict with timeframe-specific accuracy metrics.
        """
        outcomes = [o for o in self._get_outcomes(days) if o.get("timeframe") == timeframe]

        if not outcomes:
            return {"timeframe": timeframe, "total_outcomes": 0}

        wins = len([o for o in outcomes if o["actual_result"] == "win"])
        total = len(outcomes)

        return {
            "timeframe": timeframe,
            "total_outcomes": total,
            "win_rate": round(wins / total * 100, 1),
            "avg_pnl_pct": round(sum(o.get("pnl_pct", 0) for o in outcomes) / total, 2),
            "avg_bars_held": round(sum(o.get("bars_held", 0) for o in outcomes) / total, 1),
        }

    def get_confidence_calibration(self, days: int = 90) -> dict:
        """Compare predicted confidence vs actual success rate.

        Buckets predictions by confidence level (0-25%, 25-50%, 50-75%, 75-100%)
        and compares to actual win rates to detect over/under-confidence.

        Args:
            days: Lookback period.

        Returns:
            Dict with calibration buckets and assessment.
        """
        outcomes = self._get_outcomes(days)
        if not outcomes:
            return {"total_outcomes": 0, "message": "Insufficient data for calibration."}

        buckets = {
            "0-25%": {"predicted_avg": 0, "actual_wins": 0, "total": 0},
            "25-50%": {"predicted_avg": 0, "actual_wins": 0, "total": 0},
            "50-75%": {"predicted_avg": 0, "actual_wins": 0, "total": 0},
            "75-100%": {"predicted_avg": 0, "actual_wins": 0, "total": 0},
        }

        for o in outcomes:
            conf = o.get("predicted_confidence", 0.5) * 100
            if conf < 25:
                bucket = "0-25%"
            elif conf < 50:
                bucket = "25-50%"
            elif conf < 75:
                bucket = "50-75%"
            else:
                bucket = "75-100%"

            buckets[bucket]["total"] += 1
            buckets[bucket]["predicted_avg"] += conf
            if o["actual_result"] == "win":
                buckets[bucket]["actual_wins"] += 1

        # Compute averages
        calibration = {}
        for name, data in buckets.items():
            if data["total"] > 0:
                predicted = round(data["predicted_avg"] / data["total"], 1)
                actual = round(data["actual_wins"] / data["total"] * 100, 1)
                calibration[name] = {
                    "predicted_confidence": predicted,
                    "actual_win_rate": actual,
                    "sample_size": data["total"],
                    "calibration_gap": round(predicted - actual, 1),
                    "assessment": (
                        "well_calibrated" if abs(predicted - actual) < 10
                        else "overconfident" if predicted > actual
                        else "underconfident"
                    ),
                }

        return {
            "days": days,
            "total_outcomes": len(outcomes),
            "buckets": calibration,
        }

    def get_accuracy_summary(self, days: int = 90) -> dict:
        """Full accuracy dashboard data.

        Returns:
            Dict with overall accuracy, pattern breakdown, calibration, and trends.
        """
        pattern_acc = self.get_pattern_accuracy(days=days)
        calibration = self.get_confidence_calibration(days=days)

        # Daily trend (last 30 days)
        outcomes = self._get_outcomes(days=30)
        daily = {}
        for o in outcomes:
            date = o.get("recorded_at", "")[:10]
            if date not in daily:
                daily[date] = {"wins": 0, "losses": 0}
            if o["actual_result"] == "win":
                daily[date]["wins"] += 1
            elif o["actual_result"] == "loss":
                daily[date]["losses"] += 1

        daily_trend = [
            {"date": d, "win_rate": round(v["wins"] / max(v["wins"] + v["losses"], 1) * 100, 1)}
            for d, v in sorted(daily.items())
        ]

        return {
            "summary": pattern_acc,
            "calibration": calibration,
            "daily_trend": daily_trend[-14:],  # Last 14 days
        }

    # ── Gamification ──────────────────────────────────

    def get_streak_data(self) -> dict:
        """Get current and best win/loss streaks.

        Returns:
            Dict with current streak, best streak, and streak history.
        """
        outcomes = self._get_outcomes(days=365)
        if not outcomes:
            return {"current_streak": 0, "streak_type": "none", "best_win_streak": 0, "best_loss_streak": 0}

        # Sort chronologically
        sorted_outcomes = sorted(outcomes, key=lambda o: o.get("recorded_at", ""))

        current_streak = 0
        streak_type = "none"
        best_win_streak = 0
        best_loss_streak = 0
        temp_win = 0
        temp_loss = 0

        for o in sorted_outcomes:
            result = o.get("actual_result", "")
            if result == "win":
                temp_win += 1
                temp_loss = 0
                best_win_streak = max(best_win_streak, temp_win)
                current_streak = temp_win
                streak_type = "win"
            elif result == "loss":
                temp_loss += 1
                temp_win = 0
                best_loss_streak = max(best_loss_streak, temp_loss)
                current_streak = temp_loss
                streak_type = "loss"
            else:
                temp_win = 0
                temp_loss = 0

        return {
            "current_streak": current_streak,
            "streak_type": streak_type,
            "best_win_streak": best_win_streak,
            "best_loss_streak": best_loss_streak,
            "is_hot_streak": streak_type == "win" and current_streak >= 3,
            "total_outcomes_analyzed": len(sorted_outcomes),
        }

    def get_leaderboard_stats(self) -> dict:
        """Get gamification stats: win rate trends, R:R, and badges.

        Returns:
            Dict with multi-period stats, trend direction, and earned badges.
        """
        periods = {"7d": 7, "30d": 30, "90d": 90}
        stats = {}

        for label, days in periods.items():
            outcomes = self._get_outcomes(days=days)
            if not outcomes:
                stats[label] = {"win_rate": 0, "avg_rr": 0, "trades": 0}
                continue

            wins = [o for o in outcomes if o["actual_result"] == "win"]
            losses = [o for o in outcomes if o["actual_result"] == "loss"]
            total_decided = len(wins) + len(losses)

            avg_win = sum(o.get("pnl_pct", 0) for o in wins) / max(len(wins), 1)
            avg_loss = abs(sum(o.get("pnl_pct", 0) for o in losses) / max(len(losses), 1))

            stats[label] = {
                "win_rate": round(len(wins) / max(total_decided, 1) * 100, 1),
                "avg_rr": round(avg_win / max(avg_loss, 0.01), 2),
                "trades": len(outcomes),
                "total_pnl_pct": round(sum(o.get("pnl_pct", 0) for o in outcomes), 2),
            }

        # Compute trend direction (30d vs 7d)
        wr_7 = stats.get("7d", {}).get("win_rate", 0)
        wr_30 = stats.get("30d", {}).get("win_rate", 0)
        trend = "improving" if wr_7 > wr_30 else "declining" if wr_7 < wr_30 else "stable"

        # Badges
        badges = []
        streaks = self.get_streak_data()
        if streaks.get("is_hot_streak"):
            badges.append({"name": "🔥 Hot Streak", "description": f"{streaks['current_streak']} wins in a row"})
        if streaks.get("best_win_streak", 0) >= 5:
            badges.append({"name": "⭐ Streak Master", "description": f"Best streak: {streaks['best_win_streak']}"})
        if wr_30 >= 60:
            badges.append({"name": "🎯 Sharpshooter", "description": f"30-day win rate: {wr_30}%"})
        if stats.get("30d", {}).get("avg_rr", 0) >= 2.0:
            badges.append({"name": "💎 Risk Manager", "description": "R:R ≥ 2.0"})
        if stats.get("90d", {}).get("trades", 0) >= 100:
            badges.append({"name": "📊 Centurion", "description": "100+ trades in 90 days"})
        if trend == "improving":
            badges.append({"name": "📈 On the Rise", "description": "Win rate trending up"})

        return {
            "periods": stats,
            "trend": trend,
            "badges": badges,
            "streak": streaks,
        }
