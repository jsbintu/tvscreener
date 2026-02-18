"""
Bubby Vision — Chart Engine

Generates TradingView-quality candlestick charts with indicators using Plotly.
Produces interactive HTML or static PNG for agent responses and infographics.

Visual DNA follows TradingView dark theme:
  - Background: #131722
  - Bullish: #26a69a
  - Bearish: #ef5350
  - Grid: #363c4e
  - Text: #d1d4dc
"""

from __future__ import annotations

import io
from typing import Optional

import plotly.graph_objects as go
from plotly.subplots import make_subplots

from app.models import OHLCV, TechnicalIndicators


# ──────────────────────────────────────────────
# TradingView Color Constants
# ──────────────────────────────────────────────

TV_BG = "#131722"
TV_PANEL_BG = "#1e222d"
TV_GRID = "#363c4e"
TV_TEXT = "#d1d4dc"
TV_TEXT_DIM = "#787b86"
TV_BULLISH = "#26a69a"
TV_BEARISH = "#ef5350"
TV_VOLUME_BULL = "rgba(38, 166, 154, 0.4)"
TV_VOLUME_BEAR = "rgba(239, 83, 80, 0.4)"
TV_SMA_20 = "#f7a21b"      # Orange
TV_SMA_50 = "#2196f3"      # Blue
TV_SMA_200 = "#e040fb"     # Purple
TV_EMA_8 = "#00e5ff"       # Cyan
TV_EMA_21 = "#ff6d00"      # Deep orange
TV_BB_FILL = "rgba(33, 150, 243, 0.1)"
TV_BB_LINE = "rgba(33, 150, 243, 0.5)"
TV_VWAP = "#ffeb3b"        # Yellow
TV_SUPPORT = "#26a69a"
TV_RESISTANCE = "#ef5350"


