"""
Bubby Vision — Technical Analysis Engine

Pure domain logic for computing technical indicators, support/resistance levels,
divergences, and multi-timeframe analysis. No LLM dependency.

Uses the `ta` library for indicator calculations on pandas DataFrames.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

import numpy as np
import pandas as pd
from ta.momentum import (
    RSIIndicator,
    StochasticOscillator,
    WilliamsRIndicator,
    ROCIndicator,
    TSIIndicator,
    UltimateOscillator,
)
from ta.trend import (
    ADXIndicator,
    AroonIndicator,
    CCIIndicator,
    EMAIndicator,
    IchimokuIndicator,
    MACD,
    PSARIndicator,
    SMAIndicator,
)
from ta.volatility import (
    AverageTrueRange,
    BollingerBands,
    DonchianChannel,
    KeltnerChannel,
)
from ta.volume import (
    ChaikinMoneyFlowIndicator,
    ForceIndexIndicator,
    MFIIndicator,
    OnBalanceVolumeIndicator,
    VolumeWeightedAveragePrice,
)

# finta for unique indicators not in ta library (KAMA, ZLEMA, HMA, FRAMA, PPO, AO, Pivots)
try:
    from finta import TA as FinTA
    _HAS_FINTA = True
except ImportError:
    _HAS_FINTA = False

from app.models import (
    OHLCV,
    SignalStrength,
    SupportResistance,
    TechnicalIndicators,
    TimeFrame,
)


class TAEngine:
    """Pure-Python technical analysis engine.

    Usage:
        engine = TAEngine()
        indicators = engine.compute_indicators(ohlcv_bars, timeframe="1d")
    """

    def compute_indicators(
        self,
        bars: list[OHLCV],
        timeframe: str = "1d",
        ticker: str = "",
    ) -> TechnicalIndicators:
        """Compute all technical indicators for a list of OHLCV bars.

        Args:
            bars: List of OHLCV bars (minimum 200 for reliable signals).
            timeframe: The timeframe of the bars.
            ticker: Ticker symbol for labeling.

        Returns:
            TechnicalIndicators with all computed values.
        """
        if len(bars) < 14:
            return TechnicalIndicators(
                ticker=ticker,
                timeframe=TimeFrame(timeframe) if timeframe in [t.value for t in TimeFrame] else TimeFrame.D1,
            )

        df = self._bars_to_dataframe(bars)

        # ── Trend Indicators ──
        sma_20 = SMAIndicator(df["close"], window=20).sma_indicator().iloc[-1] if len(df) >= 20 else None
        sma_50 = SMAIndicator(df["close"], window=50).sma_indicator().iloc[-1] if len(df) >= 50 else None
        sma_200 = SMAIndicator(df["close"], window=200).sma_indicator().iloc[-1] if len(df) >= 200 else None
        ema_8 = EMAIndicator(df["close"], window=8).ema_indicator().iloc[-1] if len(df) >= 8 else None
        ema_21 = EMAIndicator(df["close"], window=21).ema_indicator().iloc[-1] if len(df) >= 21 else None

        # ── MACD ──
        macd_obj = MACD(df["close"])
        macd_line = macd_obj.macd().iloc[-1] if len(df) >= 26 else None
        macd_signal = macd_obj.macd_signal().iloc[-1] if len(df) >= 26 else None
        macd_histogram = macd_obj.macd_diff().iloc[-1] if len(df) >= 26 else None

        # ── Momentum ──
        rsi_14 = RSIIndicator(df["close"], window=14).rsi().iloc[-1]

        stoch = StochasticOscillator(df["high"], df["low"], df["close"])
        stoch_k = stoch.stoch().iloc[-1] if len(df) >= 14 else None
        stoch_d = stoch.stoch_signal().iloc[-1] if len(df) >= 14 else None

        # ── Volatility ──
        atr_14 = AverageTrueRange(df["high"], df["low"], df["close"], window=14).average_true_range().iloc[-1]

        bb = BollingerBands(df["close"], window=20, window_dev=2)
        bb_upper = bb.bollinger_hband().iloc[-1] if len(df) >= 20 else None
        bb_middle = bb.bollinger_mavg().iloc[-1] if len(df) >= 20 else None
        bb_lower = bb.bollinger_lband().iloc[-1] if len(df) >= 20 else None
        bb_width = bb.bollinger_wband().iloc[-1] if len(df) >= 20 else None

        # ── Trend Strength ──
        adx = ADXIndicator(df["high"], df["low"], df["close"], window=14).adx().iloc[-1] if len(df) >= 28 else None

        # ── Volume ──
        obv = OnBalanceVolumeIndicator(df["close"], df["volume"]).on_balance_volume().iloc[-1]

        vwap = None
        if len(df) >= 1:
            try:
                vwap_indicator = VolumeWeightedAveragePrice(
                    df["high"], df["low"], df["close"], df["volume"]
                )
                vwap = vwap_indicator.volume_weighted_average_price().iloc[-1]
            except Exception:
                pass

        volume_sma_20 = df["volume"].rolling(20).mean().iloc[-1] if len(df) >= 20 else None
        current_volume = df["volume"].iloc[-1]
        relative_volume = (current_volume / volume_sma_20) if volume_sma_20 and volume_sma_20 > 0 else None

        # ── Extended Momentum ──
        williams_r = None
        if len(df) >= 14:
            williams_r = WilliamsRIndicator(df["high"], df["low"], df["close"], lbp=14).williams_r().iloc[-1]

        cci = None
        if len(df) >= 20:
            cci = CCIIndicator(df["high"], df["low"], df["close"], window=20).cci().iloc[-1]

        roc = None
        if len(df) >= 12:
            roc = ROCIndicator(df["close"], window=12).roc().iloc[-1]

        tsi = None
        if len(df) >= 40:
            tsi = TSIIndicator(df["close"], window_slow=25, window_fast=13).tsi().iloc[-1]

        ultimate_osc = None
        if len(df) >= 28:
            ultimate_osc = UltimateOscillator(
                df["high"], df["low"], df["close"],
                window1=7, window2=14, window3=28,
            ).ultimate_oscillator().iloc[-1]

        # ── Extended Volume ──
        mfi = None
        if len(df) >= 14:
            mfi = MFIIndicator(df["high"], df["low"], df["close"], df["volume"], window=14).money_flow_index().iloc[-1]

        cmf = None
        if len(df) >= 20:
            cmf = ChaikinMoneyFlowIndicator(df["high"], df["low"], df["close"], df["volume"], window=20).chaikin_money_flow().iloc[-1]

        force_index = None
        if len(df) >= 13:
            force_index = ForceIndexIndicator(df["close"], df["volume"], window=13).force_index().iloc[-1]

        # ── Extended Volatility (Channels) ──
        keltner_upper = keltner_lower = None
        if len(df) >= 20:
            kc = KeltnerChannel(df["high"], df["low"], df["close"], window=20)
            keltner_upper = kc.keltner_channel_hband().iloc[-1]
            keltner_lower = kc.keltner_channel_lband().iloc[-1]

        donchian_upper = donchian_lower = None
        if len(df) >= 20:
            dc = DonchianChannel(df["high"], df["low"], df["close"], window=20)
            donchian_upper = dc.donchian_channel_hband().iloc[-1]
            donchian_lower = dc.donchian_channel_lband().iloc[-1]

        # ── Extended Trend ──
        aroon_up = aroon_down = None
        if len(df) >= 25:
            aroon = AroonIndicator(df["close"], window=25)
            aroon_up = aroon.aroon_up().iloc[-1]
            aroon_down = aroon.aroon_down().iloc[-1]

        # ── Ichimoku Cloud (native ta library) ──
        ichimoku_a = ichimoku_b = ichimoku_base = None
        if len(df) >= 52:
            try:
                ichi = IchimokuIndicator(df["high"], df["low"], window1=9, window2=26, window3=52)
                ichimoku_a = ichi.ichimoku_a().iloc[-1]  # Senkou Span A
                ichimoku_b = ichi.ichimoku_b().iloc[-1]  # Senkou Span B
                ichimoku_base = ichi.ichimoku_base_line().iloc[-1]  # Kijun-sen
            except Exception:
                pass

        # ── Parabolic SAR (native ta library) ──
        psar = None
        if len(df) >= 14:
            try:
                psar_ind = PSARIndicator(df["high"], df["low"], df["close"])
                psar = psar_ind.psar().iloc[-1]
            except Exception:
                pass

        # ── Supertrend (manual — ATR × multiplier ± HL2) ──
        supertrend = None
        supertrend_direction = None
        if len(df) >= 14:
            try:
                st_len, st_mult = 10, 3.0
                atr_st = AverageTrueRange(df["high"], df["low"], df["close"], window=st_len).average_true_range()
                hl2 = (df["high"] + df["low"]) / 2
                upper_band = hl2 + st_mult * atr_st
                lower_band = hl2 - st_mult * atr_st
                st_dir = pd.Series(1, index=df.index)  # 1 = up, -1 = down
                st_val = pd.Series(np.nan, index=df.index)
                for i in range(st_len, len(df)):
                    if i == st_len:
                        st_dir.iloc[i] = 1
                        st_val.iloc[i] = lower_band.iloc[i]
                        continue
                    if st_dir.iloc[i - 1] == 1:
                        lower_band.iloc[i] = max(lower_band.iloc[i], lower_band.iloc[i - 1]) if df["close"].iloc[i - 1] > lower_band.iloc[i - 1] else lower_band.iloc[i]
                        if df["close"].iloc[i] < lower_band.iloc[i]:
                            st_dir.iloc[i] = -1
                            st_val.iloc[i] = upper_band.iloc[i]
                        else:
                            st_dir.iloc[i] = 1
                            st_val.iloc[i] = lower_band.iloc[i]
                    else:
                        upper_band.iloc[i] = min(upper_band.iloc[i], upper_band.iloc[i - 1]) if df["close"].iloc[i - 1] < upper_band.iloc[i - 1] else upper_band.iloc[i]
                        if df["close"].iloc[i] > upper_band.iloc[i]:
                            st_dir.iloc[i] = 1
                            st_val.iloc[i] = lower_band.iloc[i]
                        else:
                            st_dir.iloc[i] = -1
                            st_val.iloc[i] = upper_band.iloc[i]
                supertrend = st_val.iloc[-1]
                supertrend_direction = "up" if st_dir.iloc[-1] == 1 else "down"
            except Exception:
                pass

        # ── Squeeze (BB inside KC = squeeze is on — no external dep needed) ──
        squeeze_on = None
        if len(df) >= 20 and bb_upper is not None and keltner_upper is not None:
            try:
                squeeze_on = (bb_upper < keltner_upper) and (bb_lower > keltner_lower)  # type: ignore[operator]
            except Exception:
                pass

        # ── Finta unique indicators ──
        kama_val = zlema_val = hma_val = frama_val = None
        ppo_val = ppo_signal_val = ao_val = None
        pivot_val = pivot_r1 = pivot_s1 = None
        if _HAS_FINTA and len(df) >= 30:
            try:
                finta_df = df.rename(columns={"open": "open", "high": "high", "low": "low", "close": "close", "volume": "volume"})
                # KAMA — Kaufman Adaptive MA (adapts to noise)
                kama_ser = FinTA.KAMA(finta_df)
                if kama_ser is not None and len(kama_ser) > 0:
                    kama_val = float(kama_ser.iloc[-1]) if not pd.isna(kama_ser.iloc[-1]) else None
                # ZLEMA — Zero-Lag EMA
                zlema_ser = FinTA.ZLEMA(finta_df)
                if zlema_ser is not None and len(zlema_ser) > 0:
                    zlema_val = float(zlema_ser.iloc[-1]) if not pd.isna(zlema_ser.iloc[-1]) else None
                # HMA — Hull MA (fast, smooth)
                hma_ser = FinTA.HMA(finta_df)
                if hma_ser is not None and len(hma_ser) > 0:
                    hma_val = float(hma_ser.iloc[-1]) if not pd.isna(hma_ser.iloc[-1]) else None
                # FRAMA — Fractal Adaptive MA
                try:
                    frama_ser = FinTA.FRAMA(finta_df)
                    if frama_ser is not None and len(frama_ser) > 0:
                        frama_val = float(frama_ser.iloc[-1]) if not pd.isna(frama_ser.iloc[-1]) else None
                except Exception:
                    pass  # FRAMA can fail on short datasets
                # PPO — Percentage Price Oscillator
                ppo_ser = FinTA.PPO(finta_df)
                if ppo_ser is not None and len(ppo_ser) > 0:
                    if isinstance(ppo_ser, pd.DataFrame):
                        ppo_val = float(ppo_ser.iloc[-1, 0]) if not pd.isna(ppo_ser.iloc[-1, 0]) else None
                        if ppo_ser.shape[1] > 1:
                            ppo_signal_val = float(ppo_ser.iloc[-1, 1]) if not pd.isna(ppo_ser.iloc[-1, 1]) else None
                    else:
                        ppo_val = float(ppo_ser.iloc[-1]) if not pd.isna(ppo_ser.iloc[-1]) else None
                # AO — Awesome Oscillator (momentum)
                ao_ser = FinTA.AO(finta_df)
                if ao_ser is not None and len(ao_ser) > 0:
                    ao_val = float(ao_ser.iloc[-1]) if not pd.isna(ao_ser.iloc[-1]) else None
                # Pivot Points (classic)
                pivot_ser = FinTA.PIVOT(finta_df)
                if pivot_ser is not None and len(pivot_ser) > 0:
                    last_pivot = pivot_ser.iloc[-1]
                    if isinstance(last_pivot, pd.Series):
                        pivot_val = float(last_pivot.get("pivot", last_pivot.iloc[0])) if not pd.isna(last_pivot.iloc[0]) else None
                        if len(last_pivot) >= 3:
                            pivot_r1 = float(last_pivot.iloc[1]) if not pd.isna(last_pivot.iloc[1]) else None
                            pivot_s1 = float(last_pivot.iloc[2]) if not pd.isna(last_pivot.iloc[2]) else None
            except Exception:
                pass  # finta indicators are optional — never crash

        # ── Support/Resistance ──
        support_levels = self._find_support_resistance(df, level_type="support")
        resistance_levels = self._find_support_resistance(df, level_type="resistance")

        # ── Overall Signal ──
        overall_signal = self._compute_overall_signal(
            rsi_14=rsi_14,
            macd_histogram=macd_histogram,
            sma_20=sma_20,
            sma_50=sma_50,
            current_price=df["close"].iloc[-1],
            adx=adx,
        )

        tf = TimeFrame(timeframe) if timeframe in [t.value for t in TimeFrame] else TimeFrame.D1

        return TechnicalIndicators(
            ticker=ticker,
            timeframe=tf,
            rsi_14=self._safe_round(rsi_14),
            macd_line=self._safe_round(macd_line, 4),
            macd_signal=self._safe_round(macd_signal, 4),
            macd_histogram=self._safe_round(macd_histogram, 4),
            sma_20=self._safe_round(sma_20),
            sma_50=self._safe_round(sma_50),
            sma_200=self._safe_round(sma_200),
            ema_8=self._safe_round(ema_8),
            ema_21=self._safe_round(ema_21),
            atr_14=self._safe_round(atr_14),
            bb_upper=self._safe_round(bb_upper),
            bb_middle=self._safe_round(bb_middle),
            bb_lower=self._safe_round(bb_lower),
            bb_width=self._safe_round(bb_width, 4),
            stoch_k=self._safe_round(stoch_k),
            stoch_d=self._safe_round(stoch_d),
            adx=self._safe_round(adx),
            obv=self._safe_round(obv, 0),
            vwap=self._safe_round(vwap),
            volume_sma_20=self._safe_round(volume_sma_20, 0),
            relative_volume=self._safe_round(relative_volume),
            # Extended indicators
            williams_r=self._safe_round(williams_r),
            cci=self._safe_round(cci),
            mfi=self._safe_round(mfi),
            cmf=self._safe_round(cmf, 4),
            roc=self._safe_round(roc, 4),
            tsi=self._safe_round(tsi),
            force_index=self._safe_round(force_index, 0),
            ultimate_osc=self._safe_round(ultimate_osc),
            keltner_upper=self._safe_round(keltner_upper),
            keltner_lower=self._safe_round(keltner_lower),
            donchian_upper=self._safe_round(donchian_upper),
            donchian_lower=self._safe_round(donchian_lower),
            aroon_up=self._safe_round(aroon_up),
            aroon_down=self._safe_round(aroon_down),
            ichimoku_a=self._safe_round(ichimoku_a),
            ichimoku_b=self._safe_round(ichimoku_b),
            ichimoku_base=self._safe_round(ichimoku_base),
            psar=self._safe_round(psar),
            supertrend=self._safe_round(supertrend),
            supertrend_direction=supertrend_direction,
            squeeze_on=squeeze_on,
            # Finta unique indicators
            kama=self._safe_round(kama_val),
            zlema=self._safe_round(zlema_val),
            hma=self._safe_round(hma_val),
            frama=self._safe_round(frama_val),
            ppo=self._safe_round(ppo_val, 4),
            ppo_signal=self._safe_round(ppo_signal_val, 4),
            awesome_oscillator=self._safe_round(ao_val, 4),
            pivot=self._safe_round(pivot_val),
            pivot_r1=self._safe_round(pivot_r1),
            pivot_s1=self._safe_round(pivot_s1),
            overall_signal=overall_signal,
            support_levels=support_levels,
            resistance_levels=resistance_levels,
        )

    def detect_divergences(self, bars: list[OHLCV], lookback: int = 20) -> list[dict]:
        """Detect RSI and MACD divergences.

        Returns list of divergence signals with type and confidence.
        """
        if len(bars) < max(lookback + 14, 30):
            return []

        df = self._bars_to_dataframe(bars)
        rsi = RSIIndicator(df["close"], window=14).rsi()
        macd = MACD(df["close"]).macd()

        divergences = []

        # Check last `lookback` bars for price vs RSI divergence
        recent = df.iloc[-lookback:]
        recent_rsi = rsi.iloc[-lookback:]

        # Bullish divergence: price makes lower low, RSI makes higher low
        price_lows = self._find_local_extrema(recent["close"], mode="min")
        rsi_lows = self._find_local_extrema(recent_rsi, mode="min")

        if len(price_lows) >= 2 and len(rsi_lows) >= 2:
            if price_lows[-1][1] < price_lows[-2][1] and rsi_lows[-1][1] > rsi_lows[-2][1]:
                divergences.append({
                    "type": "bullish_divergence",
                    "indicator": "RSI",
                    "confidence": 0.72,
                    "description": f"Price made lower low but RSI made higher low (RSI: {rsi_lows[-1][1]:.1f})",
                })

        # Bearish divergence: price makes higher high, RSI makes lower high
        price_highs = self._find_local_extrema(recent["close"], mode="max")
        rsi_highs = self._find_local_extrema(recent_rsi, mode="max")

        if len(price_highs) >= 2 and len(rsi_highs) >= 2:
            if price_highs[-1][1] > price_highs[-2][1] and rsi_highs[-1][1] < rsi_highs[-2][1]:
                divergences.append({
                    "type": "bearish_divergence",
                    "indicator": "RSI",
                    "confidence": 0.70,
                    "description": f"Price made higher high but RSI made lower high (RSI: {rsi_highs[-1][1]:.1f})",
                })

        return divergences

    def compute_multi_timeframe_score(
        self,
        signals: dict[str, TechnicalIndicators],
    ) -> dict:
        """Compute multi-timeframe confluence score.

        Args:
            signals: Dict of timeframe -> TechnicalIndicators
                     e.g. {"1h": indicators, "4h": indicators, "1d": indicators}

        Returns:
            Dict with confluence_score (0-5), aligned_direction, and breakdown.
        """
        bullish_count = 0
        bearish_count = 0
        breakdown = {}

        for tf, indicators in signals.items():
            signal = indicators.overall_signal
            if signal in (SignalStrength.BUY, SignalStrength.STRONG_BUY):
                bullish_count += 1
                breakdown[tf] = "bullish"
            elif signal in (SignalStrength.SELL, SignalStrength.STRONG_SELL):
                bearish_count += 1
                breakdown[tf] = "bearish"
            else:
                breakdown[tf] = "neutral"

        total = len(signals)
        if bullish_count > bearish_count:
            direction = "bullish"
            score = min(5, bullish_count)
        elif bearish_count > bullish_count:
            direction = "bearish"
            score = min(5, bearish_count)
        else:
            direction = "neutral"
            score = 0

        return {
            "confluence_score": score,
            "max_score": total,
            "aligned_direction": direction,
            "breakdown": breakdown,
            "alignment_pct": round(max(bullish_count, bearish_count) / total * 100, 1) if total > 0 else 0,
        }

    # ──────────────────────────────────────────────
    # Standalone Indicator Helpers
    # ──────────────────────────────────────────────

    @staticmethod
    def _sma(closes: list[float], period: int) -> list[Optional[float]]:
        """Simple Moving Average over a list of close prices.

        Returns a list the same length as closes. Positions before
        `period` are None.
        """
        result: list[Optional[float]] = [None] * len(closes)
        for i in range(period - 1, len(closes)):
            window = closes[i - period + 1: i + 1]
            result[i] = sum(window) / period
        return result

    @staticmethod
    def _ema(closes: list[float], period: int) -> list[Optional[float]]:
        """Exponential Moving Average over a list of close prices.

        Returns a list the same length as closes. Positions before
        `period - 1` are None.
        """
        result: list[Optional[float]] = [None] * len(closes)
        if len(closes) < period:
            return result

        # Seed EMA with SMA of first `period` values
        sma_seed = sum(closes[:period]) / period
        result[period - 1] = sma_seed

        multiplier = 2 / (period + 1)
        for i in range(period, len(closes)):
            result[i] = (closes[i] - result[i - 1]) * multiplier + result[i - 1]
        return result

    @staticmethod
    def _rsi(closes: list[float], period: int = 14) -> list[Optional[float]]:
        """Relative Strength Index over a list of close prices.

        Returns a list the same length as closes. Positions before
        `period` are None.
        """
        result: list[Optional[float]] = [None] * len(closes)
        if len(closes) < period + 1:
            return result

        gains = []
        losses = []
        for i in range(1, len(closes)):
            diff = closes[i] - closes[i - 1]
            gains.append(max(0, diff))
            losses.append(max(0, -diff))

        # Initial average
        avg_gain = sum(gains[:period]) / period
        avg_loss = sum(losses[:period]) / period

        if avg_loss == 0:
            result[period] = 100.0
        else:
            rs = avg_gain / avg_loss
            result[period] = round(100 - 100 / (1 + rs), 4)

        # Smoothed averages
        for i in range(period, len(gains)):
            avg_gain = (avg_gain * (period - 1) + gains[i]) / period
            avg_loss = (avg_loss * (period - 1) + losses[i]) / period

            if avg_loss == 0:
                result[i + 1] = 100.0
            else:
                rs = avg_gain / avg_loss
                result[i + 1] = round(100 - 100 / (1 + rs), 4)

        return result

    def detect_support_resistance(self, bars: list[OHLCV]) -> SupportResistance:
        """Detect support and resistance levels from OHLCV bars.

        Returns a SupportResistance object with support and resistance lists.
        """
        df = self._bars_to_dataframe(bars)
        support = self._find_support_resistance(df, level_type="support")
        resistance = self._find_support_resistance(df, level_type="resistance")
        return type("SR", (), {"support": support, "resistance": resistance})()

    # ──────────────────────────────────────────────
    # Private Helpers
    # ──────────────────────────────────────────────

    @staticmethod
    def _bars_to_dataframe(bars: list[OHLCV]) -> pd.DataFrame:
        """Convert OHLCV bars to a pandas DataFrame."""
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

    @staticmethod
    def _safe_round(value, decimals: int = 2):
        """Safely round a value, handling None and NaN."""
        if value is None:
            return None
        try:
            if np.isnan(value) or np.isinf(value):
                return None
            return round(float(value), decimals)
        except (TypeError, ValueError):
            return None

    def _find_support_resistance(
        self,
        df: pd.DataFrame,
        level_type: str = "support",
        window: int = 10,
        num_levels: int = 3,
    ) -> list[SupportResistance]:
        """Find support or resistance levels using pivot point detection."""
        if len(df) < window * 2:
            return []

        col = "low" if level_type == "support" else "high"
        levels = []

        for i in range(window, len(df) - window):
            if level_type == "support":
                is_pivot = all(df[col].iloc[i] <= df[col].iloc[i - j] for j in range(1, window + 1)) and \
                           all(df[col].iloc[i] <= df[col].iloc[i + j] for j in range(1, min(window + 1, len(df) - i)))
            else:
                is_pivot = all(df[col].iloc[i] >= df[col].iloc[i - j] for j in range(1, window + 1)) and \
                           all(df[col].iloc[i] >= df[col].iloc[i + j] for j in range(1, min(window + 1, len(df) - i)))

            if is_pivot:
                levels.append(df[col].iloc[i])

        if not levels:
            return []

        # Cluster nearby levels
        clustered = self._cluster_levels(levels, df["close"].iloc[-1])

        result = []
        for price, strength in clustered[:num_levels]:
            result.append(
                SupportResistance(
                    price=round(price, 2),
                    strength=min(5, strength),
                    level_type=level_type,
                )
            )
        return result

    @staticmethod
    def _cluster_levels(levels: list[float], current_price: float, tolerance: float = 0.02) -> list[tuple[float, int]]:
        """Cluster nearby price levels and count touches."""
        if not levels:
            return []

        sorted_levels = sorted(levels)
        clusters: list[list[float]] = [[sorted_levels[0]]]

        for level in sorted_levels[1:]:
            if abs(level - clusters[-1][-1]) / clusters[-1][-1] < tolerance:
                clusters[-1].append(level)
            else:
                clusters.append([level])

        # Return (avg_price, touch_count) sorted by distance from current price
        result = [(np.mean(c), len(c)) for c in clusters]
        result.sort(key=lambda x: abs(x[0] - current_price))
        return result

    @staticmethod
    def _compute_overall_signal(
        rsi_14: Optional[float],
        macd_histogram: Optional[float],
        sma_20: Optional[float],
        sma_50: Optional[float],
        current_price: float,
        adx: Optional[float],
    ) -> SignalStrength:
        """Compute an overall signal from multiple indicators."""
        score = 0  # -4 to +4

        # RSI
        if rsi_14 is not None:
            if rsi_14 < 30:
                score += 1  # oversold = bullish
            elif rsi_14 > 70:
                score -= 1  # overbought = bearish

        # MACD
        if macd_histogram is not None:
            if macd_histogram > 0:
                score += 1
            elif macd_histogram < 0:
                score -= 1

        # Price vs SMAs
        if sma_20 is not None:
            if current_price > sma_20:
                score += 1
            else:
                score -= 1

        if sma_50 is not None:
            if current_price > sma_50:
                score += 1
            else:
                score -= 1

        if score >= 3:
            return SignalStrength.STRONG_BUY
        elif score >= 1:
            return SignalStrength.BUY
        elif score <= -3:
            return SignalStrength.STRONG_SELL
        elif score <= -1:
            return SignalStrength.SELL
        else:
            return SignalStrength.NEUTRAL

    @staticmethod
    def _find_local_extrema(series: pd.Series, mode: str = "min", order: int = 5) -> list[tuple[int, float]]:
        """Find local minima or maxima in a series."""
        extrema = []
        values = series.values
        for i in range(order, len(values) - order):
            if mode == "min":
                if all(values[i] <= values[i - j] for j in range(1, order + 1)) and \
                   all(values[i] <= values[i + j] for j in range(1, order + 1)):
                    extrema.append((i, float(values[i])))
            else:
                if all(values[i] >= values[i - j] for j in range(1, order + 1)) and \
                   all(values[i] >= values[i + j] for j in range(1, order + 1)):
                    extrema.append((i, float(values[i])))
        return extrema

    # ──────────────────────────────────────────────
    # Anchored VWAP
    # ──────────────────────────────────────────────

    def compute_anchored_vwap(
        self,
        bars: list[OHLCV],
        anchor_index: int = 0,
    ) -> dict:
        """Compute Anchored VWAP from a specific bar forward.

        VWAP = Σ(typical_price × volume) / Σ(volume)
        Bands = VWAP ± k × σ  where σ = std(typical_price − VWAP)

        Args:
            bars: OHLCV bar list.
            anchor_index: Bar index to anchor from (0 = start of data).

        Returns:
            Dict with vwap values, bands, and current deviation.
        """
        if not bars or anchor_index >= len(bars):
            return {"error": "insufficient_data"}

        anchored = bars[anchor_index:]
        n = len(anchored)

        typical = [(b.high + b.low + b.close) / 3 for b in anchored]
        volumes = [b.volume for b in anchored]

        # Cumulative VWAP
        cum_tp_vol = 0.0
        cum_vol = 0.0
        vwap_values: list[float] = []
        deviations: list[float] = []

        for i in range(n):
            cum_tp_vol += typical[i] * volumes[i]
            cum_vol += volumes[i]
            vwap_i = cum_tp_vol / max(cum_vol, 1)
            vwap_values.append(round(vwap_i, 4))
            deviations.append(typical[i] - vwap_i)

        # Standard deviation bands
        import math
        if n > 1:
            variance = sum(d ** 2 for d in deviations) / n
            std_dev = math.sqrt(variance)
        else:
            std_dev = 0.0

        current_vwap = vwap_values[-1]
        current_price = anchored[-1].close

        # Bands at current point
        upper_1 = round(current_vwap + std_dev, 4)
        lower_1 = round(current_vwap - std_dev, 4)
        upper_2 = round(current_vwap + 2 * std_dev, 4)
        lower_2 = round(current_vwap - 2 * std_dev, 4)

        # Deviation from VWAP as percentage
        dev_pct = ((current_price - current_vwap) / max(current_vwap, 0.01)) * 100

        return {
            "anchor_index": anchor_index,
            "anchor_date": str(anchored[0].timestamp) if hasattr(anchored[0], "timestamp") else None,
            "bars_computed": n,
            "current_vwap": current_vwap,
            "current_price": round(current_price, 4),
            "deviation_pct": round(dev_pct, 2),
            "bands": {
                "upper_2sd": upper_2,
                "upper_1sd": upper_1,
                "vwap": current_vwap,
                "lower_1sd": lower_1,
                "lower_2sd": lower_2,
            },
            "std_dev": round(std_dev, 4),
            "price_position": (
                "above_2sd" if current_price > upper_2 else
                "above_1sd" if current_price > upper_1 else
                "at_vwap" if abs(dev_pct) < 0.5 else
                "below_1sd" if current_price < lower_1 else
                "below_2sd" if current_price < lower_2 else
                "between_bands"
            ),
            "vwap_series": vwap_values[-20:],  # Last 20 for charting
        }

    def compute_volume_profile(
        self,
        bars: list[OHLCV],
        num_bins: int = 50,
    ) -> dict:
        """Compute Volume Profile — price-at-volume histogram.

        Buckets the price range into ``num_bins`` levels, sums volume at each
        level, and identifies:
        - **POC** (Point of Control): Price level with highest volume
        - **Value Area High / Low**: Range containing 70% of total volume

        Args:
            bars: OHLCV bar list.
            num_bins: Number of price level buckets (default 50).

        Returns:
            Dict with profile, POC, value_area, and high-volume nodes.
        """
        if len(bars) < 10:
            return {"error": "insufficient_data", "required_bars": 10}

        import numpy as np

        highs = [b.high for b in bars]
        lows = [b.low for b in bars]
        closes = [b.close for b in bars]
        volumes = [b.volume for b in bars]

        price_min = min(lows)
        price_max = max(highs)
        price_range = price_max - price_min

        if price_range <= 0:
            return {"error": "zero_price_range"}

        bin_size = price_range / num_bins
        profile = [0.0] * num_bins
        bin_prices = [round(price_min + (i + 0.5) * bin_size, 4) for i in range(num_bins)]

        # Distribute each bar's volume across the bins it covers
        for i, bar in enumerate(bars):
            bar_low_bin = max(0, int((bar.low - price_min) / bin_size))
            bar_high_bin = min(num_bins - 1, int((bar.high - price_min) / bin_size))
            bins_covered = max(1, bar_high_bin - bar_low_bin + 1)
            vol_per_bin = volumes[i] / bins_covered
            for b in range(bar_low_bin, bar_high_bin + 1):
                if b < num_bins:
                    profile[b] += vol_per_bin

        total_volume = sum(profile)
        if total_volume <= 0:
            return {"error": "no_volume_data"}

        # POC: bin with highest volume
        poc_idx = int(np.argmax(profile))
        poc_price = bin_prices[poc_idx]
        poc_volume = profile[poc_idx]

        # Value Area: 70% of total volume centered on POC
        target_volume = total_volume * 0.70
        va_volume = profile[poc_idx]
        va_low_idx = poc_idx
        va_high_idx = poc_idx

        while va_volume < target_volume and (va_low_idx > 0 or va_high_idx < num_bins - 1):
            expand_low = profile[va_low_idx - 1] if va_low_idx > 0 else 0
            expand_high = profile[va_high_idx + 1] if va_high_idx < num_bins - 1 else 0

            if expand_low >= expand_high and va_low_idx > 0:
                va_low_idx -= 1
                va_volume += profile[va_low_idx]
            elif va_high_idx < num_bins - 1:
                va_high_idx += 1
                va_volume += profile[va_high_idx]
            else:
                va_low_idx -= 1
                va_volume += profile[va_low_idx]

        # High-volume nodes (bins above 80th percentile)
        threshold = float(np.percentile(profile, 80))
        hvn = [
            {"price": bin_prices[i], "volume": round(profile[i]), "pct_of_total": round(profile[i] / total_volume * 100, 1)}
            for i in range(num_bins) if profile[i] >= threshold
        ]

        # Low-volume nodes (bins below 20th percentile, excluding zeros)
        non_zero = [v for v in profile if v > 0]
        lvn_threshold = float(np.percentile(non_zero, 20)) if non_zero else 0
        lvn = [
            {"price": bin_prices[i], "volume": round(profile[i])}
            for i in range(num_bins) if 0 < profile[i] <= lvn_threshold
        ]

        return {
            "bars_analyzed": len(bars),
            "num_bins": num_bins,
            "price_range": {"min": round(price_min, 4), "max": round(price_max, 4)},
            "poc": {"price": poc_price, "volume": round(poc_volume), "pct_of_total": round(poc_volume / total_volume * 100, 1)},
            "value_area": {
                "high": bin_prices[va_high_idx],
                "low": bin_prices[va_low_idx],
                "volume_pct": round(va_volume / total_volume * 100, 1),
            },
            "high_volume_nodes": hvn[:10],
            "low_volume_nodes": lvn[:10],
            "current_price": round(float(closes[-1]), 4),
            "price_vs_poc": "above" if closes[-1] > poc_price else "below" if closes[-1] < poc_price else "at_poc",
            "profile": [
                {"price": bin_prices[i], "volume": round(profile[i])}
                for i in range(num_bins) if profile[i] > 0
            ],
        }

    def detect_consolidation_zones(
        self,
        bars: list[OHLCV],
        atr_multiplier: float = 0.5,
        min_bars: int = 8,
    ) -> dict:
        """Detect price consolidation zones (tight ranges).

        A consolidation zone is where price stays within ``ATR × atr_multiplier``
        for at least ``min_bars`` consecutive bars.

        Args:
            bars: OHLCV bar list.
            atr_multiplier: Range threshold as ATR fraction (default 0.5).
            min_bars: Minimum bars to qualify as consolidation (default 8).

        Returns:
            Dict with detected zones, each containing boundaries and duration.
        """
        if len(bars) < max(min_bars + 14, 30):
            return {"error": "insufficient_data", "required_bars": max(min_bars + 14, 30)}

        # Compute ATR(14)
        atr_values = []
        for i in range(1, len(bars)):
            tr = max(
                bars[i].high - bars[i].low,
                abs(bars[i].high - bars[i - 1].close),
                abs(bars[i].low - bars[i - 1].close),
            )
            atr_values.append(tr)

        if len(atr_values) < 14:
            return {"error": "insufficient_data_for_atr"}

        # Simple moving ATR(14)
        atr_14 = sum(atr_values[-14:]) / 14
        threshold = atr_14 * atr_multiplier

        zones = []
        zone_start = None
        zone_high = 0.0
        zone_low = float("inf")

        for i in range(len(bars)):
            if zone_start is None:
                zone_start = i
                zone_high = bars[i].high
                zone_low = bars[i].low
            else:
                new_high = max(zone_high, bars[i].high)
                new_low = min(zone_low, bars[i].low)

                if new_high - new_low <= threshold:
                    zone_high = new_high
                    zone_low = new_low
                else:
                    # Check if current zone qualifies
                    duration = i - zone_start
                    if duration >= min_bars:
                        zones.append({
                            "start_bar": zone_start,
                            "end_bar": i - 1,
                            "duration_bars": duration,
                            "high": round(zone_high, 4),
                            "low": round(zone_low, 4),
                            "mid": round((zone_high + zone_low) / 2, 4),
                            "range_pct": round((zone_high - zone_low) / max(zone_low, 0.01) * 100, 2),
                        })
                    # Reset
                    zone_start = i
                    zone_high = bars[i].high
                    zone_low = bars[i].low

        # Check final zone
        if zone_start is not None:
            duration = len(bars) - zone_start
            if duration >= min_bars:
                zones.append({
                    "start_bar": zone_start,
                    "end_bar": len(bars) - 1,
                    "duration_bars": duration,
                    "high": round(zone_high, 4),
                    "low": round(zone_low, 4),
                    "mid": round((zone_high + zone_low) / 2, 4),
                    "range_pct": round((zone_high - zone_low) / max(zone_low, 0.01) * 100, 2),
                    "active": True,
                })

        current_price = float(bars[-1].close)

        return {
            "zones_found": len(zones),
            "atr_14": round(atr_14, 4),
            "threshold": round(threshold, 4),
            "current_price": round(current_price, 4),
            "in_consolidation": any(z.get("active") for z in zones),
            "zones": zones,
        }

    def detect_liquidity_zones(
        self,
        bars: list[OHLCV],
        num_bins: int = 30,
        threshold_pct: float = 80,
    ) -> dict:
        """Detect liquidity zones — high-volume price nodes.

        These are price levels where significant volume has traded,
        acting as magnets for future price action (support/resistance).

        Args:
            bars: OHLCV bar list.
            num_bins: Number of price buckets (default 30).
            threshold_pct: Volume percentile to qualify as liquidity zone (default 80).

        Returns:
            Dict with liquidity zones, their strength, and proximity to current price.
        """
        if len(bars) < 20:
            return {"error": "insufficient_data", "required_bars": 20}

        import numpy as np

        price_min = min(b.low for b in bars)
        price_max = max(b.high for b in bars)
        price_range = price_max - price_min

        if price_range <= 0:
            return {"error": "zero_price_range"}

        bin_size = price_range / num_bins
        vol_bins = [0.0] * num_bins

        for bar in bars:
            # Distribute volume to the bin at the typical price
            typical = (bar.high + bar.low + bar.close) / 3
            bin_idx = min(num_bins - 1, max(0, int((typical - price_min) / bin_size)))
            vol_bins[bin_idx] += bar.volume

        total_vol = sum(vol_bins)
        if total_vol <= 0:
            return {"error": "no_volume_data"}

        threshold_vol = float(np.percentile([v for v in vol_bins if v > 0], threshold_pct))

        current_price = float(bars[-1].close)
        zones = []

        for i in range(num_bins):
            if vol_bins[i] >= threshold_vol:
                zone_price = round(price_min + (i + 0.5) * bin_size, 4)
                distance_pct = round(abs(current_price - zone_price) / max(current_price, 0.01) * 100, 2)
                zones.append({
                    "price": zone_price,
                    "volume": round(vol_bins[i]),
                    "pct_of_total": round(vol_bins[i] / total_vol * 100, 1),
                    "distance_from_current_pct": distance_pct,
                    "type": "support" if zone_price < current_price else "resistance",
                    "strength": "strong" if vol_bins[i] >= threshold_vol * 1.5 else "moderate",
                })

        # Sort by proximity to current price
        zones.sort(key=lambda z: z["distance_from_current_pct"])

        # Nearest support and resistance
        nearest_support = next((z for z in zones if z["type"] == "support"), None)
        nearest_resistance = next((z for z in zones if z["type"] == "resistance"), None)

        return {
            "bars_analyzed": len(bars),
            "zones_found": len(zones),
            "current_price": round(current_price, 4),
            "nearest_support": nearest_support,
            "nearest_resistance": nearest_resistance,
            "zones": zones[:15],
        }

    # ── Incremental Updates ───────────────────────────

    def update_indicators_incremental(
        self,
        prev_state: dict,
        new_bar: OHLCV,
    ) -> dict:
        """Update technical indicators incrementally from previous state + 1 new bar.

        Instead of recomputing all indicators from scratch on every tick,
        this method applies rolling window math to update SMA, EMA, RSI,
        and MACD from the last computed state.

        Args:
            prev_state: Previous indicator state dict with keys:
                - sma_20_window: list of last 20 closes
                - sma_50_window: list of last 50 closes
                - ema_12_prev: previous EMA-12 value
                - ema_26_prev: previous EMA-26 value
                - signal_prev: previous MACD signal line
                - rsi_prev_gain: previous avg gain (14-period)
                - rsi_prev_loss: previous avg loss (14-period)
                - close_prev: previous close price
            new_bar: New OHLCV bar to incorporate.

        Returns:
            Dict with updated indicator values and new state for next call.
        """
        close = new_bar.get("close", 0)
        volume = new_bar.get("volume", 0)
        high = new_bar.get("high", close)
        low = new_bar.get("low", close)

        # ── SMA-20 (rolling window) ──
        sma_20_window = list(prev_state.get("sma_20_window", []))
        sma_20_window.append(close)
        if len(sma_20_window) > 20:
            sma_20_window = sma_20_window[-20:]
        sma_20 = round(sum(sma_20_window) / len(sma_20_window), 4) if sma_20_window else None

        # ── SMA-50 (rolling window) ──
        sma_50_window = list(prev_state.get("sma_50_window", []))
        sma_50_window.append(close)
        if len(sma_50_window) > 50:
            sma_50_window = sma_50_window[-50:]
        sma_50 = round(sum(sma_50_window) / len(sma_50_window), 4) if sma_50_window else None

        # ── EMA-12 / EMA-26 (exponential smoothing) ──
        ema_12_prev = prev_state.get("ema_12_prev")
        ema_26_prev = prev_state.get("ema_26_prev")

        k12 = 2 / (12 + 1)
        k26 = 2 / (26 + 1)

        ema_12 = round(close * k12 + ema_12_prev * (1 - k12), 4) if ema_12_prev is not None else close
        ema_26 = round(close * k26 + ema_26_prev * (1 - k26), 4) if ema_26_prev is not None else close

        # ── MACD ──
        macd_line = round(ema_12 - ema_26, 4)
        signal_prev = prev_state.get("signal_prev", macd_line)
        k_signal = 2 / (9 + 1)
        signal = round(macd_line * k_signal + signal_prev * (1 - k_signal), 4)
        macd_histogram = round(macd_line - signal, 4)

        # ── RSI-14 (Wilder's smoothing) ──
        close_prev = prev_state.get("close_prev", close)
        change = close - close_prev
        gain = max(change, 0)
        loss = abs(min(change, 0))

        prev_avg_gain = prev_state.get("rsi_prev_gain", 0)
        prev_avg_loss = prev_state.get("rsi_prev_loss", 0)

        avg_gain = round((prev_avg_gain * 13 + gain) / 14, 6)
        avg_loss = round((prev_avg_loss * 13 + loss) / 14, 6)

        if avg_loss == 0:
            rsi = 100.0
        else:
            rs = avg_gain / avg_loss
            rsi = round(100 - (100 / (1 + rs)), 2)

        # ── Signal Assessment ──
        bullish_count = sum([
            rsi > 50,
            macd_histogram > 0,
            close > (sma_20 or 0),
            close > (sma_50 or 0),
        ])
        if bullish_count >= 3:
            signal_dir = "bullish"
        elif bullish_count <= 1:
            signal_dir = "bearish"
        else:
            signal_dir = "neutral"

        return {
            # Current indicator values
            "close": round(close, 4),
            "sma_20": sma_20,
            "sma_50": sma_50,
            "ema_12": ema_12,
            "ema_26": ema_26,
            "macd_line": macd_line,
            "macd_signal": signal,
            "macd_histogram": macd_histogram,
            "rsi_14": rsi,
            "signal": signal_dir,
            # State for next incremental call
            "sma_20_window": sma_20_window,
            "sma_50_window": sma_50_window,
            "ema_12_prev": ema_12,
            "ema_26_prev": ema_26,
            "signal_prev": signal,
            "rsi_prev_gain": avg_gain,
            "rsi_prev_loss": avg_loss,
            "close_prev": close,
        }
