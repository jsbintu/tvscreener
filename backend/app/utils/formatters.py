"""
Bubby Vision — Shared Formatters

Human-readable formatting for currency, percentages, large numbers,
tickers, and timestamps.  Used across agents, routes, and notifications.
"""

from __future__ import annotations

import math
from datetime import datetime, timezone


def format_currency(value: float | int, decimals: int = 2) -> str:
    """Format a numeric value as USD currency.

    >>> format_currency(1234.5)
    '$1,234.50'
    >>> format_currency(-789.1)
    '-$789.10'
    """
    sign = "-" if value < 0 else ""
    return f"{sign}${abs(value):,.{decimals}f}"


def format_pct(value: float | int, decimals: int = 2, show_sign: bool = True) -> str:
    """Format a value as a percentage with optional sign.

    >>> format_pct(12.345)
    '+12.35%'
    >>> format_pct(-3.1, decimals=1)
    '-3.1%'
    """
    if show_sign and value > 0:
        return f"+{value:.{decimals}f}%"
    return f"{value:.{decimals}f}%"


_SUFFIXES = [
    (1_000_000_000_000, "T"),
    (1_000_000_000, "B"),
    (1_000_000, "M"),
    (1_000, "K"),
]


def format_large_number(value: float | int, decimals: int = 2) -> str:
    """Abbreviate large numbers with K/M/B/T suffix.

    >>> format_large_number(1_234_567)
    '1.23M'
    >>> format_large_number(45_600_000_000)
    '45.60B'
    >>> format_large_number(999)
    '999'
    """
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return "N/A"

    sign = "-" if value < 0 else ""
    abs_val = abs(value)

    for threshold, suffix in _SUFFIXES:
        if abs_val >= threshold:
            return f"{sign}{abs_val / threshold:.{decimals}f}{suffix}"

    # No suffix needed
    if isinstance(value, int) or value == int(value):
        return f"{sign}{int(abs_val)}"
    return f"{sign}{abs_val:.{decimals}f}"


def format_ticker(raw: str) -> str:
    """Normalize a ticker symbol to uppercase, stripped of whitespace.

    >>> format_ticker('  aapl ')
    'AAPL'
    >>> format_ticker('BRK.B')
    'BRK.B'
    """
    return raw.strip().upper()


def format_timestamp(dt: datetime, relative: bool = True) -> str:
    """Format a datetime as a human-friendly string.

    If *relative* is True and the timestamp is within the last 24 hours,
    returns a relative string like '3h ago'.  Otherwise returns ISO-style.

    >>> from datetime import timedelta
    >>> now = datetime.now(timezone.utc)
    >>> format_timestamp(now - timedelta(minutes=5))
    '5m ago'
    """
    if not relative:
        return dt.strftime("%Y-%m-%d %H:%M:%S")

    now = datetime.now(timezone.utc)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)

    delta = now - dt
    seconds = int(delta.total_seconds())

    if seconds < 0:
        return "just now"
    if seconds < 60:
        return f"{seconds}s ago"
    if seconds < 3600:
        return f"{seconds // 60}m ago"
    if seconds < 86400:
        return f"{seconds // 3600}h ago"
    if seconds < 604800:
        return f"{seconds // 86400}d ago"
    return dt.strftime("%Y-%m-%d")
