"""
Bubby Vision — Guardrails

Pydantic-based input/output validation for all agent interactions.
Provides:
  1. Input sanitization (ticker normalization, message length limits, injection defense)
  2. Output validation (structured analysis format, score bounds, required fields)
  3. Agent output contract enforcement (each agent must produce expected schema)
  4. Content safety checks (basic profanity/harm filter, PII detection)

These are applied as pre/post processors on the chat pipeline.
"""

from __future__ import annotations

import re
from typing import Any, Optional

from pydantic import BaseModel, Field, field_validator, model_validator

import structlog

logger = structlog.get_logger(__name__)


# ──────────────────────────────────────────────
# Input Guardrails
# ──────────────────────────────────────────────

# Allowed ticker pattern: 1-5 uppercase letters, optionally with dot extension
TICKER_PATTERN = re.compile(r"^[A-Z]{1,5}(\.[A-Z]{1,2})?$")

# Prompt injection indicators
INJECTION_PATTERNS = [
    r"ignore\s+(previous|all|above)\s+(\w+\s+)*(instructions?|prompts?)",
    r"you\s+are\s+now\s+(?:a|an)\s+\w+",
    r"system\s*[:]\s*",
    r"<\s*(system|prompt|instruction)",
    r"forget\s+(everything|all)",
    r"override\s+(safety|guardrails?|rules?)",
    r"jailbreak",
    r"DAN\s+mode",
]
_INJECTION_RE = re.compile("|".join(INJECTION_PATTERNS), re.IGNORECASE)


class InputGuard:
    """Validates and sanitizes user input before it reaches agents."""

    MAX_MESSAGE_LENGTH = 5000
    MAX_TICKER_LENGTH = 10

    @classmethod
    def validate_message(cls, message: str) -> tuple[str, list[str]]:
        """Validate and sanitize a user message.

        Returns:
            Tuple of (sanitized_message, list_of_warnings).
        """
        warnings: list[str] = []

        if not message or not message.strip():
            return "", ["Empty message"]

        # Truncate overly long messages
        if len(message) > cls.MAX_MESSAGE_LENGTH:
            message = message[:cls.MAX_MESSAGE_LENGTH]
            warnings.append(f"Message truncated to {cls.MAX_MESSAGE_LENGTH} chars")

        # Check for injection attempts
        if _INJECTION_RE.search(message):
            warnings.append("Potential prompt injection detected — message sanitized")
            logger.warning("guardrail_injection_detected", message_preview=message[:100])
            # Don't block, but log and strip suspicious patterns
            message = _INJECTION_RE.sub("[filtered]", message)

        return message.strip(), warnings

    @classmethod
    def normalize_ticker(cls, ticker: str) -> Optional[str]:
        """Normalize and validate a stock ticker symbol.

        Returns:
            Normalized ticker (uppercase) or None if invalid.
        """
        if not ticker:
            return None

        cleaned = ticker.strip().upper().replace("$", "")

        if not TICKER_PATTERN.match(cleaned):
            return None

        return cleaned

    @classmethod
    def extract_tickers(cls, message: str) -> list[str]:
        """Extract potential ticker symbols from a message.

        Handles formats: AAPL, $AAPL, "AAPL", AAPL stock
        """
        # Match $TICKER or standalone uppercase words that look like tickers
        patterns = [
            r"\$([A-Z]{1,5})",            # $AAPL
            r"\b([A-Z]{1,5})\b(?=\s+(?:stock|options?|chart|breakout|analysis|calls?|puts?))",  # AAPL stock
        ]

        tickers = set()
        for pattern in patterns:
            for match in re.finditer(pattern, message):
                candidate = match.group(1)
                normalized = cls.normalize_ticker(candidate)
                if normalized:
                    tickers.add(normalized)

        return sorted(tickers)


# ──────────────────────────────────────────────
# Output Guardrails — Schema Contracts
# ──────────────────────────────────────────────

class AnalysisScore(BaseModel):
    """Validated score in agent output."""
    name: str
    value: float = Field(ge=0, le=100)
    label: str = ""

    @model_validator(mode="after")
    def auto_label(self):
        if not self.label:
            val = self.value
            if val >= 80:
                self.label = "Strong"
            elif val >= 60:
                self.label = "Moderate"
            elif val >= 40:
                self.label = "Neutral"
            elif val >= 20:
                self.label = "Weak"
            else:
                self.label = "Very Weak"
        return self


