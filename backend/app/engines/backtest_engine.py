"""
Bubby Vision — Backtest Engine (VectorBT)

Provides pre-built strategy backtesting (SMA crossover, RSI, MACD)
and custom entry/exit backtesting using VectorBT.

VectorBT is an optional dependency — install via: pip install .[backtest]
The engine gracefully degrades if VectorBT is not installed.
"""

from __future__ import annotations

import structlog
from typing import Optional

from app.models import BacktestResult

log = structlog.get_logger()

# Lazy import check for vectorbt
_VBT_AVAILABLE = False
try:
    import vectorbt as vbt  # noqa: F401
    _VBT_AVAILABLE = True
except ImportError:
    pass


class BacktestEngine:
    """Strategy backtesting engine powered by VectorBT."""

    @property
    def is_available(self) -> bool:
        return _VBT_AVAILABLE

    def _ensure_vbt(self):
        """Raise if VectorBT is not installed."""
        if not _VBT_AVAILABLE:
            raise RuntimeError(
                "VectorBT is not installed. Install with: pip install .[backtest]"
            )

    def _fetch_data(self, ticker: str, period: str = "2y", interval: str = "1d"):
        """Fetch OHLCV data using yfinance (bundled with VectorBT)."""
        import yfinance as yf
        df = yf.download(ticker, period=period, interval=interval, progress=False)
        if df.empty:
            raise ValueError(f"No data returned for {ticker}")
        return df

    def run_sma_crossover(
        self,
        ticker: str,
        fast: int = 10,
        slow: int = 50,
        period: str = "2y",
    ) -> BacktestResult:
        """Run SMA crossover strategy.

        Buy when fast SMA crosses above slow SMA, sell on cross below.

        Args:
            ticker: Stock ticker symbol.
            fast: Fast SMA window (default 10).
            slow: Slow SMA window (default 50).
            period: Backtest period (default 2y).
        """
        self._ensure_vbt()
        import vectorbt as vbt

        df = self._fetch_data(ticker, period=period)
        close = df["Close"]

        fast_ma = vbt.MA.run(close, window=fast)
        slow_ma = vbt.MA.run(close, window=slow)

        entries = fast_ma.ma_crossed_above(slow_ma)
        exits = fast_ma.ma_crossed_below(slow_ma)

        pf = vbt.Portfolio.from_signals(close, entries, exits, init_cash=10000)

        return self._portfolio_to_result(
            pf, f"SMA_{fast}_{slow}_crossover", ticker, period
        )

    def run_rsi_strategy(
        self,
        ticker: str,
        rsi_window: int = 14,
        overbought: float = 70,
        oversold: float = 30,
        period: str = "2y",
    ) -> BacktestResult:
        """Run RSI mean-reversion strategy.

        Buy when RSI drops below oversold, sell when RSI rises above overbought.

        Args:
            ticker: Stock ticker symbol.
            rsi_window: RSI lookback window (default 14).
            overbought: Sell threshold (default 70).
            oversold: Buy threshold (default 30).
            period: Backtest period (default 2y).
        """
        self._ensure_vbt()
        import vectorbt as vbt

        df = self._fetch_data(ticker, period=period)
        close = df["Close"]

        rsi = vbt.RSI.run(close, window=rsi_window)

        entries = rsi.rsi_below(oversold)
        exits = rsi.rsi_above(overbought)

        pf = vbt.Portfolio.from_signals(close, entries, exits, init_cash=10000)

        return self._portfolio_to_result(
            pf, f"RSI_{rsi_window}_{int(oversold)}_{int(overbought)}", ticker, period
        )

    def run_macd_strategy(
        self,
        ticker: str,
        fast: int = 12,
        slow: int = 26,
        signal: int = 9,
        period: str = "2y",
    ) -> BacktestResult:
        """Run MACD signal crossover strategy.

        Buy when MACD line crosses above signal line, sell on cross below.

        Args:
            ticker: Stock ticker symbol.
            fast: Fast EMA period (default 12).
            slow: Slow EMA period (default 26).
            signal: Signal line period (default 9).
            period: Backtest period (default 2y).
        """
        self._ensure_vbt()
        import vectorbt as vbt

        df = self._fetch_data(ticker, period=period)
        close = df["Close"]

        macd = vbt.MACD.run(close, fast_window=fast, slow_window=slow, signal_window=signal)

        entries = macd.macd_above(macd.signal)
        exits = macd.macd_below(macd.signal)

        pf = vbt.Portfolio.from_signals(close, entries, exits, init_cash=10000)

        return self._portfolio_to_result(
            pf, f"MACD_{fast}_{slow}_{signal}", ticker, period
        )

    def compare_strategies(
        self,
        ticker: str,
        period: str = "2y",
    ) -> list[BacktestResult]:
        """Run all built-in strategies on the same ticker and compare.

        Returns a list of BacktestResult sorted by total_return descending.
        """
        results = []

        strategies = [
            ("SMA Crossover 10/50", lambda: self.run_sma_crossover(ticker, 10, 50, period)),
            ("SMA Crossover 20/200", lambda: self.run_sma_crossover(ticker, 20, 200, period)),
            ("RSI 14", lambda: self.run_rsi_strategy(ticker, period=period)),
            ("MACD Default", lambda: self.run_macd_strategy(ticker, period=period)),
        ]

        for name, fn in strategies:
            try:
                result = fn()
                results.append(result)
            except Exception as e:
                log.warning("backtest.strategy_failed", strategy=name, error=str(e))

        # Sort by total return descending
        results.sort(key=lambda r: r.total_return, reverse=True)
        return results

    def _portfolio_to_result(
        self,
        pf,
        strategy_name: str,
        ticker: str,
        period: str,
    ) -> BacktestResult:
        """Convert a VectorBT Portfolio object into a BacktestResult model."""
        stats = pf.stats()

        return BacktestResult(
            strategy=strategy_name,
            ticker=ticker.upper(),
            period=period,
            total_return=round(float(stats.get("Total Return [%]", 0)), 2),
            sharpe_ratio=round(float(stats.get("Sharpe Ratio", 0)), 3) if stats.get("Sharpe Ratio") else None,
            max_drawdown=round(float(stats.get("Max Drawdown [%]", 0)), 2),
            win_rate=round(float(stats.get("Win Rate [%]", 0)), 2),
            total_trades=int(stats.get("Total Trades", 0)),
            avg_trade_duration=str(stats.get("Avg Winning Trade Duration", "N/A")),
            equity_final=round(float(pf.final_value()), 2),
            benchmark_return=round(float(stats.get("Benchmark Return [%]", 0)), 2) if stats.get("Benchmark Return [%]") else None,
        )

    def run_walk_forward(
        self,
        ticker: str,
        strategy: str = "sma_crossover",
        in_sample_pct: float = 0.7,
        period: str = "5y",
        n_folds: int = 3,
    ) -> dict:
        """Walk-forward backtest to prevent overfitting.

        Splits data into in-sample (optimization) and out-of-sample
        (validation) periods across multiple folds.

        Args:
            ticker: Stock ticker.
            strategy: Strategy name ('sma_crossover', 'rsi', 'macd').
            in_sample_pct: Fraction used for optimization (default 0.7).
            period: Total data period (default '5y').
            n_folds: Number of walk-forward folds (default 3).

        Returns:
            Dict with per-fold results, in-sample vs out-of-sample comparison.
        """
        self._ensure_vbt()
        import vectorbt as vbt
        import numpy as np

        df = self._fetch_data(ticker, period=period)
        close = df["Close"]
        total_bars = len(close)
        fold_size = total_bars // n_folds

        folds = []
        for fold in range(n_folds):
            start = fold * fold_size
            end = min((fold + 1) * fold_size, total_bars)
            fold_data = close.iloc[start:end]

            if len(fold_data) < 60:
                continue

            split_idx = int(len(fold_data) * in_sample_pct)
            in_sample = fold_data.iloc[:split_idx]
            out_sample = fold_data.iloc[split_idx:]

            # Run strategy on both samples
            in_result = self._run_strategy_on_series(
                in_sample, strategy, f"fold{fold + 1}_in_sample", ticker, period,
            )
            out_result = self._run_strategy_on_series(
                out_sample, strategy, f"fold{fold + 1}_out_sample", ticker, period,
            )

            folds.append({
                "fold": fold + 1,
                "in_sample_bars": split_idx,
                "out_sample_bars": len(fold_data) - split_idx,
                "in_sample": in_result,
                "out_sample": out_result,
                "robustness_ratio": round(
                    out_result.get("total_return", 0) / max(abs(in_result.get("total_return", 0)), 0.01), 2
                ),
            })

        # Average robustness across folds
        ratios = [f["robustness_ratio"] for f in folds if f.get("robustness_ratio")]
        avg_robustness = round(sum(ratios) / max(len(ratios), 1), 2)

        return {
            "ticker": ticker.upper(),
            "strategy": strategy,
            "period": period,
            "n_folds": len(folds),
            "in_sample_pct": in_sample_pct,
            "avg_robustness_ratio": avg_robustness,
            "assessment": (
                "robust" if avg_robustness > 0.6
                else "marginal" if avg_robustness > 0.3
                else "overfit"
            ),
            "folds": folds,
        }

    def _run_strategy_on_series(
        self,
        close_series,
        strategy: str,
        label: str,
        ticker: str,
        period: str,
    ) -> dict:
        """Run a strategy on a specific price series (helper for walk-forward)."""
        import vectorbt as vbt

        try:
            if strategy == "sma_crossover":
                fast_ma = vbt.MA.run(close_series, window=10)
                slow_ma = vbt.MA.run(close_series, window=50)
                entries = fast_ma.ma_crossed_above(slow_ma)
                exits = fast_ma.ma_crossed_below(slow_ma)
            elif strategy == "rsi":
                rsi = vbt.RSI.run(close_series, window=14)
                entries = rsi.rsi_below(30)
                exits = rsi.rsi_above(70)
            elif strategy == "macd":
                macd = vbt.MACD.run(close_series, fast_window=12, slow_window=26, signal_window=9)
                entries = macd.macd_above(macd.signal)
                exits = macd.macd_below(macd.signal)
            else:
                return {"error": f"Unknown strategy: {strategy}"}

            pf = vbt.Portfolio.from_signals(close_series, entries, exits, init_cash=10000)
            stats = pf.stats()

            return {
                "strategy": label,
                "total_return": round(float(stats.get("Total Return [%]", 0)), 2),
                "sharpe_ratio": round(float(stats.get("Sharpe Ratio", 0)), 3) if stats.get("Sharpe Ratio") else None,
                "max_drawdown": round(float(stats.get("Max Drawdown [%]", 0)), 2),
                "win_rate": round(float(stats.get("Win Rate [%]", 0)), 2),
                "total_trades": int(stats.get("Total Trades", 0)),
            }
        except Exception as e:
            log.warning("backtest.walk_forward_fold_failed", label=label, error=str(e))
            return {"strategy": label, "total_return": 0, "error": str(e)}

    def run_monte_carlo(
        self,
        ticker: str,
        strategy: str = "sma_crossover",
        n_simulations: int = 1000,
        period: str = "2y",
    ) -> dict:
        """Monte Carlo simulation — shuffle trade order to estimate risk.

        Runs the strategy once to get trade returns, then shuffles
        trade order N times to compute drawdown confidence intervals.

        Args:
            ticker: Stock ticker.
            strategy: Strategy name.
            n_simulations: Number of simulations (default 1000).
            period: Data period.

        Returns:
            Dict with drawdown percentiles, return distribution, and risk assessment.
        """
        self._ensure_vbt()
        import vectorbt as vbt
        import numpy as np

        df = self._fetch_data(ticker, period=period)
        close = df["Close"]

        # Run base strategy to get trade returns
        try:
            if strategy == "sma_crossover":
                fast_ma = vbt.MA.run(close, window=10)
                slow_ma = vbt.MA.run(close, window=50)
                entries = fast_ma.ma_crossed_above(slow_ma)
                exits = fast_ma.ma_crossed_below(slow_ma)
            elif strategy == "rsi":
                rsi = vbt.RSI.run(close, window=14)
                entries = rsi.rsi_below(30)
                exits = rsi.rsi_above(70)
            elif strategy == "macd":
                macd = vbt.MACD.run(close, fast_window=12, slow_window=26, signal_window=9)
                entries = macd.macd_above(macd.signal)
                exits = macd.macd_below(macd.signal)
            else:
                return {"error": f"Unknown strategy: {strategy}"}

            pf = vbt.Portfolio.from_signals(close, entries, exits, init_cash=10000)
        except Exception as e:
            return {"error": f"Strategy execution failed: {str(e)}"}

        # Extract individual trade returns
        try:
            trades = pf.trades.records_readable
            if trades.empty or len(trades) < 3:
                return {
                    "ticker": ticker.upper(),
                    "strategy": strategy,
                    "error": "insufficient_trades",
                    "total_trades": len(trades) if not trades.empty else 0,
                }
            trade_returns = trades["Return"].values
        except Exception:
            return {"error": "Could not extract trade returns"}

        # Monte Carlo: shuffle trade order, compute equity curves
        np.random.seed(42)
        max_drawdowns = []
        final_returns = []
        initial_equity = 10000.0

        for _ in range(n_simulations):
            shuffled = np.random.permutation(trade_returns)
            equity = [initial_equity]

            for ret in shuffled:
                equity.append(equity[-1] * (1 + ret))

            equity_arr = np.array(equity)
            running_max = np.maximum.accumulate(equity_arr)
            drawdowns = (equity_arr - running_max) / running_max * 100
            max_drawdowns.append(float(np.min(drawdowns)))
            final_returns.append(float((equity_arr[-1] / initial_equity - 1) * 100))

        # Compute percentiles
        dd_5 = round(float(np.percentile(max_drawdowns, 5)), 2)
        dd_50 = round(float(np.percentile(max_drawdowns, 50)), 2)
        dd_95 = round(float(np.percentile(max_drawdowns, 95)), 2)
        ret_5 = round(float(np.percentile(final_returns, 5)), 2)
        ret_50 = round(float(np.percentile(final_returns, 50)), 2)
        ret_95 = round(float(np.percentile(final_returns, 95)), 2)

        return {
            "ticker": ticker.upper(),
            "strategy": strategy,
            "period": period,
            "n_simulations": n_simulations,
            "total_trades": len(trade_returns),
            "base_return": round(float(np.sum(trade_returns) * 100), 2),
            "drawdown_percentiles": {
                "p5_worst": dd_5,
                "p50_median": dd_50,
                "p95_best": dd_95,
            },
            "return_percentiles": {
                "p5_worst": ret_5,
                "p50_median": ret_50,
                "p95_best": ret_95,
            },
            "risk_assessment": (
                "high_risk" if dd_5 < -30
                else "moderate_risk" if dd_5 < -15
                else "low_risk"
            ),
            "profit_probability": round(float(np.mean([r > 0 for r in final_returns]) * 100), 1),
        }
