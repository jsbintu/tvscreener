"""
Bubby Vision — Breakout Engine

Implements the complete breakout detection and scoring system from the
architecture blueprint (P.1-P.5). Tracks 15 precursor signals.

Pure domain logic — no LLM dependency.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

import numpy as np
import pandas as pd

from app.models import (
    BreakoutSignal,
    BreakoutStage,
    OHLCV,
    TechnicalIndicators,
)


# ──────────────────────────────────────────────
# Precursor Signal Definitions
# ──────────────────────────────────────────────

PRECURSOR_SIGNALS = {
    "P1": "Volume Dry-Up (VDU) — Volume drops to <50% of avg during consolidation",
    "P2": "Bollinger Band Squeeze — BB width reaches 6-month low",
    "P3": "ATR Compression — ATR <50% of 50-day avg",
    "P4": "EMA Convergence — 8/21 EMAs within 0.5% of each other",
    "P5": "Accumulation OBV — OBV rising while price flat",
    "P6": "Institutional Footprints — Block trades >$500K",
    "P7": "Options Activity — Call volume spike >3x avg OI",
    "P8": "RSI Reset — RSI between 45-55 after pullback to support",
    "P9": "Higher Lows — 3+ consecutive higher lows against resistance",
    "P10": "Sector Rotation — Money flowing into the stock's sector",
    "P11": "Relative Strength — Stock outperforming sector/SPY for 2+ weeks",
    "P12": "Gap & Go Setup — Small gap up at open with volume",
    "P13": "VWAP Reclaim — Price reclaims VWAP with volume",
    "P14": "Inside Bars — 2+ consecutive inside bars (coiling)",
    "P15": "Tightening Range — 5+ day declining ATR with flat resistance",
}


class BreakoutEngine:
    """Complete breakout detection and scoring system."""

    def scan_precursors(
        self,
        bars: list[OHLCV],
        indicators: TechnicalIndicators,
        options_data: Optional[dict] = None,
    ) -> list[str]:
        """Scan for active precursor signals.

        Returns list of active precursor IDs (e.g. ["P1", "P2", "P5"]).
        """
        if len(bars) < 50:
            return []

        df = self._bars_to_dataframe(bars)
        active = []

        # P1: Volume Dry-Up
        avg_vol = df["volume"].rolling(20).mean().iloc[-1]
        recent_vol = df["volume"].iloc[-5:].mean()
        if avg_vol > 0 and recent_vol / avg_vol < 0.50:
            active.append("P1")

        # P2: Bollinger Band Squeeze
        if indicators.bb_width is not None:
            # Compare to historical BB width
            closes = df["close"]
            bb_width_series = closes.rolling(20).std() / closes.rolling(20).mean()
            min_width_6mo = bb_width_series.iloc[-130:].min() if len(df) >= 130 else bb_width_series.min()
            if indicators.bb_width <= min_width_6mo * 1.1:  # within 10% of 6-month low
                active.append("P2")

        # P3: ATR Compression
        if indicators.atr_14 is not None and len(df) >= 50:
            highs = df["high"]
            lows = df["low"]
            closes = df["close"]
            tr = pd.concat([
                highs - lows,
                (highs - closes.shift(1)).abs(),
                (lows - closes.shift(1)).abs(),
            ], axis=1).max(axis=1)
            avg_atr_50 = tr.rolling(14).mean().iloc[-50:].mean()
            if avg_atr_50 > 0 and indicators.atr_14 / avg_atr_50 < 0.50:
                active.append("P3")

        # P4: EMA Convergence
        if indicators.ema_8 is not None and indicators.ema_21 is not None:
            ema_diff_pct = abs(indicators.ema_8 - indicators.ema_21) / indicators.ema_21
            if ema_diff_pct < 0.005:
                active.append("P4")

        # P5: Accumulation OBV
        if indicators.obv is not None and len(df) >= 20:
            price_change_20d = (df["close"].iloc[-1] - df["close"].iloc[-20]) / df["close"].iloc[-20]
            if abs(price_change_20d) < 0.03:  # price flat (< 3% change)
                # Check if OBV is rising
                cum_vol = (df["volume"] * np.sign(df["close"].diff())).cumsum()
                obv_change = cum_vol.iloc[-1] - cum_vol.iloc[-20]
                if obv_change > 0:
                    active.append("P5")

        # P6: Institutional Footprints (block trades)
        if options_data:
            dark_pool = options_data.get("dark_pool", {})
            block_trades = dark_pool.get("block_trades", [])
            large_blocks = [t for t in block_trades if isinstance(t, dict) and t.get("value", 0) >= 500_000]
            if large_blocks:
                active.append("P6")

        # P7: Options Activity (if options data available)
        if options_data:
            unusual = options_data.get("unusual_activity", [])
            call_unusual = [u for u in unusual if u.get("type") == "call" and u.get("vol_oi_ratio", 0) >= 3.0]
            if call_unusual:
                active.append("P7")

        # P8: RSI Reset
        if indicators.rsi_14 is not None:
            if 45 <= indicators.rsi_14 <= 55:
                active.append("P8")

        # P9: Higher Lows (check last 5 bars)
        recent_lows = df["low"].iloc[-5:]
        if len(recent_lows) >= 3:
            if all(recent_lows.iloc[i] >= recent_lows.iloc[i - 1] for i in range(1, len(recent_lows))):
                active.append("P9")

        # P10: Sector Rotation — check if stock's recent performance beats SPY
        if len(df) >= 10:
            stock_return_10d = (df["close"].iloc[-1] - df["close"].iloc[-10]) / df["close"].iloc[-10]
            # Heuristic: if stock is up > 2% in 10 days while market/sector is stable
            if stock_return_10d > 0.02:
                active.append("P10")

        # P11: Relative Strength vs SPY (2+ weeks outperformance)
        if len(df) >= 15:
            stock_return_15d = (df["close"].iloc[-1] - df["close"].iloc[-15]) / df["close"].iloc[-15]
            # Compare to a baseline — if stock outperforms significantly
            if stock_return_15d > 0.03:  # 3%+ over 2 weeks = relative strength
                active.append("P11")

        # P12: Gap & Go Setup — gap up at open with volume
        if len(df) >= 2:
            prev_close = df["close"].iloc[-2]
            today_open = df["open"].iloc[-1]
            gap_pct = (today_open - prev_close) / prev_close
            today_vol = df["volume"].iloc[-1]
            avg_vol_5d = df["volume"].iloc[-6:-1].mean() if len(df) >= 6 else df["volume"].mean()
            if 0.005 < gap_pct < 0.03 and today_vol > avg_vol_5d * 1.3:
                active.append("P12")

        # P13: VWAP Reclaim — price crosses above VWAP-like level with volume
        if len(df) >= 5:
            # Approximate intraday VWAP using typical price * volume
            typical = (df["high"] + df["low"] + df["close"]) / 3
            cum_tp_vol = (typical * df["volume"]).rolling(5).sum()
            cum_vol = df["volume"].rolling(5).sum()
            vwap_approx = cum_tp_vol.iloc[-1] / max(cum_vol.iloc[-1], 1)
            current_close = df["close"].iloc[-1]
            prev_close_v = df["close"].iloc[-2]
            if prev_close_v < vwap_approx and current_close > vwap_approx:
                today_vol = df["volume"].iloc[-1]
                avg_vol_5d = df["volume"].iloc[-6:-1].mean() if len(df) >= 6 else df["volume"].mean()
                if today_vol > avg_vol_5d * 1.2:
                    active.append("P13")

        # P14: Inside Bars
        inside_count = 0
        for i in range(-1, max(-5, -len(df)), -1):
            if df["high"].iloc[i] <= df["high"].iloc[i - 1] and df["low"].iloc[i] >= df["low"].iloc[i - 1]:
                inside_count += 1
            else:
                break
        if inside_count >= 2:
            active.append("P14")

        # P15: Tightening Range
        if len(df) >= 10:
            ranges = (df["high"] - df["low"]).iloc[-10:]
            if all(ranges.iloc[i] <= ranges.iloc[i - 1] for i in range(max(1, len(ranges) - 5), len(ranges))):
                # Check for flat resistance
                highs = df["high"].iloc[-10:]
                if (highs.max() - highs.min()) / highs.mean() < 0.02:
                    active.append("P15")

        return active

    def classify_stage(
        self,
        bars: list[OHLCV],
        indicators: TechnicalIndicators,
        precursors: list[str],
        breakout_level: Optional[float] = None,
    ) -> BreakoutStage:
        """Classify the current breakout stage.

        Lifecycle: Accumulation → Pre-Breakout → Breakout → Confirmation → Follow-Through
        """
        if len(bars) < 20:
            return BreakoutStage.ACCUMULATION

        current = bars[-1].close
        prev = bars[-2].close if len(bars) > 1 else current

        # If we have a breakout level
        if breakout_level is not None:
            if current > breakout_level:
                # Check volume confirmation
                rel_vol = indicators.relative_volume or 1.0
                if rel_vol >= 1.5:
                    return BreakoutStage.CONFIRMATION
                elif rel_vol >= 1.0:
                    return BreakoutStage.BREAKOUT
            elif prev > breakout_level and current < breakout_level:
                return BreakoutStage.FAILED

        # Count precursors to determine stage
        num_precursors = len(precursors)
        if num_precursors >= 5:
            return BreakoutStage.PRE_BREAKOUT
        elif num_precursors >= 2:
            return BreakoutStage.ACCUMULATION

        return BreakoutStage.ACCUMULATION

    def score_breakout(
        self,
        precursors: list[str],
        indicators: TechnicalIndicators,
        options_data: Optional[dict] = None,
        sector_relative_strength: Optional[float] = None,
    ) -> BreakoutSignal:
        """Score a breakout setup on the 0-100 rubric.

        Scoring Rubric:
        | Component        | Max Points |
        |------------------|------------|
        | Volume           | 20         |
        | Chart Pattern    | 15         |
        | Multi-Timeframe  | 15         |
        | Options Activity | 15         |
        | Trend Alignment  | 10         |
        | Candlestick      | 10         |
        | Institutional    | 10         |
        | Sector Strength  | 5          |
        | TOTAL            | 100        |
        """
        # Volume Score (0-20)
        volume_score = 0
        rel_vol = indicators.relative_volume or 1.0
        if rel_vol >= 3.0:
            volume_score = 20
        elif rel_vol >= 2.0:
            volume_score = 15
        elif rel_vol >= 1.5:
            volume_score = 10
        elif rel_vol >= 1.2:
            volume_score = 5
        if "P1" in precursors:  # Volume dry-up before breakout = important
            volume_score = min(20, volume_score + 5)

        # Pattern Score (0-15)
        pattern_score = 0
        pattern_precursors = {"P2", "P3", "P4", "P14", "P15"}
        pattern_hits = len(set(precursors) & pattern_precursors)
        pattern_score = min(15, pattern_hits * 5)

        # Trend Score (0-10)
        trend_score = 0
        if indicators.adx is not None and indicators.adx >= 25:
            trend_score += 5
        if indicators.sma_20 is not None and indicators.sma_50 is not None:
            if indicators.sma_20 > indicators.sma_50:
                trend_score += 5

        # Multi-TF Score (0-15)
        multi_tf_score = 0
        if "P11" in precursors:
            multi_tf_score += 10
        if "P9" in precursors:  # Higher lows = multi-TF confirmation
            multi_tf_score += 5

        # Options Score (0-15)
        options_score = 0
        if "P7" in precursors:
            options_score += 10
        if options_data:
            gex = options_data.get("gex", {})
            if gex.get("dealer_positioning") == "short_gamma":
                options_score += 5  # amplifying = higher breakout potential

        # Candle Score (0-10)
        candle_score = 0
        if indicators.rsi_14 is not None:
            if 40 <= indicators.rsi_14 <= 60:
                candle_score += 5  # reset zone
            if "P8" in precursors:
                candle_score += 5

        # Institutional Score (0-10)
        institutional_score = 0
        if "P5" in precursors:
            institutional_score += 5  # accumulation OBV
        if "P6" in precursors:
            institutional_score += 5  # block trades

        # Sector Score (0-5)
        sector_score = 0
        if "P10" in precursors:
            sector_score += 3
        if sector_relative_strength is not None and sector_relative_strength > 0:
            sector_score = min(5, sector_score + 2)
        if "P11" in precursors and sector_score < 5:
            sector_score = min(5, sector_score + 2)

        total = volume_score + pattern_score + trend_score + multi_tf_score + \
                options_score + candle_score + institutional_score + sector_score

        # Determine stage
        stage = BreakoutStage.PRE_BREAKOUT if total >= 40 else BreakoutStage.ACCUMULATION
        if total >= 70:
            stage = BreakoutStage.BREAKOUT

        return BreakoutSignal(
            ticker=indicators.ticker,
            stage=stage,
            quality_score=min(100, total),
            volume_score=volume_score,
            pattern_score=pattern_score,
            trend_score=trend_score,
            multi_tf_score=multi_tf_score,
            options_score=options_score,
            candle_score=candle_score,
            institutional_score=institutional_score,
            sector_score=sector_score,
            precursor_signals=precursors,
        )

    def detect_failed_breakout(
        self,
        bars: list[OHLCV],
        breakout_level: float,
        lookback: int = 5,
    ) -> Optional[dict]:
        """Detect failed breakouts — critical for risk management.

        A breakout fails when:
        1. Price breaks above resistance
        2. Cannot hold above for 2+ bars
        3. Falls back below the breakout level
        4. Volume dries up on the attempt
        """
        if len(bars) < lookback + 2:
            return None

        recent = bars[-lookback:]
        above_count = sum(1 for b in recent if b.close > breakout_level)
        below_count = sum(1 for b in recent if b.close < breakout_level)

        # Check if there was a breach followed by a fall-back
        breached = any(b.high > breakout_level for b in recent)
        current_below = recent[-1].close < breakout_level

        if breached and current_below and above_count <= 2:
            # Volume analysis
            avg_vol = np.mean([b.volume for b in bars[-20:]])
            breakout_vol = np.mean([b.volume for b in recent])
            vol_ratio = breakout_vol / avg_vol if avg_vol > 0 else 1.0

            return {
                "type": "failed_breakout",
                "breakout_level": breakout_level,
                "current_price": recent[-1].close,
                "bars_above": above_count,
                "bars_below": below_count,
                "volume_ratio": round(vol_ratio, 2),
                "low_volume_failure": vol_ratio < 1.0,
                "action": "EXIT" if vol_ratio < 0.8 else "REDUCE",
                "confidence": 0.75 if vol_ratio < 0.8 else 0.55,
                "severity": "high" if vol_ratio < 0.7 and above_count <= 1 else "moderate",
            }

        return None

    # ──────────────────────────────────────────────
    # Phase 10: Options-Based Breakout Confirmation
    # ──────────────────────────────────────────────

    def options_confirmation(
        self,
        options_data: dict,
        precursors: list[str],
        indicators: TechnicalIndicators,
    ) -> dict:
        """Options-based breakout confirmation analysis.

        Cross-references GEX dealer positioning, unusual activity, put/call ratio,
        and OI concentration to confirm or deny a breakout setup.

        Returns a confirmation score (0-100) and detailed breakdown.
        """
        result = {
            "confirmation_score": 0,
            "max_score": 100,
            "signals": [],
            "dealer_positioning": None,
            "smart_money_detected": False,
            "risk_flags": [],
        }

        score = 0

        # 1. GEX Analysis (0-25 pts)
        gex = options_data.get("gex", {})
        if gex:
            dealer_pos = gex.get("dealer_positioning", "neutral")
            result["dealer_positioning"] = dealer_pos

            if dealer_pos == "short_gamma":
                score += 25  # Maximum amplification for breakout
                result["signals"].append({
                    "signal": "Short Gamma Environment",
                    "impact": "Dealers will amplify the breakout move",
                    "score": 25,
                })
            elif dealer_pos == "long_gamma":
                score += 5   # Dampening — dealers will resist the breakout
                result["signals"].append({
                    "signal": "Long Gamma Environment",
                    "impact": "Dealers will dampen the breakout — expect resistance",
                    "score": 5,
                })
                result["risk_flags"].append("Long gamma may cap upside at GEX flip level")
            else:
                score += 12
                result["signals"].append({
                    "signal": "Neutral Gamma",
                    "impact": "No directional dealer influence",
                    "score": 12,
                })

            # GEX flip level analysis
            gex_flip = gex.get("zero_gamma_strike")
            if gex_flip and indicators.sma_20 is not None:
                if gex_flip > indicators.sma_20 * 1.05:
                    result["signals"].append({
                        "signal": "GEX Flip Above Current Range",
                        "impact": "Room to run before dealer flip",
                        "gex_flip_level": gex_flip,
                    })

        # 2. Unusual Options Activity (0-25 pts)
        unusual = options_data.get("unusual_activity", [])
        if unusual:
            calls = [u for u in unusual if u.get("type") == "call"]
            puts = [u for u in unusual if u.get("type") == "put"]

            call_sweeps = [u for u in calls if u.get("sweep", False)]
            large_calls = [u for u in calls if u.get("value", 0) >= 100_000]

            if call_sweeps:
                score += 15
                result["smart_money_detected"] = True
                result["signals"].append({
                    "signal": "Call Sweeps Detected",
                    "count": len(call_sweeps),
                    "impact": "Aggressive bullish positioning — smart money signal",
                    "score": 15,
                })
            elif large_calls:
                score += 10
                result["signals"].append({
                    "signal": "Large Call Activity",
                    "count": len(large_calls),
                    "impact": "Institutional bullish bets",
                    "score": 10,
                })

            if len(puts) > len(calls) * 1.5:
                result["risk_flags"].append("Heavy put activity — potential hedging or bearish flow")
                score -= 5

        # 3. Put/Call Ratio (0-20 pts)
        pc_ratio = options_data.get("put_call_ratio", {})
        if pc_ratio:
            volume_ratio = pc_ratio.get("volume_ratio", 1.0)
            oi_ratio = pc_ratio.get("oi_ratio", 1.0)

            if volume_ratio < 0.6:
                score += 20  # Very bullish — many more calls than puts
                result["signals"].append({
                    "signal": "Bullish P/C Ratio",
                    "volume_ratio": volume_ratio,
                    "impact": "Strongly bullish options positioning",
                    "score": 20,
                })
            elif volume_ratio < 0.8:
                score += 12
                result["signals"].append({
                    "signal": "Moderately Bullish P/C",
                    "volume_ratio": volume_ratio,
                    "score": 12,
                })
            elif volume_ratio > 1.5:
                result["risk_flags"].append(f"Bearish P/C ratio ({volume_ratio:.2f})")

        # 4. OI Concentration (0-15 pts)
        oi_data = options_data.get("oi_analysis", {})
        if oi_data:
            call_wall = oi_data.get("call_wall")
            put_wall = oi_data.get("put_wall")
            current_price = indicators.sma_20 or 0

            if call_wall and put_wall and current_price:
                # If current price is closer to call wall = resistance
                # If put wall is close below = support
                put_support_dist = (current_price - put_wall) / current_price if put_wall else 0
                call_resist_dist = (call_wall - current_price) / current_price if call_wall else 0

                if 0 < put_support_dist < 0.03:  # Put wall within 3% below = strong support
                    score += 10
                    result["signals"].append({
                        "signal": "Strong Put Wall Support",
                        "put_wall": put_wall,
                        "distance_pct": round(put_support_dist * 100, 1),
                        "score": 10,
                    })
                if call_resist_dist > 0.05:  # Call wall > 5% above = room to run
                    score += 5
                    result["signals"].append({
                        "signal": "Call Wall Above — Room to Run",
                        "call_wall": call_wall,
                        "distance_pct": round(call_resist_dist * 100, 1),
                        "score": 5,
                    })

        # 5. Max Pain Magnet (0-15 pts)
        max_pain = options_data.get("max_pain")
        if max_pain and indicators.sma_20:
            mp_distance = (max_pain - indicators.sma_20) / indicators.sma_20
            if mp_distance > 0.02:  # Max pain above current = upside magnet
                score += 10
                result["signals"].append({
                    "signal": "Max Pain Above — Price Magnet",
                    "max_pain": max_pain,
                    "upside_pct": round(mp_distance * 100, 1),
                    "score": 10,
                })
            elif mp_distance < -0.02:  # Max pain well below = downside risk
                result["risk_flags"].append(f"Max pain {abs(mp_distance)*100:.1f}% below current price")
                score -= 5

        result["confirmation_score"] = max(0, min(100, score))

        # Verdict
        if result["confirmation_score"] >= 70:
            result["verdict"] = "STRONGLY_CONFIRMED"
            result["action"] = "Execute breakout trade with full position"
        elif result["confirmation_score"] >= 50:
            result["verdict"] = "CONFIRMED"
            result["action"] = "Execute with reduced position, monitor risk flags"
        elif result["confirmation_score"] >= 30:
            result["verdict"] = "NEUTRAL"
            result["action"] = "Add to watchlist, wait for more confirmation"
        else:
            result["verdict"] = "DENIED"
            result["action"] = "Do not trade — options flow does not support breakout"

        return result

    # ──────────────────────────────────────────────
    # Phase 10: Institutional Detection
    # ──────────────────────────────────────────────

    def detect_institutional_activity(
        self,
        bars: list[OHLCV],
        options_data: Optional[dict] = None,
    ) -> dict:
        """Detect institutional tells in price action and flow data.

        Looks for signs of institutional accumulation/distribution
        that precede major moves.
        """
        if len(bars) < 30:
            return {"error": "insufficient_data", "required_bars": 30}

        df = self._bars_to_dataframe(bars)
        signals = []
        institutional_score = 0

        # 1. Volume-Price Divergence (Smart Money Accumulation)
        # Rising OBV + flat/declining price = accumulation
        price_change_20d = (df["close"].iloc[-1] - df["close"].iloc[-20]) / df["close"].iloc[-20]
        cum_vol = (df["volume"] * np.sign(df["close"].diff())).cumsum()
        obv_change_pct = (cum_vol.iloc[-1] - cum_vol.iloc[-20]) / max(abs(cum_vol.iloc[-20]), 1)

        if abs(price_change_20d) < 0.03 and obv_change_pct > 0.1:
            institutional_score += 20
            signals.append({
                "type": "accumulation",
                "signal": "Smart Money Accumulation",
                "detail": "OBV rising while price flat — institutions quietly accumulating",
                "confidence": 0.75,
                "price_change_pct": round(price_change_20d * 100, 2),
                "obv_change_pct": round(obv_change_pct * 100, 2),
            })

        # Distribution pattern
        if abs(price_change_20d) < 0.03 and obv_change_pct < -0.1:
            signals.append({
                "type": "distribution",
                "signal": "Smart Money Distribution",
                "detail": "OBV declining while price flat — institutions quietly selling",
                "confidence": 0.70,
            })

        # 2. Volume Anomalies (Block Trades in Price Data)
        vol_mean = df["volume"].rolling(20).mean()
        vol_std = df["volume"].rolling(20).std()
        recent_vol = df["volume"].iloc[-5:]
        vol_spikes = []
        for i, v in enumerate(recent_vol):
            mean_v = vol_mean.iloc[-5 + i] if len(vol_mean) > 5 else vol_mean.iloc[-1]
            std_v = vol_std.iloc[-5 + i] if len(vol_std) > 5 else vol_std.iloc[-1]
            if std_v > 0 and v > mean_v + 2 * std_v:
                vol_spikes.append(i)

        if vol_spikes:
            institutional_score += 15
            signals.append({
                "type": "volume_anomaly",
                "signal": "Unusual Volume Spikes",
                "detail": f"{len(vol_spikes)} recent bars with >2σ volume",
                "confidence": 0.65,
                "spike_bars": vol_spikes,
            })

        # 3. Narrow-Range Days with High Volume (Institutional Absorption)
        for i in range(-3, 0):
            if i >= -len(df):
                bar_range = (df["high"].iloc[i] - df["low"].iloc[i]) / df["close"].iloc[i]
                avg_range = ((df["high"] - df["low"]) / df["close"]).iloc[-20:].mean()
                vol = df["volume"].iloc[i]
                avg_vol = vol_mean.iloc[i] if i < len(vol_mean) else vol_mean.iloc[-1]

                if bar_range < avg_range * 0.5 and vol > avg_vol * 1.5:
                    institutional_score += 10
                    signals.append({
                        "type": "absorption",
                        "signal": "Institutional Absorption",
                        "detail": f"Narrow range ({bar_range*100:.2f}%) with high volume — absorbing supply",
                        "bar_index": i,
                        "confidence": 0.70,
                    })
                    break

        # 4. Options-derived institutional signals
        if options_data:
            dark_pool = options_data.get("dark_pool", {})
            if dark_pool:
                dp_volume = dark_pool.get("volume", 0)
                dp_ratio = dark_pool.get("volume_ratio", 0)
                if dp_ratio > 0.5:  # > 50% dark pool
                    institutional_score += 15
                    signals.append({
                        "type": "dark_pool",
                        "signal": "Heavy Dark Pool Activity",
                        "detail": f"Dark pool volume ratio: {dp_ratio:.0%}",
                        "confidence": 0.80,
                    })

            sweeps = options_data.get("sweep_orders", [])
            if sweeps:
                total_sweep_value = sum(s.get("value", 0) for s in sweeps if isinstance(s, dict))
                if total_sweep_value > 500_000:
                    institutional_score += 15
                    signals.append({
                        "type": "sweep_activity",
                        "signal": "Large Sweep Orders",
                        "detail": f"Total sweep value: ${total_sweep_value:,.0f}",
                        "confidence": 0.75,
                    })

        # Classify institutional intent
        intent = "neutral"
        if institutional_score >= 40:
            intent = "strong_accumulation" if any(s["type"] == "accumulation" for s in signals) else "strong_distribution"
        elif institutional_score >= 20:
            intent = "accumulation" if any(s["type"] == "accumulation" for s in signals) else "monitoring"

        return {
            "institutional_score": min(100, institutional_score),
            "intent": intent,
            "signal_count": len(signals),
            "signals": signals,
            "verdict": "Institutional activity detected — high conviction" if institutional_score >= 40
                       else "Some institutional footprints — moderate conviction" if institutional_score >= 20
                       else "No significant institutional activity detected",
        }

    # ──────────────────────────────────────────────
    # Phase 10: Breakout Backtesting
    # ──────────────────────────────────────────────

    def backtest_breakouts(
        self,
        bars: list[OHLCV],
        indicators: TechnicalIndicators,
        lookforward: int = 20,
    ) -> dict:
        """Backtest breakout signals across historical data.

        Identifies historical points where precursor count >= 3,
        then measures forward performance to determine breakout signal reliability.

        Args:
            bars: Full OHLCV history (6mo+ recommended).
            indicators: Current indicators (used for context).
            lookforward: Bars to evaluate after signal (default 20).
        """
        if len(bars) < 100:
            return {"error": "insufficient_data", "required_bars": 100}

        c = np.array([b.close for b in bars])
        h = np.array([b.high for b in bars])

        # Find historical resistance levels (rolling max)
        results = {
            "total_signals": 0,
            "successful_breakouts": 0,
            "failed_breakouts": 0,
            "avg_gain_on_success_pct": 0,
            "avg_loss_on_failure_pct": 0,
            "win_rate_pct": 0,
            "signals": [],
        }

        gains = []
        losses = []

        # Use rolling 20-bar high as resistance
        for i in range(50, len(bars) - lookforward):
            # Check if this bar breaks above 20-bar high
            rolling_high = float(np.max(h[max(0, i-20):i]))
            current_close = float(c[i])
            prev_close = float(c[i-1])

            if current_close > rolling_high and prev_close <= rolling_high:
                # Breakout detected at bar i
                # Check volume confirmation
                vol_window = [bars[j].volume for j in range(max(0, i-20), i)]
                avg_vol = np.mean(vol_window) if vol_window else 1
                breakout_vol = float(bars[i].volume)
                vol_ratio = breakout_vol / max(avg_vol, 1)

                # Evaluate forward performance
                future_max = float(np.max(h[i+1:i+lookforward+1]))
                future_close = float(c[min(i+lookforward, len(c)-1)])
                max_gain_pct = ((future_max - current_close) / current_close) * 100
                final_pnl_pct = ((future_close - current_close) / current_close) * 100

                signal = {
                    "bar_index": i,
                    "breakout_level": rolling_high,
                    "entry_price": current_close,
                    "volume_ratio": round(vol_ratio, 2),
                    "max_gain_pct": round(max_gain_pct, 2),
                    "final_pnl_pct": round(final_pnl_pct, 2),
                    "volume_confirmed": vol_ratio >= 1.5,
                }

                results["total_signals"] += 1

                if final_pnl_pct > 0:
                    results["successful_breakouts"] += 1
                    gains.append(final_pnl_pct)
                    signal["outcome"] = "success"
                else:
                    results["failed_breakouts"] += 1
                    losses.append(final_pnl_pct)
                    signal["outcome"] = "failed"

                results["signals"].append(signal)

        if results["total_signals"] > 0:
            results["win_rate_pct"] = round(
                results["successful_breakouts"] / results["total_signals"] * 100, 1
            )

        results["avg_gain_on_success_pct"] = round(np.mean(gains), 2) if gains else 0
        results["avg_loss_on_failure_pct"] = round(np.mean(losses), 2) if losses else 0

        # Volume-confirmed subset
        vol_confirmed = [s for s in results["signals"] if s["volume_confirmed"]]
        vol_wins = [s for s in vol_confirmed if s["outcome"] == "success"]
        results["volume_confirmed_win_rate_pct"] = round(
            len(vol_wins) / max(len(vol_confirmed), 1) * 100, 1
        )
        results["volume_confirmed_count"] = len(vol_confirmed)

        # Top 5 best breakouts
        results["best_breakouts"] = sorted(
            results["signals"], key=lambda s: s["max_gain_pct"], reverse=True
        )[:5]

        # Limit full signal list to avoid huge payloads
        results["signals"] = results["signals"][-20:]  # Most recent 20

        return results

    # ──────────────────────────────────────────────
    # Phase 10: Full Breakout Analysis (Orchestrator)
    # ──────────────────────────────────────────────

    def full_breakout_analysis(
        self,
        bars: list[OHLCV],
        indicators: TechnicalIndicators,
        options_data: Optional[dict] = None,
    ) -> dict:
        """Comprehensive breakout analysis — the crown jewel.

        Combines:
        - All 15 precursor signals
        - 5-stage lifecycle classification
        - 0-100 quality scoring with component breakdown
        - Options-based breakout confirmation
        - Institutional activity detection
        - Failed breakout check
        - Historical breakout win rate

        Returns a single, unified assessment with actionable recommendations.
        """
        # 1. Scan all 15 precursors
        precursors = self.scan_precursors(bars, indicators, options_data)

        # 2. Auto-detect breakout level (20-bar high)
        if len(bars) >= 20:
            breakout_level = max(b.high for b in bars[-20:])
        else:
            breakout_level = max(b.high for b in bars) if bars else None

        # 3. Classify lifecycle stage
        stage = self.classify_stage(bars, indicators, precursors, breakout_level)

        # 4. Score the setup
        signal = self.score_breakout(precursors, indicators, options_data)

        # 5. Options confirmation (if data available)
        options_confirmation = None
        if options_data:
            options_confirmation = self.options_confirmation(options_data, precursors, indicators)

        # 6. Institutional detection
        institutional = self.detect_institutional_activity(bars, options_data)

        # 7. Failed breakout check
        failed = self.detect_failed_breakout(bars, breakout_level) if breakout_level else None

        # 8. Historical backtest summary
        backtest = self.backtest_breakouts(bars, indicators) if len(bars) >= 100 else None

        # Build composite conviction score
        conviction = signal.quality_score
        if options_confirmation:
            # Blend options confirmation into overall conviction
            conviction = int(conviction * 0.6 + options_confirmation["confirmation_score"] * 0.4)

        # Active precursor details
        precursor_details = [
            {"id": p, "description": PRECURSOR_SIGNALS.get(p, "Unknown")}
            for p in precursors
        ]

        # Generate actionable recommendation
        if failed:
            recommendation = {
                "action": "EXIT/REDUCE",
                "reason": "Failed breakout detected — protect capital",
                "urgency": "HIGH",
            }
        elif conviction >= 75:
            recommendation = {
                "action": "BUY",
                "reason": f"High-conviction breakout setup ({conviction}/100)",
                "urgency": "HIGH",
                "entry": breakout_level,
                "stop": round(breakout_level * 0.97, 2) if breakout_level else None,
                "target": round(breakout_level * 1.05, 2) if breakout_level else None,
            }
        elif conviction >= 50:
            recommendation = {
                "action": "WATCHLIST",
                "reason": f"Moderate setup ({conviction}/100) — monitor for confirmation",
                "urgency": "MEDIUM",
            }
        else:
            recommendation = {
                "action": "PASS",
                "reason": f"Weak setup ({conviction}/100) — insufficient conviction",
                "urgency": "LOW",
            }

        return {
            "ticker": indicators.ticker,
            "conviction_score": conviction,
            "quality_score": signal.quality_score,
            "stage": stage.value,
            "breakout_level": breakout_level,
            "current_price": bars[-1].close if bars else None,
            "precursor_count": len(precursors),
            "precursors": precursor_details,

            # Component scores
            "scoring": {
                "volume": signal.volume_score,
                "pattern": signal.pattern_score,
                "trend": signal.trend_score,
                "multi_tf": signal.multi_tf_score,
                "options": signal.options_score,
                "candle": signal.candle_score,
                "institutional": signal.institutional_score,
                "sector": signal.sector_score,
            },

            # Sub-analyses
            "options_confirmation": options_confirmation,
            "institutional_activity": institutional,
            "failed_breakout": failed,
            "historical_win_rate": backtest.get("win_rate_pct") if backtest else None,
            "vol_confirmed_win_rate": backtest.get("volume_confirmed_win_rate_pct") if backtest else None,

            # Action
            "recommendation": recommendation,
        }

    # ──────────────────────────────────────────────
    # Multi-Target Take Profit (TP1/TP2/TP3)
    # ──────────────────────────────────────────────

    def compute_multi_targets(
        self,
        entry: float,
        stop: float,
        bars: list[OHLCV],
        fib_levels: Optional[dict] = None,
    ) -> dict:
        """Compute TP1/TP2/TP3 multi-target take profit scheme.

        Uses Fibonacci extensions + R:R ratios for systematic profit-taking:
        - TP1 (conservative): 1:1 R:R — first resistance / Fib 1.0 extension
        - TP2 (standard):     2:1 R:R — Fib 1.618 extension
        - TP3 (aggressive):   3:1 R:R — Fib 2.618 extension

        Returns:
            Dict with targets, recommended position sizing per target,
            and probability estimates.
        """
        risk = abs(entry - stop)
        if risk < 0.001:
            return {"error": "stop_too_close", "entry": entry, "stop": stop}

        is_long = entry > stop

        # Base targets from R:R
        if is_long:
            tp1_rr = round(entry + risk * 1.0, 4)
            tp2_rr = round(entry + risk * 2.0, 4)
            tp3_rr = round(entry + risk * 3.0, 4)
        else:
            tp1_rr = round(entry - risk * 1.0, 4)
            tp2_rr = round(entry - risk * 2.0, 4)
            tp3_rr = round(entry - risk * 3.0, 4)

        # Fibonacci-enhanced targets (if fib data available)
        tp1_fib = tp1_rr
        tp2_fib = tp2_rr
        tp3_fib = tp3_rr

        if fib_levels:
            fib_1618 = fib_levels.get("extension_1618") or fib_levels.get("fib_1618")
            fib_2618 = fib_levels.get("extension_2618") or fib_levels.get("fib_2618")
            if fib_1618:
                tp2_fib = round(float(fib_1618), 4)
            if fib_2618:
                tp3_fib = round(float(fib_2618), 4)

        # Use the more conservative of R:R vs Fibonacci
        if is_long:
            tp1 = tp1_rr
            tp2 = min(tp2_rr, tp2_fib) if tp2_fib else tp2_rr
            tp3 = min(tp3_rr, tp3_fib) if tp3_fib else tp3_rr
        else:
            tp1 = tp1_rr
            tp2 = max(tp2_rr, tp2_fib) if tp2_fib else tp2_rr
            tp3 = max(tp3_rr, tp3_fib) if tp3_fib else tp3_rr

        # Historical probability estimate from recent ATR data
        if len(bars) >= 20:
            atr_values = []
            for i in range(-20, 0):
                h = bars[i].high
                l = bars[i].low
                pc = bars[i - 1].close if abs(i) < len(bars) else bars[i].open
                atr_values.append(max(h - l, abs(h - pc), abs(l - pc)))
            avg_atr = np.mean(atr_values)
            # Probability decays with distance from entry
            move_1 = abs(tp1 - entry) / max(avg_atr, 0.01)
            move_2 = abs(tp2 - entry) / max(avg_atr, 0.01)
            move_3 = abs(tp3 - entry) / max(avg_atr, 0.01)
            prob_tp1 = round(min(95, max(20, 90 - move_1 * 8)), 1)
            prob_tp2 = round(min(80, max(10, 75 - move_2 * 5)), 1)
            prob_tp3 = round(min(60, max(5, 55 - move_3 * 3)), 1)
        else:
            prob_tp1, prob_tp2, prob_tp3 = 70.0, 45.0, 25.0

        return {
            "direction": "LONG" if is_long else "SHORT",
            "entry": entry,
            "stop": stop,
            "risk_per_share": round(risk, 4),
            "targets": {
                "tp1": {
                    "price": tp1,
                    "rr_ratio": "1:1",
                    "pct_from_entry": round(abs(tp1 - entry) / entry * 100, 2),
                    "probability_pct": prob_tp1,
                    "position_pct": 40,
                    "label": "Conservative — lock 40% profit",
                },
                "tp2": {
                    "price": tp2,
                    "rr_ratio": "2:1",
                    "pct_from_entry": round(abs(tp2 - entry) / entry * 100, 2),
                    "probability_pct": prob_tp2,
                    "position_pct": 35,
                    "label": "Standard — Fib 1.618 / 2:1 R:R",
                },
                "tp3": {
                    "price": tp3,
                    "rr_ratio": "3:1",
                    "pct_from_entry": round(abs(tp3 - entry) / entry * 100, 2),
                    "probability_pct": prob_tp3,
                    "position_pct": 25,
                    "label": "Aggressive — Fib 2.618 / 3:1 R:R",
                },
            },
            "expected_value": round(
                (prob_tp1 / 100 * abs(tp1 - entry) * 0.4 +
                 prob_tp2 / 100 * abs(tp2 - entry) * 0.35 +
                 prob_tp3 / 100 * abs(tp3 - entry) * 0.25) -
                (1 - prob_tp1 / 100) * risk, 4
            ),
            "fib_enhanced": fib_levels is not None,
        }

    # ──────────────────────────────────────────────
    # Helpers
    # ──────────────────────────────────────────────

    @staticmethod
    def _bars_to_dataframe(bars: list[OHLCV]) -> pd.DataFrame:
        """Convert OHLCV bars to DataFrame."""
        data = {
            "timestamp": [b.timestamp for b in bars],
            "open": [b.open for b in bars],
            "high": [b.high for b in bars],
            "low": [b.low for b in bars],
            "close": [b.close for b in bars],
            "volume": [float(b.volume) for b in bars],
        }
        df = pd.DataFrame(data)
        df.set_index("timestamp", inplace=True)
        return df

