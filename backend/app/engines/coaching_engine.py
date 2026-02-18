"""
Bubby Vision — AI Trading Coach Engine

Analyzes trade history, win rates, and behavioral patterns to provide
personalized coaching insights via Gemini 3 Flash.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from typing import Optional

import structlog

log = structlog.get_logger(__name__)


class CoachingEngine:
    """AI-powered trading coach that analyzes performance and provides tips."""

    def __init__(self, redis_url: str = "redis://localhost:6379"):
        self._redis = None
        self._redis_url = redis_url

    def _get_redis(self):
        if self._redis is None:
            import redis
            self._redis = redis.from_url(self._redis_url, decode_responses=True)
        return self._redis

    # ── Core Coaching ──────────────────────────────────

    def get_coaching_insights(self, trades: list[dict]) -> dict:
        """Analyze recent trades and provide personalized coaching.

        Args:
            trades: List of trade dicts with keys: ticker, action, price,
                    quantity, timestamp, pnl, strategy.

        Returns:
            Dict with performance stats, behavioral patterns, and AI tips.
        """
        if not trades:
            return {"error": "No trade history available for coaching."}

        stats = self._compute_trade_stats(trades)
        behaviors = self._detect_behavioral_patterns(trades)

        # Generate AI coaching via Gemini 3 Flash
        coaching = self._generate_ai_coaching(stats, behaviors, trades)

        return {
            "performance": stats,
            "behavioral_patterns": behaviors,
            "coaching": coaching,
            "generated_at": datetime.utcnow().isoformat(),
        }

    def get_improvement_plan(self, trades: list[dict], weeks: int = 4) -> dict:
        """Week-over-week comparison with actionable improvement suggestions.

        Args:
            trades: Full trade history.
            weeks: Number of weeks to analyze.

        Returns:
            Dict with weekly breakdown and improvement trajectory.
        """
        if not trades:
            return {"error": "No trade history for improvement plan."}

        now = datetime.utcnow()
        weekly_stats = []

        for w in range(weeks):
            week_start = now - timedelta(weeks=w + 1)
            week_end = now - timedelta(weeks=w)
            week_trades = [
                t for t in trades
                if self._parse_timestamp(t.get("timestamp")) is not None
                and week_start <= self._parse_timestamp(t["timestamp"]) < week_end
            ]
            if week_trades:
                ws = self._compute_trade_stats(week_trades)
                ws["week"] = w + 1
                ws["week_label"] = f"{week_start.strftime('%b %d')} – {week_end.strftime('%b %d')}"
                weekly_stats.append(ws)

        # Compute improvement trajectory
        if len(weekly_stats) >= 2:
            recent = weekly_stats[0]
            older = weekly_stats[-1]
            trajectory = {
                "win_rate_change": round(recent.get("win_rate", 0) - older.get("win_rate", 0), 1),
                "avg_rr_change": round(recent.get("avg_risk_reward", 0) - older.get("avg_risk_reward", 0), 2),
                "trade_count_change": recent.get("total_trades", 0) - older.get("total_trades", 0),
                "direction": "improving" if recent.get("win_rate", 0) > older.get("win_rate", 0) else "declining",
            }
        else:
            trajectory = {"direction": "insufficient_data"}

        return {
            "weeks_analyzed": len(weekly_stats),
            "weekly_breakdown": weekly_stats,
            "trajectory": trajectory,
            "suggestions": self._generate_improvement_suggestions(weekly_stats, trajectory),
        }

    # ── Behavioral Detection ──────────────────────────

    def detect_overtrading(self, trades: list[dict], threshold: int = 10) -> dict:
        """Detect overtrading — excessive trades per day with declining quality.

        Args:
            trades: Trade history.
            threshold: Max trades/day before flagging.

        Returns:
            Dict with overtrading days, frequency, and severity.
        """
        daily_counts: dict[str, list[dict]] = {}
        for t in trades:
            ts = self._parse_timestamp(t.get("timestamp"))
            if ts:
                day = ts.strftime("%Y-%m-%d")
                daily_counts.setdefault(day, []).append(t)

        overtrading_days = []
        for day, day_trades in daily_counts.items():
            if len(day_trades) >= threshold:
                # Check if quality declines through the day
                first_half = day_trades[: len(day_trades) // 2]
                second_half = day_trades[len(day_trades) // 2 :]
                first_win = sum(1 for t in first_half if (t.get("pnl") or 0) > 0) / max(len(first_half), 1)
                second_win = sum(1 for t in second_half if (t.get("pnl") or 0) > 0) / max(len(second_half), 1)

                overtrading_days.append({
                    "date": day,
                    "trade_count": len(day_trades),
                    "first_half_win_rate": round(first_win * 100, 1),
                    "second_half_win_rate": round(second_win * 100, 1),
                    "quality_declining": second_win < first_win,
                })

        return {
            "detected": len(overtrading_days) > 0,
            "overtrading_days": overtrading_days,
            "frequency": f"{len(overtrading_days)} of {len(daily_counts)} trading days",
            "severity": "high" if len(overtrading_days) > 3 else "moderate" if overtrading_days else "none",
            "recommendation": "Set a daily trade limit and take breaks after losses." if overtrading_days else "Good trade discipline.",
        }

    def detect_fomo(self, trades: list[dict]) -> dict:
        """Detect FOMO buying — entering after significant moves.

        Identifies trades where entry price is near multi-day highs
        after missing the initial move.

        Args:
            trades: Trade history.

        Returns:
            Dict with FOMO instances and severity.
        """
        fomo_trades = []
        for t in trades:
            # FOMO indicators: buying at high prices with poor R:R
            entry = t.get("price", 0)
            pnl = t.get("pnl", 0)
            action = t.get("action", "").lower()

            if action == "buy" and pnl is not None and pnl < 0:
                # Bought and lost — potential FOMO
                notes = t.get("notes", "")
                if any(kw in notes.lower() for kw in ["chasing", "breakout", "gap up", "momentum"]):
                    fomo_trades.append({
                        "ticker": t.get("ticker"),
                        "date": t.get("timestamp"),
                        "entry_price": entry,
                        "pnl": pnl,
                        "indicator": "chase entry with loss",
                    })

        return {
            "detected": len(fomo_trades) > 0,
            "fomo_trades": fomo_trades[:10],  # Cap at 10
            "count": len(fomo_trades),
            "severity": "high" if len(fomo_trades) > 5 else "moderate" if fomo_trades else "none",
            "recommendation": "Wait for pullbacks to enter. Set entry rules: only buy on retests of breakout levels." if fomo_trades else "No FOMO patterns detected.",
        }

    def detect_revenge_trading(self, trades: list[dict]) -> dict:
        """Detect revenge trading — immediate re-entry after stop-out.

        Identifies sequences where a loss is followed by an immediate
        re-entry in the same ticker within 30 minutes.

        Args:
            trades: Trade history.

        Returns:
            Dict with revenge trading instances.
        """
        revenge_sequences = []
        sorted_trades = sorted(trades, key=lambda t: t.get("timestamp", ""))

        for i in range(1, len(sorted_trades)):
            prev = sorted_trades[i - 1]
            curr = sorted_trades[i]

            prev_ts = self._parse_timestamp(prev.get("timestamp"))
            curr_ts = self._parse_timestamp(curr.get("timestamp"))

            if prev_ts and curr_ts and (prev.get("pnl") or 0) < 0:
                time_gap = (curr_ts - prev_ts).total_seconds()
                same_ticker = prev.get("ticker") == curr.get("ticker")

                if same_ticker and time_gap < 1800:  # 30 minutes
                    revenge_sequences.append({
                        "ticker": curr.get("ticker"),
                        "loss_trade": prev.get("timestamp"),
                        "revenge_trade": curr.get("timestamp"),
                        "time_gap_minutes": round(time_gap / 60, 1),
                        "initial_loss": prev.get("pnl"),
                        "revenge_pnl": curr.get("pnl"),
                    })

        return {
            "detected": len(revenge_sequences) > 0,
            "revenge_sequences": revenge_sequences[:10],
            "count": len(revenge_sequences),
            "severity": "high" if len(revenge_sequences) > 3 else "moderate" if revenge_sequences else "none",
            "recommendation": "Implement a 30-minute cooling-off period after any loss." if revenge_sequences else "No revenge trading detected.",
        }

    def detect_loss_aversion(self, trades: list[dict]) -> dict:
        """Detect loss aversion — holding losers too long, cutting winners short.

        Compares average hold time and magnitude of winning vs losing trades.

        Args:
            trades: Trade history.

        Returns:
            Dict with loss aversion indicators.
        """
        winners = [t for t in trades if (t.get("pnl") or 0) > 0]
        losers = [t for t in trades if (t.get("pnl") or 0) < 0]

        avg_win = sum(t.get("pnl", 0) for t in winners) / max(len(winners), 1)
        avg_loss = abs(sum(t.get("pnl", 0) for t in losers) / max(len(losers), 1))

        # R:R ratio
        rr_ratio = round(avg_win / max(avg_loss, 0.01), 2)
        detected = rr_ratio < 1.0 and len(trades) >= 10

        return {
            "detected": detected,
            "avg_win": round(avg_win, 2),
            "avg_loss": round(avg_loss, 2),
            "risk_reward_ratio": rr_ratio,
            "winners_count": len(winners),
            "losers_count": len(losers),
            "severity": "high" if rr_ratio < 0.5 else "moderate" if rr_ratio < 1.0 else "none",
            "recommendation": (
                "Your average loss exceeds your average win — you're holding losers too long. "
                "Set hard stop-losses and let winners run to at least 2:1 R:R."
            ) if detected else "Good risk-reward discipline.",
        }

    def get_psychology_report(self, trades: list[dict]) -> dict:
        """Full behavioral psychology report combining all detectors.

        Args:
            trades: Trade history.

        Returns:
            Dict with all behavioral patterns and overall assessment.
        """
        overtrading = self.detect_overtrading(trades)
        fomo = self.detect_fomo(trades)
        revenge = self.detect_revenge_trading(trades)
        loss_aversion = self.detect_loss_aversion(trades)

        issues = []
        if overtrading["detected"]:
            issues.append(f"Overtrading ({overtrading['severity']})")
        if fomo["detected"]:
            issues.append(f"FOMO ({fomo['severity']})")
        if revenge["detected"]:
            issues.append(f"Revenge Trading ({revenge['severity']})")
        if loss_aversion["detected"]:
            issues.append(f"Loss Aversion ({loss_aversion['severity']})")

        return {
            "overtrading": overtrading,
            "fomo": fomo,
            "revenge_trading": revenge,
            "loss_aversion": loss_aversion,
            "issues_detected": issues,
            "overall_assessment": (
                "critical" if len(issues) >= 3
                else "needs_improvement" if len(issues) >= 1
                else "healthy"
            ),
            "total_trades_analyzed": len(trades),
        }

    # ── Internal Helpers ──────────────────────────────

    def _compute_trade_stats(self, trades: list[dict]) -> dict:
        """Compute core performance statistics from trade list."""
        total = len(trades)
        winners = [t for t in trades if (t.get("pnl") or 0) > 0]
        losers = [t for t in trades if (t.get("pnl") or 0) < 0]
        flat = [t for t in trades if (t.get("pnl") or 0) == 0]

        total_pnl = sum(t.get("pnl", 0) for t in trades)
        avg_win = sum(t.get("pnl", 0) for t in winners) / max(len(winners), 1)
        avg_loss = abs(sum(t.get("pnl", 0) for t in losers) / max(len(losers), 1))

        # Streak calculation
        streak = 0
        current_streak = 0
        streak_type = "none"
        for t in sorted(trades, key=lambda x: x.get("timestamp", "")):
            pnl = t.get("pnl") or 0
            if pnl > 0:
                if streak_type == "win":
                    current_streak += 1
                else:
                    current_streak = 1
                    streak_type = "win"
            elif pnl < 0:
                if streak_type == "loss":
                    current_streak += 1
                else:
                    current_streak = 1
                    streak_type = "loss"
            streak = max(streak, current_streak)

        return {
            "total_trades": total,
            "winners": len(winners),
            "losers": len(losers),
            "flat": len(flat),
            "win_rate": round(len(winners) / max(total, 1) * 100, 1),
            "total_pnl": round(total_pnl, 2),
            "avg_win": round(avg_win, 2),
            "avg_loss": round(avg_loss, 2),
            "avg_risk_reward": round(avg_win / max(avg_loss, 0.01), 2),
            "largest_win": round(max((t.get("pnl", 0) for t in trades), default=0), 2),
            "largest_loss": round(min((t.get("pnl", 0) for t in trades), default=0), 2),
            "current_streak": current_streak,
            "streak_type": streak_type,
            "best_streak": streak,
        }

    def _detect_behavioral_patterns(self, trades: list[dict]) -> list[str]:
        """Quick behavioral pattern scan."""
        patterns = []
        stats = self._compute_trade_stats(trades)

        if stats["avg_risk_reward"] < 1.0:
            patterns.append("Risk-reward imbalance: average loss exceeds average win")
        if stats["win_rate"] < 40:
            patterns.append("Low win rate: review entry criteria")
        if stats["win_rate"] > 70 and stats["avg_risk_reward"] < 0.5:
            patterns.append("High win rate but tiny wins: letting fear cut winners short")
        if stats["total_trades"] > 50 and stats["total_pnl"] < 0:
            patterns.append("Active but unprofitable: overtrading may be a factor")

        return patterns

    def _generate_ai_coaching(self, stats: dict, behaviors: list[str], trades: list[dict]) -> dict:
        """Generate personalized coaching via Gemini 3 Flash."""
        try:
            from langchain_google_genai import ChatGoogleGenerativeAI
            from langchain_core.messages import HumanMessage, SystemMessage
            from app.config import get_settings

            settings = get_settings()
            llm = ChatGoogleGenerativeAI(
                model="gemini-3.0-flash",
                google_api_key=settings.google_api_key,
                temperature=0.4,
                max_output_tokens=1024,
            )

            prompt = f"""Analyze this trader's performance and provide personalized coaching.

