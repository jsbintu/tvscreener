"""
Bubby Vision — Input Sanitization (OWASP)

Security utilities for sanitizing user-supplied input:
- Ticker symbol validation (strict alphanumeric + dots)
- Path traversal prevention
- Request body size limiting
- XSS prevention for string fields
"""

from __future__ import annotations

import re
from typing import Optional

import structlog

log = structlog.get_logger(__name__)


# ────────────────────────────────────────────────
# Ticker Validation
# ────────────────────────────────────────────────

# Valid ticker: 1-10 uppercase alpha + optional dots (e.g. BRK.B)
_TICKER_RE = re.compile(r"^[A-Z]{1,10}(\.[A-Z]{1,5})?$")


def is_valid_ticker(ticker: str) -> bool:
    """Check if a ticker symbol is safe and valid."""
    return bool(_TICKER_RE.match(ticker.upper()))


def sanitize_ticker(ticker: str) -> str:
    """Normalize and validate a ticker symbol.

    Returns uppercased ticker if valid, raises ValueError otherwise.
    """
    cleaned = ticker.strip().upper()
    if not _TICKER_RE.match(cleaned):
        raise ValueError(f"Invalid ticker symbol: {ticker!r}")
    return cleaned


# ────────────────────────────────────────────────
# String Sanitization (XSS Prevention)
# ────────────────────────────────────────────────

_DANGEROUS_PATTERNS = [
    re.compile(r"<script", re.IGNORECASE),
    re.compile(r"javascript:", re.IGNORECASE),
    re.compile(r"on\w+=", re.IGNORECASE),  # onclick=, onerror=, etc.
    re.compile(r"<iframe", re.IGNORECASE),
    re.compile(r"<object", re.IGNORECASE),
    re.compile(r"<embed", re.IGNORECASE),
]


def contains_xss(text: str) -> bool:
    """Check if text contains potential XSS patterns."""
    return any(p.search(text) for p in _DANGEROUS_PATTERNS)


def sanitize_string(text: str, max_length: int = 1000) -> str:
    """Sanitize a user-supplied string.

    - Truncates to max_length
    - Strips leading/trailing whitespace
    - Rejects XSS patterns
    """
    cleaned = text.strip()[:max_length]
    if contains_xss(cleaned):
        log.warning("input.xss_detected", text_preview=cleaned[:50])
        raise ValueError("Input contains potentially dangerous content")
    return cleaned


# ────────────────────────────────────────────────
# Path Traversal Prevention
# ────────────────────────────────────────────────


def is_path_safe(value: str) -> bool:
    """Check if a value contains path traversal sequences."""
    dangerous = ["..", "/", "\\", "%2e", "%2f", "%5c"]
    lower = value.lower()
    return not any(d in lower for d in dangerous)


# ────────────────────────────────────────────────
# Request Size Validation
# ────────────────────────────────────────────────

MAX_REQUEST_BODY_BYTES = 1_048_576  # 1 MB


def validate_body_size(content_length: Optional[int]) -> bool:
    """Check if request body is within acceptable limits."""
    if content_length is None:
        return True  # No content-length header, streaming
    return content_length <= MAX_REQUEST_BODY_BYTES
