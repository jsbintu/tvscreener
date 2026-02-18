/**
 * ChartLegend — Real-time OHLCV + indicator values overlay.
 *
 * Positioned at top-left of the chart, updates on crosshair move.
 * Shows ticker, OHLCV data, change %, and values for all active indicators.
 */
import { useMemo } from 'react';

export interface LegendData {
    /** Raw OHLCV at crosshair */
    open?: number;
    high?: number;
    low?: number;
    close?: number;
    volume?: number;
    /** Previous close for delta calculation */
    prevClose?: number;
    /** Active indicator values: { sma_20: 185.32, rsi: 62.1, ... } */
    indicators: Record<string, number | null>;
    /** Whether data is for a valid bar or the crosshair is between bars */
    valid: boolean;
}

interface ChartLegendProps {
    ticker: string;
    data: LegendData;
    chartType: string;
}

/* ─── Indicator display config ─── */
const INDICATOR_META: Record<string, { label: string; color: string; precision?: number }> = {
    sma_20: { label: 'SMA 20', color: '#ffb74d' },
    sma_50: { label: 'SMA 50', color: '#42a5f5' },
    sma_200: { label: 'SMA 200', color: '#ef5350' },
    ema_8: { label: 'EMA 8', color: '#81c784' },
    ema_21: { label: 'EMA 21', color: '#ce93d8' },
    bb_upper: { label: 'BB↑', color: 'rgba(33,150,243,0.7)' },
    bb_middle: { label: 'BB', color: 'rgba(33,150,243,0.9)' },
    bb_lower: { label: 'BB↓', color: 'rgba(33,150,243,0.7)' },
    vwap: { label: 'VWAP', color: '#ffd54f' },
    rsi: { label: 'RSI', color: '#ab47bc', precision: 1 },
    macd_line: { label: 'MACD', color: '#42a5f5', precision: 3 },
    macd_signal: { label: 'Signal', color: '#ef5350', precision: 3 },
    macd_hist: { label: 'Hist', color: '#78909c', precision: 3 },
    stoch_k: { label: '%K', color: '#29b6f6', precision: 1 },
    stoch_d: { label: '%D', color: '#ff7043', precision: 1 },
};

function formatPrice(val: number | undefined | null, precision = 2): string {
    if (val == null || Number.isNaN(val)) return '—';
    return val.toFixed(precision);
}

function formatVolume(vol: number | undefined): string {
    if (vol == null) return '—';
    if (vol >= 1_000_000_000) return `${(vol / 1_000_000_000).toFixed(2)}B`;
    if (vol >= 1_000_000) return `${(vol / 1_000_000).toFixed(2)}M`;
    if (vol >= 1_000) return `${(vol / 1_000).toFixed(1)}K`;
    return vol.toString();
}

export default function ChartLegend({ ticker, data, chartType }: ChartLegendProps) {
    const change = useMemo(() => {
        if (data.close == null || data.prevClose == null || data.prevClose === 0) return null;
        const delta = data.close - data.prevClose;
        const pct = (delta / data.prevClose) * 100;
        return { delta, pct };
    }, [data.close, data.prevClose]);

    const isUp = change ? change.delta >= 0 : true;

    return (
        <div className="chart-legend">
            {/* Ticker + chart type */}
            <div className="legend-header">
                <span className="legend-ticker">{ticker}</span>
                <span className="legend-chart-type">{chartType}</span>
            </div>

            {/* OHLCV row */}
            {data.valid && (
                <div className="legend-ohlcv">
                    <span className="legend-label">O</span>
                    <span className={`legend-val ${isUp ? 'up' : 'down'}`}>{formatPrice(data.open)}</span>
                    <span className="legend-label">H</span>
                    <span className={`legend-val ${isUp ? 'up' : 'down'}`}>{formatPrice(data.high)}</span>
                    <span className="legend-label">L</span>
                    <span className={`legend-val ${isUp ? 'up' : 'down'}`}>{formatPrice(data.low)}</span>
                    <span className="legend-label">C</span>
                    <span className={`legend-val ${isUp ? 'up' : 'down'}`}>{formatPrice(data.close)}</span>

                    {change && (
                        <span className={`legend-change ${isUp ? 'up' : 'down'}`}>
                            {isUp ? '+' : ''}
                            {change.delta.toFixed(2)} ({isUp ? '+' : ''}
                            {change.pct.toFixed(2)}%)
                        </span>
                    )}

                    <span className="legend-label legend-vol-label">Vol</span>
                    <span className="legend-val legend-vol">{formatVolume(data.volume)}</span>
                </div>
            )}

            {/* Active indicator values */}
            {Object.keys(data.indicators).length > 0 && (
                <div className="legend-indicators">
                    {Object.entries(data.indicators).map(([key, val]) => {
                        const meta = INDICATOR_META[key];
                        if (!meta || val == null) return null;
                        return (
                            <span key={key} className="legend-indicator">
                                <span className="legend-ind-dot" style={{ background: meta.color }} />
                                <span className="legend-ind-label">{meta.label}</span>
                                <span className="legend-ind-val">{formatPrice(val, meta.precision ?? 2)}</span>
                            </span>
                        );
                    })}
                </div>
            )}
        </div>
    );
}
