"""
Bubby Vision — Pattern Detection Engine

Rule-based detection of 40+ candlestick and chart patterns from OHLCV data.
Deterministic analysis — no ML/GPU required.

Candlestick Patterns (~25):
  Single:  Doji, Hammer, Inverted Hammer, Shooting Star, Spinning Top,
           Marubozu (Bull/Bear), Hanging Man, Dragonfly/Gravestone Doji
  Double:  Engulfing (Bull/Bear), Harami, Tweezer Top/Bottom,
           Piercing Pattern, Dark Cloud Cover
  Triple:  Morning/Evening Star, Three White Soldiers, Three Black Crows,
           Three Inside Up/Down, Abandoned Baby (Bull/Bear)

Chart Patterns (~15):
  Double Top/Bottom, Head & Shoulders (& Inverse), Rising/Falling Wedge,
  Ascending/Descending/Symmetrical Triangle, Bull/Bear Flag,
  Cup & Handle, Rectangle, Channel (Ascending/Descending)
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Optional

import numpy as np

from app.models import OHLCV


# ──────────────────────────────────────────────
# Pattern Result Data Models
# ──────────────────────────────────────────────

@dataclass
class PatternSignal:
    """A single detected pattern."""
    name: str
    category: str          # "candlestick" | "chart"
    direction: str         # "bullish" | "bearish" | "neutral"
    confidence: float      # 0.0 – 1.0
    bar_index: int         # index in the bars list where pattern ends
    description: str = ""
    entry_trigger: Optional[float] = None
    target: Optional[float] = None
    stop_loss: Optional[float] = None

    def to_dict(self) -> dict:
        return {k: v for k, v in asdict(self).items() if v is not None}


@dataclass
class PatternScanResult:
    """Full scan result."""
    candlestick_patterns: list[PatternSignal] = field(default_factory=list)
    chart_patterns: list[PatternSignal] = field(default_factory=list)
    pattern_count: int = 0
    bullish_count: int = 0
    bearish_count: int = 0
    overall_bias: str = "neutral"

    def to_dict(self) -> dict:
        d = asdict(self)
        d["candlestick_patterns"] = [p.to_dict() for p in self.candlestick_patterns]
        d["chart_patterns"] = [p.to_dict() for p in self.chart_patterns]
        return d


class PatternEngine:
    """Rule-based candlestick and chart pattern detector.

    Usage:
        engine = PatternEngine()
        result = engine.scan_all_patterns(bars)
    """

    # ──────────────────────────────────────────
    # Public API
    # ──────────────────────────────────────────

    def detect_candlestick_patterns(self, bars: list[OHLCV]) -> list[PatternSignal]:
        """Scan for all candlestick patterns in recent bars."""
        if len(bars) < 5:
            return []

        o = np.array([b.open for b in bars])
        h = np.array([b.high for b in bars])
        l = np.array([b.low for b in bars])
        c = np.array([b.close for b in bars])

        patterns: list[PatternSignal] = []

        # Scan last 10 bars (or all if less)
        scan_range = range(max(3, len(bars) - 10), len(bars))

        for i in scan_range:
            # ── Single-bar patterns ──
            patterns.extend(self._single_bar(o, h, l, c, i))

            # ── Double-bar patterns ──
            if i >= 1:
                patterns.extend(self._double_bar(o, h, l, c, i))

            # ── Triple-bar patterns ──
            if i >= 2:
                patterns.extend(self._triple_bar(o, h, l, c, i))

        return patterns

    def detect_chart_patterns(self, bars: list[OHLCV]) -> list[PatternSignal]:
        """Detect structural chart patterns using swing highs/lows."""
        if len(bars) < 30:
            return []

        h = np.array([b.high for b in bars])
        l = np.array([b.low for b in bars])
        c = np.array([b.close for b in bars])

        # Find swing highs and lows
        swing_highs = self._find_swings(h, mode="high", order=5)
        swing_lows = self._find_swings(l, mode="low", order=5)

        patterns: list[PatternSignal] = []

        patterns.extend(self._detect_double_top(swing_highs, c, bars))
        patterns.extend(self._detect_double_bottom(swing_lows, c, bars))
        patterns.extend(self._detect_head_and_shoulders(swing_highs, swing_lows, c, bars))
        patterns.extend(self._detect_inverse_head_and_shoulders(swing_highs, swing_lows, c, bars))
        patterns.extend(self._detect_triangles(swing_highs, swing_lows, c, bars))
        patterns.extend(self._detect_wedges(swing_highs, swing_lows, c, bars))
        patterns.extend(self._detect_flags(h, l, c, bars))
        patterns.extend(self._detect_cup_and_handle(swing_lows, c, bars))
        patterns.extend(self._detect_channels(swing_highs, swing_lows, c, bars))
        patterns.extend(self._detect_rectangle(swing_highs, swing_lows, c, bars))

        return patterns

    def scan_all_patterns(self, bars: list[OHLCV]) -> dict:
        """Combined candlestick + chart pattern scan."""
        candle = self.detect_candlestick_patterns(bars)
        chart = self.detect_chart_patterns(bars)

        all_patterns = candle + chart
        bullish = sum(1 for p in all_patterns if p.direction == "bullish")
        bearish = sum(1 for p in all_patterns if p.direction == "bearish")

        if bullish > bearish:
            bias = "bullish"
        elif bearish > bullish:
            bias = "bearish"
        else:
            bias = "neutral"

        result = PatternScanResult(
            candlestick_patterns=candle,
            chart_patterns=chart,
            pattern_count=len(all_patterns),
            bullish_count=bullish,
            bearish_count=bearish,
            overall_bias=bias,
        )
        return result.to_dict()

    def pattern_confluence(
        self,
        bars: list[OHLCV],
        indicators: dict,
    ) -> dict:
        """Cross-reference detected patterns with technical indicators.

        Returns a conviction score (0-100) combining pattern signals
        with RSI, MACD, volume, and trend alignment.
        """
        scan = self.scan_all_patterns(bars)
        score = 50  # Neutral baseline

        # Pattern bias contribution (±20 max)
        bias = scan["overall_bias"]
        pattern_count = scan["pattern_count"]
        if bias == "bullish":
            score += min(20, pattern_count * 5)
        elif bias == "bearish":
            score -= min(20, pattern_count * 5)

        # RSI alignment (±10)
        rsi = indicators.get("rsi_14")
        if rsi is not None:
            if bias == "bullish" and rsi < 40:
                score += 10  # oversold + bullish pattern
            elif bias == "bearish" and rsi > 60:
                score -= 10  # overbought + bearish pattern

        # MACD alignment (±10)
        macd_hist = indicators.get("macd_histogram")
        if macd_hist is not None:
            if bias == "bullish" and macd_hist > 0:
                score += 10
            elif bias == "bearish" and macd_hist < 0:
                score -= 10

        # Volume confirmation (±10)
        rel_vol = indicators.get("relative_volume")
        if rel_vol is not None and rel_vol > 1.5:
            if bias in ("bullish", "bearish"):
                score += 10 if bias == "bullish" else -10

        score = max(0, min(100, score))

        return {
            "conviction_score": score,
            "pattern_scan": scan,
            "bias": bias,
            "alignment": {
                "rsi_supports": rsi is not None and (
                    (bias == "bullish" and rsi < 40) or
                    (bias == "bearish" and rsi > 60)
                ),
                "macd_supports": macd_hist is not None and (
                    (bias == "bullish" and macd_hist > 0) or
                    (bias == "bearish" and macd_hist < 0)
                ),
                "volume_confirms": rel_vol is not None and rel_vol > 1.5,
            },
            "recommendation": (
                "strong_signal" if abs(score - 50) >= 30 else
                "moderate_signal" if abs(score - 50) >= 15 else
                "weak_signal"
            ),
        }

    # ──────────────────────────────────────────
    # Single-Bar Candlestick Patterns
    # ──────────────────────────────────────────

    def _single_bar(self, o, h, l, c, i: int) -> list[PatternSignal]:
        """Detect single-bar patterns at index i."""
        patterns = []
        body = abs(c[i] - o[i])
        rng = h[i] - l[i]
        if rng == 0:
            return patterns

        body_pct = body / rng
        upper_shadow = h[i] - max(o[i], c[i])
        lower_shadow = min(o[i], c[i]) - l[i]

        # Average body for context
        lookback = min(14, i)
        if lookback > 0:
            avg_body = np.mean(np.abs(c[i - lookback:i] - o[i - lookback:i]))
        else:
            avg_body = body

        # Doji — tiny body relative to range
        if body_pct < 0.10 and rng > 0:
            # Dragonfly (long lower shadow, no upper)
            if lower_shadow > 2 * body and upper_shadow < body:
                patterns.append(PatternSignal(
                    name="Dragonfly Doji", category="candlestick",
                    direction="bullish", confidence=0.65,
                    bar_index=i, description="Dragonfly doji — bullish reversal signal after downtrend",
                ))
            # Gravestone (long upper shadow, no lower)
            elif upper_shadow > 2 * body and lower_shadow < body:
                patterns.append(PatternSignal(
                    name="Gravestone Doji", category="candlestick",
                    direction="bearish", confidence=0.65,
                    bar_index=i, description="Gravestone doji — bearish reversal signal after uptrend",
                ))
            else:
                patterns.append(PatternSignal(
                    name="Doji", category="candlestick",
                    direction="neutral", confidence=0.50,
                    bar_index=i, description="Doji — indecision, potential reversal",
                ))

        # Hammer — small body at top, long lower shadow
        elif body_pct < 0.35 and lower_shadow > 2 * body and upper_shadow < body * 0.5:
            # Check if we're in a downtrend (last 5 bars)
            if i >= 5 and c[i] < c[i - 5]:
                patterns.append(PatternSignal(
                    name="Hammer", category="candlestick",
                    direction="bullish", confidence=0.68,
                    bar_index=i, description="Hammer — bullish reversal after downtrend",
                    entry_trigger=float(h[i]),
                ))
            else:
                patterns.append(PatternSignal(
                    name="Hanging Man", category="candlestick",
                    direction="bearish", confidence=0.60,
                    bar_index=i, description="Hanging man — bearish warning after uptrend",
                ))

        # Inverted Hammer / Shooting Star
        elif body_pct < 0.35 and upper_shadow > 2 * body and lower_shadow < body * 0.5:
            if i >= 5 and c[i] < c[i - 5]:
                patterns.append(PatternSignal(
                    name="Inverted Hammer", category="candlestick",
                    direction="bullish", confidence=0.60,
                    bar_index=i, description="Inverted hammer — potential bullish reversal",
                ))
            else:
                patterns.append(PatternSignal(
                    name="Shooting Star", category="candlestick",
                    direction="bearish", confidence=0.68,
                    bar_index=i, description="Shooting star — bearish reversal signal",
                    entry_trigger=float(l[i]),
                ))

        # Spinning Top
        elif 0.10 <= body_pct < 0.30 and upper_shadow > body and lower_shadow > body:
            patterns.append(PatternSignal(
                name="Spinning Top", category="candlestick",
                direction="neutral", confidence=0.45,
                bar_index=i, description="Spinning top — indecision, trend may stall",
            ))

        # Marubozu — full body, almost no shadows
        elif body_pct > 0.90:
            direction = "bullish" if c[i] > o[i] else "bearish"
            patterns.append(PatternSignal(
                name=f"{'Bullish' if direction == 'bullish' else 'Bearish'} Marubozu",
                category="candlestick",
                direction=direction, confidence=0.72,
                bar_index=i,
                description=f"{'Bullish' if direction == 'bullish' else 'Bearish'} marubozu — strong {direction} conviction",
            ))

        return patterns

    # ──────────────────────────────────────────
    # Double-Bar Candlestick Patterns
    # ──────────────────────────────────────────

    def _double_bar(self, o, h, l, c, i: int) -> list[PatternSignal]:
        """Detect two-bar patterns ending at index i."""
        patterns = []
        prev = i - 1

        body_now = abs(c[i] - o[i])
        body_prev = abs(c[prev] - o[prev])
        rng_now = h[i] - l[i]

        if body_prev == 0 or rng_now == 0:
            return patterns

        # Bullish Engulfing
        if (c[prev] < o[prev] and c[i] > o[i] and  # prev red, now green
            o[i] <= c[prev] and c[i] >= o[prev] and  # body engulfs
            body_now > body_prev):
            patterns.append(PatternSignal(
                name="Bullish Engulfing", category="candlestick",
                direction="bullish", confidence=0.75,
                bar_index=i, description="Bullish engulfing — strong reversal signal",
                entry_trigger=float(h[i]),
            ))

        # Bearish Engulfing
        elif (c[prev] > o[prev] and c[i] < o[i] and  # prev green, now red
              o[i] >= c[prev] and c[i] <= o[prev] and  # body engulfs
              body_now > body_prev):
            patterns.append(PatternSignal(
                name="Bearish Engulfing", category="candlestick",
                direction="bearish", confidence=0.75,
                bar_index=i, description="Bearish engulfing — strong reversal signal",
                entry_trigger=float(l[i]),
            ))

        # Bullish Harami
        elif (c[prev] < o[prev] and c[i] > o[i] and  # prev red, now green
              c[i] < o[prev] and o[i] > c[prev] and  # inside previous body
              body_now < body_prev * 0.5):
            patterns.append(PatternSignal(
                name="Bullish Harami", category="candlestick",
                direction="bullish", confidence=0.58,
                bar_index=i, description="Bullish harami — potential reversal, needs confirmation",
            ))

        # Bearish Harami
        elif (c[prev] > o[prev] and c[i] < o[i] and
              c[i] > o[prev] and o[i] < c[prev] and
              body_now < body_prev * 0.5):
            patterns.append(PatternSignal(
                name="Bearish Harami", category="candlestick",
                direction="bearish", confidence=0.58,
                bar_index=i, description="Bearish harami — potential reversal, needs confirmation",
            ))

        # Tweezer Top — same highs, one green one red
        if abs(h[i] - h[prev]) / max(h[i], 0.01) < 0.002:
            if c[prev] > o[prev] and c[i] < o[i]:  # green then red
                patterns.append(PatternSignal(
                    name="Tweezer Top", category="candlestick",
                    direction="bearish", confidence=0.62,
                    bar_index=i, description="Tweezer top — bearish reversal at resistance",
                ))

        # Tweezer Bottom — same lows
        if abs(l[i] - l[prev]) / max(l[i], 0.01) < 0.002:
            if c[prev] < o[prev] and c[i] > o[i]:  # red then green
                patterns.append(PatternSignal(
                    name="Tweezer Bottom", category="candlestick",
                    direction="bullish", confidence=0.62,
                    bar_index=i, description="Tweezer bottom — bullish reversal at support",
                ))

        # Piercing Pattern — strong bullish after gap down
        if (c[prev] < o[prev] and c[i] > o[i] and  # prev red, now green
            o[i] < c[prev] and  # gap down open
            c[i] > (o[prev] + c[prev]) / 2 and c[i] < o[prev]):  # closes above midpoint
            patterns.append(PatternSignal(
                name="Piercing Pattern", category="candlestick",
                direction="bullish", confidence=0.66,
                bar_index=i, description="Piercing pattern — bullish reversal with gap-down recovery",
            ))

        # Dark Cloud Cover — opposite of piercing
        if (c[prev] > o[prev] and c[i] < o[i] and  # prev green, now red
            o[i] > c[prev] and  # gap up open
            c[i] < (o[prev] + c[prev]) / 2 and c[i] > o[prev]):  # closes below midpoint
            patterns.append(PatternSignal(
                name="Dark Cloud Cover", category="candlestick",
                direction="bearish", confidence=0.66,
                bar_index=i, description="Dark cloud cover — bearish reversal with gap-up rejection",
            ))

        return patterns

    # ──────────────────────────────────────────
    # Triple-Bar Candlestick Patterns
    # ──────────────────────────────────────────

    def _triple_bar(self, o, h, l, c, i: int) -> list[PatternSignal]:
        """Detect three-bar patterns ending at index i."""
        patterns = []
        p1, p2 = i - 2, i - 1  # first, middle

        body_1 = abs(c[p1] - o[p1])
        body_2 = abs(c[p2] - o[p2])
        body_3 = abs(c[i] - o[i])
        rng_2 = h[p2] - l[p2]

        # Morning Star (bullish)
        if (c[p1] < o[p1] and body_1 > 0 and  # big red
            rng_2 > 0 and body_2 / rng_2 < 0.30 and  # small body / doji
            c[i] > o[i] and  # green
            c[i] > (o[p1] + c[p1]) / 2):  # closes above midpoint of first
            patterns.append(PatternSignal(
                name="Morning Star", category="candlestick",
                direction="bullish", confidence=0.78,
                bar_index=i, description="Morning star — strong three-bar bullish reversal",
                entry_trigger=float(h[i]),
            ))

        # Evening Star (bearish)
        elif (c[p1] > o[p1] and body_1 > 0 and  # big green
              rng_2 > 0 and body_2 / rng_2 < 0.30 and  # small body / doji
              c[i] < o[i] and  # red
              c[i] < (o[p1] + c[p1]) / 2):  # closes below midpoint of first
            patterns.append(PatternSignal(
                name="Evening Star", category="candlestick",
                direction="bearish", confidence=0.78,
                bar_index=i, description="Evening star — strong three-bar bearish reversal",
                entry_trigger=float(l[i]),
            ))

        # Three White Soldiers
        if (c[p1] > o[p1] and c[p2] > o[p2] and c[i] > o[i] and  # 3 green
            c[p2] > c[p1] and c[i] > c[p2] and  # ascending closes
            o[p2] > o[p1] and o[i] > o[p2] and  # ascending opens
            body_1 > 0 and body_2 > 0 and body_3 > 0):
            patterns.append(PatternSignal(
                name="Three White Soldiers", category="candlestick",
                direction="bullish", confidence=0.80,
                bar_index=i, description="Three white soldiers — very strong bullish continuation",
            ))

        # Three Black Crows
        elif (c[p1] < o[p1] and c[p2] < o[p2] and c[i] < o[i] and  # 3 red
              c[p2] < c[p1] and c[i] < c[p2] and  # descending closes
              o[p2] < o[p1] and o[i] < o[p2] and
              body_1 > 0 and body_2 > 0 and body_3 > 0):
            patterns.append(PatternSignal(
                name="Three Black Crows", category="candlestick",
                direction="bearish", confidence=0.80,
                bar_index=i, description="Three black crows — very strong bearish continuation",
            ))

        # Three Inside Up
        if (c[p1] < o[p1] and  # first red
            c[p2] > o[p2] and o[p2] > c[p1] and c[p2] < o[p1] and  # harami
            c[i] > o[i] and c[i] > o[p1]):  # confirmation close above first open
            patterns.append(PatternSignal(
                name="Three Inside Up", category="candlestick",
                direction="bullish", confidence=0.72,
                bar_index=i, description="Three inside up — confirmed bullish harami reversal",
            ))

        # Three Inside Down
        elif (c[p1] > o[p1] and  # first green
              c[p2] < o[p2] and o[p2] < c[p1] and c[p2] > o[p1] and  # harami
              c[i] < o[i] and c[i] < o[p1]):  # confirmation close below first open
            patterns.append(PatternSignal(
                name="Three Inside Down", category="candlestick",
                direction="bearish", confidence=0.72,
                bar_index=i, description="Three inside down — confirmed bearish harami reversal",
            ))

        # Abandoned Baby Bullish
        if (c[p1] < o[p1] and  # big red
            h[p2] < l[p1] and  # gap down, doji
            rng_2 > 0 and body_2 / rng_2 < 0.15 and
            c[i] > o[i] and l[i] > h[p2]):  # gap up green
            patterns.append(PatternSignal(
                name="Bullish Abandoned Baby", category="candlestick",
                direction="bullish", confidence=0.85,
                bar_index=i, description="Bullish abandoned baby — rare, very strong reversal",
            ))

        # Abandoned Baby Bearish
        elif (c[p1] > o[p1] and  # big green
              l[p2] > h[p1] and  # gap up, doji
              rng_2 > 0 and body_2 / rng_2 < 0.15 and
              c[i] < o[i] and h[i] < l[p2]):  # gap down red
            patterns.append(PatternSignal(
                name="Bearish Abandoned Baby", category="candlestick",
                direction="bearish", confidence=0.85,
                bar_index=i, description="Bearish abandoned baby — rare, very strong reversal",
            ))

        return patterns

    # ──────────────────────────────────────────
    # Chart Pattern Detection Helpers
    # ──────────────────────────────────────────

    @staticmethod
    def _find_swings(data: np.ndarray, mode: str = "high", order: int = 5) -> list[tuple[int, float]]:
        """Find swing highs or lows. Returns list of (index, value)."""
        swings = []
        for i in range(order, len(data) - order):
            if mode == "high":
                if all(data[i] >= data[i - j] for j in range(1, order + 1)) and \
                   all(data[i] >= data[i + j] for j in range(1, order + 1)):
                    swings.append((i, float(data[i])))
            else:
                if all(data[i] <= data[i - j] for j in range(1, order + 1)) and \
                   all(data[i] <= data[i + j] for j in range(1, order + 1)):
                    swings.append((i, float(data[i])))
        return swings

    def _detect_double_top(self, swing_highs, c, bars) -> list[PatternSignal]:
        """Double top: two peaks at similar levels with a valley between."""
        patterns = []
        if len(swing_highs) < 2:
            return patterns

        for j in range(1, len(swing_highs)):
            idx1, val1 = swing_highs[j - 1]
            idx2, val2 = swing_highs[j]
            if abs(idx2 - idx1) < 5:
                continue
            tol = val1 * 0.02
            if abs(val2 - val1) < tol:
                # Neckline = lowest low between the two peaks
                neckline = float(np.min(c[idx1:idx2 + 1]))
                if c[-1] < neckline:
                    target_price = neckline - (val1 - neckline)
                else:
                    target_price = None
                patterns.append(PatternSignal(
                    name="Double Top", category="chart",
                    direction="bearish", confidence=0.72,
                    bar_index=idx2,
                    description=f"Double top at ~${val1:.2f}, neckline ~${neckline:.2f}",
                    entry_trigger=neckline,
                    target=target_price,
                    stop_loss=float(max(val1, val2)),
                ))
                break
        return patterns

    def _detect_double_bottom(self, swing_lows, c, bars) -> list[PatternSignal]:
        """Double bottom: two troughs at similar levels."""
        patterns = []
        if len(swing_lows) < 2:
            return patterns

        for j in range(1, len(swing_lows)):
            idx1, val1 = swing_lows[j - 1]
            idx2, val2 = swing_lows[j]
            if abs(idx2 - idx1) < 5:
                continue
            tol = val1 * 0.02
            if abs(val2 - val1) < tol:
                neckline = float(np.max(c[idx1:idx2 + 1]))
                if c[-1] > neckline:
                    target_price = neckline + (neckline - val1)
                else:
                    target_price = None
                patterns.append(PatternSignal(
                    name="Double Bottom", category="chart",
                    direction="bullish", confidence=0.72,
                    bar_index=idx2,
                    description=f"Double bottom at ~${val1:.2f}, neckline ~${neckline:.2f}",
                    entry_trigger=neckline,
                    target=target_price,
                    stop_loss=float(min(val1, val2)),
                ))
                break
        return patterns

    def _detect_head_and_shoulders(self, swing_highs, swing_lows, c, bars) -> list[PatternSignal]:
        """Head & Shoulders: left shoulder, head (higher), right shoulder (≈ left)."""
        patterns = []
        if len(swing_highs) < 3:
            return patterns

        for j in range(2, len(swing_highs)):
            ls_i, ls_v = swing_highs[j - 2]
            hd_i, hd_v = swing_highs[j - 1]
            rs_i, rs_v = swing_highs[j]

            # Head must be highest
            if hd_v <= ls_v or hd_v <= rs_v:
                continue
            # Shoulders ~equal (within 3%)
            if abs(ls_v - rs_v) / max(ls_v, 0.01) > 0.03:
                continue
            # Right shoulder after head
            if rs_i <= hd_i or hd_i <= ls_i:
                continue

            neckline = float(np.min(c[ls_i:rs_i + 1]))
            target_price = neckline - (hd_v - neckline)

            patterns.append(PatternSignal(
                name="Head & Shoulders", category="chart",
                direction="bearish", confidence=0.82,
                bar_index=rs_i,
                description=f"H&S: LS=${ls_v:.2f}, Head=${hd_v:.2f}, RS=${rs_v:.2f}, Neckline=${neckline:.2f}",
                entry_trigger=neckline,
                target=target_price,
                stop_loss=float(hd_v),
            ))
            break
        return patterns

    def _detect_inverse_head_and_shoulders(self, swing_highs, swing_lows, c, bars) -> list[PatternSignal]:
        """Inverse H&S: left trough, deeper head, right trough (≈ left)."""
        patterns = []
        if len(swing_lows) < 3:
            return patterns

        for j in range(2, len(swing_lows)):
            ls_i, ls_v = swing_lows[j - 2]
            hd_i, hd_v = swing_lows[j - 1]
            rs_i, rs_v = swing_lows[j]

            if hd_v >= ls_v or hd_v >= rs_v:
                continue
            if abs(ls_v - rs_v) / max(ls_v, 0.01) > 0.03:
                continue
            if rs_i <= hd_i or hd_i <= ls_i:
                continue

            neckline = float(np.max(c[ls_i:rs_i + 1]))
            target_price = neckline + (neckline - hd_v)

            patterns.append(PatternSignal(
                name="Inverse Head & Shoulders", category="chart",
                direction="bullish", confidence=0.82,
                bar_index=rs_i,
                description=f"iH&S: LS=${ls_v:.2f}, Head=${hd_v:.2f}, RS=${rs_v:.2f}, Neckline=${neckline:.2f}",
                entry_trigger=neckline,
                target=target_price,
                stop_loss=float(hd_v),
            ))
            break
        return patterns

    def _detect_triangles(self, swing_highs, swing_lows, c, bars) -> list[PatternSignal]:
        """Ascending, Descending, and Symmetrical triangles."""
        patterns = []
        if len(swing_highs) < 2 or len(swing_lows) < 2:
            return patterns

        # Use last 4 swing points
        recent_highs = swing_highs[-3:] if len(swing_highs) >= 3 else swing_highs[-2:]
        recent_lows = swing_lows[-3:] if len(swing_lows) >= 3 else swing_lows[-2:]

        high_vals = [v for _, v in recent_highs]
        low_vals = [v for _, v in recent_lows]

        highs_flat = all(abs(high_vals[i] - high_vals[0]) / max(high_vals[0], 0.01) < 0.015
                        for i in range(len(high_vals)))
        lows_rising = all(low_vals[i] >= low_vals[i - 1] * 0.99 for i in range(1, len(low_vals)))
        lows_flat = all(abs(low_vals[i] - low_vals[0]) / max(low_vals[0], 0.01) < 0.015
                       for i in range(len(low_vals)))
        highs_falling = all(high_vals[i] <= high_vals[i - 1] * 1.01 for i in range(1, len(high_vals)))
        lows_rising_strict = len(low_vals) >= 2 and low_vals[-1] > low_vals[0]
        highs_falling_strict = len(high_vals) >= 2 and high_vals[-1] < high_vals[0]

        last_idx = max(recent_highs[-1][0], recent_lows[-1][0])

        # Ascending Triangle — flat top, rising lows
        if highs_flat and lows_rising_strict:
            patterns.append(PatternSignal(
                name="Ascending Triangle", category="chart",
                direction="bullish", confidence=0.70,
                bar_index=last_idx,
                description=f"Ascending triangle with resistance ~${high_vals[-1]:.2f}",
                entry_trigger=float(high_vals[-1]),
                target=float(high_vals[-1] + (high_vals[-1] - low_vals[0])),
            ))

        # Descending Triangle — flat bottom, falling highs
        elif lows_flat and highs_falling_strict:
            patterns.append(PatternSignal(
                name="Descending Triangle", category="chart",
                direction="bearish", confidence=0.70,
                bar_index=last_idx,
                description=f"Descending triangle with support ~${low_vals[-1]:.2f}",
                entry_trigger=float(low_vals[-1]),
                target=float(low_vals[-1] - (high_vals[0] - low_vals[-1])),
            ))

        # Symmetrical Triangle — converging
        elif highs_falling_strict and lows_rising_strict:
            patterns.append(PatternSignal(
                name="Symmetrical Triangle", category="chart",
                direction="neutral", confidence=0.60,
                bar_index=last_idx,
                description="Symmetrical triangle — breakout direction unclear, watch for resolution",
            ))

        return patterns

    def _detect_wedges(self, swing_highs, swing_lows, c, bars) -> list[PatternSignal]:
        """Rising and Falling wedges."""
        patterns = []
        if len(swing_highs) < 2 or len(swing_lows) < 2:
            return patterns

        high_vals = [v for _, v in swing_highs[-3:]]
        low_vals = [v for _, v in swing_lows[-3:]]

        if len(high_vals) < 2 or len(low_vals) < 2:
            return patterns

        highs_rising = high_vals[-1] > high_vals[0]
        lows_rising = low_vals[-1] > low_vals[0]
        highs_falling = high_vals[-1] < high_vals[0]
        lows_falling = low_vals[-1] < low_vals[0]

        # Rates of convergence
        high_spread = high_vals[-1] - high_vals[0]
        low_spread = low_vals[-1] - low_vals[0]

        last_idx = max(swing_highs[-1][0], swing_lows[-1][0])

        # Rising Wedge (bearish) — both rising, converging
        if highs_rising and lows_rising and abs(high_spread) < abs(low_spread):
            patterns.append(PatternSignal(
                name="Rising Wedge", category="chart",
                direction="bearish", confidence=0.68,
                bar_index=last_idx,
                description="Rising wedge — bearish reversal, expect breakdown",
            ))

        # Falling Wedge (bullish) — both falling, converging
        elif highs_falling and lows_falling and abs(low_spread) < abs(high_spread):
            patterns.append(PatternSignal(
                name="Falling Wedge", category="chart",
                direction="bullish", confidence=0.68,
                bar_index=last_idx,
                description="Falling wedge — bullish reversal, expect breakout",
            ))

        return patterns

    def _detect_flags(self, h, l, c, bars) -> list[PatternSignal]:
        """Bull and Bear flags: sharp move then tight consolidation."""
        patterns = []
        if len(bars) < 20:
            return patterns

        # Look for a strong move in bars[-20:-10], then consolidation in [-10:]
        pole_start = -20
        pole_end = -10
        flag_section = slice(-10, None)

        pole_change = (c[pole_end] - c[pole_start]) / max(abs(c[pole_start]), 0.01)
        flag_range = float(np.max(h[flag_section]) - np.min(l[flag_section]))
        pole_range = float(np.max(h[pole_start:pole_end]) - np.min(l[pole_start:pole_end]))

        if pole_range == 0:
            return patterns

        # Flag: consolidation range < 40% of pole range
        if flag_range < pole_range * 0.40:
            if pole_change > 0.05:  # 5% pole up
                patterns.append(PatternSignal(
                    name="Bull Flag", category="chart",
                    direction="bullish", confidence=0.72,
                    bar_index=len(bars) - 1,
                    description=f"Bull flag — {pole_change:.1%} pole, tight consolidation",
                    target=float(c[-1] + pole_range),
                ))
            elif pole_change < -0.05:
                patterns.append(PatternSignal(
                    name="Bear Flag", category="chart",
                    direction="bearish", confidence=0.72,
                    bar_index=len(bars) - 1,
                    description=f"Bear flag — {pole_change:.1%} pole, tight consolidation",
                    target=float(c[-1] - pole_range),
                ))

        return patterns

    def _detect_cup_and_handle(self, swing_lows, c, bars) -> list[PatternSignal]:
        """Cup & Handle: U-shaped recovery + small pullback."""
        patterns = []
        if len(swing_lows) < 3 or len(bars) < 40:
            return patterns

        # Need: left lip, cup bottom, right lip near left, then small handle
        for j in range(2, len(swing_lows)):
            left_i, left_v = swing_lows[j - 2]
            bot_i, bot_v = swing_lows[j - 1]
            right_i, right_v = swing_lows[j]

            # Cup bottom must be lowest
            if bot_v >= left_v or bot_v >= right_v:
                continue
            # Right lip near or above left lip
            if right_v < left_v * 0.97:
                continue
            # Reasonable proportions
            if right_i - left_i < 15:
                continue

            # Check for handle (small pullback after right lip)
            if right_i < len(c) - 3:
                handle_low = float(np.min(c[right_i:]))
                if handle_low > bot_v and handle_low > right_v * 0.97:
                    depth = left_v - bot_v
                    patterns.append(PatternSignal(
                        name="Cup & Handle", category="chart",
                        direction="bullish", confidence=0.76,
                        bar_index=len(bars) - 1,
                        description=f"Cup & handle — cup depth ${depth:.2f}, bulls regaining control",
                        target=float(c[-1] + depth),
                        entry_trigger=float(max(left_v, right_v)),
                    ))
                    break
        return patterns

    def _detect_channels(self, swing_highs, swing_lows, c, bars) -> list[PatternSignal]:
        """Ascending and Descending channels."""
        patterns = []
        if len(swing_highs) < 3 or len(swing_lows) < 3:
            return patterns

        high_vals = np.array([v for _, v in swing_highs[-4:]])
        low_vals = np.array([v for _, v in swing_lows[-4:]])

        if len(high_vals) < 2 or len(low_vals) < 2:
            return patterns

        # Linear regression on swing highs/lows
        high_x = np.arange(len(high_vals))
        low_x = np.arange(len(low_vals))

        high_slope = np.polyfit(high_x, high_vals, 1)[0] if len(high_vals) >= 2 else 0
        low_slope = np.polyfit(low_x, low_vals, 1)[0] if len(low_vals) >= 2 else 0

        # Parallel slopes = channel
        avg_price = float(np.mean(c[-20:]))
        high_slope_pct = high_slope / max(avg_price, 0.01)
        low_slope_pct = low_slope / max(avg_price, 0.01)

        if abs(high_slope_pct - low_slope_pct) < 0.005:  # roughly parallel
            last_idx = max(swing_highs[-1][0], swing_lows[-1][0])
            if high_slope_pct > 0.002:
                patterns.append(PatternSignal(
                    name="Ascending Channel", category="chart",
                    direction="bullish", confidence=0.62,
                    bar_index=last_idx,
                    description="Ascending channel — buy at channel bottom, sell at top",
                ))
            elif high_slope_pct < -0.002:
                patterns.append(PatternSignal(
                    name="Descending Channel", category="chart",
                    direction="bearish", confidence=0.62,
                    bar_index=last_idx,
                    description="Descending channel — bearish, watch for breakdown",
                ))

        return patterns

    def _detect_rectangle(self, swing_highs, swing_lows, c, bars) -> list[PatternSignal]:
        """Rectangle/Range: flat top and flat bottom."""
        patterns = []
        if len(swing_highs) < 2 or len(swing_lows) < 2:
            return patterns

        high_vals = [v for _, v in swing_highs[-3:]]
        low_vals = [v for _, v in swing_lows[-3:]]

        avg_high = np.mean(high_vals)
        avg_low = np.mean(low_vals)

        highs_flat = all(abs(v - avg_high) / max(avg_high, 0.01) < 0.015 for v in high_vals)
        lows_flat = all(abs(v - avg_low) / max(avg_low, 0.01) < 0.015 for v in low_vals)

        if highs_flat and lows_flat:
            last_idx = max(swing_highs[-1][0], swing_lows[-1][0])
            # Determine bias from current price position
            mid = (avg_high + avg_low) / 2
            if c[-1] > mid:
                direction = "bullish"
                desc = "approaching resistance for potential breakout"
            else:
                direction = "bearish"
                desc = "approaching support, watch for breakdown"

            patterns.append(PatternSignal(
                name="Rectangle", category="chart",
                direction=direction, confidence=0.58,
                bar_index=last_idx,
                description=f"Rectangle range ${avg_low:.2f} — ${avg_high:.2f}, {desc}",
                entry_trigger=float(avg_high),
                target=float(avg_high + (avg_high - avg_low)),
                stop_loss=float(avg_low),
            ))

        return patterns

    # ──────────────────────────────────────────
    # Gap Detection
    # ──────────────────────────────────────────

    def detect_gaps(self, bars: list[OHLCV]) -> list[PatternSignal]:
        """Detect price gaps: gap up, gap down, island reversal, exhaustion gap."""
        if len(bars) < 5:
            return []

        o = np.array([b.open for b in bars])
        h = np.array([b.high for b in bars])
        l = np.array([b.low for b in bars])
        c = np.array([b.close for b in bars])
        v = np.array([b.volume for b in bars])

        patterns: list[PatternSignal] = []

        # Check last 15 bars
        scan_start = max(1, len(bars) - 15)
        for i in range(scan_start, len(bars)):
            # Gap Up: current low > previous high
            if l[i] > h[i - 1]:
                gap_size = l[i] - h[i - 1]
                gap_pct = gap_size / max(h[i - 1], 0.01) * 100

                # Avg volume check for breakaway vs exhaustion
                avg_vol = float(np.mean(v[max(0, i-20):i])) if i > 5 else float(v[i])
                vol_ratio = v[i] / max(avg_vol, 1)

                if gap_pct > 1.0:
                    # High volume = breakaway gap (continuation), low volume = exhaustion gap
                    if vol_ratio > 2.0:
                        name = "Breakaway Gap Up"
                        confidence = 0.78
                        desc = f"Breakaway gap up {gap_pct:.1f}% on {vol_ratio:.1f}x volume — strong bullish"
                    elif vol_ratio < 0.7:
                        name = "Exhaustion Gap Up"
                        confidence = 0.65
                        desc = f"Exhaustion gap up {gap_pct:.1f}% on low volume — potential reversal"
                    else:
                        name = "Gap Up"
                        confidence = 0.55
                        desc = f"Gap up {gap_pct:.1f}% — {gap_size:.2f} point gap"

                    patterns.append(PatternSignal(
                        name=name, category="candlestick",
                        direction="bullish" if "Exhaustion" not in name else "bearish",
                        confidence=confidence,
                        bar_index=i, description=desc,
                    ))

            # Gap Down: current high < previous low
            elif h[i] < l[i - 1]:
                gap_size = l[i - 1] - h[i]
                gap_pct = gap_size / max(l[i - 1], 0.01) * 100

                avg_vol = float(np.mean(v[max(0, i-20):i])) if i > 5 else float(v[i])
                vol_ratio = v[i] / max(avg_vol, 1)

                if gap_pct > 1.0:
                    if vol_ratio > 2.0:
                        name = "Breakaway Gap Down"
                        confidence = 0.78
                        desc = f"Breakaway gap down {gap_pct:.1f}% on {vol_ratio:.1f}x volume — strong bearish"
                    elif vol_ratio < 0.7:
                        name = "Exhaustion Gap Down"
                        confidence = 0.65
                        desc = f"Exhaustion gap down {gap_pct:.1f}% on low volume — potential reversal"
                    else:
                        name = "Gap Down"
                        confidence = 0.55
                        desc = f"Gap down {gap_pct:.1f}% — {gap_size:.2f} point gap"

                    patterns.append(PatternSignal(
                        name=name, category="candlestick",
                        direction="bearish" if "Exhaustion" not in name else "bullish",
                        confidence=confidence,
                        bar_index=i, description=desc,
                    ))

        # Island Reversal: gap in one direction, then gap back
        for i in range(scan_start + 1, len(bars)):
            # Bullish island: gap down then gap up within 3-5 bars
            if h[i] < l[i - 1]:  # gap down exists
                for j in range(i + 1, min(i + 6, len(bars))):
                    if l[j] > h[j - 1]:  # gap up follows
                        patterns.append(PatternSignal(
                            name="Bullish Island Reversal", category="chart",
                            direction="bullish", confidence=0.80,
                            bar_index=j,
                            description=f"Island reversal — isolated {j - i} bars gapped both sides",
                        ))
                        break
            # Bearish island: gap up then gap down
            if l[i] > h[i - 1]:
                for j in range(i + 1, min(i + 6, len(bars))):
                    if h[j] < l[j - 1]:
                        patterns.append(PatternSignal(
                            name="Bearish Island Reversal", category="chart",
                            direction="bearish", confidence=0.80,
                            bar_index=j,
                            description=f"Island reversal — isolated {j - i} bars gapped both sides",
                        ))
                        break

        return patterns

    # ──────────────────────────────────────────
    # Volume Pattern Detection
    # ──────────────────────────────────────────

    def detect_volume_patterns(self, bars: list[OHLCV]) -> list[PatternSignal]:
        """Detect volume-based patterns: climax, dry-up, accumulation, distribution."""
        if len(bars) < 20:
            return []

        v = np.array([b.volume for b in bars], dtype=float)
        c = np.array([b.close for b in bars])
        o = np.array([b.open for b in bars])

        patterns: list[PatternSignal] = []
        avg_vol = float(np.mean(v[-50:] if len(v) >= 50 else v))

        for i in range(max(1, len(bars) - 10), len(bars)):
            vol_ratio = v[i] / max(avg_vol, 1)

            # Volume Climax (>3x average)
            if vol_ratio > 3.0:
                direction = "bullish" if c[i] > o[i] else "bearish"
                patterns.append(PatternSignal(
                    name=f"Volume Climax ({'Buying' if direction == 'bullish' else 'Selling'})",
                    category="candlestick",
                    direction=direction, confidence=0.70,
                    bar_index=i,
                    description=f"Volume climax at {vol_ratio:.1f}x average — potential exhaustion or breakout confirmation",
                ))

            # Volume Dry-Up (<0.3x average over 3+ bars)
            if i >= 3 and all(v[i-j] / max(avg_vol, 1) < 0.35 for j in range(3)):
                patterns.append(PatternSignal(
                    name="Volume Dry-Up", category="candlestick",
                    direction="neutral", confidence=0.55,
                    bar_index=i,
                    description="Volume dry-up — 3+ bars at <35% average volume, breakout imminent",
                ))

        # Accumulation: price flat, gradually rising volume
        price_range_pct = (np.max(c[-15:]) - np.min(c[-15:])) / max(np.mean(c[-15:]), 0.01) * 100
        vol_trend = np.polyfit(np.arange(min(15, len(v))), v[-15:] if len(v) >= 15 else v[:15], 1)[0]

        if price_range_pct < 5.0 and vol_trend > 0:
            patterns.append(PatternSignal(
                name="Accumulation", category="chart",
                direction="bullish", confidence=0.60,
                bar_index=len(bars) - 1,
                description=f"Accumulation — flat price ({price_range_pct:.1f}% range) with rising volume",
            ))

        # Distribution: price flat or rising, falling volume
        if price_range_pct < 5.0 and vol_trend < 0 and c[-1] >= c[-15]:
            patterns.append(PatternSignal(
                name="Distribution", category="chart",
                direction="bearish", confidence=0.58,
                bar_index=len(bars) - 1,
                description="Distribution — price holding but volume declining, smart money exiting",
            ))

        return patterns

    # ──────────────────────────────────────────
    # Fibonacci Retracement Levels
    # ──────────────────────────────────────────

    def detect_fibonacci_levels(self, bars: list[OHLCV]) -> dict:
        """Calculate Fibonacci retracement and extension levels from recent swing.

        Returns levels, current price position relative to fibs, and active zone.
        """
        if len(bars) < 20:
            return {"levels": {}, "active_zone": "insufficient_data"}

        c = np.array([b.close for b in bars])
        h = np.array([b.high for b in bars])
        l = np.array([b.low for b in bars])

        # Find the significant high/low in last 90 bars
        lookback = min(90, len(bars))
        recent_h = h[-lookback:]
        recent_l = l[-lookback:]

        swing_high_idx = int(np.argmax(recent_h))
        swing_low_idx = int(np.argmin(recent_l))
        swing_high = float(recent_h[swing_high_idx])
        swing_low = float(recent_l[swing_low_idx])
        current = float(c[-1])

        diff = swing_high - swing_low
        if diff <= 0:
            return {"levels": {}, "active_zone": "no_range"}

        # Uptrend: low came before high (retracement from top)
        if swing_low_idx < swing_high_idx:
            direction = "uptrend_retrace"
            levels = {
                "0.0%": round(swing_high, 2),
                "23.6%": round(swing_high - diff * 0.236, 2),
                "38.2%": round(swing_high - diff * 0.382, 2),
                "50.0%": round(swing_high - diff * 0.500, 2),
                "61.8%": round(swing_high - diff * 0.618, 2),
                "78.6%": round(swing_high - diff * 0.786, 2),
                "100.0%": round(swing_low, 2),
            }
            extensions = {
                "127.2%": round(swing_high + diff * 0.272, 2),
                "161.8%": round(swing_high + diff * 0.618, 2),
                "261.8%": round(swing_high + diff * 1.618, 2),
            }
        else:
            direction = "downtrend_retrace"
            levels = {
                "0.0%": round(swing_low, 2),
                "23.6%": round(swing_low + diff * 0.236, 2),
                "38.2%": round(swing_low + diff * 0.382, 2),
                "50.0%": round(swing_low + diff * 0.500, 2),
                "61.8%": round(swing_low + diff * 0.618, 2),
                "78.6%": round(swing_low + diff * 0.786, 2),
                "100.0%": round(swing_high, 2),
            }
            extensions = {
                "127.2%": round(swing_low - diff * 0.272, 2),
                "161.8%": round(swing_low - diff * 0.618, 2),
                "261.8%": round(swing_low - diff * 1.618, 2),
            }

        # Determine active zone
        active_zone = "below_100%"
        fib_vals = sorted(levels.values())
        for j in range(len(fib_vals) - 1):
            if fib_vals[j] <= current <= fib_vals[j + 1]:
                # Find the corresponding percentage labels
                for k, v in levels.items():
                    if v == fib_vals[j]:
                        lower_label = k
                    if v == fib_vals[j + 1]:
                        upper_label = k
                active_zone = f"{lower_label} — {upper_label}"
                break

        return {
            "swing_high": swing_high,
            "swing_low": swing_low,
            "current_price": current,
            "direction": direction,
            "retracement_levels": levels,
            "extension_levels": extensions,
            "active_zone": active_zone,
            "golden_pocket": {
                "low": levels["61.8%"],
                "high": levels["50.0%"],
                "description": "Key reversal zone — 50-61.8% retracement",
            },
        }

    # ──────────────────────────────────────────
    # Trend Line Detection
    # ──────────────────────────────────────────

    def detect_trend_lines(self, bars: list[OHLCV]) -> list[PatternSignal]:
        """Detect trend lines using linear regression on swing points."""
        if len(bars) < 30:
            return []

        h = np.array([b.high for b in bars])
        l = np.array([b.low for b in bars])
        c = np.array([b.close for b in bars])

        swing_highs = self._find_swings(h, mode="high", order=5)
        swing_lows = self._find_swings(l, mode="low", order=5)

        patterns: list[PatternSignal] = []

        # Uptrend line (connecting swing lows)
        if len(swing_lows) >= 3:
            indices = np.array([idx for idx, _ in swing_lows[-5:]])
            values = np.array([val for _, val in swing_lows[-5:]])

            if len(indices) >= 2:
                slope, intercept = np.polyfit(indices, values, 1)
                r_squared = 1 - np.sum((values - (slope * indices + intercept)) ** 2) / \
                           max(np.sum((values - np.mean(values)) ** 2), 1e-10)

                if slope > 0 and r_squared > 0.7:
                    trendline_now = slope * len(bars) + intercept
                    distance_pct = (c[-1] - trendline_now) / max(trendline_now, 0.01) * 100

                    if distance_pct < 2.0:  # price near trendline
                        patterns.append(PatternSignal(
                            name="Uptrend Line Support", category="chart",
                            direction="bullish", confidence=min(0.85, 0.5 + r_squared * 0.4),
                            bar_index=len(bars) - 1,
                            description=f"Price testing uptrend line support (R²={r_squared:.2f}), {distance_pct:.1f}% above",
                            entry_trigger=float(trendline_now),
                            stop_loss=float(trendline_now * 0.98),
                        ))
                    elif distance_pct < -1.0:
                        patterns.append(PatternSignal(
                            name="Uptrend Line Break", category="chart",
                            direction="bearish", confidence=0.72,
                            bar_index=len(bars) - 1,
                            description=f"Uptrend line broken — price {abs(distance_pct):.1f}% below trendline",
                        ))

        # Downtrend line (connecting swing highs)
        if len(swing_highs) >= 3:
            indices = np.array([idx for idx, _ in swing_highs[-5:]])
            values = np.array([val for _, val in swing_highs[-5:]])

            if len(indices) >= 2:
                slope, intercept = np.polyfit(indices, values, 1)
                r_squared = 1 - np.sum((values - (slope * indices + intercept)) ** 2) / \
                           max(np.sum((values - np.mean(values)) ** 2), 1e-10)

                if slope < 0 and r_squared > 0.7:
                    trendline_now = slope * len(bars) + intercept
                    distance_pct = (trendline_now - c[-1]) / max(trendline_now, 0.01) * 100

                    if distance_pct < 2.0:
                        patterns.append(PatternSignal(
                            name="Downtrend Line Resistance", category="chart",
                            direction="bearish", confidence=min(0.85, 0.5 + r_squared * 0.4),
                            bar_index=len(bars) - 1,
                            description=f"Price testing downtrend line resistance (R²={r_squared:.2f})",
                        ))
                    elif distance_pct < -1.0:
                        patterns.append(PatternSignal(
                            name="Downtrend Line Break", category="chart",
                            direction="bullish", confidence=0.72,
                            bar_index=len(bars) - 1,
                            description=f"Downtrend line broken — price {abs(distance_pct):.1f}% above resistance",
                        ))

        return patterns

    # ──────────────────────────────────────────
    # Emerging / Forming Patterns
    # ──────────────────────────────────────────

    def detect_emerging_patterns(self, bars: list[OHLCV]) -> list[dict]:
        """Detect patterns that are still forming (not yet confirmed).

        Returns patterns with formation progress percentage and expected completion.
        Covers 16+ forming pattern types across candlestick and chart structures.
        """
        if len(bars) < 20:
            return []

        o = np.array([b.open for b in bars])
        h = np.array([b.high for b in bars])
        l = np.array([b.low for b in bars])
        c = np.array([b.close for b in bars])
        v = np.array([b.volume for b in bars], dtype=float)

        swing_highs = self._find_swings(h, mode="high", order=3)  # Tighter order for forming patterns
        swing_lows = self._find_swings(l, mode="low", order=3)

        emerging: list[dict] = []

        # ── 1. Forming Head & Shoulders ──
        # Have left shoulder + head, watching for right shoulder
        if len(swing_highs) >= 2:
            ls_i, ls_v = swing_highs[-2]
            hd_i, hd_v = swing_highs[-1]

            if hd_v > ls_v * 1.01 and hd_i > ls_i:
                expected_rs = ls_v
                # Check if price is pulling back from head
                if c[-1] < hd_v:
                    pullback_pct = (hd_v - c[-1]) / max(hd_v - ls_v, 0.01) * 100
                    progress = min(85, 60 + int(pullback_pct * 0.25))
                else:
                    progress = 55
                emerging.append({
                    "name": "Head & Shoulders (Forming)",
                    "stage": "forming",
                    "progress": progress,
                    "direction": "bearish",
                    "description": f"LS=${ls_v:.2f}, Head=${hd_v:.2f} — watching for right shoulder near ${expected_rs:.2f}",
                    "watch_level": round(expected_rs, 2),
                    "invalidation": round(float(hd_v), 2),
                    "neckline_est": round(float(np.min(c[ls_i:hd_i])) if hd_i > ls_i else float(c[-1]), 2),
                })

        # ── 2. Forming Inverse H&S ──
        if len(swing_lows) >= 2:
            ls_i, ls_v = swing_lows[-2]
            hd_i, hd_v = swing_lows[-1]

            if hd_v < ls_v * 0.99 and hd_i > ls_i:
                expected_rs = ls_v
                if c[-1] > hd_v:
                    recovery_pct = (c[-1] - hd_v) / max(ls_v - hd_v, 0.01) * 100
                    progress = min(85, 60 + int(recovery_pct * 0.25))
                else:
                    progress = 55
                emerging.append({
                    "name": "Inverse H&S (Forming)",
                    "stage": "forming",
                    "progress": progress,
                    "direction": "bullish",
                    "description": f"LS=${ls_v:.2f}, Head=${hd_v:.2f} — watching for right shoulder near ${expected_rs:.2f}",
                    "watch_level": round(expected_rs, 2),
                    "invalidation": round(float(hd_v), 2),
                    "neckline_est": round(float(np.max(c[ls_i:hd_i])) if hd_i > ls_i else float(c[-1]), 2),
                })

        # ── 3. Forming Double Top ──
        # One peak formed, price pulled back, watching for second approach
        if len(swing_highs) >= 1:
            peak_i, peak_v = swing_highs[-1]
            if peak_i < len(bars) - 3:  # Peak isn't the current bar
                pullback_low = float(np.min(c[peak_i:]))
                pullback_depth = (peak_v - pullback_low) / max(peak_v, 0.01) * 100
                current_approach = (c[-1] - pullback_low) / max(peak_v - pullback_low, 0.01) * 100

                if 2.0 < pullback_depth < 15.0 and current_approach > 40:
                    progress = min(85, 50 + int(current_approach * 0.35))
                    emerging.append({
                        "name": "Double Top (Forming)",
                        "stage": "forming",
                        "progress": progress,
                        "direction": "bearish",
                        "description": f"Peak at ${peak_v:.2f}, pulled back {pullback_depth:.1f}%, approaching again ({current_approach:.0f}% recovery)",
                        "watch_level": round(float(peak_v), 2),
                        "invalidation": round(float(peak_v * 1.02), 2),
                    })

        # ── 4. Forming Double Bottom ──
        if len(swing_lows) >= 1:
            trough_i, trough_v = swing_lows[-1]
            if trough_i < len(bars) - 3:
                bounce_high = float(np.max(c[trough_i:]))
                bounce_depth = (bounce_high - trough_v) / max(trough_v, 0.01) * 100
                current_approach = (bounce_high - c[-1]) / max(bounce_high - trough_v, 0.01) * 100

                if 2.0 < bounce_depth < 15.0 and current_approach > 40:
                    progress = min(85, 50 + int(current_approach * 0.35))
                    emerging.append({
                        "name": "Double Bottom (Forming)",
                        "stage": "forming",
                        "progress": progress,
                        "direction": "bullish",
                        "description": f"Trough at ${trough_v:.2f}, bounced {bounce_depth:.1f}%, declining again ({current_approach:.0f}% retracement)",
                        "watch_level": round(float(trough_v), 2),
                        "invalidation": round(float(trough_v * 0.98), 2),
                    })

        # ── 5. Forming Symmetrical Triangle ──
        if len(swing_highs) >= 2 and len(swing_lows) >= 2:
            high_vals = [v for _, v in swing_highs[-3:]]
            low_vals = [v for _, v in swing_lows[-3:]]

            if len(high_vals) >= 2 and len(low_vals) >= 2:
                range_first = high_vals[0] - low_vals[0]
                range_last = high_vals[-1] - low_vals[-1]
                highs_declining = high_vals[-1] < high_vals[0]
                lows_rising = low_vals[-1] > low_vals[0]

                if range_first > 0 and range_last > 0 and range_last < range_first * 0.7:
                    progress = int((1 - range_last / range_first) * 100)

                    if highs_declining and lows_rising:
                        tri_type = "Symmetrical Triangle"
                        direction = "neutral"
                    elif not highs_declining and lows_rising:
                        tri_type = "Ascending Triangle"
                        direction = "bullish"
                    elif highs_declining and not lows_rising:
                        tri_type = "Descending Triangle"
                        direction = "bearish"
                    else:
                        tri_type = "Triangle"
                        direction = "neutral"

                    # Estimate bars to apex
                    if len(swing_highs) >= 2 and len(swing_lows) >= 2:
                        hi_indices = [i for i, _ in swing_highs[-2:]]
                        lo_indices = [i for i, _ in swing_lows[-2:]]
                        if hi_indices[-1] != hi_indices[0] and lo_indices[-1] != lo_indices[0]:
                            hi_slope = (high_vals[-1] - high_vals[-2]) / max(hi_indices[-1] - hi_indices[-2], 1)
                            lo_slope = (low_vals[-1] - low_vals[-2]) / max(lo_indices[-1] - lo_indices[-2], 1)
                            if hi_slope != lo_slope:
                                apex_bar = int((low_vals[-1] - high_vals[-1]) / max(hi_slope - lo_slope, 0.0001))
                            else:
                                apex_bar = 0
                        else:
                            apex_bar = 0
                    else:
                        apex_bar = 0

                    emerging.append({
                        "name": f"{tri_type} (Forming)",
                        "stage": "forming",
                        "progress": min(90, progress),
                        "direction": direction,
                        "description": f"Converging range ${range_first:.2f}→${range_last:.2f} — apex ~{max(0, apex_bar)} bars away",
                        "watch_level": round(float(high_vals[-1]), 2),
                        "watch_level_low": round(float(low_vals[-1]), 2),
                        "invalidation": None,
                        "estimated_breakout_bars": max(0, apex_bar),
                    })

        # ── 6. Forming Rising Wedge ──
        if len(swing_highs) >= 2 and len(swing_lows) >= 2:
            hi_i = [i for i, _ in swing_highs[-3:]]
            hi_v = [v for _, v in swing_highs[-3:]]
            lo_i = [i for i, _ in swing_lows[-3:]]
            lo_v = [v for _, v in swing_lows[-3:]]

            if len(hi_v) >= 2 and len(lo_v) >= 2:
                hi_rising = hi_v[-1] > hi_v[0]
                lo_rising = lo_v[-1] > lo_v[0]

                if hi_rising and lo_rising:
                    hi_range = hi_v[-1] - hi_v[0]
                    lo_range = lo_v[-1] - lo_v[0]
                    # Wedge = converging AND both rising
                    spread_first = hi_v[0] - lo_v[0] if hi_v[0] > lo_v[0] else 0
                    spread_last = hi_v[-1] - lo_v[-1] if hi_v[-1] > lo_v[-1] else 0

                    if spread_first > 0 and spread_last > 0 and spread_last < spread_first * 0.85:
                        progress = int((1 - spread_last / spread_first) * 100)
                        emerging.append({
                            "name": "Rising Wedge (Forming)",
                            "stage": "forming",
                            "progress": min(85, progress),
                            "direction": "bearish",
                            "description": f"Both highs & lows rising but converging — bearish breakdown expected",
                            "watch_level": round(float(lo_v[-1]), 2),
                            "invalidation": round(float(hi_v[-1] * 1.02), 2),
                        })

        # ── 7. Forming Falling Wedge ──
        if len(swing_highs) >= 2 and len(swing_lows) >= 2:
            hi_v = [v for _, v in swing_highs[-3:]]
            lo_v = [v for _, v in swing_lows[-3:]]

            if len(hi_v) >= 2 and len(lo_v) >= 2:
                hi_falling = hi_v[-1] < hi_v[0]
                lo_falling = lo_v[-1] < lo_v[0]

                if hi_falling and lo_falling:
                    spread_first = hi_v[0] - lo_v[0] if hi_v[0] > lo_v[0] else 0
                    spread_last = hi_v[-1] - lo_v[-1] if hi_v[-1] > lo_v[-1] else 0

                    if spread_first > 0 and spread_last > 0 and spread_last < spread_first * 0.85:
                        progress = int((1 - spread_last / spread_first) * 100)
                        emerging.append({
                            "name": "Falling Wedge (Forming)",
                            "stage": "forming",
                            "progress": min(85, progress),
                            "direction": "bullish",
                            "description": f"Both highs & lows falling but converging — bullish breakout expected",
                            "watch_level": round(float(hi_v[-1]), 2),
                            "invalidation": round(float(lo_v[-1] * 0.98), 2),
                        })

        # ── 8. Forming Bull Flag ──
        # Sharp move up (pole), then tight consolidation (flag)
        if len(bars) >= 15:
            # Look for a strong impulse in last 15 bars
            for pole_end in range(len(bars) - 5, max(len(bars) - 15, 4), -1):
                pole_start = max(0, pole_end - 8)
                pole_move = (c[pole_end] - c[pole_start]) / max(c[pole_start], 0.01) * 100
                if pole_move > 5.0:  # >5% move = potential pole
                    # Check if consolidation after pole
                    flag_bars = c[pole_end:]
                    if len(flag_bars) >= 3:
                        flag_range = (float(np.max(flag_bars)) - float(np.min(flag_bars))) / max(float(np.mean(flag_bars)), 0.01) * 100
                        flag_drift = (flag_bars[-1] - flag_bars[0]) / max(flag_bars[0], 0.01) * 100
                        if flag_range < 4.0 and abs(flag_drift) < 3.0:  # Tight range, minor drift
                            progress = min(80, 50 + len(flag_bars) * 5)
                            emerging.append({
                                "name": "Bull Flag (Forming)",
                                "stage": "forming",
                                "progress": progress,
                                "direction": "bullish",
                                "description": f"Pole: +{pole_move:.1f}% move, flag: {len(flag_bars)} bars consolidating ({flag_range:.1f}% range)",
                                "watch_level": round(float(np.max(h[pole_end:])), 2),
                                "invalidation": round(float(np.min(l[pole_end:])), 2),
                                "pole_size_pct": round(pole_move, 1),
                            })
                            break

        # ── 9. Forming Bear Flag ──
        if len(bars) >= 15:
            for pole_end in range(len(bars) - 5, max(len(bars) - 15, 4), -1):
                pole_start = max(0, pole_end - 8)
                pole_move = (c[pole_start] - c[pole_end]) / max(c[pole_start], 0.01) * 100
                if pole_move > 5.0:  # >5% drop = potential pole
                    flag_bars = c[pole_end:]
                    if len(flag_bars) >= 3:
                        flag_range = (float(np.max(flag_bars)) - float(np.min(flag_bars))) / max(float(np.mean(flag_bars)), 0.01) * 100
                        flag_drift = (flag_bars[-1] - flag_bars[0]) / max(flag_bars[0], 0.01) * 100
                        if flag_range < 4.0 and abs(flag_drift) < 3.0:
                            progress = min(80, 50 + len(flag_bars) * 5)
                            emerging.append({
                                "name": "Bear Flag (Forming)",
                                "stage": "forming",
                                "progress": progress,
                                "direction": "bearish",
                                "description": f"Pole: -{pole_move:.1f}% drop, flag: {len(flag_bars)} bars consolidating ({flag_range:.1f}% range)",
                                "watch_level": round(float(np.min(l[pole_end:])), 2),
                                "invalidation": round(float(np.max(h[pole_end:])), 2),
                                "pole_size_pct": round(pole_move, 1),
                            })
                            break

        # ── 10. Forming Rectangle / Range ──
        if len(bars) >= 15:
            recent_h = h[-15:]
            recent_l = l[-15:]
            top = float(np.max(recent_h))
            bottom = float(np.min(recent_l))
            range_pct = (top - bottom) / max(bottom, 0.01) * 100

            if range_pct < 8.0:
                # Count touches of top and bottom
                touch_top = sum(1 for x in recent_h if abs(x - top) / max(top, 0.01) < 0.005)
                touch_bottom = sum(1 for x in recent_l if abs(x - bottom) / max(bottom, 0.01) < 0.005)

                if touch_top >= 2 and touch_bottom >= 2:
                    midpoint = (top + bottom) / 2
                    position = "upper half" if c[-1] > midpoint else "lower half"
                    emerging.append({
                        "name": "Rectangle (Forming)",
                        "stage": "forming",
                        "progress": min(80, 40 + (touch_top + touch_bottom) * 8),
                        "direction": "neutral",
                        "description": f"Range ${bottom:.2f}—${top:.2f} ({range_pct:.1f}%), {touch_top} top / {touch_bottom} bottom touches, price in {position}",
                        "watch_level": round(top, 2),
                        "watch_level_low": round(bottom, 2),
                        "invalidation": None,
                    })

        # ── 11. Forming Channel Up / Channel Down ──
        if len(swing_highs) >= 3 and len(swing_lows) >= 3:
            hi_i = np.array([i for i, _ in swing_highs[-4:]])
            hi_v_arr = np.array([v for _, v in swing_highs[-4:]])
            lo_i = np.array([i for i, _ in swing_lows[-4:]])
            lo_v_arr = np.array([v for _, v in swing_lows[-4:]])

            if len(hi_i) >= 2 and len(lo_i) >= 2:
                hi_slope, hi_intercept = np.polyfit(hi_i, hi_v_arr, 1)
                lo_slope, lo_intercept = np.polyfit(lo_i, lo_v_arr, 1)

                # Check if slopes are roughly parallel (within 30%)
                if hi_slope != 0 and abs(hi_slope - lo_slope) / max(abs(hi_slope), 0.0001) < 0.4:
                    if hi_slope > 0.01:
                        ch_type = "Ascending Channel"
                        direction = "bullish"
                    elif hi_slope < -0.01:
                        ch_type = "Descending Channel"
                        direction = "bearish"
                    else:
                        ch_type = "Horizontal Channel"
                        direction = "neutral"

                    # R² for quality
                    hi_predicted = hi_slope * hi_i + hi_intercept
                    hi_r2 = 1 - np.sum((hi_v_arr - hi_predicted) ** 2) / max(np.sum((hi_v_arr - np.mean(hi_v_arr)) ** 2), 1e-10)
                    lo_predicted = lo_slope * lo_i + lo_intercept
                    lo_r2 = 1 - np.sum((lo_v_arr - lo_predicted) ** 2) / max(np.sum((lo_v_arr - np.mean(lo_v_arr)) ** 2), 1e-10)

                    if hi_r2 > 0.6 and lo_r2 > 0.6:
                        upper_now = hi_slope * len(bars) + hi_intercept
                        lower_now = lo_slope * len(bars) + lo_intercept
                        pos_in_channel = (c[-1] - lower_now) / max(upper_now - lower_now, 0.01) * 100

                        emerging.append({
                            "name": f"{ch_type} (Forming)",
                            "stage": "forming",
                            "progress": min(85, int((hi_r2 + lo_r2) / 2 * 85)),
                            "direction": direction,
                            "description": f"Parallel lines R²={hi_r2:.2f}/{lo_r2:.2f}, price at {pos_in_channel:.0f}% of channel",
                            "watch_level": round(float(upper_now), 2),
                            "watch_level_low": round(float(lower_now), 2),
                            "invalidation": None,
                            "channel_width_pct": round((upper_now - lower_now) / max(lower_now, 0.01) * 100, 2),
                        })

        # ── 12. Forming Broadening Formation (Megaphone) ──
        if len(swing_highs) >= 2 and len(swing_lows) >= 2:
            high_vals = [v for _, v in swing_highs[-3:]]
            low_vals = [v for _, v in swing_lows[-3:]]

            if len(high_vals) >= 2 and len(low_vals) >= 2:
                highs_expanding = high_vals[-1] > high_vals[0]
                lows_expanding = low_vals[-1] < low_vals[0]

                if highs_expanding and lows_expanding:
                    spread_first = high_vals[0] - low_vals[0]
                    spread_last = high_vals[-1] - low_vals[-1]

                    if spread_first > 0 and spread_last > spread_first * 1.2:
                        expansion = (spread_last / spread_first - 1) * 100
                        emerging.append({
                            "name": "Broadening Formation (Forming)",
                            "stage": "forming",
                            "progress": min(80, 40 + int(expansion)),
                            "direction": "bearish",  # Broadening tops are typically bearish
                            "description": f"Megaphone — range expanding {expansion:.0f}%, higher highs AND lower lows",
                            "watch_level": round(float(high_vals[-1]), 2),
                            "watch_level_low": round(float(low_vals[-1]), 2),
                            "invalidation": None,
                        })

        # ── 13. Forming Rounded Bottom (Saucer) ──
        if len(bars) >= 30:
            lookback = min(60, len(bars))
            segment = c[-lookback:]
            midpoint = len(segment) // 2

            left_high = float(np.max(segment[:midpoint // 2]))
            center_low = float(np.min(segment[midpoint // 2: midpoint + midpoint // 2]))
            right_level = float(segment[-1])

            depth = (left_high - center_low) / max(left_high, 0.01) * 100

            if depth > 5.0 and right_level > center_low:
                recovery_pct = (right_level - center_low) / max(left_high - center_low, 0.01) * 100

                # Check if the descent and recovery are gradual (not V-shaped)
                left_descent = segment[:midpoint]
                right_recovery = segment[midpoint:]
                if len(left_descent) >= 5 and len(right_recovery) >= 5:
                    left_volatility = float(np.std(np.diff(left_descent)))
                    right_volatility = float(np.std(np.diff(right_recovery)))
                    avg_price = float(np.mean(segment))
                    normalized_vol = (left_volatility + right_volatility) / 2 / max(avg_price, 0.01) * 100

                    if normalized_vol < 2.0 and 30 < recovery_pct < 95:  # Gradual, not sharp
                        emerging.append({
                            "name": "Rounded Bottom (Forming)",
                            "stage": "forming",
                            "progress": int(recovery_pct),
                            "direction": "bullish",
                            "description": f"Saucer pattern — {depth:.1f}% depth, {recovery_pct:.0f}% recovered gradually",
                            "watch_level": round(left_high, 2),
                            "invalidation": round(center_low, 2),
                        })

        # ── 14. Forming Cup & Handle ──
        if len(bars) >= 30:
            left_high = float(np.max(c[:len(c)//3]))
            cup_low = float(np.min(c[len(c)//4:3*len(c)//4]))
            right_level = float(c[-1])

            if cup_low < left_high * 0.92 and right_level > cup_low:
                recovery_pct = (right_level - cup_low) / max(left_high - cup_low, 0.01) * 100

                if recovery_pct >= 95:
                    # Cup recovered, now check for handle forming
                    handle_bars = c[-5:] if len(c) >= 5 else c[-3:]
                    handle_drop = (float(np.max(handle_bars)) - float(np.min(handle_bars))) / max(left_high, 0.01) * 100
                    if 1.0 < handle_drop < 8.0:
                        emerging.append({
                            "name": "Cup & Handle (Handle Forming)",
                            "stage": "forming",
                            "progress": min(92, 85 + int(handle_drop)),
                            "direction": "bullish",
                            "description": f"Cup complete, handle pullback {handle_drop:.1f}% — breakout above ${left_high:.2f}",
                            "watch_level": round(left_high, 2),
                            "invalidation": round(float(np.min(handle_bars)), 2),
                        })
                elif 50 < recovery_pct < 95:
                    emerging.append({
                        "name": "Cup & Handle (Forming Cup)",
                        "stage": "forming",
                        "progress": int(recovery_pct),
                        "direction": "bullish",
                        "description": f"Cup {recovery_pct:.0f}% recovered — left rim ${left_high:.2f}, bottom ${cup_low:.2f}",
                        "watch_level": round(left_high, 2),
                        "invalidation": round(cup_low, 2),
                    })

        # ── 15. Forming Triple Top ──
        if len(swing_highs) >= 2:
            tops = [(i, v) for i, v in swing_highs[-4:]]
            # Find tops at similar levels
            for a_idx in range(len(tops)):
                for b_idx in range(a_idx + 1, len(tops)):
                    a_v, b_v = tops[a_idx][1], tops[b_idx][1]
                    if abs(a_v - b_v) / max(a_v, 0.01) < 0.015:  # Within 1.5%
                        resistance = (a_v + b_v) / 2
                        approach_pct = (c[-1] - float(np.min(c[tops[b_idx][0]:]))) / max(resistance - float(np.min(c[tops[b_idx][0]:])), 0.01) * 100
                        if approach_pct > 40 and c[-1] < resistance:
                            emerging.append({
                                "name": "Triple Top (Forming)",
                                "stage": "forming",
                                "progress": min(80, int(55 + approach_pct * 0.3)),
                                "direction": "bearish",
                                "description": f"Two peaks at ${resistance:.2f}, approaching for potential 3rd test",
                                "watch_level": round(float(resistance), 2),
                                "invalidation": round(float(resistance * 1.02), 2),
                            })
                            break
                else:
                    continue
                break

        # ── 16. Forming Triple Bottom ──
        if len(swing_lows) >= 2:
            bottoms = [(i, v) for i, v in swing_lows[-4:]]
            for a_idx in range(len(bottoms)):
                for b_idx in range(a_idx + 1, len(bottoms)):
                    a_v, b_v = bottoms[a_idx][1], bottoms[b_idx][1]
                    if abs(a_v - b_v) / max(a_v, 0.01) < 0.015:
                        support = (a_v + b_v) / 2
                        approach_pct = (float(np.max(c[bottoms[b_idx][0]:])) - c[-1]) / max(float(np.max(c[bottoms[b_idx][0]:])) - support, 0.01) * 100
                        if approach_pct > 40 and c[-1] > support:
                            emerging.append({
                                "name": "Triple Bottom (Forming)",
                                "stage": "forming",
                                "progress": min(80, int(55 + approach_pct * 0.3)),
                                "direction": "bullish",
                                "description": f"Two troughs at ${support:.2f}, declining toward potential 3rd test",
                                "watch_level": round(float(support), 2),
                                "invalidation": round(float(support * 0.98), 2),
                            })
                            break
                else:
                    continue
                break

        return emerging

    # ──────────────────────────────────────────
    # Pre-Candle Formations (1 Bar From Confirmation)
    # ──────────────────────────────────────────

    def detect_pre_candle_formations(self, bars: list[OHLCV]) -> list[dict]:
        """Detect candlestick patterns that are exactly 1 bar from confirmation.

        These are 'setup' candles where the pattern is partially formed and
        a specific candle type on the NEXT bar would confirm it. Useful for
        anticipating and preparing for pattern signals.

        Returns list of potential formations with:
        - name: What pattern would form
        - setup_type: What setup condition is met
        - confirmation_needed: What the next candle needs to look like
        - probability: Estimated likelihood based on current conditions
        """
        if len(bars) < 5:
            return []

        o = np.array([b.open for b in bars])
        h = np.array([b.high for b in bars])
        l = np.array([b.low for b in bars])
        c = np.array([b.close for b in bars])

        pre_formations: list[dict] = []
        i = len(bars) - 1  # Current (latest) bar

        body = abs(c[i] - o[i])
        rng = h[i] - l[i]
        body_prev = abs(c[i-1] - o[i-1]) if i >= 1 else 0
        rng_prev = h[i-1] - l[i-1] if i >= 1 else 0

        if rng == 0:
            return pre_formations

        body_pct = body / rng

        # Average body for context
        lookback = min(14, i)
        avg_body = float(np.mean(np.abs(c[i - lookback:i] - o[i - lookback:i]))) if lookback > 0 else body
        avg_vol = float(np.mean([b.volume for b in bars[max(0, i-20):i]])) if i > 5 else float(bars[i].volume)

        # ── 1. Pre-Morning Star ──
        # Setup: Big red + small body/doji on current bar, need green confirmation next
        if i >= 1:
            if (c[i-1] < o[i-1] and body_prev > avg_body * 1.2 and  # Previous was big red
                body_pct < 0.35):  # Current is small body or doji
                pre_formations.append({
                    "name": "Pre-Morning Star",
                    "stage": "pre_formation",
                    "setup_type": "Big red candle + small body/doji formed",
                    "confirmation_needed": "Bullish candle closing above midpoint of the first red candle",
                    "confirmation_above": round(float((o[i-1] + c[i-1]) / 2), 2),
                    "direction": "bullish",
                    "probability": 0.55,
                    "bar_index": i,
                    "description": "Two of three morning star candles formed — watch for bullish close above midpoint",
                })

        # ── 2. Pre-Evening Star ──
        if i >= 1:
            if (c[i-1] > o[i-1] and body_prev > avg_body * 1.2 and  # Previous was big green
                body_pct < 0.35):  # Current is small body or doji
                pre_formations.append({
                    "name": "Pre-Evening Star",
                    "stage": "pre_formation",
                    "setup_type": "Big green candle + small body/doji formed",
                    "confirmation_needed": "Bearish candle closing below midpoint of the first green candle",
                    "confirmation_below": round(float((o[i-1] + c[i-1]) / 2), 2),
                    "direction": "bearish",
                    "probability": 0.55,
                    "bar_index": i,
                    "description": "Two of three evening star candles formed — watch for bearish close below midpoint",
                })

        # ── 3. Pre-Three White Soldiers ──
        # Setup: 2 ascending green candles, need 3rd
        if i >= 1:
            if (c[i-1] > o[i-1] and c[i] > o[i] and  # Two greens
                c[i] > c[i-1] and o[i] > o[i-1] and  # Ascending
                body > avg_body * 0.7 and body_prev > avg_body * 0.7):  # Decent bodies
                pre_formations.append({
                    "name": "Pre-Three White Soldiers",
                    "stage": "pre_formation",
                    "setup_type": "Two ascending green candles in sequence",
                    "confirmation_needed": f"Third green candle opening above ${o[i]:.2f} and closing above ${c[i]:.2f}",
                    "confirmation_above": round(float(c[i]), 2),
                    "direction": "bullish",
                    "probability": 0.50,
                    "bar_index": i,
                    "description": "Two of three white soldiers formed — third ascending green needed",
                })

        # ── 4. Pre-Three Black Crows ──
        if i >= 1:
            if (c[i-1] < o[i-1] and c[i] < o[i] and  # Two reds
                c[i] < c[i-1] and o[i] < o[i-1] and  # Descending
                body > avg_body * 0.7 and body_prev > avg_body * 0.7):
                pre_formations.append({
                    "name": "Pre-Three Black Crows",
                    "stage": "pre_formation",
                    "setup_type": "Two descending red candles in sequence",
                    "confirmation_needed": f"Third red candle opening below ${o[i]:.2f} and closing below ${c[i]:.2f}",
                    "confirmation_below": round(float(c[i]), 2),
                    "direction": "bearish",
                    "probability": 0.50,
                    "bar_index": i,
                    "description": "Two of three black crows formed — third descending red needed",
                })

        # ── 5. Pre-Bullish Engulfing ──
        # Setup: Current bar is red, next green bar that engulfs would confirm
        if c[i] < o[i] and body > avg_body * 0.5:
            i_in_downtrend = i >= 5 and c[i] < c[i-5]
            if i_in_downtrend:
                pre_formations.append({
                    "name": "Pre-Bullish Engulfing",
                    "stage": "pre_formation",
                    "setup_type": "Red candle in downtrend — setup for engulfing",
                    "confirmation_needed": f"Green candle opening at/below ${c[i]:.2f} and closing above ${o[i]:.2f}",
                    "confirmation_above": round(float(o[i]), 2),
                    "direction": "bullish",
                    "probability": 0.45,
                    "bar_index": i,
                    "description": "Red candle in downtrend — next green engulfing candle would be strong reversal",
                })

        # ── 6. Pre-Bearish Engulfing ──
        if c[i] > o[i] and body > avg_body * 0.5:
            i_in_uptrend = i >= 5 and c[i] > c[i-5]
            if i_in_uptrend:
                pre_formations.append({
                    "name": "Pre-Bearish Engulfing",
                    "stage": "pre_formation",
                    "setup_type": "Green candle in uptrend — setup for engulfing",
                    "confirmation_needed": f"Red candle opening at/above ${c[i]:.2f} and closing below ${o[i]:.2f}",
                    "confirmation_below": round(float(o[i]), 2),
                    "direction": "bearish",
                    "probability": 0.45,
                    "bar_index": i,
                    "description": "Green candle in uptrend — next red engulfing candle would be strong reversal",
                })

        # ── 7. Pre-Three Inside Up ──
        # Setup: Red candle + current green harami (inside previous body)
        if i >= 1:
            if (c[i-1] < o[i-1] and c[i] > o[i] and  # prev red, now green
                o[i] > c[i-1] and c[i] < o[i-1] and  # inside previous body (harami)
                body < body_prev * 0.5):
                pre_formations.append({
                    "name": "Pre-Three Inside Up",
                    "stage": "pre_formation",
                    "setup_type": "Bullish harami formed (red + inside green)",
                    "confirmation_needed": f"Green candle closing above ${o[i-1]:.2f} (open of first bar)",
                    "confirmation_above": round(float(o[i-1]), 2),
                    "direction": "bullish",
                    "probability": 0.52,
                    "bar_index": i,
                    "description": "Harami setup complete — confirmation green close above first candle's open needed",
                })

        # ── 8. Pre-Three Inside Down ──
        if i >= 1:
            if (c[i-1] > o[i-1] and c[i] < o[i] and  # prev green, now red
                o[i] < c[i-1] and c[i] > o[i-1] and  # inside previous body (harami)
                body < body_prev * 0.5):
                pre_formations.append({
                    "name": "Pre-Three Inside Down",
                    "stage": "pre_formation",
                    "setup_type": "Bearish harami formed (green + inside red)",
                    "confirmation_needed": f"Red candle closing below ${o[i-1]:.2f} (open of first bar)",
                    "confirmation_below": round(float(o[i-1]), 2),
                    "direction": "bearish",
                    "probability": 0.52,
                    "bar_index": i,
                    "description": "Harami setup complete — confirmation red close below first candle's open needed",
                })

        # ── 9. Pre-Abandoned Baby (Bullish) ──
        # Setup: Big red + gap-down doji (current), need gap-up green next
        if i >= 1:
            if (c[i-1] < o[i-1] and body_prev > avg_body * 1.2 and  # Big red
                h[i] < l[i-1] and  # Gap down from previous
                body_pct < 0.15):  # Current is a doji
                pre_formations.append({
                    "name": "Pre-Abandoned Baby (Bullish)",
                    "stage": "pre_formation",
                    "setup_type": "Big red + gap-down doji formed",
                    "confirmation_needed": f"Gap-up green candle (low above ${h[i]:.2f})",
                    "confirmation_above": round(float(h[i]), 2),
                    "direction": "bullish",
                    "probability": 0.40,  # Rare pattern
                    "bar_index": i,
                    "description": "Rare abandoned baby setup — gap-up green candle would complete this high-reliability reversal",
                })

        # ── 10. Pre-Abandoned Baby (Bearish) ──
        if i >= 1:
            if (c[i-1] > o[i-1] and body_prev > avg_body * 1.2 and  # Big green
                l[i] > h[i-1] and  # Gap up from previous
                body_pct < 0.15):  # Current is a doji
                pre_formations.append({
                    "name": "Pre-Abandoned Baby (Bearish)",
                    "stage": "pre_formation",
                    "setup_type": "Big green + gap-up doji formed",
                    "confirmation_needed": f"Gap-down red candle (high below ${l[i]:.2f})",
                    "confirmation_below": round(float(l[i]), 2),
                    "direction": "bearish",
                    "probability": 0.40,
                    "bar_index": i,
                    "description": "Rare abandoned baby setup — gap-down red candle would complete this high-reliability reversal",
                })

        # ── 11. Pre-Piercing Pattern ──
        # Setup: Current bar is a big red candle, need gap-down green closing above midpoint
        if c[i] < o[i] and body > avg_body * 1.2:
            midpoint = (o[i] + c[i]) / 2
            i_in_downtrend = i >= 5 and c[i] < c[i-5]
            if i_in_downtrend:
                pre_formations.append({
                    "name": "Pre-Piercing Pattern",
                    "stage": "pre_formation",
                    "setup_type": "Strong red candle in downtrend",
                    "confirmation_needed": f"Green candle opening below ${c[i]:.2f} and closing above ${midpoint:.2f}",
                    "confirmation_above": round(float(midpoint), 2),
                    "direction": "bullish",
                    "probability": 0.42,
                    "bar_index": i,
                    "description": "Big red candle in downtrend — gap-down green closing above midpoint would be a piercing pattern",
                })

        # ── 12. Pre-Dark Cloud Cover ──
        if c[i] > o[i] and body > avg_body * 1.2:
            midpoint = (o[i] + c[i]) / 2
            i_in_uptrend = i >= 5 and c[i] > c[i-5]
            if i_in_uptrend:
                pre_formations.append({
                    "name": "Pre-Dark Cloud Cover",
                    "stage": "pre_formation",
                    "setup_type": "Strong green candle in uptrend",
                    "confirmation_needed": f"Red candle opening above ${c[i]:.2f} and closing below ${midpoint:.2f}",
                    "confirmation_below": round(float(midpoint), 2),
                    "direction": "bearish",
                    "probability": 0.42,
                    "bar_index": i,
                    "description": "Big green candle in uptrend — gap-up red closing below midpoint would be dark cloud cover",
                })

        # ── 13. Pre-Hammer/Inverted Hammer ──
        # If in downtrend, watch for hammer-shaped candle
        if i >= 5 and c[i] < c[i-5]:  # Currently in downtrend
            # Volume expansion often precedes hammer reversals
            vol_ratio = bars[i].volume / max(avg_vol, 1) if avg_vol > 0 else 1
            if vol_ratio > 1.3:
                pre_formations.append({
                    "name": "Pre-Hammer Reversal Zone",
                    "stage": "pre_formation",
                    "setup_type": "Downtrend + expanding volume (climax conditions)",
                    "confirmation_needed": "Hammer or inverted hammer candle (small body, long shadow)",
                    "direction": "bullish",
                    "probability": 0.38,
                    "bar_index": i,
                    "description": f"Conditions ripe for hammer reversal — downtrend + {vol_ratio:.1f}x volume expansion",
                    "volume_ratio": round(vol_ratio, 1),
                })

        # ── 14. Pre-Shooting Star Zone ──
        if i >= 5 and c[i] > c[i-5]:  # Currently in uptrend
            vol_ratio = bars[i].volume / max(avg_vol, 1) if avg_vol > 0 else 1
            if vol_ratio > 1.3:
                pre_formations.append({
                    "name": "Pre-Shooting Star Zone",
                    "stage": "pre_formation",
                    "setup_type": "Uptrend + expanding volume (exhaustion conditions)",
                    "confirmation_needed": "Shooting star candle (small body at bottom, long upper shadow)",
                    "direction": "bearish",
                    "probability": 0.38,
                    "bar_index": i,
                    "description": f"Conditions ripe for shooting star — uptrend + {vol_ratio:.1f}x volume expansion",
                    "volume_ratio": round(vol_ratio, 1),
                })

        return pre_formations

    # ──────────────────────────────────────────
    # Multi-Timeframe Pattern Analysis
    # ──────────────────────────────────────────

    def multi_timeframe_scan(
        self,
        bars_by_tf: dict[str, list[OHLCV]],
    ) -> dict:
        """Cross-reference patterns across multiple timeframes.

        Runs full_scan on each timeframe, then identifies:
        - Pattern confluence: same pattern type at multiple timeframes
        - Bias alignment: all timeframes agree on direction
        - Fractal patterns: same structure at different scales
        - Dominant signal: the strongest cross-timeframe signal

        Args:
            bars_by_tf: Dict mapping timeframe labels (e.g. "5m", "1h", "1d")
                        to their respective OHLCV bar lists.

        Returns:
            Comprehensive multi-timeframe analysis with alignment score.
        """
        if not bars_by_tf:
            return {"error": "no_timeframes_provided"}

        # Ordered by significance (higher = more weight)
        tf_weights = {
            "1m": 0.3, "5m": 0.5, "15m": 0.7, "30m": 0.8,
            "1h": 1.0, "4h": 1.3, "1d": 1.5, "1W": 1.8, "1M": 2.0,
        }

        scans_by_tf: dict[str, dict] = {}
        all_pattern_names: dict[str, list[str]] = {}  # pattern_name -> [timeframes]
        bias_by_tf: dict[str, str] = {}
        emerging_by_tf: dict[str, list[dict]] = {}
        pre_candles_by_tf: dict[str, list[dict]] = {}

        # Run full scan + emerging + pre-candle on each timeframe
        for tf, bars in bars_by_tf.items():
            if len(bars) < 10:
                continue

            scan = self.full_scan(bars) if len(bars) >= 20 else self.scan_all_patterns(bars)
            scans_by_tf[tf] = scan
            bias_by_tf[tf] = scan.get("overall_bias", "neutral")

            # Emerging patterns
            if len(bars) >= 20:
                emerging_by_tf[tf] = self.detect_emerging_patterns(bars)

            # Pre-candle formations
            pre_candles_by_tf[tf] = self.detect_pre_candle_formations(bars)

            # Collect pattern names by timeframe
            for cat in ["candlestick_patterns", "chart_patterns", "gap_patterns",
                         "volume_patterns", "trend_line_patterns"]:
                for p in scan.get(cat, []):
                    if isinstance(p, dict):
                        name = p.get("name", "")
                        if name:
                            all_pattern_names.setdefault(name, []).append(tf)

        # ── Cross-Timeframe Pattern Confluence ──
        confluent_patterns = []
        for name, tfs in all_pattern_names.items():
            if len(tfs) >= 2:
                max_weight = max(tf_weights.get(t, 1.0) for t in tfs)
                confluent_patterns.append({
                    "pattern": name,
                    "timeframes": sorted(tfs, key=lambda t: tf_weights.get(t, 1.0)),
                    "timeframe_count": len(tfs),
                    "weight": round(max_weight * len(tfs), 2),
                    "significance": "high" if len(tfs) >= 3 else "moderate",
                })
        confluent_patterns.sort(key=lambda x: x["weight"], reverse=True)

        # ── Bias Alignment Score ──
        # 0 = fully mixed, 100 = all timeframes agree
        weighted_bull = 0.0
        weighted_bear = 0.0
        total_weight = 0.0

        for tf, bias in bias_by_tf.items():
            w = tf_weights.get(tf, 1.0)
            total_weight += w
            if bias == "bullish":
                weighted_bull += w
            elif bias == "bearish":
                weighted_bear += w

        if total_weight > 0:
            bull_pct = weighted_bull / total_weight * 100
            bear_pct = weighted_bear / total_weight * 100
            alignment_score = max(bull_pct, bear_pct)
            dominant_bias = "bullish" if bull_pct > bear_pct else "bearish" if bear_pct > bull_pct else "neutral"
        else:
            alignment_score = 0
            dominant_bias = "neutral"

        # ── Fractal Analysis ──
        # Same pattern at vastly different timeframes = fractal structure
        fractal_patterns = []
        for name, tfs in all_pattern_names.items():
            tf_spreads = [tf_weights.get(t, 1.0) for t in tfs]
            if len(tfs) >= 2 and max(tf_spreads) / max(min(tf_spreads), 0.01) >= 2.0:
                fractal_patterns.append({
                    "pattern": name,
                    "timeframes": sorted(tfs, key=lambda t: tf_weights.get(t, 1.0)),
                    "scale_ratio": round(max(tf_spreads) / max(min(tf_spreads), 0.01), 1),
                    "description": f"Fractal: {name} appearing at both short and long timeframes",
                })

        # ── Cross-Timeframe Emerging Pattern Reinforcement ──
        emerging_confluence = []
        emerging_names: dict[str, list[str]] = {}
        for tf, patterns in emerging_by_tf.items():
            for p in patterns:
                ename = p.get("name", "")
                if ename:
                    emerging_names.setdefault(ename, []).append(tf)

        for ename, tfs in emerging_names.items():
            if len(tfs) >= 2:
                emerging_confluence.append({
                    "pattern": ename,
                    "timeframes": sorted(tfs, key=lambda t: tf_weights.get(t, 1.0)),
                    "reinforcement": "strong" if len(tfs) >= 3 else "moderate",
                })

        # ── Dominant Signal ──
        dominant_signal = None
        if confluent_patterns:
            top = confluent_patterns[0]
            # Find direction from the scan data
            for tf in top["timeframes"]:
                scan = scans_by_tf.get(tf, {})
                for cat in ["candlestick_patterns", "chart_patterns"]:
                    for p in scan.get(cat, []):
                        if isinstance(p, dict) and p.get("name") == top["pattern"]:
                            dominant_signal = {
                                "pattern": top["pattern"],
                                "direction": p.get("direction", "neutral"),
                                "confidence": p.get("confidence", 0.5),
                                "timeframes": top["timeframes"],
                                "weight": top["weight"],
                            }
                            break
                    if dominant_signal:
                        break
                if dominant_signal:
                    break

        return {
            "timeframes_analyzed": list(scans_by_tf.keys()),
            "scan_count": len(scans_by_tf),
            "bias_by_timeframe": bias_by_tf,
            "dominant_bias": dominant_bias,
            "alignment_score": round(alignment_score, 1),
            "alignment_label": (
                "strong" if alignment_score >= 75 else
                "moderate" if alignment_score >= 50 else
                "weak" if alignment_score >= 25 else
                "divergent"
            ),
            "confluent_patterns": confluent_patterns[:10],
            "fractal_patterns": fractal_patterns,
            "emerging_confluence": emerging_confluence,
            "dominant_signal": dominant_signal,
            "pre_candle_formations_by_tf": pre_candles_by_tf,
            "per_timeframe": {
                tf: {
                    "pattern_count": scan.get("pattern_count", 0),
                    "bias": scan.get("overall_bias", "neutral"),
                    "bullish": scan.get("bullish_count", 0),
                    "bearish": scan.get("bearish_count", 0),
                    "emerging_count": len(emerging_by_tf.get(tf, [])),
                }
                for tf, scan in scans_by_tf.items()
            },
        }

    # ──────────────────────────────────────────
    # Pattern Aging / Decay System
    # ──────────────────────────────────────────

    # Decay rates by pattern category (confidence multiplier per bar)
    _DECAY_RATES = {
        # Fast-decaying: single-bar candlestick patterns
        "Doji": 0.92, "Dragonfly Doji": 0.90, "Gravestone Doji": 0.90,
        "Hammer": 0.91, "Hanging Man": 0.91,
        "Inverted Hammer": 0.91, "Shooting Star": 0.91,
        "Spinning Top": 0.93, "Bullish Marubozu": 0.92, "Bearish Marubozu": 0.92,

        # Medium-decaying: multi-bar candlestick patterns
        "Bullish Engulfing": 0.93, "Bearish Engulfing": 0.93,
        "Bullish Harami": 0.94, "Bearish Harami": 0.94,
        "Tweezer Top": 0.93, "Tweezer Bottom": 0.93,
        "Piercing Pattern": 0.93, "Dark Cloud Cover": 0.93,
        "Morning Star": 0.94, "Evening Star": 0.94,
        "Three White Soldiers": 0.95, "Three Black Crows": 0.95,
        "Three Inside Up": 0.94, "Three Inside Down": 0.94,
        "Bullish Abandoned Baby": 0.95, "Bearish Abandoned Baby": 0.95,

        # Slow-decaying: chart structure patterns (take longer to play out)
        "Double Top": 0.97, "Double Bottom": 0.97,
        "Head & Shoulders": 0.975, "Inverse Head & Shoulders": 0.975,
        "Ascending Triangle": 0.97, "Descending Triangle": 0.97,
        "Symmetrical Triangle": 0.97,
        "Rising Wedge": 0.975, "Falling Wedge": 0.975,
        "Bull Flag": 0.96, "Bear Flag": 0.96,
        "Cup & Handle": 0.98,
        "Rectangle": 0.975, "Channel": 0.975,

        # Gap patterns decay medium-fast (gaps fill or continue quickly)
        "Gap Up": 0.93, "Gap Down": 0.93,
        "Breakaway Gap Up": 0.95, "Breakaway Gap Down": 0.95,
        "Exhaustion Gap Up": 0.91, "Exhaustion Gap Down": 0.91,

        # Volume patterns decay fast (volume is ephemeral)
        "Volume Climax (Buying)": 0.90, "Volume Climax (Selling)": 0.90,
        "Volume Dry-Up": 0.92, "Accumulation": 0.95, "Distribution": 0.95,

        # Trend line patterns decay slowly
        "Uptrend Line Support": 0.98, "Uptrend Line Break": 0.96,
        "Downtrend Line Resistance": 0.98, "Downtrend Line Break": 0.96,
    }

    _DEFAULT_DECAY = 0.94  # Default for unlisted patterns

    def age_pattern_signals(
        self,
        pattern_signals: list[dict],
        current_bar_index: int,
        current_close: float,
        current_high: float | None = None,
        current_low: float | None = None,
    ) -> list[dict]:
        """Apply time-decay to pattern confidence and check invalidation.

        For each pattern signal, computes:
        - aged_confidence: Decayed confidence based on bars elapsed
        - staleness: 0 (fresh) to 100 (stale) — how aged the signal is
        - status: fresh | active | aging | stale | invalidated | confirmed
        - bars_elapsed: How many bars since detection
        - decay_rate: The per-bar decay factor used

        Patterns are marked 'invalidated' if:
        - Price passes the invalidation level
        - Confidence decays below 0.15 (essentially noise)
        - Direction-specific: bullish pattern but price making new lows, etc.

        Patterns are marked 'confirmed' if:
        - Price breaks past the watch_level in the expected direction
        - Entry trigger is hit

        Args:
            pattern_signals: List of pattern signal dicts (from scan or emerging).
            current_bar_index: Index of the current/latest bar.
            current_close: Current closing price.
            current_high: Current bar's high (optional, for confirmation checks).
            current_low: Current bar's low (optional, for invalidation checks).

        Returns:
            Same list of dicts with aging metadata added to each.
        """
        if not pattern_signals:
            return []

        aged: list[dict] = []

        for p in pattern_signals:
            result = dict(p)  # Copy to avoid mutation

            # Determine bars elapsed
            detect_idx = p.get("bar_index", 0)
            bars_elapsed = max(0, current_bar_index - detect_idx)

            # Get decay rate for this pattern type
            name = p.get("name", "")
            decay_rate = self._DECAY_RATES.get(name, self._DEFAULT_DECAY)

            # Apply decay
            original_confidence = p.get("confidence", 0.5)
            aged_confidence = original_confidence * (decay_rate ** bars_elapsed)

            # Staleness score: 0=fresh, 100=stale
            if aged_confidence <= 0:
                staleness = 100
            else:
                staleness = max(0, min(100, int((1 - aged_confidence / max(original_confidence, 0.01)) * 100)))

            # Determine status
            direction = p.get("direction", "neutral")
            invalidation = p.get("invalidation")
            watch_level = p.get("watch_level")
            entry_trigger = p.get("entry_trigger")

            status = "active"

            # ── Invalidation Checks ──
            invalidated = False

            # Check explicit invalidation level
            if invalidation is not None:
                if direction == "bullish" and current_low is not None and current_low < invalidation:
                    invalidated = True
                    result["invalidation_reason"] = f"Price broke below invalidation ${invalidation:.2f}"
                elif direction == "bearish" and current_high is not None and current_high > invalidation:
                    invalidated = True
                    result["invalidation_reason"] = f"Price broke above invalidation ${invalidation:.2f}"

            # Check extreme decay (essentially noise at this point)
            if aged_confidence < 0.15:
                invalidated = True
                result["invalidation_reason"] = result.get("invalidation_reason", "Confidence decayed below threshold (0.15)")

            # Check direction-specific invalidation
            if not invalidated and bars_elapsed > 5:
                if direction == "bullish" and current_low is not None:
                    # If price is making new lows well past detection, invalidate
                    detect_price = p.get("entry_trigger") or p.get("watch_level") or current_close
                    if isinstance(detect_price, (int, float)) and current_low < detect_price * 0.95:
                        invalidated = True
                        result["invalidation_reason"] = "Price making new lows — bullish thesis negated"

                elif direction == "bearish" and current_high is not None:
                    detect_price = p.get("entry_trigger") or p.get("watch_level") or current_close
                    if isinstance(detect_price, (int, float)) and current_high > detect_price * 1.05:
                        invalidated = True
                        result["invalidation_reason"] = "Price making new highs — bearish thesis negated"

            if invalidated:
                status = "invalidated"
                aged_confidence = 0.0
                staleness = 100

            # ── Confirmation Checks ──
            if not invalidated:
                confirmed = False

                if entry_trigger is not None:
                    if direction == "bullish" and current_high is not None and current_high >= entry_trigger:
                        confirmed = True
                        result["confirmation_reason"] = f"Entry trigger ${entry_trigger:.2f} hit"
                    elif direction == "bearish" and current_low is not None and current_low <= entry_trigger:
                        confirmed = True
                        result["confirmation_reason"] = f"Entry trigger ${entry_trigger:.2f} hit"

                if not confirmed and watch_level is not None:
                    if direction == "bullish" and current_high is not None and current_high >= watch_level:
                        confirmed = True
                        result["confirmation_reason"] = f"Watch level ${watch_level:.2f} breached"
                    elif direction == "bearish" and current_low is not None and current_low <= watch_level:
                        confirmed = True
                        result["confirmation_reason"] = f"Watch level ${watch_level:.2f} breached"

                if confirmed:
                    status = "confirmed"
                    # Boost confidence on confirmation
                    aged_confidence = min(1.0, aged_confidence * 1.3)
                    staleness = max(0, staleness - 20)

            # ── Status from staleness (if not invalidated/confirmed) ──
            if status == "active":
                if bars_elapsed == 0:
                    status = "fresh"
                elif staleness < 15:
                    status = "fresh"
                elif staleness < 40:
                    status = "active"
                elif staleness < 70:
                    status = "aging"
                else:
                    status = "stale"

            # Write to result
            result["aged_confidence"] = round(aged_confidence, 4)
            result["original_confidence"] = round(original_confidence, 4)
            result["staleness"] = staleness
            result["status"] = status
            result["bars_elapsed"] = bars_elapsed
            result["decay_rate"] = round(decay_rate, 4)
            result["half_life_bars"] = round(-0.693 / max(np.log(decay_rate), -0.5), 1)  # ln(0.5) / ln(decay)

            aged.append(result)

        # Sort: confirmed first, then by aged_confidence desc
        status_order = {"confirmed": 0, "fresh": 1, "active": 2, "aging": 3, "stale": 4, "invalidated": 5}
        aged.sort(key=lambda x: (status_order.get(x.get("status", "active"), 3), -x.get("aged_confidence", 0)))

        return aged

    # ──────────────────────────────────────────
    # Enhanced scan_all_patterns (with new detectors)
    # ──────────────────────────────────────────

    def full_scan(self, bars: list[OHLCV]) -> dict:
        """Comprehensive scan: all patterns, gaps, volume, fibs, trend lines, emerging.

        This is the deep-dive version of scan_all_patterns with complete coverage.
        """
        base_scan = self.scan_all_patterns(bars)

        # Add gap patterns
        gaps = self.detect_gaps(bars)
        base_scan["gap_patterns"] = [g.to_dict() for g in gaps]
        base_scan["pattern_count"] += len(gaps)

        # Add volume patterns
        vol_patterns = self.detect_volume_patterns(bars)
        base_scan["volume_patterns"] = [vp.to_dict() for vp in vol_patterns]
        base_scan["pattern_count"] += len(vol_patterns)

        # Add trend line analysis
        tl_patterns = self.detect_trend_lines(bars)
        base_scan["trend_line_patterns"] = [t.to_dict() for t in tl_patterns]
        base_scan["pattern_count"] += len(tl_patterns)

        # Fibonacci levels
        base_scan["fibonacci"] = self.detect_fibonacci_levels(bars)

        # Emerging patterns
        base_scan["emerging_patterns"] = self.detect_emerging_patterns(bars)

        # Pre-candle formations (1 bar from confirmation)
        base_scan["pre_candle_formations"] = self.detect_pre_candle_formations(bars)

        # Recalculate bias with all signals
        all_signals = (
            base_scan["candlestick_patterns"] + base_scan["chart_patterns"] +
            base_scan["gap_patterns"] + base_scan["volume_patterns"] +
            base_scan["trend_line_patterns"]
        )
        bullish = sum(1 for p in all_signals if isinstance(p, dict) and p.get("direction") == "bullish")
        bearish = sum(1 for p in all_signals if isinstance(p, dict) and p.get("direction") == "bearish")
        base_scan["bullish_count"] = bullish
        base_scan["bearish_count"] = bearish
        base_scan["overall_bias"] = "bullish" if bullish > bearish else "bearish" if bearish > bullish else "neutral"

        # Apply aging/decay to all pattern signals for freshness tracking
        all_pattern_dicts = [
            p for p in all_signals if isinstance(p, dict) and p.get("bar_index") is not None
        ]
        if all_pattern_dicts and len(bars) > 0:
            base_scan["aged_patterns"] = self.age_pattern_signals(
                all_pattern_dicts,
                current_bar_index=len(bars) - 1,
                current_close=float(bars[-1].close),
                current_high=float(bars[-1].high),
                current_low=float(bars[-1].low),
            )
            # Summary stats
            aged = base_scan["aged_patterns"]
            base_scan["aging_summary"] = {
                "total": len(aged),
                "fresh": sum(1 for a in aged if a.get("status") == "fresh"),
                "active": sum(1 for a in aged if a.get("status") == "active"),
                "aging": sum(1 for a in aged if a.get("status") == "aging"),
                "stale": sum(1 for a in aged if a.get("status") == "stale"),
                "invalidated": sum(1 for a in aged if a.get("status") == "invalidated"),
                "confirmed": sum(1 for a in aged if a.get("status") == "confirmed"),
            }

        return base_scan

    # ──────────────────────────────────────────
    # Pattern Outcome Evaluation (Failure Alerts)
    # ──────────────────────────────────────────

    def evaluate_pattern_outcomes(
        self,
        bars: list[OHLCV],
        pattern_log: list[dict],
        lookforward: int = 20,
    ) -> list[dict]:
        """Evaluate whether previously detected patterns succeeded or failed.

        For each pattern in the log:
        - SUCCESS: price hit target within lookforward bars
        - FAILED: price hit stop_loss within lookforward bars
        - ACTIVE: neither target nor stop hit yet
        - EXPIRED: lookforward bars passed with no outcome

        Args:
            bars: Current OHLCV bar list.
            pattern_log: Previously detected patterns with bar_index, target, stop_loss.
            lookforward: Number of bars to evaluate after pattern detection.

        Returns:
            Updated pattern log with 'outcome' field added.
        """
        if not bars or not pattern_log:
            return pattern_log

        c = np.array([b.close for b in bars])
        h = np.array([b.high for b in bars])
        l = np.array([b.low for b in bars])

        results = []
        for plog in pattern_log:
            result = dict(plog)
            detect_idx = plog.get("bar_index", 0)
            target = plog.get("target")
            stop_loss = plog.get("stop_loss")
            direction = plog.get("direction", "bullish")

            if detect_idx >= len(bars) - 1:
                result["outcome"] = "too_recent"
                result["outcome_detail"] = "Pattern detected on latest bar, no bars to evaluate"
                results.append(result)
                continue

            # Evaluate forward from detection
            eval_start = detect_idx + 1
            eval_end = min(detect_idx + lookforward + 1, len(bars))
            future_highs = h[eval_start:eval_end]
            future_lows = l[eval_start:eval_end]
            future_closes = c[eval_start:eval_end]

            if len(future_closes) == 0:
                result["outcome"] = "too_recent"
                results.append(result)
                continue

            # Check target hit
            target_hit = False
            stop_hit = False
            target_bar = None
            stop_bar = None

            if target is not None:
                if direction == "bullish":
                    target_hits = np.where(future_highs >= target)[0]
                else:
                    target_hits = np.where(future_lows <= target)[0]
                if len(target_hits) > 0:
                    target_hit = True
                    target_bar = int(target_hits[0])

            if stop_loss is not None:
                if direction == "bullish":
                    stop_hits = np.where(future_lows <= stop_loss)[0]
                else:
                    stop_hits = np.where(future_highs >= stop_loss)[0]
                if len(stop_hits) > 0:
                    stop_hit = True
                    stop_bar = int(stop_hits[0])

            # Determine outcome
            if target_hit and stop_hit:
                # Which came first?
                if target_bar <= stop_bar:
                    result["outcome"] = "success"
                    result["outcome_bars"] = target_bar + 1
                else:
                    result["outcome"] = "failed"
                    result["outcome_bars"] = stop_bar + 1
            elif target_hit:
                result["outcome"] = "success"
                result["outcome_bars"] = target_bar + 1
            elif stop_hit:
                result["outcome"] = "failed"
                result["outcome_bars"] = stop_bar + 1
            elif eval_end - eval_start >= lookforward:
                # Calculate P&L at expiry
                entry = float(c[detect_idx])
                final = float(future_closes[-1])
                pnl_pct = ((final - entry) / max(entry, 0.01)) * 100
                if direction == "bearish":
                    pnl_pct = -pnl_pct  # Invert for bearish trades

                result["outcome"] = "expired"
                result["pnl_at_expiry_pct"] = round(pnl_pct, 2)
                result["outcome_bars"] = lookforward
            else:
                result["outcome"] = "active"
                result["bars_remaining"] = lookforward - (eval_end - eval_start)

            # Add max adverse/favorable excursion
            entry_price = float(c[detect_idx])
            if len(future_closes) > 0:
                if direction == "bullish":
                    result["max_favorable_pct"] = round(
                        ((float(np.max(future_highs)) - entry_price) / max(entry_price, 0.01)) * 100, 2
                    )
                    result["max_adverse_pct"] = round(
                        ((entry_price - float(np.min(future_lows))) / max(entry_price, 0.01)) * 100, 2
                    )
                else:
                    result["max_favorable_pct"] = round(
                        ((entry_price - float(np.min(future_lows))) / max(entry_price, 0.01)) * 100, 2
                    )
                    result["max_adverse_pct"] = round(
                        ((float(np.max(future_highs)) - entry_price) / max(entry_price, 0.01)) * 100, 2
                    )

            results.append(result)

        return results

    # ──────────────────────────────────────────
    # Historical Pattern Backtesting
    # ──────────────────────────────────────────

    def backtest_patterns(
        self,
        bars: list[OHLCV],
        window_size: int = 60,
        step: int = 5,
        lookforward: int = 20,
    ) -> dict:
        """Historical pattern backtest — scan sliding windows and measure outcomes.

        Slides a detection window across the full dataset, detects patterns at each
        position, then evaluates whether they succeeded, failed, or expired.

        Args:
            bars: Full OHLCV history (1-2 years recommended).
            window_size: Number of bars in each detection window (default 60).
            step: Slide step between windows (default 5 bars).
            lookforward: Bars to evaluate after pattern detection (default 20).

        Returns:
            Per-pattern statistics: occurrences, win_rate, avg_return, reliability.
        """
        if len(bars) < window_size + lookforward + 10:
            return {
                "error": "insufficient_data",
                "required_bars": window_size + lookforward + 10,
                "available_bars": len(bars),
            }

        c = np.array([b.close for b in bars])
        h = np.array([b.high for b in bars])
        l = np.array([b.low for b in bars])

        # Track stats per pattern name
        pattern_stats: dict[str, dict] = {}

        # Slide window across data
        for start in range(0, len(bars) - window_size - lookforward, step):
            window = bars[start:start + window_size]

            # Detect patterns in this window
            scan_result = self.scan_all_patterns(window)

            # Collect all raw PatternSignal-like dicts
            all_patterns = scan_result.get("candlestick_patterns", []) + \
                          scan_result.get("chart_patterns", [])

            for p in all_patterns:
                if not isinstance(p, dict):
                    continue

                name = p.get("name", "Unknown")
                direction = p.get("direction", "neutral")
                confidence = p.get("confidence", 0.5)
                target = p.get("target")
                stop_loss = p.get("stop_loss")
                detect_idx = p.get("bar_index", window_size - 1)

                # Absolute index in full dataset
                abs_idx = start + detect_idx

                if abs_idx >= len(bars) - lookforward - 1:
                    continue  # Not enough forward data

                # Evaluate outcome
                entry_price = float(c[abs_idx])
                eval_start = abs_idx + 1
                eval_end = min(abs_idx + lookforward + 1, len(bars))

                future_h = h[eval_start:eval_end]
                future_l = l[eval_start:eval_end]
                future_c = c[eval_start:eval_end]

                if len(future_c) == 0:
                    continue

                # Calculate max favorable/adverse
                if direction == "bullish":
                    max_up = (float(np.max(future_h)) - entry_price) / max(entry_price, 0.01) * 100
                    max_down = (entry_price - float(np.min(future_l))) / max(entry_price, 0.01) * 100
                    pnl_at_end = (float(future_c[-1]) - entry_price) / max(entry_price, 0.01) * 100
                else:
                    max_up = (entry_price - float(np.min(future_l))) / max(entry_price, 0.01) * 100
                    max_down = (float(np.max(future_h)) - entry_price) / max(entry_price, 0.01) * 100
                    pnl_at_end = (entry_price - float(future_c[-1])) / max(entry_price, 0.01) * 100

                # Determine outcome
                target_hit = False
                stop_hit = False

                if target is not None:
                    if direction == "bullish":
                        target_hit = bool(np.any(future_h >= target))
                    else:
                        target_hit = bool(np.any(future_l <= target))

                if stop_loss is not None:
                    if direction == "bullish":
                        stop_hit = bool(np.any(future_l <= stop_loss))
                    else:
                        stop_hit = bool(np.any(future_h >= stop_loss))

                # Consider it a "win" if target hit (and stop not hit first) or pnl > 0
                if target is not None and stop_loss is not None:
                    won = target_hit and not stop_hit
                elif target is not None:
                    won = target_hit
                else:
                    won = pnl_at_end > 0

                # Accumulate stats
                if name not in pattern_stats:
                    pattern_stats[name] = {
                        "name": name,
                        "direction": direction,
                        "occurrences": 0,
                        "wins": 0,
                        "losses": 0,
                        "total_pnl_pct": 0.0,
                        "max_favorable_pcts": [],
                        "max_adverse_pcts": [],
                        "avg_confidence": 0.0,
                        "confidence_sum": 0.0,
                    }

                stats = pattern_stats[name]
                stats["occurrences"] += 1
                stats["confidence_sum"] += confidence
                stats["total_pnl_pct"] += pnl_at_end
                stats["max_favorable_pcts"].append(max_up)
                stats["max_adverse_pcts"].append(max_down)

                if won:
                    stats["wins"] += 1
                else:
                    stats["losses"] += 1

        # Compile final results
        results = []
        for name, stats in sorted(pattern_stats.items(), key=lambda x: x[1]["occurrences"], reverse=True):
            occ = stats["occurrences"]
            if occ == 0:
                continue

            win_rate = stats["wins"] / occ * 100
            avg_pnl = stats["total_pnl_pct"] / occ
            avg_confidence = stats["confidence_sum"] / occ
            avg_favorable = float(np.mean(stats["max_favorable_pcts"])) if stats["max_favorable_pcts"] else 0
            avg_adverse = float(np.mean(stats["max_adverse_pcts"])) if stats["max_adverse_pcts"] else 0

            # Reliability score: weighted combination of win rate, sample size, and risk/reward
            sample_factor = min(1.0, occ / 20)  # Full weight at 20+ samples
            rr_factor = min(1.0, avg_favorable / max(avg_adverse, 0.01))
            reliability = round((win_rate * 0.5 + sample_factor * 25 + min(rr_factor * 25, 25)), 1)

            results.append({
                "pattern": name,
                "direction": stats["direction"],
                "occurrences": occ,
                "wins": stats["wins"],
                "losses": stats["losses"],
                "win_rate_pct": round(win_rate, 1),
                "avg_pnl_pct": round(avg_pnl, 2),
                "avg_max_favorable_pct": round(avg_favorable, 2),
                "avg_max_adverse_pct": round(avg_adverse, 2),
                "risk_reward": round(avg_favorable / max(avg_adverse, 0.01), 2),
                "avg_confidence": round(avg_confidence, 2),
                "reliability_score": reliability,
            })

        # Sort by reliability
        results.sort(key=lambda r: r["reliability_score"], reverse=True)

        return {
            "total_patterns_found": sum(r["occurrences"] for r in results),
            "unique_patterns": len(results),
            "total_bars_scanned": len(bars),
            "window_size": window_size,
            "lookforward": lookforward,
            "patterns": results,
            "top_reliable": results[:5] if results else [],
            "least_reliable": results[-3:] if len(results) > 3 else [],
        }

    # ──────────────────────────────────────────────
    # Market Structure Detection
    # ──────────────────────────────────────────────

    def detect_market_structure(
        self,
        bars: list[OHLCV],
        lookback: int = 5,
    ) -> dict:
        """Classify price action structure using swing highs/lows.

        Identifies:
        - **Uptrend**: Higher Highs + Higher Lows (HH + HL)
        - **Downtrend**: Lower Highs + Lower Lows (LH + LL)
        - **Range**: No clear directional sequence

        Also computes break-of-structure (BOS) invalidation levels.

        Args:
            bars: OHLCV bar list (needs ≥ 30 bars for reliable structure).
            lookback: N-bar lookback for swing detection (default 5).

        Returns:
            Dict with structure classification, swing levels, and invalidation.
        """
        if len(bars) < lookback * 4:
            return {"error": "insufficient_data", "required_bars": lookback * 4}

        h = np.array([b.high for b in bars])
        l = np.array([b.low for b in bars])
        c = np.array([b.close for b in bars])

        # Find swing highs and lows
        swing_highs = self._find_swings(h, mode="high", order=lookback)
        swing_lows = self._find_swings(l, mode="low", order=lookback)

        if len(swing_highs) < 2 or len(swing_lows) < 2:
            return {
                "structure": "undefined",
                "reason": "insufficient_swing_points",
                "swing_highs": len(swing_highs),
                "swing_lows": len(swing_lows),
            }

        # Analyze the last 4 swing points of each type
        recent_highs = swing_highs[-4:]
        recent_lows = swing_lows[-4:]

        # Check for Higher Highs / Higher Lows
        hh_count = sum(1 for i in range(1, len(recent_highs)) if recent_highs[i][1] > recent_highs[i-1][1])
        hl_count = sum(1 for i in range(1, len(recent_lows)) if recent_lows[i][1] > recent_lows[i-1][1])

        # Check for Lower Highs / Lower Lows
        lh_count = sum(1 for i in range(1, len(recent_highs)) if recent_highs[i][1] < recent_highs[i-1][1])
        ll_count = sum(1 for i in range(1, len(recent_lows)) if recent_lows[i][1] < recent_lows[i-1][1])

        total_checks = max(len(recent_highs) - 1, 1)

        # Classify
        bull_score = (hh_count + hl_count) / (total_checks * 2)
        bear_score = (lh_count + ll_count) / (total_checks * 2)

        if bull_score >= 0.6:
            structure = "uptrend"
            # BOS invalidation: if price breaks below the most recent swing low
            bos_level = recent_lows[-1][1]
            bos_direction = "below"
        elif bear_score >= 0.6:
            structure = "downtrend"
            # BOS invalidation: if price breaks above the most recent swing high
            bos_level = recent_highs[-1][1]
            bos_direction = "above"
        else:
            structure = "range"
            # Range boundaries
            bos_level = None
            bos_direction = None

        current_price = float(c[-1])

        # Key levels
        last_sh = recent_highs[-1]
        last_sl = recent_lows[-1]

        return {
            "structure": structure,
            "bull_score": round(bull_score * 100, 1),
            "bear_score": round(bear_score * 100, 1),
            "current_price": round(current_price, 4),
            "swing_highs": [
                {"bar_index": int(sh[0]), "price": round(float(sh[1]), 4)}
                for sh in recent_highs
            ],
            "swing_lows": [
                {"bar_index": int(sl[0]), "price": round(float(sl[1]), 4)}
                for sl in recent_lows
            ],
            "last_swing_high": round(float(last_sh[1]), 4),
            "last_swing_low": round(float(last_sl[1]), 4),
            "bos_invalidation": {
                "level": round(float(bos_level), 4) if bos_level else None,
                "direction": bos_direction,
                "description": (
                    f"Structure breaks if price moves {bos_direction} ${bos_level:.2f}"
                    if bos_level else "No clear BOS level in range"
                ),
            },
            "hh_count": hh_count,
            "hl_count": hl_count,
            "lh_count": lh_count,
            "ll_count": ll_count,
            "range_size_pct": round(
                ((float(last_sh[1]) - float(last_sl[1])) / max(float(last_sl[1]), 0.01)) * 100, 2
            ),
        }
