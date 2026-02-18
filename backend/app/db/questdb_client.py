"""
Bubby Vision — QuestDB Persistence Layer

Time-series database client for OHLCV data, price alerts, and watchlists.
Connects via PostgreSQL wire protocol (psycopg2).
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

import structlog

from app.config import get_settings

log = structlog.get_logger(__name__)


class QuestDBClient:
    """Time-series database client backed by QuestDB.

    Usage::

        db = get_questdb()
        db.ensure_tables()
        db.insert_ohlcv("AAPL", bars)
        rows = db.query_ohlcv("AAPL", start, end)
    """

    def __init__(self):
        self._dsn = get_settings().questdb_dsn
        self._conn = None

    # ──────────────────────────────────────────────
    # Connection
    # ──────────────────────────────────────────────

    def _get_conn(self):
        """Get or create a psycopg2 connection."""
        if self._conn is None or self._conn.closed:
            try:
                import psycopg2
                self._conn = psycopg2.connect(self._dsn, connect_timeout=5)
                self._conn.autocommit = True
                log.info("questdb.connected")
            except Exception as exc:
                log.warning("questdb.connection_failed", error=str(exc))
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

    def ensure_tables(self) -> bool:
        """Create tables if they don't exist (idempotent).

        Returns True if tables were created/verified successfully.
        """
        conn = self._get_conn()
        if not conn:
            return False

        try:
            cur = conn.cursor()

            # OHLCV time-series with dedup
            cur.execute("""
                CREATE TABLE IF NOT EXISTS ohlcv (
                    ticker SYMBOL,
                    ts TIMESTAMP,
                    open DOUBLE,
                    high DOUBLE,
                    low DOUBLE,
                    close DOUBLE,
                    volume LONG
                ) TIMESTAMP(ts) PARTITION BY MONTH
                DEDUP UPSERT KEYS(ticker, ts);
            """)

            # Price alerts
            cur.execute("""
                CREATE TABLE IF NOT EXISTS price_alerts (
                    id SYMBOL,
                    user_id SYMBOL,
                    ticker SYMBOL,
                    threshold DOUBLE,
                    direction SYMBOL,
                    active BOOLEAN,
                    created_at TIMESTAMP,
                    triggered_at TIMESTAMP
                ) TIMESTAMP(created_at) PARTITION BY MONTH;
            """)

            # Watchlist
            cur.execute("""
                CREATE TABLE IF NOT EXISTS watchlist (
                    user_id SYMBOL,
                    ticker SYMBOL,
                    added_at TIMESTAMP
                ) TIMESTAMP(added_at) PARTITION BY YEAR;
            """)

            # Users (authentication)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id SYMBOL,
                    email SYMBOL,
                    hashed_password STRING,
                    display_name STRING,
                    is_active BOOLEAN,
                    created_at TIMESTAMP
                ) TIMESTAMP(created_at) PARTITION BY YEAR;
            """)

            cur.close()
            log.info("questdb.tables_ensured")
            return True

        except Exception as exc:
            log.error("questdb.ensure_tables_failed", error=str(exc))
            return False

    # ──────────────────────────────────────────────
    # OHLCV Operations
    # ──────────────────────────────────────────────

    def insert_ohlcv(self, ticker: str, bars: list[dict]) -> int:
        """Batch-insert OHLCV bars with dedup on (ticker, ts).

        Args:
            ticker: Stock ticker symbol.
            bars: List of dicts with keys: timestamp, open, high, low, close, volume.

        Returns:
            Number of rows inserted.
        """
        conn = self._get_conn()
        if not conn or not bars:
            return 0

        try:
            cur = conn.cursor()
            count = 0

            for bar in bars:
                cur.execute(
                    """
                    INSERT INTO ohlcv (ticker, ts, open, high, low, close, volume)
                    VALUES (%s, %s, %s, %s, %s, %s, %s);
                    """,
                    (
                        ticker.upper(),
                        bar["timestamp"],
                        bar["open"],
                        bar["high"],
                        bar["low"],
                        bar["close"],
                        int(bar["volume"]),
                    ),
                )
                count += 1

            cur.close()
            log.info("questdb.ohlcv_inserted", ticker=ticker, rows=count)
            return count

        except Exception as exc:
            log.error("questdb.ohlcv_insert_failed", ticker=ticker, error=str(exc))
            return 0

    def query_ohlcv(
        self,
        ticker: str,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
        limit: int = 1000,
    ) -> list[dict]:
        """Query OHLCV bars for a ticker within a time range.

        Returns list of dicts with timestamp, open, high, low, close, volume.
        """
        conn = self._get_conn()
        if not conn:
            return []

        try:
            cur = conn.cursor()
            query = "SELECT ts, open, high, low, close, volume FROM ohlcv WHERE ticker = %s"
            params: list = [ticker.upper()]

            if start:
                query += " AND ts >= %s"
                params.append(start)
            if end:
                query += " AND ts <= %s"
                params.append(end)

            query += " ORDER BY ts DESC LIMIT %s"
            params.append(limit)

            cur.execute(query, params)
            rows = cur.fetchall()
            cur.close()

            return [
                {
                    "timestamp": row[0].isoformat() if row[0] else None,
                    "open": row[1],
                    "high": row[2],
                    "low": row[3],
                    "close": row[4],
                    "volume": row[5],
                }
                for row in rows
            ]

        except Exception as exc:
            log.error("questdb.ohlcv_query_failed", ticker=ticker, error=str(exc))
            return []

    # ──────────────────────────────────────────────
    # Price Alerts
    # ──────────────────────────────────────────────

    def insert_alert(
        self,
        alert_id: str,
        user_id: str,
        ticker: str,
        threshold: float,
        direction: str = "above",
    ) -> bool:
        """Create a price alert."""
        conn = self._get_conn()
        if not conn:
            return False

        try:
            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO price_alerts
                    (id, user_id, ticker, threshold, direction, active, created_at)
                VALUES (%s, %s, %s, %s, %s, true, %s);
                """,
                (alert_id, user_id, ticker.upper(), threshold, direction,
                 datetime.now(timezone.utc)),
            )
            cur.close()
            log.info("questdb.alert_created", alert_id=alert_id, ticker=ticker)
            return True

        except Exception as exc:
            log.error("questdb.alert_insert_failed", error=str(exc))
            return False

    def get_active_alerts(self, user_id: str) -> list[dict]:
        """Get all active (untriggered) alerts for a user."""
        conn = self._get_conn()
        if not conn:
            return []

        try:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT id, ticker, threshold, direction, created_at
                FROM price_alerts
                WHERE user_id = %s AND active = true
                ORDER BY created_at DESC;
                """,
                (user_id,),
            )
            rows = cur.fetchall()
            cur.close()

            return [
                {
                    "id": row[0],
                    "ticker": row[1],
                    "threshold": row[2],
                    "direction": row[3],
                    "created_at": row[4].isoformat() if row[4] else None,
                }
                for row in rows
            ]

        except Exception as exc:
            log.error("questdb.alert_query_failed", error=str(exc))
            return []

    def deactivate_alert(self, alert_id: str) -> bool:
        """Mark an alert as triggered/inactive."""
        conn = self._get_conn()
        if not conn:
            return False

        try:
            cur = conn.cursor()
            cur.execute(
                """
                UPDATE price_alerts
                SET active = false, triggered_at = %s
                WHERE id = %s;
                """,
                (datetime.now(timezone.utc), alert_id),
            )
            cur.close()
            return True

        except Exception as exc:
            log.error("questdb.alert_deactivate_failed", error=str(exc))
            return False

    # ──────────────────────────────────────────────
    # Watchlist
    # ──────────────────────────────────────────────

    def get_watchlist(self, user_id: str) -> list[dict]:
        """Get all tickers on a user's watchlist."""
        conn = self._get_conn()
        if not conn:
            return []

        try:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT ticker, added_at
                FROM watchlist
                WHERE user_id = %s
                ORDER BY added_at DESC;
                """,
                (user_id,),
            )
            rows = cur.fetchall()
            cur.close()

            return [
                {"ticker": row[0], "added_at": row[1].isoformat() if row[1] else None}
                for row in rows
            ]

        except Exception as exc:
            log.error("questdb.watchlist_query_failed", error=str(exc))
            return []

    def add_to_watchlist(self, user_id: str, ticker: str) -> bool:
        """Add a ticker to a user's watchlist."""
        conn = self._get_conn()
        if not conn:
            return False

        try:
            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO watchlist (user_id, ticker, added_at)
                VALUES (%s, %s, %s);
                """,
                (user_id, ticker.upper(), datetime.now(timezone.utc)),
            )
            cur.close()
            log.info("questdb.watchlist_added", user_id=user_id, ticker=ticker)
            return True

        except Exception as exc:
            log.error("questdb.watchlist_add_failed", error=str(exc))
            return False

    def remove_from_watchlist(self, user_id: str, ticker: str) -> bool:
        """Remove a ticker from a user's watchlist."""
        conn = self._get_conn()
        if not conn:
            return False

        try:
            cur = conn.cursor()
            cur.execute(
                """
                DELETE FROM watchlist
                WHERE user_id = %s AND ticker = %s;
                """,
                (user_id, ticker.upper()),
            )
            cur.close()
            log.info("questdb.watchlist_removed", user_id=user_id, ticker=ticker)
            return True

        except Exception as exc:
            log.error("questdb.watchlist_remove_failed", error=str(exc))
            return False

    # ──────────────────────────────────────────────
    # User Management
    # ──────────────────────────────────────────────

    def insert_user(
        self,
        user_id: str,
        email: str,
        hashed_password: str,
        display_name: str | None = None,
    ) -> bool:
        """Create a new user record."""
        conn = self._get_conn()
        if not conn:
            return False

        try:
            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO users (id, email, hashed_password, display_name, is_active, created_at)
                VALUES (%s, %s, %s, %s, true, %s);
                """,
                (user_id, email.lower(), hashed_password, display_name or "",
                 datetime.now(timezone.utc)),
            )
            cur.close()
            log.info("questdb.user_created", user_id=user_id, email=email)
            return True

        except Exception as exc:
            log.error("questdb.user_insert_failed", error=str(exc))
            return False

    def get_user_by_email(self, email: str) -> dict | None:
        """Look up a user by email address."""
        conn = self._get_conn()
        if not conn:
            return None

        try:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT id, email, hashed_password, display_name, is_active, created_at
                FROM users
                WHERE email = %s
                LIMIT 1;
                """,
                (email.lower(),),
            )
            row = cur.fetchone()
            cur.close()

            if not row:
                return None

            return {
                "id": row[0],
                "email": row[1],
                "hashed_password": row[2],
                "display_name": row[3] if row[3] else None,
                "is_active": row[4],
                "created_at": row[5],
            }

        except Exception as exc:
            log.error("questdb.user_query_failed", error=str(exc))
            return None

    def get_user_by_id(self, user_id: str) -> dict | None:
        """Look up a user by their unique ID."""
        conn = self._get_conn()
        if not conn:
            return None

        try:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT id, email, hashed_password, display_name, is_active, created_at
                FROM users
                WHERE id = %s
                LIMIT 1;
                """,
                (user_id,),
            )
            row = cur.fetchone()
            cur.close()

            if not row:
                return None

            return {
                "id": row[0],
                "email": row[1],
                "hashed_password": row[2],
                "display_name": row[3] if row[3] else None,
                "is_active": row[4],
                "created_at": row[5],
            }

        except Exception as exc:
            log.error("questdb.user_query_failed", error=str(exc))
            return None


    def update_user_display_name(self, user_id: str, display_name: str) -> bool:
        """Update a user's display name."""
        conn = self._get_conn()
        if not conn:
            return False

        try:
            cur = conn.cursor()
            cur.execute(
                """
                UPDATE users
                SET display_name = %s
                WHERE id = %s;
                """,
                (display_name, user_id),
            )
            conn.commit()
            cur.close()
            return True

        except Exception as exc:
            log.error("questdb.update_display_name_failed", error=str(exc))
            return False

    def update_user_password(self, user_id: str, hashed_password: str) -> bool:
        """Update a user's hashed password."""
        conn = self._get_conn()
        if not conn:
            return False

        try:
            cur = conn.cursor()
            cur.execute(
                """
                UPDATE users
                SET hashed_password = %s
                WHERE id = %s;
                """,
                (hashed_password, user_id),
            )
            conn.commit()
            cur.close()
            return True

        except Exception as exc:
            log.error("questdb.update_password_failed", error=str(exc))
            return False


# ──────────────────────────────────────────────
# Singleton
# ──────────────────────────────────────────────

_client: Optional[QuestDBClient] = None


def get_questdb() -> QuestDBClient:
    """Get or create the QuestDB client singleton."""
    global _client
    if _client is None:
        _client = QuestDBClient()
    return _client