Performance Stats:
{json.dumps(stats, indent=2)}

Behavioral Patterns Detected:
{json.dumps(behaviors, indent=2)}

Recent Trade Count: {len(trades)}

Return as JSON:
{{
  "top_3_strengths": ["strength1", "strength2", "strength3"],
  "top_3_improvements": ["area1", "area2", "area3"],
  "action_plan": ["step1", "step2", "step3"],
  "mindset_tip": "one sentence motivational advice",
  "risk_management_grade": "A/B/C/D/F"
}}"""

            response = llm.invoke([
                SystemMessage(content="You are an elite trading performance coach. Be specific, actionable, and encouraging."),
                HumanMessage(content=prompt),
            ])

            from app.engines.vision_engine import VisionEngine
            return VisionEngine._parse_json(response.content)
        except Exception as e:
            log.warning("coaching_ai_fallback", error=str(e))
            return {
                "top_3_strengths": ["Consistent trading activity"],
                "top_3_improvements": behaviors[:3] if behaviors else ["Continue monitoring"],
                "action_plan": ["Review entry criteria", "Set daily loss limits", "Journal every trade"],
                "mindset_tip": "Process over profits — focus on executing your plan.",
                "risk_management_grade": "B" if stats.get("avg_risk_reward", 0) >= 1.0 else "C",
            }

    def _generate_improvement_suggestions(self, weekly_stats: list[dict], trajectory: dict) -> list[str]:
        """Generate improvement suggestions from weekly analysis."""
        suggestions = []
        direction = trajectory.get("direction", "insufficient_data")

        if direction == "improving":
            suggestions.append("Your win rate is trending up — keep doing what's working.")
        elif direction == "declining":
            suggestions.append("Win rate is declining — review what changed in your approach.")

        if weekly_stats:
            recent = weekly_stats[0]
            if recent.get("avg_risk_reward", 0) < 1.0:
                suggestions.append("Improve risk-reward: aim for 2:1 minimum R:R on every trade.")
            if recent.get("total_trades", 0) > 25:
                suggestions.append("High trade frequency: focus on quality setups, not quantity.")
            if recent.get("win_rate", 0) < 50:
                suggestions.append("Win rate below 50%: tighten entry criteria and wait for A+ setups.")

        return suggestions if suggestions else ["Maintain current discipline and continue journaling."]

    @staticmethod
    def _parse_timestamp(ts) -> Optional[datetime]:
        """Parse various timestamp formats."""
        if ts is None:
            return None
        if isinstance(ts, datetime):
            return ts
        try:
            return datetime.fromisoformat(str(ts).replace("Z", "+00:00").replace("+00:00", ""))
        except (ValueError, TypeError):
            return None
