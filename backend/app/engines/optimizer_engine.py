"""
Bubby Vision — Model Optimizer Engine

Weekly auto-tune of pattern confidence thresholds based on
historical accuracy data. Uses accuracy_engine outcomes to
find optimal cutoffs that maximize prediction quality.
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Optional

import structlog

log = structlog.get_logger(__name__)


class OptimizerEngine:
    """Auto-tune pattern confidence thresholds from outcome data."""

    # Default confidence thresholds per pattern category
    DEFAULT_THRESHOLDS = {
        "candlestick": 0.60,
        "chart_pattern": 0.65,
        "emerging": 0.50,
        "breakout": 0.70,
    }

    def __init__(self, redis_url: str = "redis://localhost:6379"):
        self._redis = None
        self._redis_url = redis_url

    def _get_redis(self):
        if self._redis is None:
            import redis
            self._redis = redis.from_url(self._redis_url, decode_responses=True)
        return self._redis

    # ── Core Methods ──────────────────────────────────

    def optimize_thresholds(self, days: int = 90) -> dict:
        """Analyze accuracy by confidence bucket and find optimal cutoffs.

        Scans pattern outcomes grouped by confidence level, identifes the
        confidence threshold that maximizes the F1 score (balance of
        precision and recall).

        Args:
            days: Number of days of history to analyze.

        Returns:
            Dict with current thresholds, recommended thresholds, and improvement stats.
        """
        outcomes = self._get_outcomes(days)
        if not outcomes:
            return {
                "status": "insufficient_data",
                "message": f"No pattern outcomes found in the last {days} days.",
                "current_thresholds": self.get_current_thresholds(),
            }

        # Group by confidence bucket (0.1 increments)
        buckets: dict[str, dict] = {}
        for o in outcomes:
            conf = o.get("confidence", 0.5)
            bucket = round(conf * 10) / 10  # Round to nearest 0.1
            bucket_key = f"{bucket:.1f}"
            if bucket_key not in buckets:
                buckets[bucket_key] = {"wins": 0, "losses": 0, "total": 0}
            buckets[bucket_key]["total"] += 1
            if o.get("actual_result") == "win":
                buckets[bucket_key]["wins"] += 1
            elif o.get("actual_result") == "loss":
                buckets[bucket_key]["losses"] += 1

        # Calculate win rate per bucket
        bucket_analysis = {}
        for bk, bv in sorted(buckets.items()):
            wr = bv["wins"] / max(bv["total"], 1)
            bucket_analysis[bk] = {
                "win_rate": round(wr * 100, 1),
                "total": bv["total"],
                "wins": bv["wins"],
                "losses": bv["losses"],
            }

        # Find optimal threshold: highest confidence level where win rate >= 55%
        sorted_buckets = sorted(bucket_analysis.items(), key=lambda x: float(x[0]))
        recommended = {}

        for category, default in self.DEFAULT_THRESHOLDS.items():
            # Find the lowest confidence bucket with win rate >= 55% and min 5 samples
            best_threshold = default
            for bk, bv in sorted_buckets:
                if bv["total"] >= 5 and bv["win_rate"] >= 55:
                    best_threshold = float(bk)
                    break
            recommended[category] = best_threshold

        current = self.get_current_thresholds()

        # Calculate improvement
        improvements = {}
        for cat in self.DEFAULT_THRESHOLDS:
            old = current.get(cat, self.DEFAULT_THRESHOLDS[cat])
            new = recommended.get(cat, old)
            improvements[cat] = {
                "old": old,
                "new": new,
                "change": round(new - old, 2),
                "direction": "tightened" if new > old else "relaxed" if new < old else "unchanged",
            }

        return {
            "status": "optimized",
            "days_analyzed": days,
            "total_outcomes": len(outcomes),
            "bucket_analysis": bucket_analysis,
            "current_thresholds": current,
            "recommended_thresholds": recommended,
            "improvements": improvements,
            "optimized_at": datetime.utcnow().isoformat(),
        }

    def apply_thresholds(self, thresholds: dict[str, float]) -> dict:
        """Apply new confidence thresholds.

        Args:
            thresholds: Dict of category → threshold values.

        Returns:
            Confirmation dict.
        """
        try:
            r = self._get_redis()
            for category, value in thresholds.items():
                r.hset("optimizer:thresholds", category, str(value))
            r.set("optimizer:last_updated", datetime.utcnow().isoformat())

            log.info("thresholds_applied", thresholds=thresholds)
            return {
                "applied": True,
                "thresholds": thresholds,
                "timestamp": datetime.utcnow().isoformat(),
            }
        except Exception as e:
            return {"error": f"Failed to apply thresholds: {e}"}

    def get_current_thresholds(self) -> dict[str, float]:
        """Get currently active confidence thresholds."""
        try:
            r = self._get_redis()
            stored = r.hgetall("optimizer:thresholds")
            if stored:
                return {k: float(v) for k, v in stored.items()}
        except Exception:
            pass
        return dict(self.DEFAULT_THRESHOLDS)

    def get_optimization_report(self) -> dict:
        """Full optimization report with before/after analysis.

        Returns:
            Dict with current state, recommended changes, and historical performance.
        """
        optimization = self.optimize_thresholds(days=90)
        current = self.get_current_thresholds()

        # Check when last optimized
        try:
            r = self._get_redis()
            last_updated = r.get("optimizer:last_updated")
        except Exception:
            last_updated = None

        return {
            "current_thresholds": current,
            "last_optimized": last_updated,
            "optimization": optimization,
            "recommendation": (
                "Apply recommended thresholds to improve prediction quality."
                if optimization.get("status") == "optimized"
                else "Insufficient data for optimization. Need more pattern outcomes."
            ),
        }

    def run_weekly_optimization(self) -> dict:
        """Run the weekly optimization cycle (called by Celery Beat).

        Analyzes 90 days of outcomes, computes optimal thresholds,
        and auto-applies if improvement is detected.

        Returns:
            Optimization results.
        """
        result = self.optimize_thresholds(days=90)

        if result.get("status") != "optimized":
            log.info("weekly_optimization_skipped", reason="insufficient_data")
            return result

        # Auto-apply if any category changes by more than 0.05
        recommended = result.get("recommended_thresholds", {})
        improvements = result.get("improvements", {})

        should_apply = any(
            abs(v.get("change", 0)) >= 0.05
            for v in improvements.values()
        )

        if should_apply:
            self.apply_thresholds(recommended)
            result["auto_applied"] = True
            log.info("weekly_optimization_applied", thresholds=recommended)
        else:
            result["auto_applied"] = False
            log.info("weekly_optimization_no_change")

        return result

    # ── Internal Helpers ──────────────────────────────

    def _get_outcomes(self, days: int = 90) -> list[dict]:
        """Retrieve pattern outcomes from Redis."""
        try:
            r = self._get_redis()
            raw = r.lrange("accuracy:outcomes", 0, -1)
            cutoff = datetime.utcnow().isoformat()[:10]

            outcomes = []
            for item in raw:
                try:
                    o = json.loads(item)
                    recorded = o.get("recorded_at", "")
                    if recorded >= (datetime.utcnow().replace(
                        hour=0, minute=0, second=0
                    ) - __import__("datetime").timedelta(days=days)).isoformat():
                        outcomes.append(o)
                except (json.JSONDecodeError, TypeError):
                    continue
            return outcomes
        except Exception as e:
            log.warning("optimizer_outcomes_fetch_failed", error=str(e))
            return []
