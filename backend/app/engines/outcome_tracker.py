"""
Bubby Vision — Pattern Outcome Tracker

Persists pattern outcome evaluations to QuestDB for long-term accuracy tracking,
Bayesian probability updates, and ML readiness.

Uses the same psycopg2 connection pattern as QuestDBClient.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Optional

import structlog

from app.config import get_settings

log = structlog.get_logger(__name__)


class OutcomeTracker:
    """Tracks pattern prediction outcomes in QuestDB.

    Records every pattern detection → outcome (success/failed/expired) pair
    for historical accuracy analysis and confidence calibration.

    Usage::

        tracker = get_outcome_tracker()
        tracker.record_outcome("AAPL", "bull_flag", "success", ...)
        stats = tracker.query_accuracy("bull_flag")
    """

    TABLE_NAME = "pattern_outcomes"

    def __init__(self):
        self._dsn = get_settings().questdb_dsn
        self._conn = None

    def _get_conn(self):
        """Get or create a psycopg2 connection."""
        if self._conn is None or self._conn.closed:
            try:
                import psycopg2
                self._conn = psycopg2.connect(self._dsn, connect_timeout=5)
                self._conn.autocommit = True
                log.info("outcome_tracker.connected")
            except Exception as exc:
                log.warning("outcome_tracker.connection_failed", error=str(exc))
                self._conn = None
        return self._conn

    @property
    def available(self) -> bool:
        conn = self._get_conn()
        return conn is not None

    def close(self):
        if self._conn and not self._conn.closed:
            self._conn.close()

    # ──────────────────────────────────────────────
    # Schema
    # ──────────────────────────────────────────────

    def ensure_table(self) -> bool:
        """Create the pattern_outcomes table if it doesn't exist (idempotent)."""
        conn = self._get_conn()
        if not conn:
            return False

        try:
            cur = conn.cursor()
            cur.execute(f"""
                CREATE TABLE IF NOT EXISTS {self.TABLE_NAME} (
                    ticker SYMBOL,
                    pattern_name SYMBOL,
                    direction SYMBOL,
                    outcome SYMBOL,
                    confidence DOUBLE,
                    entry_price DOUBLE,
                    target_price DOUBLE,
                    stop_price DOUBLE,
                    exit_price DOUBLE,
                    pnl_pct DOUBLE,
                    max_favorable_pct DOUBLE,
                    max_adverse_pct DOUBLE,
                    bars_held INT,
                    detected_at TIMESTAMP,
                    resolved_at TIMESTAMP
                ) TIMESTAMP(resolved_at) PARTITION BY MONTH;
            """)
            cur.close()
            log.info("outcome_tracker.table_ensured")
            return True
        except Exception as exc:
            log.error("outcome_tracker.ensure_table_failed", error=str(exc))
            return False

    # ──────────────────────────────────────────────
    # Record Outcomes
    # ──────────────────────────────────────────────

    def record_outcome(
        self,
        ticker: str,
        pattern_name: str,
        direction: str,
        outcome: str,
        confidence: float = 0.0,
        entry_price: float = 0.0,
        target_price: float = 0.0,
        stop_price: float = 0.0,
        exit_price: float = 0.0,
        pnl_pct: float = 0.0,
        max_favorable_pct: float = 0.0,
        max_adverse_pct: float = 0.0,
        bars_held: int = 0,
        detected_at: Optional[datetime] = None,
    ) -> bool:
        """Record a single pattern outcome to QuestDB.

        Args:
            ticker: Stock ticker.
            pattern_name: Name of the pattern (e.g. 'bull_flag', 'head_and_shoulders').
            direction: 'bullish' or 'bearish'.
            outcome: 'success', 'failed', or 'expired'.
            confidence: Original detection confidence 0-1.
            entry_price: Price at pattern detection.
            target_price: Predicted target.
            stop_price: Predicted stop loss.
            exit_price: Actual exit price.
            pnl_pct: Realized P&L percentage.
            max_favorable_pct: Maximum favorable excursion (%).
            max_adverse_pct: Maximum adverse excursion (%).
            bars_held: Number of bars from detection to resolution.
            detected_at: When the pattern was originally detected.

        Returns:
            True if recorded successfully.
        """
        conn = self._get_conn()
        if not conn:
            return False

        try:
            cur = conn.cursor()
            now = datetime.now(timezone.utc)
            cur.execute(
                f"""
                INSERT INTO {self.TABLE_NAME}
                    (ticker, pattern_name, direction, outcome, confidence,
                     entry_price, target_price, stop_price, exit_price,
                     pnl_pct, max_favorable_pct, max_adverse_pct, bars_held,
                     detected_at, resolved_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s);
                """,
                (
                    ticker.upper(), pattern_name, direction, outcome,
                    confidence, entry_price, target_price, stop_price,
                    exit_price, pnl_pct, max_favorable_pct, max_adverse_pct,
                    bars_held,
                    detected_at or now, now,
                ),
            )
            cur.close()
            log.info(
                "outcome_tracker.recorded",
                ticker=ticker, pattern=pattern_name, outcome=outcome, pnl=pnl_pct,
            )
            return True
        except Exception as exc:
            log.error("outcome_tracker.record_failed", error=str(exc))
            return False

    def record_batch(self, outcomes: list[dict]) -> int:
        """Record multiple outcomes in a single transaction.

        Each dict should have: ticker, pattern_name, direction, outcome,
        plus optional fields matching record_outcome() params.

        Returns:
            Number of outcomes recorded.
        """
        count = 0
        for o in outcomes:
            if self.record_outcome(
                ticker=o.get("ticker", ""),
                pattern_name=o.get("name", o.get("pattern_name", "")),
                direction=o.get("direction", "neutral"),
                outcome=o.get("outcome", "expired"),
                confidence=o.get("confidence", 0.0),
                entry_price=o.get("entry_price", 0.0),
                target_price=o.get("target", o.get("target_price", 0.0)),
                stop_price=o.get("stop_loss", o.get("stop_price", 0.0)),
                exit_price=o.get("exit_price", 0.0),
                pnl_pct=o.get("pnl_at_expiry_pct", o.get("pnl_pct", 0.0)),
                max_favorable_pct=o.get("max_favorable_pct", 0.0),
                max_adverse_pct=o.get("max_adverse_pct", 0.0),
                bars_held=o.get("bars_held", 0),
                detected_at=_parse_iso(o.get("detected_at")),
            ):
                count += 1
        return count

    # ──────────────────────────────────────────────
    # Query Accuracy
    # ──────────────────────────────────────────────

    def query_accuracy(
        self, pattern_name: Optional[str] = None, ticker: Optional[str] = None
    ) -> dict:
        """Query aggregate accuracy stats.

        Args:
            pattern_name: Filter by pattern (None = all patterns).
            ticker: Filter by ticker (None = all tickers).

        Returns:
            Dict with total, wins, losses, win_rate, avg_pnl, patterns breakdown.
        """
        conn = self._get_conn()
        if not conn:
            return {"error": "QuestDB unavailable"}

        try:
            cur = conn.cursor()

            where_clauses = []
            params: list = []
            if pattern_name:
                where_clauses.append("pattern_name = %s")
                params.append(pattern_name)
            if ticker:
                where_clauses.append("ticker = %s")
                params.append(ticker.upper())

            where = (" WHERE " + " AND ".join(where_clauses)) if where_clauses else ""

            cur.execute(
                f"""
                SELECT
                    pattern_name,
                    count(*) as total,
                    sum(CASE WHEN outcome = 'success' THEN 1 ELSE 0 END) as wins,
                    sum(CASE WHEN outcome = 'failed' THEN 1 ELSE 0 END) as losses,
                    avg(pnl_pct) as avg_pnl,
                    avg(max_favorable_pct) as avg_mfe,
                    avg(max_adverse_pct) as avg_mae,
                    avg(bars_held) as avg_bars
                FROM {self.TABLE_NAME}
                {where}
                GROUP BY pattern_name
                ORDER BY count(*) DESC
                LIMIT 50;
                """,
                params,
            )
            rows = cur.fetchall()
            cur.close()

            patterns = []
            total_all = 0
            wins_all = 0
            for row in rows:
                total_all += row[1]
                wins_all += row[2]
                patterns.append({
                    "pattern": row[0],
                    "total": row[1],
                    "wins": row[2],
                    "losses": row[3],
                    "win_rate": round(row[2] / max(row[1], 1) * 100, 1),
                    "avg_pnl_pct": round(row[4] or 0, 2),
                    "avg_mfe_pct": round(row[5] or 0, 2),
                    "avg_mae_pct": round(row[6] or 0, 2),
                    "avg_bars_held": round(row[7] or 0),
                })

            return {
                "total": total_all,
                "wins": wins_all,
                "losses": total_all - wins_all,
                "win_rate": round(wins_all / max(total_all, 1) * 100, 1),
                "patterns": patterns,
            }
        except Exception as exc:
            log.error("outcome_tracker.query_failed", error=str(exc))
            return {"error": str(exc)}

    def query_recent(self, limit: int = 50) -> list[dict]:
        """Get the most recent pattern outcomes."""
        conn = self._get_conn()
        if not conn:
            return []

        try:
            cur = conn.cursor()
            cur.execute(
                f"""
                SELECT ticker, pattern_name, direction, outcome,
                       pnl_pct, bars_held, resolved_at
                FROM {self.TABLE_NAME}
                ORDER BY resolved_at DESC
                LIMIT %s;
                """,
                (limit,),
            )
            rows = cur.fetchall()
            cur.close()

            return [
                {
                    "ticker": row[0],
                    "pattern": row[1],
                    "direction": row[2],
                    "outcome": row[3],
                    "pnl_pct": round(row[4] or 0, 2),
                    "bars_held": row[5],
                    "resolved_at": row[6].isoformat() if row[6] else None,
                }
                for row in rows
            ]
        except Exception as exc:
            log.error("outcome_tracker.query_recent_failed", error=str(exc))
            return []


# ──────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────

def _parse_iso(val) -> Optional[datetime]:
    """Parse an ISO datetime string, returning None on failure."""
    if isinstance(val, datetime):
        return val
    if isinstance(val, str):
        try:
            return datetime.fromisoformat(val.replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            return None
    return None


# ──────────────────────────────────────────────
# Singleton
# ──────────────────────────────────────────────

_tracker: Optional[OutcomeTracker] = None


def get_outcome_tracker() -> OutcomeTracker:
    """Get or create the OutcomeTracker singleton."""
    global _tracker
    if _tracker is None:
        _tracker = OutcomeTracker()
    return _tracker