class ChartEngine:
    """Generate professional TradingView-style charts with Plotly."""

    # ── Main Chart Generation ──

    def candlestick_chart(
        self,
        bars: list[OHLCV],
        ticker: str = "",
        indicators: Optional[TechnicalIndicators] = None,
        show_volume: bool = True,
        show_sma: bool = True,
        show_bb: bool = False,
        show_vwap: bool = False,
        show_rsi: bool = False,
        show_macd: bool = False,
        support_levels: Optional[list[float]] = None,
        resistance_levels: Optional[list[float]] = None,
        height: int = 700,
        width: int = 1200,
    ) -> go.Figure:
        """Create a professional candlestick chart with optional overlays.

        Args:
            bars: OHLCV data bars.
            ticker: Stock symbol for the title.
            indicators: Pre-computed technical indicators (for overlay values).
            show_volume: Show volume subplot.
            show_sma: Overlay SMA 20/50/200.
            show_bb: Overlay Bollinger Bands.
            show_vwap: Overlay VWAP line.
            show_rsi: Show RSI subplot.
            show_macd: Show MACD subplot.
            support_levels: Horizontal support lines.
            resistance_levels: Horizontal resistance lines.
            height: Chart height in pixels.
            width: Chart width in pixels.

        Returns:
            Plotly Figure object.
        """
        if not bars:
            return self._empty_chart(ticker)

        # Determine subplot layout
        rows, row_heights, subplot_titles = self._layout_subplots(
            show_volume, show_rsi, show_macd
        )

        fig = make_subplots(
            rows=rows,
            cols=1,
            shared_xaxes=True,
            vertical_spacing=0.03,
            row_heights=row_heights,
            subplot_titles=subplot_titles,
        )

        # Extract data
        dates = [b.timestamp for b in bars]
        opens = [b.open for b in bars]
        highs = [b.high for b in bars]
        lows = [b.low for b in bars]
        closes = [b.close for b in bars]
        volumes = [b.volume for b in bars]

        # ── Candlesticks ──
        fig.add_trace(
            go.Candlestick(
                x=dates,
                open=opens,
                high=highs,
                low=lows,
                close=closes,
                increasing_line_color=TV_BULLISH,
                decreasing_line_color=TV_BEARISH,
                increasing_fillcolor=TV_BULLISH,
                decreasing_fillcolor=TV_BEARISH,
                name="Price",
                showlegend=False,
            ),
            row=1, col=1,
        )

        # ── Volume ──
        current_row = 1
        if show_volume:
            current_row += 1
            colors = [
                TV_VOLUME_BULL if c >= o else TV_VOLUME_BEAR
                for o, c in zip(opens, closes)
            ]
            fig.add_trace(
                go.Bar(
                    x=dates,
                    y=volumes,
                    marker_color=colors,
                    name="Volume",
                    showlegend=False,
                ),
                row=current_row, col=1,
            )

        # ── SMA Overlays ──
        if show_sma and len(bars) >= 20:
            sma_configs = [
                (20, TV_SMA_20, "SMA 20"),
                (50, TV_SMA_50, "SMA 50"),
                (200, TV_SMA_200, "SMA 200"),
            ]
            for period, color, name in sma_configs:
                if len(closes) >= period:
                    sma = self._compute_sma(closes, period)
                    fig.add_trace(
                        go.Scatter(
                            x=dates,
                            y=sma,
                            mode="lines",
                            line=dict(color=color, width=1),
                            name=name,
                        ),
                        row=1, col=1,
                    )

        # ── Bollinger Bands ──
        if show_bb and len(bars) >= 20:
            bb_mid = self._compute_sma(closes, 20)
            bb_std = self._compute_rolling_std(closes, 20)
            bb_upper = [m + 2 * s if m and s else None for m, s in zip(bb_mid, bb_std)]
            bb_lower = [m - 2 * s if m and s else None for m, s in zip(bb_mid, bb_std)]

            fig.add_trace(
                go.Scatter(
                    x=dates, y=bb_upper, mode="lines",
                    line=dict(color=TV_BB_LINE, width=1),
                    name="BB Upper", showlegend=False,
                ),
                row=1, col=1,
            )
            fig.add_trace(
                go.Scatter(
                    x=dates, y=bb_lower, mode="lines",
                    line=dict(color=TV_BB_LINE, width=1),
                    fill="tonexty",
                    fillcolor=TV_BB_FILL,
                    name="BB Lower", showlegend=False,
                ),
                row=1, col=1,
            )

        # ── VWAP ──
        if show_vwap:
            vwap = self._compute_vwap(highs, lows, closes, volumes)
            fig.add_trace(
                go.Scatter(
                    x=dates, y=vwap, mode="lines",
                    line=dict(color=TV_VWAP, width=1, dash="dot"),
                    name="VWAP",
                ),
                row=1, col=1,
            )

        # ── Support / Resistance ──
        if support_levels:
            for sl in support_levels:
                fig.add_hline(
                    y=sl, line_dash="dash", line_color=TV_SUPPORT,
                    line_width=1, annotation_text=f"S: ${sl:.2f}",
                    annotation_position="bottom right",
                    annotation_font_color=TV_SUPPORT,
                    row=1, col=1,
                )
        if resistance_levels:
            for rl in resistance_levels:
                fig.add_hline(
                    y=rl, line_dash="dash", line_color=TV_RESISTANCE,
                    line_width=1, annotation_text=f"R: ${rl:.2f}",
                    annotation_position="top right",
                    annotation_font_color=TV_RESISTANCE,
                    row=1, col=1,
                )

        # ── RSI Subplot ──
        if show_rsi and len(bars) >= 14:
            current_row += 1
            rsi = self._compute_rsi(closes, 14)
            fig.add_trace(
                go.Scatter(
                    x=dates, y=rsi, mode="lines",
                    line=dict(color="#e040fb", width=1.5),
                    name="RSI (14)",
                ),
                row=current_row, col=1,
            )
            # Overbought / Oversold zones
            fig.add_hline(y=70, line_dash="dot", line_color=TV_BEARISH,
                          line_width=0.5, row=current_row, col=1)
            fig.add_hline(y=30, line_dash="dot", line_color=TV_BULLISH,
                          line_width=0.5, row=current_row, col=1)
            fig.add_hline(y=50, line_dash="dot", line_color=TV_TEXT_DIM,
                          line_width=0.5, row=current_row, col=1)

        # ── MACD Subplot ──
        if show_macd and len(bars) >= 26:
            current_row += 1
            macd_line, signal_line, histogram = self._compute_macd(closes)
            fig.add_trace(
                go.Scatter(
                    x=dates, y=macd_line, mode="lines",
                    line=dict(color="#2196f3", width=1.5),
                    name="MACD",
                ),
                row=current_row, col=1,
            )
            fig.add_trace(
                go.Scatter(
                    x=dates, y=signal_line, mode="lines",
                    line=dict(color="#ff5722", width=1),
                    name="Signal",
                ),
                row=current_row, col=1,
            )
            hist_colors = [
                TV_BULLISH if (h or 0) >= 0 else TV_BEARISH for h in histogram
            ]
            fig.add_trace(
                go.Bar(
                    x=dates, y=histogram,
                    marker_color=hist_colors,
                    name="Histogram",
                    showlegend=False,
                ),
                row=current_row, col=1,
            )

        # ── Apply TradingView Theme ──
        self._apply_tv_theme(fig, ticker, rows, height, width)

        return fig

    # ── Quick Chart Methods ──

    def quick_chart(self, bars: list[OHLCV], ticker: str = "") -> go.Figure:
        """Generate a simple candlestick + volume chart."""
        return self.candlestick_chart(
            bars, ticker=ticker, show_volume=True, show_sma=True,
        )

    def full_analysis_chart(
        self, bars: list[OHLCV], ticker: str = "",
        support: Optional[list[float]] = None,
        resistance: Optional[list[float]] = None,
    ) -> go.Figure:
        """Generate a full analysis chart with all overlays and subplots."""
        return self.candlestick_chart(
            bars, ticker=ticker,
            show_volume=True, show_sma=True, show_bb=True,
            show_vwap=True, show_rsi=True, show_macd=True,
            support_levels=support, resistance_levels=resistance,
            height=900,
        )

    def to_html(self, fig: go.Figure) -> str:
        """Convert a chart to an embeddable HTML string."""
        return fig.to_html(
            include_plotlyjs="cdn",
            full_html=False,
            config={"displayModeBar": True, "scrollZoom": True},
        )

    def to_png_bytes(self, fig: go.Figure, width: int = 1200, height: int = 700) -> bytes:
        """Export chart to PNG bytes (requires kaleido)."""
        return fig.to_image(format="png", width=width, height=height, engine="kaleido")

    # ──────────────────────────────────────────
    # GEX Profile Chart
    # ──────────────────────────────────────────

    def gex_chart(
        self,
        gex_by_strike: dict[float, float],
        spot_price: float,
        ticker: str = "",
    ) -> go.Figure:
        """Create a GEX (Gamma Exposure) profile chart.

        Args:
            gex_by_strike: Dict mapping strike → GEX value.
            spot_price: Current stock price.
            ticker: Stock symbol.
        """
        strikes = sorted(gex_by_strike.keys())
        values = [gex_by_strike[k] for k in strikes]
        colors = [TV_BULLISH if v >= 0 else TV_BEARISH for v in values]

        fig = go.Figure()
        fig.add_trace(
            go.Bar(
                x=strikes, y=values,
                marker_color=colors,
                name="GEX",
            )
        )
        fig.add_vline(
            x=spot_price, line_dash="solid",
            line_color=TV_VWAP, line_width=2,
            annotation_text=f"Spot: ${spot_price:.2f}",
            annotation_font_color=TV_VWAP,
        )

        fig.update_layout(
            title=f"{ticker} Gamma Exposure Profile" if ticker else "GEX Profile",
            xaxis_title="Strike Price",
            yaxis_title="Gamma Exposure ($)",
            template="plotly_dark",
            paper_bgcolor=TV_BG,
            plot_bgcolor=TV_BG,
            font=dict(color=TV_TEXT, size=12),
            height=500,
        )
        return fig

    # ──────────────────────────────────────────
    # Private Helpers
    # ──────────────────────────────────────────

    def _layout_subplots(
        self, show_volume: bool, show_rsi: bool, show_macd: bool,
    ) -> tuple[int, list[float], list[str]]:
        """Determine subplot rows and heights."""
        rows = 1
        heights = [0.6]
        titles = [""]

        if show_volume:
            rows += 1
            heights.append(0.15)
            titles.append("Volume")
        if show_rsi:
            rows += 1
            heights.append(0.12)
            titles.append("RSI")
        if show_macd:
            rows += 1
            heights.append(0.13)
            titles.append("MACD")

        # Normalize heights to sum to 1
        total = sum(heights)
        heights = [h / total for h in heights]

        return rows, heights, titles

    def _apply_tv_theme(
        self, fig: go.Figure, ticker: str, rows: int,
        height: int, width: int,
    ):
        """Apply TradingView dark theme to a figure."""
        fig.update_layout(
            title=dict(
                text=f"<b>{ticker}</b>" if ticker else "",
                x=0.5, xanchor="center",
                font=dict(size=18, color=TV_TEXT),
            ),
            template="plotly_dark",
            paper_bgcolor=TV_BG,
            plot_bgcolor=TV_BG,
            font=dict(color=TV_TEXT, family="Inter, system-ui, sans-serif", size=11),
            height=height,
            width=width,
            margin=dict(l=60, r=30, t=50, b=30),
            legend=dict(
                bgcolor="rgba(30, 34, 45, 0.8)",
                bordercolor=TV_GRID,
                font=dict(size=10, color=TV_TEXT_DIM),
                orientation="h",
                yanchor="bottom", y=1.02,
                xanchor="right", x=1,
            ),
            xaxis_rangeslider_visible=False,
        )

        # Apply grid styling to all axes
        for i in range(1, rows + 1):
            y_axis = f"yaxis{i}" if i > 1 else "yaxis"
            fig.update_layout(**{
                y_axis: dict(
                    gridcolor=TV_GRID,
                    gridwidth=0.5,
                    zerolinecolor=TV_GRID,
                    tickfont=dict(color=TV_TEXT_DIM, size=10),
                ),
            })

        fig.update_xaxes(
            gridcolor=TV_GRID, gridwidth=0.5,
            tickfont=dict(color=TV_TEXT_DIM, size=10),
            showgrid=True,
        )

    def _empty_chart(self, ticker: str) -> go.Figure:
        """Return an empty chart with a message."""
        fig = go.Figure()
        fig.add_annotation(
            text=f"No data available for {ticker}",
            xref="paper", yref="paper",
            x=0.5, y=0.5, showarrow=False,
            font=dict(size=18, color=TV_TEXT_DIM),
        )
        fig.update_layout(
            paper_bgcolor=TV_BG, plot_bgcolor=TV_BG,
            height=400, width=800,
        )
        return fig

    # ── Indicator Computations (standalone, no ta library needed) ──

    @staticmethod
    def _compute_sma(values: list[float], period: int) -> list[Optional[float]]:
        """Simple Moving Average."""
        result: list[Optional[float]] = [None] * (period - 1)
        for i in range(period - 1, len(values)):
            window = values[i - period + 1 : i + 1]
            result.append(sum(window) / period)
        return result

    @staticmethod
    def _compute_rolling_std(values: list[float], period: int) -> list[Optional[float]]:
        """Rolling standard deviation."""
        import math
        result: list[Optional[float]] = [None] * (period - 1)
        for i in range(period - 1, len(values)):
            window = values[i - period + 1 : i + 1]
            mean = sum(window) / period
            variance = sum((x - mean) ** 2 for x in window) / period
            result.append(math.sqrt(variance))
        return result

    @staticmethod
    def _compute_ema(values: list[float], period: int) -> list[Optional[float]]:
        """Exponential Moving Average."""
        result: list[Optional[float]] = [None] * (period - 1)
        multiplier = 2 / (period + 1)
        # Seed with SMA
        sma = sum(values[:period]) / period
        result.append(sma)
        for i in range(period, len(values)):
            ema = (values[i] - result[-1]) * multiplier + result[-1]
            result.append(ema)
        return result

    @staticmethod
    def _compute_rsi(closes: list[float], period: int = 14) -> list[Optional[float]]:
        """Relative Strength Index."""
        result: list[Optional[float]] = [None] * period
        deltas = [closes[i] - closes[i - 1] for i in range(1, len(closes))]
        gains = [max(d, 0) for d in deltas]
        losses = [abs(min(d, 0)) for d in deltas]

        avg_gain = sum(gains[:period]) / period
        avg_loss = sum(losses[:period]) / period

        if avg_loss == 0:
            result.append(100.0)
        else:
            rs = avg_gain / avg_loss
            result.append(100 - 100 / (1 + rs))

        for i in range(period, len(deltas)):
            avg_gain = (avg_gain * (period - 1) + gains[i]) / period
            avg_loss = (avg_loss * (period - 1) + losses[i]) / period
            if avg_loss == 0:
                result.append(100.0)
            else:
                rs = avg_gain / avg_loss
                result.append(100 - 100 / (1 + rs))

        return result

    def _compute_macd(
        self, closes: list[float],
        fast: int = 12, slow: int = 26, signal: int = 9,
    ) -> tuple[list[Optional[float]], list[Optional[float]], list[Optional[float]]]:
        """MACD line, Signal line, and Histogram."""
        ema_fast = self._compute_ema(closes, fast)
        ema_slow = self._compute_ema(closes, slow)

        macd_line: list[Optional[float]] = []
        for f, s in zip(ema_fast, ema_slow):
            if f is not None and s is not None:
                macd_line.append(f - s)
            else:
                macd_line.append(None)

        # Signal line = EMA of MACD values
        valid_macd = [v for v in macd_line if v is not None]
        if len(valid_macd) >= signal:
            signal_ema = self._compute_ema(valid_macd, signal)
            # Pad with Nones
            none_count = len(macd_line) - len(valid_macd)
            signal_line: list[Optional[float]] = [None] * none_count + signal_ema
        else:
            signal_line = [None] * len(macd_line)

        # Histogram
        histogram: list[Optional[float]] = []
        for m, s in zip(macd_line, signal_line):
            if m is not None and s is not None:
                histogram.append(m - s)
            else:
                histogram.append(None)

        return macd_line, signal_line, histogram

    @staticmethod
    def _compute_vwap(
        highs: list[float], lows: list[float],
        closes: list[float], volumes: list[int],
    ) -> list[Optional[float]]:
        """Volume Weighted Average Price (intraday)."""
        result: list[Optional[float]] = []
        cum_tp_vol = 0.0
        cum_vol = 0

        for h, l, c, v in zip(highs, lows, closes, volumes):
            typical_price = (h + l + c) / 3
            cum_tp_vol += typical_price * v
            cum_vol += v
            if cum_vol > 0:
                result.append(cum_tp_vol / cum_vol)
            else:
                result.append(None)

        return result