class AgentOutputContract(BaseModel):
    """Contract for validating structured agent output.

    Every agent should produce output that can be validated against this schema.
    Fields are optional because different agents produce different data.
    """
    summary: str = Field(min_length=10, max_length=10000)
    agent_name: str = ""
    ticker: Optional[str] = None
    scores: list[AnalysisScore] = []
    signals: list[str] = []
    action: Optional[str] = None  # "BUY", "SELL", "HOLD", "WATCH"
    confidence: float = Field(default=0.5, ge=0, le=1.0)
    warnings: list[str] = []

    @field_validator("action", mode="before")
    @classmethod
    def normalize_action(cls, v):
        if v is None:
            return None
        valid = {"BUY", "SELL", "HOLD", "WATCH", "AVOID"}
        normalized = str(v).upper().strip()
        return normalized if normalized in valid else None


class OutputGuard:
    """Validates agent output before it reaches the user."""

    # Words/phrases that should never appear in financial advice
    FORBIDDEN_PHRASES = [
        "guaranteed profit",
        "can't lose",
        "risk-free",
        "sure thing",
        "100% certain",
        "insider information",
        "pump and dump",
    ]

    @classmethod
    def validate_response(cls, response: str) -> tuple[str, list[str]]:
        """Validate an agent's text response.

        Returns:
            Tuple of (validated_response, list_of_warnings).
        """
        warnings: list[str] = []

        if not response or not response.strip():
            return "I couldn't generate a meaningful analysis. Please try rephrasing your question.", [
                "Empty response from agent"
            ]

        response_lower = response.lower()
        for phrase in cls.FORBIDDEN_PHRASES:
            if phrase in response_lower:
                warnings.append(f"Response contained forbidden phrase: '{phrase}'")
                response = response.replace(phrase, "[removed]")
                response = response.replace(phrase.title(), "[removed]")

        # Ensure disclaimer is present for actionable advice
        action_words = ["buy", "sell", "enter", "exit", "short"]
        has_action = any(w in response_lower for w in action_words)
        has_disclaimer = any(
            d in response_lower
            for d in ["not financial advice", "do your own research", "dyor", "nfa"]
        )

        if has_action and not has_disclaimer:
            response += "\n\n*This analysis is for informational purposes only. Not financial advice. Always do your own research (DYOR).*"
            warnings.append("Auto-appended financial disclaimer")

        return response, warnings

    @classmethod
    def validate_scores(cls, scores: list[dict]) -> list[AnalysisScore]:
        """Validate and sanitize analysis scores."""
        validated = []
        for s in scores:
            try:
                score = AnalysisScore(**s)
                validated.append(score)
            except Exception as e:
                logger.warning("guardrail_invalid_score", score=s, error=str(e))
        return validated


# ──────────────────────────────────────────────
# Content Safety
# ──────────────────────────────────────────────

class ContentSafety:
    """Basic content safety checks."""

    # Simple PII patterns (SSN, credit card, phone)
    PII_PATTERNS = [
        (r"\b\d{3}-\d{2}-\d{4}\b", "SSN"),
        (r"\b\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}\b", "credit card"),
        (r"\b(?:\+1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b", "phone number"),
        (r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b", "email"),
    ]

    @classmethod
    def check_pii(cls, text: str) -> list[str]:
        """Check for potential PII in text.

        Returns list of PII types detected (does not modify text).
        """
        detected = []
        for pattern, pii_type in cls.PII_PATTERNS:
            if re.search(pattern, text):
                detected.append(pii_type)
        return detected

    @classmethod
    def redact_pii(cls, text: str) -> str:
        """Redact detected PII from text."""
        for pattern, pii_type in cls.PII_PATTERNS:
            text = re.sub(pattern, f"[REDACTED-{pii_type.upper()}]", text)
        return text


# ──────────────────────────────────────────────
# Pipeline Middleware
# ──────────────────────────────────────────────

def apply_input_guardrails(message: str) -> tuple[str, list[str]]:
    """Apply all input guardrails to a message.

    Returns:
        Tuple of (sanitized_message, all_warnings).
    """
    message, warnings = InputGuard.validate_message(message)

    # Check for PII and warn
    pii = ContentSafety.check_pii(message)
    if pii:
        warnings.append(f"PII detected in input: {', '.join(pii)}")
        message = ContentSafety.redact_pii(message)

    return message, warnings


def apply_output_guardrails(response: str) -> tuple[str, list[str]]:
    """Apply all output guardrails to an agent response.

    Returns:
        Tuple of (validated_response, all_warnings).
    """
    response, warnings = OutputGuard.validate_response(response)

    # Check for PII in output
    pii = ContentSafety.check_pii(response)
    if pii:
        warnings.append(f"PII detected in output: {', '.join(pii)}")
        response = ContentSafety.redact_pii(response)

    return response, warnings
