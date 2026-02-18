"""
Bubby Vision — Vision Analysis Engine (EDUCATIONAL / USER-UPLOAD ONLY)

⚠️  This engine is for EDUCATIONAL screenshot analysis only.
    Core platform analysis MUST use direct data engines:
      - ta_engine.py      → indicators (RSI, MACD, BB, etc.)
      - pattern_engine.py  → 40+ patterns from raw OHLCV math
      - breakout_engine.py → 15 breakout precursors from data

    Do NOT use this engine for programmatic/automated analysis.
    Only use when a user explicitly uploads their own screenshot.

Uses Gemini 3 Flash via langchain-google-genai.
"""

from __future__ import annotations

import base64
import json
import re
from typing import Optional

import structlog

from langchain_core.messages import HumanMessage

from app.config import get_settings

log = structlog.get_logger(__name__)


class VisionEngine:
    """Gemini Vision chart analysis engine (EDUCATIONAL / USER-UPLOAD ONLY).

    Sends user-uploaded chart images to Gemini 3 Flash for interpretation.
    All methods accept raw PNG/JPEG bytes and return structured dicts.

    ⚠️  For core analysis, use ta_engine, pattern_engine, breakout_engine instead.
    This engine should ONLY be used when a user uploads their own screenshot.
    """

    def __init__(self):
        self._llm = None

    def _get_llm(self):
        """Lazy-init LLM to avoid import-time API calls."""
        if self._llm is None:
            from langchain_google_genai import ChatGoogleGenerativeAI
            settings = get_settings()
            self._llm = ChatGoogleGenerativeAI(
                model="gemini-3.0-flash",
                google_api_key=settings.google_api_key,
                temperature=0.2,
                max_output_tokens=4096,
            )
        return self._llm

    @staticmethod
    def _image_message(image_bytes: bytes, mime_type: str = "image/png") -> dict:
        """Create an inline image part for Gemini Vision."""
        b64 = base64.b64encode(image_bytes).decode("utf-8")
        return {
            "type": "image_url",
            "image_url": {"url": f"data:{mime_type};base64,{b64}"},
        }

    def _invoke_vision(self, prompt: str, images: list[bytes], mime: str = "image/png") -> str:
        """Send images + prompt to Gemini Vision and return text response.

        Includes robust error handling for API failures, rate limits, and quota.
        """
        try:
            llm = self._get_llm()
            content = [{"type": "text", "text": prompt}]
            for img in images:
                content.append(self._image_message(img, mime))

            message = HumanMessage(content=content)
            response = llm.invoke([message])
            return response.content
        except Exception as e:
            error_str = str(e).lower()
            if "quota" in error_str or "rate" in error_str or "429" in error_str:
                log.warning("vision_rate_limit", error=str(e))
                return json.dumps({
                    "error": "rate_limit",
                    "message": "Gemini Vision API rate limit reached. Try again shortly.",
                    "fallback": "Use deterministic pattern detection (scan_chart_patterns) instead.",
                })
            elif "api_key" in error_str or "401" in error_str or "403" in error_str:
                log.error("vision_auth_error", error=str(e))
                return json.dumps({
                    "error": "auth_failure",
                    "message": "Gemini Vision API authentication failed. Check google_api_key.",
                })
            else:
                log.error("vision_api_error", error=str(e))
                return json.dumps({
                    "error": "api_error",
                    "message": f"Gemini Vision unavailable: {str(e)[:200]}",
                    "fallback": "Use deterministic pattern detection (scan_chart_patterns) as fallback.",
                })

    @staticmethod
    def _parse_json(text: str) -> dict:
        """Extract JSON from LLM response that may contain markdown fences."""
        # Try to find JSON block in markdown code fence
        match = re.search(r"```(?:json)?\s*\n(.*?)\n```", text, re.DOTALL)
        if match:
            text = match.group(1)
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return {"raw_analysis": text}

    # ──────────────────────────────────────────
    # Public API
    # ──────────────────────────────────────────

    def analyze_chart(
        self,
        image_bytes: bytes,
        context: Optional[str] = None,
        mime_type: str = "image/png",
    ) -> dict:
        """Full chart analysis from a screenshot.

        Returns structured analysis: trend, patterns, key levels, bias, trade ideas.
        """
        ctx = f"\n\nAdditional context: {context}" if context else ""
        prompt = f"""Analyze this stock chart image as an expert technical analyst.

Return your analysis as JSON with this structure:
{{
  "trend": "bullish" | "bearish" | "neutral" | "transitioning",
  "trend_strength": "strong" | "moderate" | "weak",
  "patterns_detected": [
    {{"name": "pattern_name", "direction": "bullish/bearish", "confidence": 0.0-1.0}}
  ],
  "key_levels": {{
    "support": [float],
    "resistance": [float]
  }},
  "indicators_observed": ["RSI oversold", "MACD bearish cross", ...],
  "volume_assessment": "description of volume behavior",
  "bias": "bullish" | "bearish" | "neutral",
  "confidence": 0-100,
  "trade_ideas": [
    {{"direction": "long/short", "entry": "condition", "target": "level", "stop": "level"}}
  ],
  "summary": "2-3 sentence summary of the chart"
}}{ctx}"""

        raw = self._invoke_vision(prompt, [image_bytes], mime_type)
        return self._parse_json(raw)

    def narrate_candles(
        self,
        image_bytes: bytes,
        ticker: str = "",
        mime_type: str = "image/png",
    ) -> dict:
        """Candle-by-candle narration of recent price action.

        Produces a narrative description of the last 5-10 visible candles.
        """
        ticker_ctx = f" for {ticker}" if ticker else ""
        prompt = f"""You are a professional chart narrator. Describe the visible candlestick price action{ticker_ctx} in this chart image.

Narrate the last 5-10 visible candles in sequence, describing:
- Open/close relationship (green/red body)
- Shadow length and what it means
- Any notable patterns
- Volume changes if visible

Return as JSON:
{{
  "ticker": "{ticker or 'unknown'}",
  "candle_count_narrated": int,
  "narration": [
    {{"bar_number": 1, "type": "bullish/bearish/doji", "body": "large/medium/small", "shadows": "description", "significance": "what it means"}}
  ],
  "overall_story": "2-3 sentence narrative of the price action arc",
  "key_moment": "the most significant candle and why"
}}"""

        raw = self._invoke_vision(prompt, [image_bytes], mime_type)
        return self._parse_json(raw)

    def compare_charts(
        self,
        images: list[bytes],
        tickers: Optional[list[str]] = None,
        mime_type: str = "image/png",
    ) -> dict:
        """Compare multiple charts for correlation, divergence, or relative strength.

        Accepts up to 4 chart images.
        """
        if len(images) > 4:
            images = images[:4]

        ticker_names = tickers or [f"Chart {i+1}" for i in range(len(images))]
        ticker_list = ", ".join(ticker_names)

        prompt = f"""Compare these {len(images)} stock charts ({ticker_list}) as an expert technical analyst.

Analyze for:
1. Correlation — are they moving together?
2. Relative strength — which is strongest/weakest?
3. Divergences — any diverging trends?
4. Lead/lag — is one leading the others?

Return as JSON:
{{
  "charts_compared": {len(images)},
  "tickers": {json.dumps(ticker_names)},
  "correlation": "high" | "moderate" | "low" | "inverse",
  "relative_strength_ranking": ["strongest_ticker", ..., "weakest_ticker"],
  "divergences": ["description of any divergences"],
  "leader": "ticker that appears to lead",
  "sector_trend": "overall sector/market direction assessment",
  "trade_recommendation": "which to buy/sell based on relative analysis",
  "summary": "3-4 sentence comparative summary"
}}"""

        raw = self._invoke_vision(prompt, images, mime_type)
        return self._parse_json(raw)

    def identify_patterns(
        self,
        image_bytes: bytes,
        mime_type: str = "image/png",
    ) -> dict:
        """Pattern-only identification from a chart image.

        Focuses solely on technical and candlestick pattern recognition.
        """
        prompt = """Identify ALL technical and candlestick patterns visible in this chart image.

For each pattern, provide:
- Name (standard TA nomenclature)
- Type: "candlestick", "chart_structure", "indicator"
- Direction: "bullish", "bearish", "neutral"
- Confidence: 0.0 to 1.0
- Stage: "forming", "confirmed", "completing"
- Price level where pattern occurs (if visible)

Return as JSON:
{
  "patterns": [
    {
      "name": "pattern_name",
      "type": "candlestick" | "chart_structure" | "indicator",
      "direction": "bullish" | "bearish" | "neutral",
      "confidence": 0.0-1.0,
      "stage": "forming" | "confirmed" | "completing",
      "price_level": float | null,
      "description": "brief explanation"
    }
  ],
  "pattern_count": int,
  "dominant_direction": "bullish" | "bearish" | "neutral",
  "actionable_patterns": ["list of patterns that suggest immediate action"]
}"""

        raw = self._invoke_vision(prompt, [image_bytes], mime_type)
        return self._parse_json(raw)

    def analyze_emerging_setups(
        self,
        image_bytes: bytes,
        ticker: str = "",
        mime_type: str = "image/png",
    ) -> dict:
        """AI-powered detection of forming, imminent, and predicted patterns.

        Unlike identify_patterns which focuses on confirmed patterns, this method
        specifically instructs Gemini to look for patterns that are NOT YET
        confirmed but show early formation signs — enabling predictive action.
        """
        ticker_ctx = f" for {ticker}" if ticker else ""

        prompt = f"""You are a predictive pattern recognition specialist{ticker_ctx}. Your job is NOT to identify confirmed patterns — instead, focus exclusively on:

1. **FORMING PATTERNS** — structural setups that are 50-85% complete:
   - Partial head & shoulders (left shoulder + head formed, watching for right shoulder)
   - Developing triangles (converging highs/lows, not yet broken)
   - Forming double tops/bottoms (one peak/trough formed, approaching for second test)
   - Developing cup & handle (U-shape recovery in progress)
   - Forming wedges (converging price channel with slope)
   - Emerging flags (strong impulse followed by tight consolidation beginning)

2. **PRE-CANDLE FORMATIONS** — setups where the NEXT candle could confirm a pattern:
   - Two candles of a morning/evening star already formed
   - Two ascending greens ready for three white soldiers
   - Harami formed, watching for confirmation bar
   - Setup bar for engulfing pattern

3. **PREDICTIVE SETUPS** — structural conditions that typically precede specific movements:
   - Volume climax + exhaustion signs suggesting imminent reversal
   - Coiling volatility (narrowing range) suggesting imminent breakout
   - Divergence between price and indicators
   - Support/resistance zones being tested with weakening conviction
   - Trend line approaching intersection with price

4. **EARLY WARNING SIGNALS** — subtle clues that most traders miss:
   - Shadow analysis (lengthening upper/lower shadows suggesting pressure)
   - Body size changes (shrinking bodies suggesting indecision)
   - Volume dry-up in consolidation (coiled spring)
   - Failed tests of key levels

Return as JSON:
{{
  "emerging_patterns": [
    {{
      "name": "pattern name + (Forming)",
      "progress_pct": 0-100,
      "direction": "bullish" | "bearish" | "neutral",
      "confidence": 0.0-1.0,
      "watch_level": "price level to watch for confirmation",
      "invalidation": "price level that would negate this setup",
      "bars_to_completion": "estimated bars until pattern completes",
      "description": "what to watch for next"
    }}
  ],
  "pre_candle_setups": [
    {{
      "setup_name": "e.g. Pre-Morning Star",
      "confirmation_needed": "what the next candle needs to look like",
      "direction": "bullish" | "bearish",
      "probability": 0.0-1.0
    }}
  ],
  "predictive_signals": [
    {{
      "signal": "description of the predictive condition",
      "expected_outcome": "what this typically leads to",
      "timeframe": "when this is likely to play out",
      "confidence": 0.0-1.0
    }}
  ],
  "early_warnings": ["list of subtle warning signs visible in the chart"],
  "highest_conviction_setup": {{
    "name": "the single most actionable emerging setup",
    "direction": "bullish" | "bearish",
    "reasoning": "why this is the strongest emerging signal"
  }}
}}"""

        raw = self._invoke_vision(prompt, [image_bytes], mime_type)
        return self._parse_json(raw)

    def multi_timeframe_vision(
        self,
        images: list[tuple[bytes, str]],
        ticker: str = "",
        mime_type: str = "image/png",
    ) -> dict:
        """Analyze the same ticker across multiple timeframe screenshots.

        Compares charts at different timeframes to identify:
        - Cross-timeframe alignment or divergence
        - Fractal patterns (same structure at different scales)
        - Timeframe-specific signals that reinforce or contradict
        - The dominant timeframe driving price action

        Args:
            images: List of (image_bytes, timeframe_label) tuples.
                    e.g. [(daily_bytes, "Daily"), (hourly_bytes, "1H"), (weekly_bytes, "Weekly")]
            ticker: Optional ticker symbol for context.
            mime_type: Image MIME type.
        """
        ticker_ctx = f" for {ticker}" if ticker else ""
        tf_labels = [label for _, label in images]

        prompt = f"""You are a multi-timeframe analysis specialist{ticker_ctx}. You have {len(images)} chart screenshots at timeframes: {', '.join(tf_labels)}.

Analyze the cross-timeframe structure:

1. **TIMEFRAME ALIGNMENT**: Do all timeframes agree on direction? Or is there divergence?
2. **FRACTAL PATTERNS**: Is the same pattern visible at multiple timeframes? (e.g., triangle on both daily and 4H)
3. **DOMINANT TIMEFRAME**: Which timeframe is currently driving price action?
4. **CONFLICT RESOLUTION**: If timeframes disagree, which should take priority and why?
5. **EMERGING SETUPS ACROSS TF**: Patterns forming at higher timeframes that align with signals on lower ones

Return as JSON:
{{
  "timeframes_analyzed": {json.dumps(tf_labels)},
  "alignment": {{
    "score": 0-100,
    "label": "strong" | "moderate" | "weak" | "divergent",
    "description": "how aligned the timeframes are"
  }},
  "per_timeframe": [
    {{
      "timeframe": "label",
      "trend": "up" | "down" | "sideways",
      "bias": "bullish" | "bearish" | "neutral",
      "key_patterns": ["patterns visible at this timeframe"],
      "key_levels": ["important S/R levels"]
    }}
  ],
  "fractal_patterns": [
    {{
      "pattern": "pattern visible at multiple timeframes",
      "timeframes": ["list of TFs where it appears"],
      "significance": "why this fractal matters"
    }}
  ],
  "dominant_timeframe": {{
    "timeframe": "which TF dominates",
    "reason": "why this TF is dominant"
  }},
  "cross_tf_trade": {{
    "direction": "bullish" | "bearish" | "neutral",
    "entry_timeframe": "best TF for entry timing",
    "confirmation_timeframe": "TF for trend confirmation",
    "reasoning": "cross-TF trade thesis"
  }},
  "conflicts": ["any timeframe disagreements noted"],
  "summary": "2-3 sentence multi-timeframe assessment"
}}"""

        image_bytes_list = [img for img, _ in images]
        raw = self._invoke_vision(prompt, image_bytes_list, mime_type)
        return self._parse_json(raw)

    def chart_health_report(
        self,
        image_bytes: bytes,
        indicators: Optional[dict] = None,
        mime_type: str = "image/png",
    ) -> dict:
        """Overall chart health assessment combining visual + indicator data.

        Produces a 0-100 health score across multiple dimensions.
        """
        indicator_ctx = ""
        if indicators:
            indicator_ctx = f"\n\nNumerical indicators data: {json.dumps(indicators, default=str)}"

        prompt = f"""Generate a comprehensive chart health report as an expert analyst.

Score each dimension 0-100:
- Trend Health: clarity and strength of the current trend
- Momentum: RSI/MACD/Stochastic momentum assessment
- Volume Health: volume confirmation of price moves
- Volatility: whether volatility is normal, expanding, or contracting
- Risk: overall risk level (100 = low risk, 0 = high risk)

Return as JSON:
{{
  "overall_health": 0-100,
  "grade": "A+" | "A" | "B" | "C" | "D" | "F",
  "scores": {{
    "trend": 0-100,
    "momentum": 0-100,
    "volume": 0-100,
    "volatility": 0-100,
    "risk": 0-100
  }},
  "trend_description": "current trend state",
  "key_risks": ["list of top risks"],
  "key_opportunities": ["list of top opportunities"],
  "recommendation": "hold" | "buy" | "sell" | "watch",
  "time_horizon": "day_trade" | "swing" | "position",
  "summary": "3-4 sentence health assessment"
}}{indicator_ctx}"""

        raw = self._invoke_vision(prompt, [image_bytes], mime_type)
        return self._parse_json(raw)
