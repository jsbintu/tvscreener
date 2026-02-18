"""
Bubby Vision — Input Validators

Reusable validation helpers for tickers, date ranges, and pagination.
Raise ValueError on invalid input so callers can map to 400 responses.
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from typing import Optional

# Matches standard US ticker symbols: 1-5 uppercase letters, optional .class
_TICKER_RE = re.compile(r"^[A-Z]{1,5}(\.[A-Z]{1,2})?$")


def validate_ticker(raw: str) -> str:
    """Clean and validate a stock ticker symbol.

    Returns the normalized ticker or raises ValueError.

    >>> validate_ticker('aapl')
    'AAPL'
    >>> validate_ticker('BRK.B')
    'BRK.B'
    """
    ticker = raw.strip().upper()
    if not ticker:
        raise ValueError("Ticker cannot be empty")
    if not _TICKER_RE.match(ticker):
        raise ValueError(
            f"Invalid ticker '{ticker}'. Expected 1-5 uppercase letters, "
            f"optionally followed by a class suffix (e.g. BRK.B)"
        )
    return ticker


def validate_date_range(
    start: Optional[str | datetime] = None,
    end: Optional[str | datetime] = None,
    max_days: int = 365 * 5,
    default_days: int = 365,
) -> tuple[datetime, datetime]:
    """Validate and normalize a date range.

    - Accepts ISO-8601 strings or datetime objects.
    - If *start* is None, defaults to *default_days* ago.
    - If *end* is None, defaults to now.
    - Raises ValueError if range is negative or exceeds *max_days*.

    Returns (start_dt, end_dt) as timezone-aware UTC datetimes.
    """
    now = datetime.now(timezone.utc)

    # ── Parse end ──
    if end is None:
        end_dt = now
    elif isinstance(end, str):
        end_dt = _parse_iso(end)
    else:
        end_dt = _ensure_tz(end)

    # ── Parse start ──
    if start is None:
        start_dt = end_dt - timedelta(days=default_days)
    elif isinstance(start, str):
        start_dt = _parse_iso(start)
    else:
        start_dt = _ensure_tz(start)

    # ── Validate ──
    if start_dt > end_dt:
        raise ValueError(
            f"Start date ({start_dt.date()}) must be before end date ({end_dt.date()})"
        )

    span = (end_dt - start_dt).days
    if span > max_days:
        raise ValueError(
            f"Date range of {span} days exceeds maximum of {max_days} days"
        )

    return start_dt, end_dt


def validate_pagination(
    limit: Optional[int] = None,
    offset: Optional[int] = None,
    max_limit: int = 500,
    default_limit: int = 50,
) -> tuple[int, int]:
    """Validate and clamp pagination parameters.

    Returns (limit, offset) clamped to safe ranges.

    >>> validate_pagination(limit=1000, offset=-5)
    (500, 0)
    """
    safe_limit = min(max(1, limit or default_limit), max_limit)
    safe_offset = max(0, offset or 0)
    return safe_limit, safe_offset


# ── Helpers ──────────────────────────────────────


def _parse_iso(s: str) -> datetime:
    """Parse an ISO-8601 string into a timezone-aware datetime."""
    try:
        dt = datetime.fromisoformat(s)
    except ValueError:
        raise ValueError(f"Cannot parse date string: '{s}'. Expected ISO-8601 format.")
    return _ensure_tz(dt)


def _ensure_tz(dt: datetime) -> datetime:
    """Ensure a datetime has UTC timezone info."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt
