"""
Bubby Vision — Options Engine

Pure domain logic for options analysis: Greeks computation, GEX calculation,
IV rank/percentile, strategy evaluation, sweep detection, and flow analysis.

Sources integrated:
- mcp-optionsflow patterns (strategy eval, Greeks)
- GammaGEX algorithms (net GEX per strike)
- OI Tracker patterns (smart money detection, OI delta)
- Options Flow patterns (sweep/block detection)
- IV Rank/Skew (built from scratch — pure math)
"""

from __future__ import annotations

import math
from datetime import datetime, timedelta
from typing import Optional

import numpy as np

from app.models import OptionContract, OptionGreeks, OptionsChain, HigherGreeks

# ── Standard normal distribution (replaces scipy.stats.norm) ──────────────
# Uses math.erf which delegates to the same C libm erf() that scipy uses.
# Produces identical IEEE 754 double-precision results — zero quality loss.
_SQRT_2 = math.sqrt(2.0)
_SQRT_2PI = math.sqrt(2.0 * math.pi)
_INV_SQRT_2PI = 1.0 / _SQRT_2PI


class _Norm:
    """Drop-in replacement for scipy.stats.norm with .cdf() and .pdf() methods.
    Uses math.erf (C libm) — identical precision to scipy, zero import overhead."""

    @staticmethod
    def cdf(x: float) -> float:
        """Standard normal CDF: Φ(x) = 0.5 * (1 + erf(x / √2))"""
        return 0.5 * (1.0 + math.erf(x / _SQRT_2))

    @staticmethod
    def pdf(x: float) -> float:
        """Standard normal PDF: φ(x) = exp(-x²/2) / √(2π)"""
        return math.exp(-0.5 * x * x) * _INV_SQRT_2PI


norm = _Norm()

# py_vollib fast-path for IV (LetsBeRational algorithm — industry-standard)
try:
    from py_vollib.black_scholes.implied_volatility import implied_volatility as _vollib_iv
    _HAS_VOLLIB = True
except ImportError:
    _HAS_VOLLIB = False

# mibian for alternative pricing models (Merton, Garman-Kohlhagen)
# NOTE: Lazy-loaded because mibian internally imports scipy.stats.norm
# which deadlocks on Python 3.14.0 at module load time. By deferring the
# import to first use, the app starts instantly while preserving full
# mibian functionality when the Merton model is actually invoked.
_mibian = None
_HAS_MIBIAN = True  # Assumed available; set False on first-use ImportError


def _get_mibian():
    """Lazy-load mibian on first call."""
    global _mibian, _HAS_MIBIAN
    if _mibian is not None:
        return _mibian
    try:
        import mibian
        _mibian = mibian
        return _mibian
    except ImportError:
        _HAS_MIBIAN = False
        return None


