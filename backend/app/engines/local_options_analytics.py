"""
Bubby Vision — Local Options Analytics Engine

Replaces QuantData paid API with locally-computed options analytics
using yFinance options chain data + OptionsEngine computations.

Provides:
  - Unusual activity detection (volume/OI anomalies)
  - GEX/DEX exposure per strike
  - IV volatility skew across strikes
  - IV term structure (vol surface across expirations)
  - Net flow proxy (call vs put premium imbalance)
  - Options heatmap (strike × expiry grid)
  - Gainers/losers by options premium
"""

from __future__ import annotations

import math
from datetime import datetime
from typing import Optional

import structlog

from app.data.yfinance_client import YFinanceClient
from app.engines.options_engine import OptionsEngine
from app.models import OptionsChain, OptionContract

_log = structlog.get_logger(__name__)


class LocalOptionsAnalytics:
    """Compute options analytics locally from yFinance chains.

    Replaces QuantData endpoints that require a paid subscription
    by computing equivalent metrics from free options chain data.
    """

    def __init__(self, yfinance: YFinanceClient, options_engine: OptionsEngine):
        self._yf = yfinance
        self._oe = options_engine

    # ──────────────────────────────────────────────
    # Helpers
    # ──────────────────────────────────────────────

    def _fetch_chain(
        self,
        ticker: str,
        expiration: Optional[str] = None,
    ) -> OptionsChain:
        """Fetch options chain from yFinance (synchronous)."""
        return self._yf.get_options_chain(ticker, expiration)

    def _mid_price(self, c: OptionContract) -> float:
        """Mid-price for a contract, falling back to last price."""
        if c.bid > 0 and c.ask > 0:
            return (c.bid + c.ask) / 2
        return c.last_price

    # ──────────────────────────────────────────────
    # 1. Unusual Activity
    # ──────────────────────────────────────────────

    async def compute_unusual_activity(
        self,
        ticker: str,
        volume_threshold: float = 3.0,
    ) -> list[dict]:
        """Detect unusual options activity from yFinance chain.

        Flags contracts where volume > threshold × open interest.
        Delegates to OptionsEngine.detect_unusual_activity.
        """
        try:
            chain = self._fetch_chain(ticker)
            if not chain.calls and not chain.puts:
                return []

            unusual = self._oe.detect_unusual_activity(
                chain, volume_threshold=volume_threshold,
            )

            # Enrich with estimated premium
            for entry in unusual:
                entry["ticker"] = ticker
                entry["estimated_premium"] = round(
                    entry["volume"] * self._estimate_contract_premium(
                        chain, entry["contract"],
                    ),
                    0,
                )

            return unusual

        except Exception as exc:
            _log.warning(
                "local_analytics.unusual_activity_error",
                ticker=ticker,
                error=str(exc),
            )
            return []

    def _estimate_contract_premium(
        self, chain: OptionsChain, contract_symbol: str,
    ) -> float:
        """Estimate premium for a contract symbol from chain data."""
        for c in chain.calls + chain.puts:
            if c.contract_symbol == contract_symbol:
                return self._mid_price(c) * 100
        return 0.0

    # ──────────────────────────────────────────────
    # 2. Options Exposure (GEX / DEX / VEX / CHEX)
    # ──────────────────────────────────────────────

    async def compute_gex_exposure(
        self,
        ticker: str,
        exposure_type: str = "gex",
        expiration: Optional[str] = None,
    ) -> dict:
        """Compute per-strike options exposure from yFinance chain.

        Supports:
          gex — Gamma Exposure (Gamma × OI × 100 × Spot²)
          dex — Delta Exposure (Delta × OI × 100 × Spot)
          vex — Vega Exposure (Vega × OI × 100)
          chex — Charm Exposure (Charm × OI × 100) [requires higher greeks]
        """
        try:
            chain = self._fetch_chain(ticker, expiration)
            spot = chain.underlying_price
            if not spot or (not chain.calls and not chain.puts):
                return {"ticker": ticker, "type": exposure_type, "data": []}

            # Use existing GEX computation for gex type
            if exposure_type == "gex":
                gex_data = self._oe.compute_gex(chain)
                return {
                    "ticker": ticker,
                    "type": "gex",
                    "underlying_price": spot,
                    "data": gex_data,
                }

            # Compute other exposure types manually
            exposure_by_strike: dict[float, float] = {}

            for contract in chain.calls + chain.puts:
                greeks = contract.greeks
                oi = contract.open_interest
                if oi <= 0:
                    continue

                sign = 1 if contract.option_type == "call" else -1
                strike = contract.strike

                if exposure_type == "dex":
                    delta = greeks.delta or 0.0
                    value = delta * oi * 100 * spot * sign
                elif exposure_type == "vex":
                    vega = greeks.vega or 0.0
                    value = vega * oi * 100 * sign
                elif exposure_type == "chex":
                    # Charm not available from yFinance;
                    # approximate as dDelta/dTime ≈ -theta/spot (rough)
                    theta = greeks.theta or 0.0
                    value = (-theta / spot if spot > 0 else 0.0) * oi * 100 * sign
                else:
                    value = 0.0

                exposure_by_strike[strike] = (
                    exposure_by_strike.get(strike, 0.0) + value
                )

            data = [
                {"strike": k, "exposure": round(v, 2)}
                for k, v in sorted(exposure_by_strike.items())
            ]

            return {
                "ticker": ticker,
                "type": exposure_type,
                "underlying_price": spot,
                "data": data,
            }

        except Exception as exc:
            _log.warning(
                "local_analytics.exposure_error",
                ticker=ticker,
                type=exposure_type,
                error=str(exc),
            )
            return {"ticker": ticker, "type": exposure_type, "data": []}

    # ──────────────────────────────────────────────
    # 3. Volatility Skew
    # ──────────────────────────────────────────────

    async def compute_vol_skew(
        self,
        ticker: str,
        expiration: Optional[str] = None,
    ) -> dict:
        """IV skew across strikes for a given expiration.

        Returns per-strike IV for both calls and puts, plus
        skew metrics (OTM put IV vs OTM call IV).
        """
        try:
            chain = self._fetch_chain(ticker, expiration)
            spot = chain.underlying_price
            if not spot or (not chain.calls and not chain.puts):
                return {"ticker": ticker, "skew": [], "metrics": {}}

            skew_data = []

            # Collect call IVs
            for c in chain.calls:
                iv = c.greeks.implied_volatility
                if iv and iv > 0:
                    moneyness = round((c.strike / spot - 1) * 100, 2) if spot else 0
                    skew_data.append({
                        "strike": c.strike,
                        "type": "call",
                        "iv": round(iv, 4),
                        "moneyness_pct": moneyness,
                        "volume": c.volume,
                        "open_interest": c.open_interest,
                    })

            # Collect put IVs
            for p in chain.puts:
                iv = p.greeks.implied_volatility
                if iv and iv > 0:
                    moneyness = round((p.strike / spot - 1) * 100, 2) if spot else 0
                    skew_data.append({
                        "strike": p.strike,
                        "type": "put",
                        "iv": round(iv, 4),
                        "moneyness_pct": moneyness,
                        "volume": p.volume,
                        "open_interest": p.open_interest,
                    })

            # Compute aggregate skew metric (25-delta equivalent)
            otm_put_ivs = [
                c.greeks.implied_volatility
                for c in chain.puts
                if c.greeks.implied_volatility
                and c.greeks.implied_volatility > 0
                and c.strike < spot
            ]
            otm_call_ivs = [
                c.greeks.implied_volatility
                for c in chain.calls
                if c.greeks.implied_volatility
                and c.greeks.implied_volatility > 0
                and c.strike > spot
            ]

            metrics = {}
            if otm_put_ivs and otm_call_ivs:
                avg_put_iv = sum(otm_put_ivs) / len(otm_put_ivs)
                avg_call_iv = sum(otm_call_ivs) / len(otm_call_ivs)
                metrics = self._oe.iv_skew(avg_call_iv, avg_put_iv)
                metrics["avg_otm_put_iv"] = round(avg_put_iv, 4)
                metrics["avg_otm_call_iv"] = round(avg_call_iv, 4)

            return {
                "ticker": ticker,
                "underlying_price": spot,
                "expiration": expiration or (chain.expirations[0] if chain.expirations else None),
                "skew": sorted(skew_data, key=lambda x: x["strike"]),
                "metrics": metrics,
            }

        except Exception as exc:
            _log.warning(
                "local_analytics.vol_skew_error",
                ticker=ticker,
                error=str(exc),
            )
            return {"ticker": ticker, "skew": [], "metrics": {}}

    # ──────────────────────────────────────────────
    # 4. Volatility Surface / Term Structure
    # ──────────────────────────────────────────────

    async def compute_vol_surface(
        self,
        ticker: str,
        date: Optional[str] = None,
    ) -> dict:
        """IV term structure across multiple expirations.

        Computes ATM IV per expiration to show contango/backwardation.
        The `date` param is accepted for API compatibility but not used
        (yFinance only provides current snapshot, not historical IV).
        """
        try:
            import yfinance as yf

            t = yf.Ticker(ticker)
            expirations = list(t.options or [])
            info = t.info or {}
            spot = info.get("currentPrice") or info.get("regularMarketPrice", 0.0)

            if not expirations or not spot:
                return {"ticker": ticker, "term_structure": [], "analysis": {}}

            # Fetch ATM IV for each expiration (up to 8 nearest)
            exp_ivs: list[tuple[str, float]] = []
            for exp in expirations[:8]:
                try:
                    chain = self._fetch_chain(ticker, exp)
                    atm_iv = self._get_atm_iv(chain, spot)
                    if atm_iv and atm_iv > 0:
                        exp_ivs.append((exp, atm_iv))
                except Exception:
                    continue

            if not exp_ivs:
                return {"ticker": ticker, "term_structure": [], "analysis": {}}

            # Build term structure data
            term_structure = []
            for exp, iv in exp_ivs:
                dte = self._days_to_expiry(exp)
                term_structure.append({
                    "expiration": exp,
                    "dte": dte,
                    "atm_iv": round(iv, 4),
                    "annualized_iv": round(iv * 100, 2),
                })

            # Use OptionsEngine.term_structure for analysis
            analysis = self._oe.term_structure(exp_ivs)

            return {
                "ticker": ticker,
                "underlying_price": spot,
                "term_structure": term_structure,
                "analysis": analysis,
            }

        except Exception as exc:
            _log.warning(
                "local_analytics.vol_surface_error",
                ticker=ticker,
                error=str(exc),
            )
            return {"ticker": ticker, "term_structure": [], "analysis": {}}

    def _get_atm_iv(self, chain: OptionsChain, spot: float) -> Optional[float]:
        """Get at-the-money IV from a chain (average of nearest call + put)."""
        best_call_iv = None
        best_call_dist = float("inf")
        best_put_iv = None
        best_put_dist = float("inf")

        for c in chain.calls:
            dist = abs(c.strike - spot)
            iv = c.greeks.implied_volatility
            if iv and iv > 0 and dist < best_call_dist:
                best_call_dist = dist
                best_call_iv = iv

        for p in chain.puts:
            dist = abs(p.strike - spot)
            iv = p.greeks.implied_volatility
            if iv and iv > 0 and dist < best_put_dist:
                best_put_dist = dist
                best_put_iv = iv

        if best_call_iv and best_put_iv:
            return (best_call_iv + best_put_iv) / 2
        return best_call_iv or best_put_iv

    @staticmethod
    def _days_to_expiry(exp_str: str) -> int:
        """Days to expiration from YYYY-MM-DD string."""
        try:
            exp_date = datetime.strptime(exp_str, "%Y-%m-%d")
            return max(0, (exp_date - datetime.now()).days)
        except ValueError:
            return 0

    # ──────────────────────────────────────────────
    # 5. Net Flow Proxy (Call vs Put Premium)
    # ──────────────────────────────────────────────

    async def compute_net_flow_proxy(
        self,
        ticker: Optional[str] = None,
        limit: int = 50,
    ) -> dict:
        """Approximate net flow from chain snapshot (premium imbalance).

        Computes:
          call_premium = Σ(call_volume × mid_price × 100)
          put_premium  = Σ(put_volume × mid_price × 100)
          net_drift    = call_premium - put_premium

        Note: This is a snapshot proxy, not real-time flow.
        """
        if not ticker:
            return {
                "source": "local_yfinance",
                "note": "Market-wide flow requires QuantData. Specify a ticker.",
                "data": [],
            }

        try:
            chain = self._fetch_chain(ticker)
            if not chain.calls and not chain.puts:
                return {
                    "ticker": ticker,
                    "source": "local_yfinance",
                    "call_premium": 0,
                    "put_premium": 0,
                    "net_premium": 0,
                    "sentiment": "neutral",
                    "top_contracts": [],
                }

            call_premium = 0.0
            put_premium = 0.0
            contracts: list[dict] = []

            for c in chain.calls:
                prem = c.volume * self._mid_price(c) * 100
                call_premium += prem
                if c.volume > 0:
                    contracts.append({
                        "contract": c.contract_symbol,
                        "type": "call",
                        "strike": c.strike,
                        "expiration": c.expiration.strftime("%Y-%m-%d"),
                        "volume": c.volume,
                        "premium": round(prem, 0),
                        "iv": c.greeks.implied_volatility,
                    })

            for p in chain.puts:
                prem = p.volume * self._mid_price(p) * 100
                put_premium += prem
                if p.volume > 0:
                    contracts.append({
                        "contract": p.contract_symbol,
                        "type": "put",
                        "strike": p.strike,
                        "expiration": p.expiration.strftime("%Y-%m-%d"),
                        "volume": p.volume,
                        "premium": round(prem, 0),
                        "iv": p.greeks.implied_volatility,
                    })

            net = call_premium - put_premium
            ratio = call_premium / put_premium if put_premium > 0 else float("inf")

            if ratio > 1.5:
                sentiment = "bullish"
            elif ratio > 1.1:
                sentiment = "slightly_bullish"
            elif ratio > 0.9:
                sentiment = "neutral"
            elif ratio > 0.67:
                sentiment = "slightly_bearish"
            else:
                sentiment = "bearish"

            # Top contracts by premium
            contracts.sort(key=lambda x: x["premium"], reverse=True)

            return {
                "ticker": ticker,
                "source": "local_yfinance",
                "underlying_price": chain.underlying_price,
                "call_premium": round(call_premium, 0),
                "put_premium": round(put_premium, 0),
                "net_premium": round(net, 0),
                "call_put_ratio": round(ratio, 3) if not math.isinf(ratio) else None,
                "sentiment": sentiment,
                "top_contracts": contracts[:limit],
            }

        except Exception as exc:
            _log.warning(
                "local_analytics.net_flow_error",
                ticker=ticker,
                error=str(exc),
            )
            return {
                "ticker": ticker,
                "source": "local_yfinance",
                "call_premium": 0,
                "put_premium": 0,
                "net_premium": 0,
                "sentiment": "neutral",
                "top_contracts": [],
            }

    # ──────────────────────────────────────────────
    # 6. Options Heatmap
    # ──────────────────────────────────────────────

    async def compute_options_heatmap(
        self,
        ticker: str,
        metric: str = "gex",
        expiration: Optional[str] = None,
    ) -> dict:
        """Build strike × expiry grid for OI, volume, GEX, or IV.

        If expiration is specified, returns single-expiry grid.
        Otherwise builds multi-expiry surface (up to 6 expirations).
        """
        try:
            import yfinance as yf

            t = yf.Ticker(ticker)
            expirations = list(t.options or [])
            info = t.info or {}
            spot = info.get("currentPrice") or info.get("regularMarketPrice", 0.0)

            if not expirations or not spot:
                return {"ticker": ticker, "metric": metric, "grid": []}

            target_exps = ([expiration] if expiration and expiration in expirations
                           else expirations[:6])

            grid: list[dict] = []

            for exp in target_exps:
                try:
                    chain = self._fetch_chain(ticker, exp)
                except Exception:
                    continue

                for contract in chain.calls + chain.puts:
                    oi = contract.open_interest
                    vol = contract.volume
                    iv = contract.greeks.implied_volatility or 0.0
                    gamma = contract.greeks.gamma or 0.0

                    if metric == "oi":
                        value = oi
                    elif metric == "volume":
                        value = vol
                    elif metric == "iv":
                        value = round(iv * 100, 2) if iv else 0.0
                    elif metric == "gex":
                        sign = 1 if contract.option_type == "call" else -1
                        value = round(
                            gamma * oi * 100 * spot * spot * sign / 1e6, 4,
                        )
                    elif metric == "dex":
                        delta = contract.greeks.delta or 0.0
                        sign = 1 if contract.option_type == "call" else -1
                        value = round(
                            delta * oi * 100 * spot * sign / 1e6, 4,
                        )
                    elif metric == "vex":
                        vega = contract.greeks.vega or 0.0
                        sign = 1 if contract.option_type == "call" else -1
                        value = round(vega * oi * 100 * sign / 1e3, 4)
                    else:
                        value = oi  # fallback

                    grid.append({
                        "strike": contract.strike,
                        "expiration": exp,
                        "type": contract.option_type,
                        "value": value,
                        "oi": oi,
                        "volume": vol,
                        "iv": round(iv, 4) if iv else None,
                    })

            return {
                "ticker": ticker,
                "metric": metric,
                "underlying_price": spot,
                "expirations": target_exps,
                "grid": grid,
            }

        except Exception as exc:
            _log.warning(
                "local_analytics.heatmap_error",
                ticker=ticker,
                metric=metric,
                error=str(exc),
            )
            return {"ticker": ticker, "metric": metric, "grid": []}

    # ──────────────────────────────────────────────
    # 7. Gainers / Losers by Options Premium
    # ──────────────────────────────────────────────

    async def compute_gainers_losers(
        self,
        direction: str = "bullish",
        limit: int = 25,
    ) -> list[dict]:
        """Compute gainers/losers by options premium sentiment.

        Scans a watchlist of popular tickers, computes call vs put
        premium, and ranks by net bullish or bearish premium.

        Note: This is slower than QuantData since it fetches chains
        sequentially. Results are cached by the data engine layer.
        """
        # Popular tickers to scan
        watchlist = [
            "AAPL", "MSFT", "NVDA", "AMZN", "META", "GOOGL", "TSLA",
            "AMD", "SPY", "QQQ", "IWM", "NFLX", "COIN", "PLTR", "SOFI",
            "MU", "INTC", "BAC", "JPM", "XOM", "DIS", "NIO", "BABA",
            "MARA", "UBER",
        ]

        results: list[dict] = []

        for ticker in watchlist:
            try:
                chain = self._fetch_chain(ticker)
                if not chain.calls and not chain.puts:
                    continue

                call_prem = sum(
                    c.volume * self._mid_price(c) * 100 for c in chain.calls
                )
                put_prem = sum(
                    p.volume * self._mid_price(p) * 100 for p in chain.puts
                )
                net = call_prem - put_prem

                results.append({
                    "ticker": ticker,
                    "call_premium": round(call_prem, 0),
                    "put_premium": round(put_prem, 0),
                    "net_premium": round(net, 0),
                    "underlying_price": chain.underlying_price,
                    "sentiment": (
                        "bullish" if net > 0 else "bearish"
                    ),
                })
            except Exception:
                continue

        # Sort by net premium
        if direction == "bullish":
            results.sort(key=lambda x: x["net_premium"], reverse=True)
        else:
            results.sort(key=lambda x: x["net_premium"])

        return results[:limit]