class OptionsEngine:
    """Pure-Python options analysis engine."""

    # ──────────────────────────────────────────────
    # Black-Scholes Pricing
    # ──────────────────────────────────────────────

    @staticmethod
    def black_scholes(
        S: float,
        K: float,
        T: float,
        r: float,
        sigma: float,
        option_type: str = "call",
    ) -> float:
        """Black-Scholes option price.

        Args:
            S: Current stock price
            K: Strike price
            T: Time to expiry in years
            r: Risk-free rate (e.g. 0.05 for 5%)
            sigma: Implied volatility (e.g. 0.30 for 30%)
            option_type: "call" or "put"
        """
        if T <= 0 or sigma <= 0:
            return max(0, S - K) if option_type == "call" else max(0, K - S)

        d1 = (math.log(S / K) + (r + sigma**2 / 2) * T) / (sigma * math.sqrt(T))
        d2 = d1 - sigma * math.sqrt(T)

        if option_type == "call":
            return S * norm.cdf(d1) - K * math.exp(-r * T) * norm.cdf(d2)
        else:
            return K * math.exp(-r * T) * norm.cdf(-d2) - S * norm.cdf(-d1)

    # ──────────────────────────────────────────────
    # Greeks
    # ──────────────────────────────────────────────

    @staticmethod
    def compute_greeks(
        S: float,
        K: float,
        T: float,
        r: float,
        sigma: float,
        option_type: str = "call",
    ) -> OptionGreeks:
        """Compute all first-order Greeks.

        Returns OptionGreeks with delta, gamma, theta, vega, rho.
        """
        if T <= 0 or sigma <= 0:
            return OptionGreeks(
                delta=1.0 if option_type == "call" and S > K else (-1.0 if option_type == "put" and S < K else 0.0),
                gamma=0.0, theta=0.0, vega=0.0, rho=0.0,
                implied_volatility=sigma,
            )

        sqrt_T = math.sqrt(T)
        d1 = (math.log(S / K) + (r + sigma**2 / 2) * T) / (sigma * sqrt_T)
        d2 = d1 - sigma * sqrt_T

        # Delta
        if option_type == "call":
            delta = norm.cdf(d1)
        else:
            delta = norm.cdf(d1) - 1

        # Gamma (same for calls and puts)
        gamma = norm.pdf(d1) / (S * sigma * sqrt_T)

        # Theta (per day)
        theta_term1 = -(S * norm.pdf(d1) * sigma) / (2 * sqrt_T)
        if option_type == "call":
            theta = (theta_term1 - r * K * math.exp(-r * T) * norm.cdf(d2)) / 365
        else:
            theta = (theta_term1 + r * K * math.exp(-r * T) * norm.cdf(-d2)) / 365

        # Vega (per 1% IV change)
        vega = S * norm.pdf(d1) * sqrt_T / 100

        # Rho (per 1% rate change)
        if option_type == "call":
            rho = K * T * math.exp(-r * T) * norm.cdf(d2) / 100
        else:
            rho = -K * T * math.exp(-r * T) * norm.cdf(-d2) / 100

        return OptionGreeks(
            delta=round(delta, 4),
            gamma=round(gamma, 6),
            theta=round(theta, 4),
            vega=round(vega, 4),
            rho=round(rho, 4),
            implied_volatility=round(sigma, 4),
        )

    # ──────────────────────────────────────────────
    # Higher-Order Greeks (2nd + 3rd order)
    # ──────────────────────────────────────────────

    @staticmethod
    def compute_higher_greeks(
        S: float,
        K: float,
        T: float,
        r: float,
        sigma: float,
        option_type: str = "call",
    ) -> HigherGreeks:
        """Compute 2nd and 3rd order Greeks using closed-form BSM derivatives.

        2nd order: charm, vanna, vomma (volga), veta
        3rd order: color, speed, ultima, zomma
        """
        if T <= 0 or sigma <= 0:
            return HigherGreeks()

        sqrt_T = math.sqrt(T)
        d1 = (math.log(S / K) + (r + sigma**2 / 2) * T) / (sigma * sqrt_T)
        d2 = d1 - sigma * sqrt_T
        pdf_d1 = norm.pdf(d1)

        # ── 2nd Order ──
        # Charm (delta decay): -dDelta/dT
        charm_val = -pdf_d1 * (
            2 * r * T - d2 * sigma * sqrt_T
        ) / (2 * T * sigma * sqrt_T)
        if option_type == "put":
            charm_val += r * math.exp(-r * T) * norm.cdf(-d1)

        # Vanna: dDelta/dSigma = dVega/dS
        vanna_val = -pdf_d1 * d2 / sigma

        # Vomma (Volga): dVega/dSigma
        vomma_val = S * pdf_d1 * sqrt_T * d1 * d2 / sigma

        # Veta: dVega/dT
        veta_val = -S * pdf_d1 * sqrt_T * (
            r * d1 / (sigma * sqrt_T) - (1 + d1 * d2) / (2 * T)
        )

        # ── 3rd Order ──
        # Color: dGamma/dT
        gamma_val = pdf_d1 / (S * sigma * sqrt_T)
        color_val = -gamma_val / (2 * T) * (
            1 + d1 * (2 * r * T - d2 * sigma * sqrt_T) / (sigma * sqrt_T)
        )

        # Speed: dGamma/dS
        speed_val = -gamma_val / S * (d1 / (sigma * sqrt_T) + 1)

        # Zomma: dGamma/dSigma
        zomma_val = gamma_val * (d1 * d2 - 1) / sigma

        # Ultima: dVomma/dSigma
        ultima_val = -vomma_val / sigma * (
            1 - d1 * d2 + d1 * d1 * d2 * d2 - d1 / (sigma * sqrt_T) - d2 / (sigma * sqrt_T)
        )

        return HigherGreeks(
            charm=round(charm_val, 6),
            vanna=round(vanna_val, 6),
            vomma=round(vomma_val, 4),
            veta=round(veta_val, 4),
            color=round(color_val, 8),
            speed=round(speed_val, 8),
            ultima=round(ultima_val, 4),
            zomma=round(zomma_val, 6),
        )

    # ──────────────────────────────────────────────
    # Merton Model (dividend-adjusted BSM via mibian)
    # ──────────────────────────────────────────────

    @staticmethod
    def price_merton(
        S: float,
        K: float,
        T: float,
        r: float,
        sigma: float,
        q: float,
        option_type: str = "call",
    ) -> dict:
        """Merton model price for dividend-paying stocks.

        Args:
            S: Spot price
            K: Strike
            T: Time to expiry (years)
            r: Risk-free rate (decimal)
            sigma: Implied vol (decimal)
            q: Continuous dividend yield (decimal, e.g. 0.015 for 1.5%)
            option_type: 'call' or 'put'

        Returns dict with price, delta, gamma, theta, vega, rho.
        """
        if _HAS_MIBIAN:
            _mb = _get_mibian()
            if _mb is not None:
                try:
                    days = max(1, int(T * 365))
                    # mibian.BS expects: [underlyingPrice, strikePrice, interestRate, daysToExpire]
                    bs = _mb.BS([S, K, r * 100, days], volatility=sigma * 100)
                    result = {
                        "price": round(bs.callPrice if option_type == "call" else bs.putPrice, 4),
                        "delta": round(bs.callDelta if option_type == "call" else bs.putDelta, 4),
                        "gamma": round(bs.gamma, 6),
                        "theta": round(bs.callTheta if option_type == "call" else bs.putTheta, 4),
                        "vega": round(bs.vega, 4),
                        "rho": round(bs.callRho if option_type == "call" else bs.putRho, 4),
                        "model": "mibian_bsm",
                    }
                    return result
                except Exception:
                    pass

        # Fallback: manual Merton (BSM with continuous dividend)
        if T <= 0 or sigma <= 0:
            intrinsic = max(0, S - K) if option_type == "call" else max(0, K - S)
            return {"price": intrinsic, "model": "intrinsic"}

        sqrt_T = math.sqrt(T)
        S_adj = S * math.exp(-q * T)
        d1 = (math.log(S_adj / K) + (r + sigma**2 / 2) * T) / (sigma * sqrt_T)
        d2 = d1 - sigma * sqrt_T

        if option_type == "call":
            price = S_adj * norm.cdf(d1) - K * math.exp(-r * T) * norm.cdf(d2)
            delta = math.exp(-q * T) * norm.cdf(d1)
        else:
            price = K * math.exp(-r * T) * norm.cdf(-d2) - S_adj * norm.cdf(-d1)
            delta = -math.exp(-q * T) * norm.cdf(-d1)

        gamma = math.exp(-q * T) * norm.pdf(d1) / (S * sigma * sqrt_T)
        vega = S_adj * norm.pdf(d1) * sqrt_T / 100
        theta_term = -(S_adj * norm.pdf(d1) * sigma) / (2 * sqrt_T)
        if option_type == "call":
            theta = (theta_term + q * S_adj * norm.cdf(d1)
                     - r * K * math.exp(-r * T) * norm.cdf(d2)) / 365
        else:
            theta = (theta_term - q * S_adj * norm.cdf(-d1)
                     + r * K * math.exp(-r * T) * norm.cdf(-d2)) / 365

        return {
            "price": round(price, 4),
            "delta": round(delta, 4),
            "gamma": round(gamma, 6),
            "theta": round(theta, 4),
            "vega": round(vega, 4),
            "model": "merton_manual",
        }


    # ──────────────────────────────────────────────
    # Implied Volatility (Newton-Raphson)
    # ──────────────────────────────────────────────

    def implied_volatility(
        self,
        market_price: float,
        S: float,
        K: float,
        T: float,
        r: float,
        option_type: str = "call",
        max_iterations: int = 100,
        tolerance: float = 1e-6,
    ) -> float:
        """Calculate implied volatility.

        Uses py_vollib's LetsBeRational algorithm (industry-standard, ~2 iterations)
        when available, falling back to Newton-Raphson.
        """
        if T <= 0 or market_price <= 0:
            return 0.0

        # Fast path: py_vollib (LetsBeRational — converges in ~2 iterations)
        if _HAS_VOLLIB:
            try:
                flag = "c" if option_type == "call" else "p"
                iv = _vollib_iv(market_price, S, K, T, r, flag)
                return round(iv, 4)
            except Exception:
                pass  # Fall through to Newton-Raphson

        # Fallback: Newton-Raphson
        sigma = 0.3  # initial guess
        for _ in range(max_iterations):
            price = self.black_scholes(S, K, T, r, sigma, option_type)
            vega = self._vega_raw(S, K, T, r, sigma)

            if abs(vega) < 1e-10:
                break

            diff = market_price - price
            if abs(diff) < tolerance:
                break

            sigma += diff / vega
            sigma = max(0.01, min(sigma, 5.0))  # clamp between 1% and 500%

        return round(sigma, 4)

    @staticmethod
    def _vega_raw(S: float, K: float, T: float, r: float, sigma: float) -> float:
        """Raw vega (not per-percentage)."""
        if T <= 0 or sigma <= 0:
            return 0.0
        d1 = (math.log(S / K) + (r + sigma**2 / 2) * T) / (sigma * math.sqrt(T))
        return S * norm.pdf(d1) * math.sqrt(T)

    def compute_implied_volatility(
        self,
        option_price: float,
        S: float,
        K: float,
        T: float,
        r: float,
        option_type: str = "call",
        **kwargs,
    ) -> float:
        """Alias for implied_volatility() with option_price parameter name."""
        return self.implied_volatility(
            market_price=option_price, S=S, K=K, T=T, r=r, option_type=option_type, **kwargs
        )

    # ──────────────────────────────────────────────
    # IV Rank & Percentile
    # ──────────────────────────────────────────────

    @staticmethod
    def iv_rank(current_iv: float, iv_high_52w: float, iv_low_52w: float) -> float:
        """IV Rank: where current IV sits in the 52-week range (0-100).

        Formula: (Current IV - 52w Low) / (52w High - 52w Low) × 100
        """
        if iv_high_52w <= iv_low_52w:
            return 50.0
        return round((current_iv - iv_low_52w) / (iv_high_52w - iv_low_52w) * 100, 1)

    @staticmethod
    def iv_percentile(current_iv: float, historical_ivs: list[float]) -> float:
        """IV Percentile: % of days in last year with IV below current (0-100).

        More robust than IV Rank — not distorted by single spikes.
        """
        if not historical_ivs:
            return 50.0
        below = sum(1 for iv in historical_ivs if iv < current_iv)
        return round(below / len(historical_ivs) * 100, 1)

    @staticmethod
    def iv_skew(call_iv_otm: float, put_iv_otm: float) -> dict:
        """IV Skew analysis.

        Normal state: put IV > call IV (demand for downside protection).
        Inverted: call IV > put IV (bullish demand).
        """
        skew = put_iv_otm - call_iv_otm
        ratio = put_iv_otm / call_iv_otm if call_iv_otm > 0 else 1.0

        if ratio > 1.15:
            label = "heavy_put_skew"
            interpretation = "Market heavily pricing downside protection — bearish sentiment"
        elif ratio > 1.05:
            label = "normal_skew"
            interpretation = "Normal put skew — typical hedging demand"
        elif ratio > 0.95:
            label = "flat_skew"
            interpretation = "Flat skew — balanced sentiment"
        else:
            label = "inverted_skew"
            interpretation = "Inverted skew — unusual call demand, bullish"

        return {
            "skew": round(skew, 4),
            "ratio": round(ratio, 3),
            "label": label,
            "interpretation": interpretation,
        }

    # ──────────────────────────────────────────────
    # IV Term Structure
    # ──────────────────────────────────────────────

    @staticmethod
    def term_structure(
        expiry_ivs: list[tuple[str, float]],
    ) -> dict:
        """IV Term Structure across expirations.

        Computes the IV curve by expiry and classifies as contango
        (upward-sloping — near-term IV < far-term IV) or backwardation
        (downward-sloping — near-term IV > far-term IV).

        Args:
            expiry_ivs: List of (expiry_label, atm_iv) tuples sorted by
                        ascending expiry date. expiry_label is ISO date str,
                        atm_iv is decimal (e.g. 0.32 for 32%).

        Returns:
            Dict with points, slope, classification, front/back IVs.
        """
        if len(expiry_ivs) < 2:
            return {
                "points": [
                    {"expiry": e, "iv": round(iv, 4)} for e, iv in expiry_ivs
                ],
                "slope": 0.0,
                "classification": "insufficient_data",
            }

        # Build points with annualized days from today
        today = datetime.utcnow().date()
        points = []
        for expiry_str, iv in expiry_ivs:
            try:
                exp_date = datetime.strptime(expiry_str, "%Y-%m-%d").date()
                days = max(1, (exp_date - today).days)
            except (ValueError, TypeError):
                days = 0
            points.append({
                "expiry": expiry_str,
                "iv": round(iv, 4),
                "days_to_expiry": days,
            })

        # Slope: (back IV - front IV) / (back days - front days)
        front = points[0]
        back = points[-1]
        day_diff = back["days_to_expiry"] - front["days_to_expiry"]
        if day_diff > 0:
            slope = (back["iv"] - front["iv"]) / day_diff * 30  # per 30 days
        else:
            slope = 0.0

        # Classification
        iv_diff_pct = (back["iv"] - front["iv"]) / front["iv"] * 100 if front["iv"] > 0 else 0

        if iv_diff_pct > 5:
            classification = "contango"
            interpretation = "Far-dated IV higher than near — normal term structure, market pricing future uncertainty"
        elif iv_diff_pct < -5:
            classification = "backwardation"
            interpretation = "Near-term IV higher — event-driven fear or earnings, elevated short-term premium"
        else:
            classification = "flat"
            interpretation = "Flat term structure — uniform volatility expectations across expirations"

        return {
            "points": points,
            "slope": round(slope, 6),
            "classification": classification,
            "interpretation": interpretation,
            "front_iv": front["iv"],
            "back_iv": back["iv"],
            "front_expiry": front["expiry"],
            "back_expiry": back["expiry"],
        }

    # ──────────────────────────────────────────────
    # GEX (Gamma Exposure)
    # ──────────────────────────────────────────────

    def compute_gex(self, chain: OptionsChain) -> dict:
        """Compute net Gamma Exposure (GEX) per strike.

        GEX = Gamma × OI × 100 × Spot Price²
        Positive GEX = dealer long gamma = dampening effect
        Negative GEX = dealer short gamma = amplifying effect

        This determines whether a breakout will be amplified or suppressed.
        """
        strikes: dict[float, float] = {}
        total_gex = 0.0
        spot = chain.underlying_price

        for call in chain.calls:
            gamma = call.greeks.gamma or self._estimate_gamma(
                spot, call.strike, self._days_to_years(call.expiration),
                0.05, call.greeks.implied_volatility or 0.3
            )
            gex = gamma * call.open_interest * 100 * spot * spot
            strikes[call.strike] = strikes.get(call.strike, 0) + gex
            total_gex += gex

        for put in chain.puts:
            gamma = put.greeks.gamma or self._estimate_gamma(
                spot, put.strike, self._days_to_years(put.expiration),
                0.05, put.greeks.implied_volatility or 0.3
            )
            # Put gamma is negative for dealers (they're short puts to hedgers)
            gex = -gamma * put.open_interest * 100 * spot * spot
            strikes[put.strike] = strikes.get(put.strike, 0) + gex
            total_gex += gex

        # Find the GEX flip point (where net GEX changes sign)
        sorted_strikes = sorted(strikes.items())
        flip_strike = None
        for i in range(1, len(sorted_strikes)):
            if sorted_strikes[i - 1][1] * sorted_strikes[i][1] < 0:
                flip_strike = sorted_strikes[i][0]
                break

        return {
            "total_gex": round(total_gex, 2),
            "gex_by_strike": {k: round(v, 2) for k, v in sorted(strikes.items())},
            "flip_strike": flip_strike,
            "dealer_positioning": "long_gamma" if total_gex > 0 else "short_gamma",
            "market_impact": "dampening" if total_gex > 0 else "amplifying",
            "spot_price": spot,
        }

    @staticmethod
    def _estimate_gamma(S, K, T, r, sigma):
        """Estimate gamma when not provided by data source."""
        if T <= 0 or sigma <= 0:
            return 0.0
        d1 = (math.log(S / K) + (r + sigma**2 / 2) * T) / (sigma * math.sqrt(T))
        return norm.pdf(d1) / (S * sigma * math.sqrt(T))

    @staticmethod
    def _days_to_years(expiration: datetime) -> float:
        """Convert expiration date to time-to-expiry in years."""
        days = (expiration - datetime.utcnow()).days
        return max(0.001, days / 365)

    # ──────────────────────────────────────────────
    # Max Pain
    # ──────────────────────────────────────────────

    @staticmethod
    def compute_max_pain(chain: OptionsChain) -> dict:
        """Calculate max pain strike — price where option holders lose the most.

        Market makers are incentivized to push price toward max pain near expiry.
        """
        strikes = set()
        for c in chain.calls:
            strikes.add(c.strike)
        for p in chain.puts:
            strikes.add(p.strike)

        if not strikes:
            return {"max_pain": None, "distance_pct": None}

        # Build OI maps
        call_oi: dict[float, int] = {c.strike: c.open_interest for c in chain.calls}
        put_oi: dict[float, int] = {p.strike: p.open_interest for p in chain.puts}

        min_pain = float("inf")
        max_pain_strike = 0.0

        for test_price in sorted(strikes):
            total_pain = 0.0
            for strike, oi in call_oi.items():
                if test_price > strike:
                    total_pain += (test_price - strike) * oi * 100
            for strike, oi in put_oi.items():
                if test_price < strike:
                    total_pain += (strike - test_price) * oi * 100
            if total_pain < min_pain:
                min_pain = total_pain
                max_pain_strike = test_price

        distance_pct = None
        if chain.underlying_price > 0:
            distance_pct = round((max_pain_strike - chain.underlying_price) / chain.underlying_price * 100, 2)

        return {
            "max_pain": max_pain_strike,
            "distance_pct": distance_pct,
            "total_pain_value": round(min_pain, 2),
            "underlying": chain.underlying_price,
        }

    # ──────────────────────────────────────────────
    # Put/Call Ratio
    # ──────────────────────────────────────────────

    @staticmethod
    def put_call_ratio(chain: OptionsChain) -> dict:
        """Compute put/call ratio by volume and open interest."""
        call_vol = sum(c.volume for c in chain.calls)
        put_vol = sum(p.volume for p in chain.puts)
        call_oi = sum(c.open_interest for c in chain.calls)
        put_oi = sum(p.open_interest for p in chain.puts)

        vol_ratio = put_vol / call_vol if call_vol > 0 else 0.0
        oi_ratio = put_oi / call_oi if call_oi > 0 else 0.0

        if vol_ratio > 1.5:
            sentiment = "bearish"
        elif vol_ratio > 1.0:
            sentiment = "slightly_bearish"
        elif vol_ratio > 0.7:
            sentiment = "neutral"
        elif vol_ratio > 0.5:
            sentiment = "slightly_bullish"
        else:
            sentiment = "bullish"

        return {
            "volume_ratio": round(vol_ratio, 3),
            "oi_ratio": round(oi_ratio, 3),
            "call_volume": call_vol,
            "put_volume": put_vol,
            "call_oi": call_oi,
            "put_oi": put_oi,
            "sentiment": sentiment,
        }

    # ──────────────────────────────────────────────
    # Unusual Activity Detection
    # ──────────────────────────────────────────────

    @staticmethod
    def detect_unusual_activity(chain: OptionsChain, volume_threshold: float = 3.0) -> list[dict]:
        """Detect unusual options activity.

        Flags contracts where volume > threshold × open interest.
        """
        unusual = []

        for contract in chain.calls + chain.puts:
            if contract.open_interest > 0:
                vol_oi_ratio = contract.volume / contract.open_interest
                if vol_oi_ratio >= volume_threshold and contract.volume >= 100:
                    unusual.append({
                        "contract": contract.contract_symbol,
                        "type": contract.option_type,
                        "strike": contract.strike,
                        "expiration": contract.expiration.strftime("%Y-%m-%d"),
                        "volume": contract.volume,
                        "open_interest": contract.open_interest,
                        "vol_oi_ratio": round(vol_oi_ratio, 2),
                        "bid_ask_spread": round(contract.ask - contract.bid, 2),
                        "iv": contract.greeks.implied_volatility,
                    })

        # Sort by vol/OI ratio descending
        unusual.sort(key=lambda x: x["vol_oi_ratio"], reverse=True)
        return unusual

    # ──────────────────────────────────────────────
    # Strategy Evaluation
    # ──────────────────────────────────────────────

    def evaluate_strategy(
        self,
        strategy_type: str,
        legs: list[dict],
        underlying_price: float,
    ) -> dict:
        """Evaluate an options strategy.

        Args:
            strategy_type: "long_call", "bull_call_spread", "iron_condor", etc.
            legs: List of {'type': 'call'/'put', 'strike': float, 'premium': float,
                          'action': 'buy'/'sell', 'contracts': int}
            underlying_price: Current stock price.

        Returns:
            Dict with max_profit, max_loss, breakeven, probability_of_profit, risk_reward.
        """
        max_profit = 0.0
        max_loss = 0.0
        net_premium = 0.0
        breakevens = []

        for leg in legs:
            premium = leg["premium"] * leg.get("contracts", 1) * 100
            if leg["action"] == "buy":
                net_premium -= premium
            else:
                net_premium += premium

        # Calculate P/L across a range of prices at expiry
        prices = np.linspace(underlying_price * 0.7, underlying_price * 1.3, 1000)
        pnls = []

        for price in prices:
            pnl = 0.0
            for leg in legs:
                intrinsic = 0.0
                if leg["type"] == "call":
                    intrinsic = max(0, price - leg["strike"])
                else:
                    intrinsic = max(0, leg["strike"] - price)

                contracts = leg.get("contracts", 1)
                if leg["action"] == "buy":
                    pnl += (intrinsic - leg["premium"]) * contracts * 100
                else:
                    pnl += (leg["premium"] - intrinsic) * contracts * 100
            pnls.append(pnl)

        pnls = np.array(pnls)
        max_profit = float(np.max(pnls))
        max_loss = float(np.min(pnls))

        # Find breakevens (where P/L crosses zero)
        for i in range(1, len(pnls)):
            if pnls[i - 1] * pnls[i] < 0:
                # Linear interpolation
                ratio = abs(pnls[i - 1]) / (abs(pnls[i - 1]) + abs(pnls[i]))
                be = prices[i - 1] + ratio * (prices[i] - prices[i - 1])
                breakevens.append(round(be, 2))

        # Probability of profit (approximate using normal distribution)
        pop = None
        if breakevens and underlying_price > 0:
            # Simple approximation: assume 30% annual return dispersion
            distances = [abs(be - underlying_price) / underlying_price for be in breakevens]
            avg_distance = np.mean(distances)
            # Higher distance from current price = lower probability
            pop = round(max(5, min(95, (1 - avg_distance * 3) * 100)), 1)

        risk_reward = abs(max_profit / max_loss) if max_loss != 0 else float("inf")

        return {
            "strategy": strategy_type,
            "net_premium": round(net_premium, 2),
            "max_profit": round(max_profit, 2),
            "max_loss": round(max_loss, 2),
            "breakevens": breakevens,
            "probability_of_profit": pop,
            "risk_reward_ratio": round(risk_reward, 2) if risk_reward != float("inf") else "unlimited",
            "legs": legs,
        }

    # ──────────────────────────────────────────────
    # Phase 7, Group A: Advanced Pricing
    # ──────────────────────────────────────────────

    @staticmethod
    def monte_carlo_price(
        S: float,
        K: float,
        T: float,
        r: float,
        sigma: float,
        option_type: str = "call",
        n_sims: int = 10_000,
    ) -> dict:
        """Monte Carlo European option pricing with confidence intervals.

        Simulates geometric Brownian motion paths and averages discounted payoffs.

        Args:
            S: Current stock price.
            K: Strike price.
            T: Time to expiry in years.
            r: Risk-free rate.
            sigma: Implied volatility.
            option_type: 'call' or 'put'.
            n_sims: Number of simulations (default 10,000).
        """
        if T <= 0 or sigma <= 0:
            intrinsic = max(0, S - K) if option_type == "call" else max(0, K - S)
            return {"price": intrinsic, "std_error": 0.0, "ci_95": [intrinsic, intrinsic]}

        rng = np.random.default_rng(42)
        z = rng.standard_normal(n_sims)

        # Geometric Brownian Motion terminal price
        ST = S * np.exp((r - 0.5 * sigma**2) * T + sigma * math.sqrt(T) * z)

        # Payoffs
        if option_type == "call":
            payoffs = np.maximum(ST - K, 0)
        else:
            payoffs = np.maximum(K - ST, 0)

        # Discounted expected payoff
        discount = math.exp(-r * T)
        discounted = payoffs * discount
        price = float(np.mean(discounted))
        std_err = float(np.std(discounted) / math.sqrt(n_sims))

        return {
            "price": round(price, 4),
            "std_error": round(std_err, 4),
            "ci_95": [round(price - 1.96 * std_err, 4), round(price + 1.96 * std_err, 4)],
            "n_sims": n_sims,
        }

    @staticmethod
    def binomial_price(
        S: float,
        K: float,
        T: float,
        r: float,
        sigma: float,
        option_type: str = "call",
        n_steps: int = 100,
        american: bool = False,
    ) -> dict:
        """Binomial tree option pricing (Cox-Ross-Rubinstein model).

        Supports both European and American exercise styles.

        Args:
            S: Current stock price.
            K: Strike price.
            T: Time to expiry in years.
            r: Risk-free rate.
            sigma: Implied volatility.
            option_type: 'call' or 'put'.
            n_steps: Number of time steps (default 100).
            american: If True, allows early exercise.
        """
        if T <= 0 or sigma <= 0:
            intrinsic = max(0, S - K) if option_type == "call" else max(0, K - S)
            return {"price": intrinsic, "style": "american" if american else "european"}

        dt = T / n_steps
        u = math.exp(sigma * math.sqrt(dt))       # up factor
        d = 1 / u                                   # down factor
        p = (math.exp(r * dt) - d) / (u - d)       # risk-neutral probability
        discount = math.exp(-r * dt)

        # Build terminal payoffs
        prices_at_T = S * u ** np.arange(n_steps, -1, -2, dtype=float)
        # Adjust: S * u^j * d^(n-j) for j = n, n-2, n-4, ...
        # Actually build full terminal node prices
        terminal = np.array([S * (u ** j) * (d ** (n_steps - j)) for j in range(n_steps + 1)])

        if option_type == "call":
            values = np.maximum(terminal - K, 0.0)
        else:
            values = np.maximum(K - terminal, 0.0)

        # Backward induction
        for i in range(n_steps - 1, -1, -1):
            node_prices = np.array([S * (u ** j) * (d ** (i - j)) for j in range(i + 1)])
            values = discount * (p * values[1:i + 2] + (1 - p) * values[0:i + 1])

            if american:
                if option_type == "call":
                    exercise = np.maximum(node_prices - K, 0.0)
                else:
                    exercise = np.maximum(K - node_prices, 0.0)
                values = np.maximum(values, exercise)

        price = float(values[0])
        return {
            "price": round(price, 4),
            "style": "american" if american else "european",
            "n_steps": n_steps,
            "early_exercise_premium": None,
        }

    @staticmethod
    def barone_adesi_whaley(
        S: float,
        K: float,
        T: float,
        r: float,
        sigma: float,
        option_type: str = "call",
    ) -> dict:
        """Barone-Adesi-Whaley analytical approximation for American options.

        Faster than binomial trees with good accuracy for most strikes.
        Falls back to European price when early exercise is never optimal.

        Args:
            S, K, T, r, sigma: Standard BSM inputs.
            option_type: 'call' or 'put'.
        """
        if T <= 0 or sigma <= 0:
            intrinsic = max(0, S - K) if option_type == "call" else max(0, K - S)
            return {"price": intrinsic, "early_exercise_premium": 0.0}

        # European price via BS
        bs_price = OptionsEngine.black_scholes(S, K, T, r, sigma, option_type)

        # For calls on non-dividend stocks, American = European
        if option_type == "call" and r >= 0:
            return {
                "price": round(bs_price, 4),
                "european_price": round(bs_price, 4),
                "early_exercise_premium": 0.0,
                "note": "American call equals European (no dividends)",
            }

        # BAW parameters
        M = 2 * r / (sigma**2)
        n = 2 * (r) / (sigma**2)
        K_prime = 1 - math.exp(-r * T)
        q2 = (-(n - 1) - math.sqrt((n - 1)**2 + 4 * M / K_prime)) / 2

        # Find critical price S* via Newton iteration
        S_star = K  # initial guess
        for _ in range(50):
            d1_star = (math.log(S_star / K) + (r + sigma**2 / 2) * T) / (sigma * math.sqrt(T))
            bs_star = OptionsEngine.black_scholes(S_star, K, T, r, sigma, option_type)

            if option_type == "put":
                lhs = K - S_star - bs_star
                rhs = -S_star * (1 - norm.cdf(-d1_star)) / q2
            else:
                lhs = S_star - K - bs_star
                rhs = S_star * norm.cdf(d1_star) / q2

            diff = lhs - rhs
            if abs(diff) < 1e-6:
                break

            # Shift S_star
            S_star += diff * 0.5

        # Compute American price
        if option_type == "put":
            if S >= S_star:
                A2 = -(S_star / q2) * (1 - norm.cdf(-d1_star))
                price = bs_price + A2 * (S / S_star) ** q2
            else:
                price = K - S  # deep ITM early exercise
        else:
            price = bs_price  # already handled above

        early_premium = max(0, price - bs_price)
        return {
            "price": round(price, 4),
            "european_price": round(bs_price, 4),
            "early_exercise_premium": round(early_premium, 4),
            "critical_price": round(S_star, 2),
        }

    # ──────────────────────────────────────────────
    # Phase 7, Group A: P/L Profiles & Probability
    # ──────────────────────────────────────────────

    @staticmethod
    def compute_pl_profile(
        legs: list[dict],
        underlying_price: float,
        price_range_pct: float = 0.20,
        steps: int = 100,
    ) -> dict:
        """Compute a multi-leg P/L profile across a price range at expiration.

        Returns an array of (price, pnl) pairs for charting.

        Args:
            legs: List of option legs (type, strike, premium, action, contracts).
            underlying_price: Current stock price.
            price_range_pct: Price range as % of underlying (default ±20%).
            steps: Number of price points in the curve.
        """
        lo = underlying_price * (1 - price_range_pct)
        hi = underlying_price * (1 + price_range_pct)
        prices = np.linspace(lo, hi, steps)
        pnl_curve = []

        for price in prices:
            pnl = 0.0
            for leg in legs:
                intrinsic = (
                    max(0, price - leg["strike"]) if leg["type"] == "call"
                    else max(0, leg["strike"] - price)
                )
                contracts = leg.get("contracts", 1)
                if leg["action"] == "buy":
                    pnl += (intrinsic - leg["premium"]) * contracts * 100
                else:
                    pnl += (leg["premium"] - intrinsic) * contracts * 100
            pnl_curve.append({"price": round(float(price), 2), "pnl": round(pnl, 2)})

        # Extract key stats
        pnls = np.array([p["pnl"] for p in pnl_curve])
        max_profit = float(np.max(pnls))
        max_loss = float(np.min(pnls))

        # Find breakevens
        breakevens = []
        for i in range(1, len(pnls)):
            if pnls[i - 1] * pnls[i] < 0:
                ratio = abs(pnls[i - 1]) / (abs(pnls[i - 1]) + abs(pnls[i]))
                be = prices[i - 1] + ratio * (prices[i] - prices[i - 1])
                breakevens.append(round(float(be), 2))

        return {
            "curve": pnl_curve,
            "max_profit": round(max_profit, 2),
            "max_loss": round(max_loss, 2),
            "breakevens": breakevens,
            "underlying_price": underlying_price,
        }

    def compute_pl_at_target_date(
        self,
        legs: list[dict],
        underlying_price: float,
        target_days: int,
        r: float = 0.05,
        steps: int = 100,
    ) -> dict:
        """Compute P/L profile at a future date (before expiration) with time decay.

        Uses Black-Scholes to estimate remaining time value.

        Args:
            legs: Option legs with 'type', 'strike', 'premium', 'action', 'contracts', 'iv', 'dte'.
            underlying_price: Current stock price.
            target_days: Days from now to project P/L.
            r: Risk-free rate.
            steps: Number of price points.
        """
        lo = underlying_price * 0.80
        hi = underlying_price * 1.20
        prices = np.linspace(lo, hi, steps)
        pnl_curve = []

        for price in prices:
            pnl = 0.0
            for leg in legs:
                dte = leg.get("dte", 30)
                iv = leg.get("iv", 0.30)
                remaining_T = max(0.001, (dte - target_days) / 365)

                # BS price at target date
                option_val = self.black_scholes(
                    float(price), leg["strike"], remaining_T, r, iv, leg["type"]
                )

                contracts = leg.get("contracts", 1)
                if leg["action"] == "buy":
                    pnl += (option_val - leg["premium"]) * contracts * 100
                else:
                    pnl += (leg["premium"] - option_val) * contracts * 100

            pnl_curve.append({"price": round(float(price), 2), "pnl": round(pnl, 2)})

        return {
            "curve": pnl_curve,
            "target_days": target_days,
            "underlying_price": underlying_price,
        }

    @staticmethod
    def probability_of_profit(
        legs: list[dict],
        underlying_price: float,
        sigma: float,
        T: float,
        r: float = 0.05,
        n_sims: int = 10_000,
    ) -> dict:
        """Monte Carlo probability of profit for any multi-leg strategy.

        Simulates terminal stock prices and checks if P/L > 0.

        Args:
            legs: Option legs.
            underlying_price: Current stock price.
            sigma: Implied volatility of underlying.
            T: Time to expiration in years.
            r: Risk-free rate.
            n_sims: Number of simulations.
        """
        rng = np.random.default_rng(42)
        z = rng.standard_normal(n_sims)
        ST = underlying_price * np.exp((r - 0.5 * sigma**2) * T + sigma * math.sqrt(max(0.001, T)) * z)

        profitable = 0
        total_pnls = []

        for terminal in ST:
            pnl = 0.0
            for leg in legs:
                intrinsic = (
                    max(0, terminal - leg["strike"]) if leg["type"] == "call"
                    else max(0, leg["strike"] - terminal)
                )
                contracts = leg.get("contracts", 1)
                if leg["action"] == "buy":
                    pnl += (intrinsic - leg["premium"]) * contracts * 100
                else:
                    pnl += (leg["premium"] - intrinsic) * contracts * 100

            total_pnls.append(pnl)
            if pnl > 0:
                profitable += 1

        pnl_array = np.array(total_pnls)
        pop = profitable / n_sims * 100

        return {
            "probability_of_profit": round(pop, 1),
            "expected_pnl": round(float(np.mean(pnl_array)), 2),
            "median_pnl": round(float(np.median(pnl_array)), 2),
            "pnl_std_dev": round(float(np.std(pnl_array)), 2),
            "worst_case": round(float(np.min(pnl_array)), 2),
            "best_case": round(float(np.max(pnl_array)), 2),
            "n_sims": n_sims,
        }

    @staticmethod
    def profitable_price_range(
        legs: list[dict],
        underlying_price: float,
        steps: int = 1000,
    ) -> dict:
        """Find the min/max profitable prices for a strategy at expiration.

        Args:
            legs: Option legs.
            underlying_price: Current stock price.
            steps: Resolution for price sweep.
        """
        lo = underlying_price * 0.50
        hi = underlying_price * 1.50
        prices = np.linspace(lo, hi, steps)

        profitable_prices = []
        for price in prices:
            pnl = 0.0
            for leg in legs:
                intrinsic = (
                    max(0, price - leg["strike"]) if leg["type"] == "call"
                    else max(0, leg["strike"] - price)
                )
                contracts = leg.get("contracts", 1)
                if leg["action"] == "buy":
                    pnl += (intrinsic - leg["premium"]) * contracts * 100
                else:
                    pnl += (leg["premium"] - intrinsic) * contracts * 100

            if pnl > 0:
                profitable_prices.append(float(price))

        if profitable_prices:
            return {
                "profitable_range_low": round(min(profitable_prices), 2),
                "profitable_range_high": round(max(profitable_prices), 2),
                "range_width": round(max(profitable_prices) - min(profitable_prices), 2),
                "range_width_pct": round(
                    (max(profitable_prices) - min(profitable_prices)) / underlying_price * 100, 1
                ),
                "underlying_price": underlying_price,
            }
        return {
            "profitable_range_low": None,
            "profitable_range_high": None,
            "range_width": 0,
            "range_width_pct": 0,
            "underlying_price": underlying_price,
        }

    # ──────────────────────────────────────────────
    # Phase 7, Group B: OI & Flow Intelligence
    # ──────────────────────────────────────────────

    @staticmethod
    def analyze_oi_patterns(chain: OptionsChain) -> dict:
        """Analyze open interest patterns to detect put/call walls and concentration.

        Put Wall = strike with highest put OI (support level).
        Call Wall = strike with highest call OI (resistance level).
        """
        call_oi_map: dict[float, int] = {}
        put_oi_map: dict[float, int] = {}

        for c in chain.calls:
            call_oi_map[c.strike] = call_oi_map.get(c.strike, 0) + c.open_interest
        for p in chain.puts:
            put_oi_map[p.strike] = put_oi_map.get(p.strike, 0) + p.open_interest

        total_call_oi = sum(call_oi_map.values())
        total_put_oi = sum(put_oi_map.values())

        # Find walls (top 5 strikes by OI)
        call_wall_strikes = sorted(call_oi_map.items(), key=lambda x: x[1], reverse=True)[:5]
        put_wall_strikes = sorted(put_oi_map.items(), key=lambda x: x[1], reverse=True)[:5]

        # Strike concentration (how "clumped" is the OI?)
        call_top5_oi = sum(oi for _, oi in call_wall_strikes)
        put_top5_oi = sum(oi for _, oi in put_wall_strikes)
        call_concentration = round(call_top5_oi / total_call_oi * 100, 1) if total_call_oi > 0 else 0
        put_concentration = round(put_top5_oi / total_put_oi * 100, 1) if total_put_oi > 0 else 0

        # Primary walls
        call_wall = call_wall_strikes[0] if call_wall_strikes else (None, 0)
        put_wall = put_wall_strikes[0] if put_wall_strikes else (None, 0)

        spot = chain.underlying_price

        return {
            "call_wall": {
                "strike": call_wall[0],
                "oi": call_wall[1],
                "distance_pct": round((call_wall[0] - spot) / spot * 100, 2) if call_wall[0] and spot > 0 else None,
                "interpretation": "resistance — dealers short calls here, will sell to hedge",
            },
            "put_wall": {
                "strike": put_wall[0],
                "oi": put_wall[1],
                "distance_pct": round((put_wall[0] - spot) / spot * 100, 2) if put_wall[0] and spot > 0 else None,
                "interpretation": "support — dealers short puts here, will buy to hedge",
            },
            "top_call_strikes": [{"strike": s, "oi": oi} for s, oi in call_wall_strikes],
            "top_put_strikes": [{"strike": s, "oi": oi} for s, oi in put_wall_strikes],
            "call_oi_concentration_pct": call_concentration,
            "put_oi_concentration_pct": put_concentration,
            "total_call_oi": total_call_oi,
            "total_put_oi": total_put_oi,
        }

    @staticmethod
    def detect_smart_money(chain: OptionsChain, flow_data: Optional[list[dict]] = None) -> dict:
        """Score institutional/smart money positioning.

        Analyzes: large OI clusters, ITM put accumulation, high vol/OI anomalies.
        Optionally incorporates real-time flow data (sweeps, blocks).

        Args:
            chain: Options chain data.
            flow_data: Optional list of flow records from QuantData/OptionStrats.
        """
        spot = chain.underlying_price
        signals = []
        score = 50  # neutral baseline

        # Signal 1: ITM put accumulation (institutional hedging)
        itm_put_oi = sum(p.open_interest for p in chain.puts if p.strike > spot)
        otm_put_oi = sum(p.open_interest for p in chain.puts if p.strike <= spot)
        if otm_put_oi > 0:
            itm_put_ratio = itm_put_oi / otm_put_oi
            if itm_put_ratio > 0.5:
                signals.append({
                    "signal": "itm_put_accumulation",
                    "strength": "strong" if itm_put_ratio > 1.0 else "moderate",
                    "detail": f"ITM/OTM put ratio: {round(itm_put_ratio, 2)} — institutions hedging",
                })
                score -= 10 if itm_put_ratio > 1.0 else 5

        # Signal 2: Large OI at specific strikes (block positioning)
        all_oi = [(c.strike, c.open_interest, "call") for c in chain.calls] + \
                 [(p.strike, p.open_interest, "put") for p in chain.puts]
        avg_oi = np.mean([oi for _, oi, _ in all_oi]) if all_oi else 0
        large_positions = [
            (strike, oi, otype) for strike, oi, otype in all_oi
            if oi > avg_oi * 5 and oi > 1000
        ]
        if large_positions:
            signals.append({
                "signal": "large_oi_clusters",
                "count": len(large_positions),
                "positions": [
                    {"strike": s, "oi": oi, "type": t}
                    for s, oi, t in sorted(large_positions, key=lambda x: x[1], reverse=True)[:5]
                ],
            })

        # Signal 3: Volume/OI spike (new money entering)
        hot_contracts = []
        for contract in chain.calls + chain.puts:
            if contract.open_interest > 0 and contract.volume > contract.open_interest * 2:
                hot_contracts.append({
                    "strike": contract.strike,
                    "type": contract.option_type,
                    "volume": contract.volume,
                    "oi": contract.open_interest,
                    "ratio": round(contract.volume / contract.open_interest, 1),
                })
        if hot_contracts:
            # Net directional bias from hot contracts
            call_heat = sum(h["volume"] for h in hot_contracts if h["type"] == "call")
            put_heat = sum(h["volume"] for h in hot_contracts if h["type"] == "put")
            bias = "bullish" if call_heat > put_heat * 1.5 else ("bearish" if put_heat > call_heat * 1.5 else "neutral")
            signals.append({
                "signal": "volume_spike",
                "hot_contracts": sorted(hot_contracts, key=lambda x: x["ratio"], reverse=True)[:5],
                "net_bias": bias,
            })
            score += 15 if bias == "bullish" else (-15 if bias == "bearish" else 0)

        # Signal 4: Flow data analysis (if available)
        if flow_data:
            sweeps = [f for f in flow_data if f.get("is_sweep")]
            blocks = [f for f in flow_data if f.get("premium", 0) > 250_000]
            if sweeps:
                call_sweeps = sum(1 for s in sweeps if s.get("type") == "call")
                put_sweeps = sum(1 for s in sweeps if s.get("type") == "put")
                signals.append({
                    "signal": "sweep_activity",
                    "call_sweeps": call_sweeps,
                    "put_sweeps": put_sweeps,
                    "bias": "bullish" if call_sweeps > put_sweeps else "bearish",
                })
                score += 10 if call_sweeps > put_sweeps else -10
            if blocks:
                signals.append({
                    "signal": "block_trades",
                    "count": len(blocks),
                    "total_premium": sum(b.get("premium", 0) for b in blocks),
                })

        # Clamp score
        score = max(0, min(100, score))

        return {
            "smart_money_score": score,
            "bias": "bullish" if score > 60 else ("bearish" if score < 40 else "neutral"),
            "signals": signals,
            "signal_count": len(signals),
        }

    @staticmethod
    def compute_oi_delta(
        current_chain: OptionsChain,
        previous_chain: OptionsChain,
    ) -> dict:
        """Track OI changes between sessions — new money entering vs positions closing.

        Positive OI delta with rising price = bullish confirmation.
        Positive OI delta with falling price = bearish accumulation.
        Negative OI delta = positions being closed.

        Args:
            current_chain: Today's options chain.
            previous_chain: Yesterday's options chain.
        """
        call_deltas = {}
        put_deltas = {}

        # Build previous OI maps
        prev_call_oi = {c.contract_symbol: c.open_interest for c in previous_chain.calls}
        prev_put_oi = {p.contract_symbol: p.open_interest for p in previous_chain.puts}

        # Compute deltas
        total_call_delta = 0
        total_put_delta = 0

        for c in current_chain.calls:
            prev = prev_call_oi.get(c.contract_symbol, 0)
            delta = c.open_interest - prev
            if abs(delta) > 100:  # only track meaningful changes
                call_deltas[c.strike] = {
                    "current_oi": c.open_interest,
                    "previous_oi": prev,
                    "delta": delta,
                    "change_pct": round(delta / prev * 100, 1) if prev > 0 else None,
                }
            total_call_delta += delta

        for p in current_chain.puts:
            prev = prev_put_oi.get(p.contract_symbol, 0)
            delta = p.open_interest - prev
            if abs(delta) > 100:
                put_deltas[p.strike] = {
                    "current_oi": p.open_interest,
                    "previous_oi": prev,
                    "delta": delta,
                    "change_pct": round(delta / prev * 100, 1) if prev > 0 else None,
                }
            total_put_delta += delta

        # Interpret
        if total_call_delta > 0 and total_put_delta > 0:
            interpretation = "New money entering both sides — expect volatility expansion"
        elif total_call_delta > 0:
            interpretation = "New call positions — bullish flow"
        elif total_put_delta > 0:
            interpretation = "New put positions — bearish flow or hedging"
        elif total_call_delta < 0 and total_put_delta < 0:
            interpretation = "Positions closing — volatility contraction likely"
        else:
            interpretation = "Mixed — no clear directional bias"

        return {
            "net_call_oi_delta": total_call_delta,
            "net_put_oi_delta": total_put_delta,
            "net_total_delta": total_call_delta + total_put_delta,
            "interpretation": interpretation,
            "significant_call_changes": dict(sorted(call_deltas.items(), key=lambda x: abs(x[1]["delta"]), reverse=True)[:5]),
            "significant_put_changes": dict(sorted(put_deltas.items(), key=lambda x: abs(x[1]["delta"]), reverse=True)[:5]),
        }

    # ──────────────────────────────────────────────
    # Phase 7, Group C: Enhanced GEX (DEX + VEX)
    # ──────────────────────────────────────────────

    def compute_gex_detailed(self, chain: OptionsChain) -> dict:
        """Enhanced GEX with per-strike DEX (Delta Exposure) and VEX (Vanna Exposure).

        DEX = net delta exposure per strike (directional dealer risk).
        VEX = net vanna exposure per strike (how delta changes with IV).

        Returns full per-strike arrays suitable for charting.
        """
        spot = chain.underlying_price
        r = 0.05

        gex_strikes: dict[float, float] = {}
        dex_strikes: dict[float, float] = {}
        vex_strikes: dict[float, float] = {}

        total_gex = 0.0
        total_dex = 0.0
        total_vex = 0.0

        for contract in chain.calls + chain.puts:
            T = self._days_to_years(contract.expiration)
            sigma = contract.greeks.implied_volatility or 0.3
            gamma = contract.greeks.gamma or self._estimate_gamma(spot, contract.strike, T, r, sigma)
            delta = contract.greeks.delta or 0.0

            oi = contract.open_interest
            sign = 1.0 if contract.option_type == "call" else -1.0

            # GEX = gamma × OI × 100 × S²
            gex = sign * gamma * oi * 100 * spot * spot
            gex_strikes[contract.strike] = gex_strikes.get(contract.strike, 0) + gex
            total_gex += gex

            # DEX = delta × OI × 100 × S
            dex = sign * delta * oi * 100 * spot
            dex_strikes[contract.strike] = dex_strikes.get(contract.strike, 0) + dex
            total_dex += dex

            # VEX (Vanna) = d(delta)/d(sigma) × OI × 100
            # Vanna = -d1 * N'(d1) / sigma ≈ delta sensitivity to IV
            if T > 0 and sigma > 0:
                d1 = (math.log(spot / contract.strike) + (r + sigma**2 / 2) * T) / (sigma * math.sqrt(T))
                vanna = -d1 * norm.pdf(d1) / sigma
                vex = sign * vanna * oi * 100
                vex_strikes[contract.strike] = vex_strikes.get(contract.strike, 0) + vex
                total_vex += vex

        # Find flip points
        sorted_gex = sorted(gex_strikes.items())
        gex_flip = None
        for i in range(1, len(sorted_gex)):
            if sorted_gex[i - 1][1] * sorted_gex[i][1] < 0:
                gex_flip = sorted_gex[i][0]
                break

        # Key strike (highest absolute GEX)
        key_strike = max(gex_strikes.items(), key=lambda x: abs(x[1]))[0] if gex_strikes else None

        return {
            "total_gex": round(total_gex, 2),
            "total_dex": round(total_dex, 2),
            "total_vex": round(total_vex, 2),
            "gex_by_strike": {k: round(v, 2) for k, v in sorted(gex_strikes.items())},
            "dex_by_strike": {k: round(v, 2) for k, v in sorted(dex_strikes.items())},
            "vex_by_strike": {k: round(v, 2) for k, v in sorted(vex_strikes.items())},
            "gex_flip_strike": gex_flip,
            "key_strike": key_strike,
            "dealer_positioning": "long_gamma" if total_gex > 0 else "short_gamma",
            "market_impact": "dampening" if total_gex > 0 else "amplifying",
            "dex_bias": "bullish" if total_dex > 0 else "bearish",
            "vex_note": (
                "Rising IV will push dealer delta more positive"
                if total_vex > 0
                else "Rising IV will push dealer delta more negative"
            ),
            "spot_price": spot,
        }

