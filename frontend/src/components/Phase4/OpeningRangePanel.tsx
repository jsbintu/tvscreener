/**
 * OpeningRangePanel — Intraday Opening Range Tracker
 *
 * Shows OR high/low, breakout status, and quality score.
 */

import { useQuery } from '@tanstack/react-query';
import {
    ArrowDownRight,
    ArrowUpRight,
    ChevronDown,
    ChevronUp,
    Clock,
    Loader2,
    Minus,
    RefreshCw,
    Sunrise,
} from 'lucide-react';
import { useState } from 'react';
import { analysisApi } from '../../api/client';

interface OpeningRangePanelProps {
    ticker?: string;
}

export default function OpeningRangePanel({ ticker = 'SPY' }: OpeningRangePanelProps) {
    const [expanded, setExpanded] = useState(true);
    const [minutes, setMinutes] = useState(30);

    const {
        data: orRaw,
        isLoading,
        refetch,
    } = useQuery({
        queryKey: ['openingRange', ticker, minutes],
        queryFn: () => analysisApi.captureOpeningRange(ticker, minutes),
        staleTime: 60_000,
        enabled: !!ticker,
    });
    const or = orRaw?.data;

    const { data: boRaw, refetch: refetchBo } = useQuery({
        queryKey: ['orBreakout', ticker, minutes],
        queryFn: () => analysisApi.checkORBreakout(ticker, minutes),
        staleTime: 30_000,
        enabled: !!ticker,
    });
    const breakout = boRaw?.data;

    const handleRefresh = () => {
        refetch();
        refetchBo();
    };

    const breakoutDir = breakout?.direction ?? 'none';
    const breakoutColor =
        breakoutDir === 'up'
            ? 'var(--accent-green)'
            : breakoutDir === 'down'
              ? 'var(--accent-red)'
              : 'var(--text-secondary)';

    return (
        <div className="card phase4-panel or-panel">
            <button type="button" className="card-header panel-toggle" onClick={() => setExpanded((o) => !o)}>
                <span className="card-title">
                    <Sunrise size={16} /> Opening Range
                    <span className="badge badge-blue" style={{ marginLeft: 8 }}>
                        {ticker}
                    </span>
                </span>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                    <button
                        type="button"
                        className="icon-btn"
                        onClick={(e) => {
                            e.stopPropagation();
                            handleRefresh();
                        }}
                        title="Refresh"
                    >
                        <RefreshCw size={12} />
                    </button>
                    {expanded ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
                </div>
            </button>

            {expanded && (
                <div className="panel-body">
                    {/* Minutes selector */}
                    <div className="or-controls">
                        <Clock size={12} />
                        {[15, 30, 60].map((m) => (
                            <button
                                type="button"
                                key={m}
                                className={`phase4-tab ${minutes === m ? 'active' : ''}`}
                                onClick={() => setMinutes(m)}
                            >
                                {m}m
                            </button>
                        ))}
                    </div>

                    {isLoading ? (
                        <div className="phase4-loading">
                            <Loader2 size={20} className="spin" />
                            <span>Capturing range...</span>
                        </div>
                    ) : or ? (
                        <div className="or-data">
                            {/* Range visualization */}
                            <div className="or-range-visual">
                                <div className="or-range-bar">
                                    <div className="or-range-fill" />
                                    <div className="or-high-label">
                                        <ArrowUpRight size={12} />
                                        High: ${or.high?.toFixed(2) ?? '—'}
                                    </div>
                                    <div className="or-low-label">
                                        <ArrowDownRight size={12} />
                                        Low: ${or.low?.toFixed(2) ?? '—'}
                                    </div>
                                </div>
                                <div className="or-range-width">
                                    Range: ${or.range?.toFixed(2) ?? '—'}
                                    {or.range_pct != null && ` (${or.range_pct.toFixed(2)}%)`}
                                </div>
                            </div>

                            {/* Breakout status */}
                            {breakout && (
                                <div className="or-breakout" style={{ borderLeftColor: breakoutColor }}>
                                    <div className="or-breakout-dir" style={{ color: breakoutColor }}>
                                        {breakoutDir === 'up' ? (
                                            <ArrowUpRight size={16} />
                                        ) : breakoutDir === 'down' ? (
                                            <ArrowDownRight size={16} />
                                        ) : (
                                            <Minus size={16} />
                                        )}
                                        <span>
                                            {breakoutDir === 'up'
                                                ? 'Bullish Breakout'
                                                : breakoutDir === 'down'
                                                  ? 'Bearish Breakdown'
                                                  : 'Inside Range'}
                                        </span>
                                    </div>
                                    {breakout.quality_score != null && (
                                        <div className="or-quality">
                                            <span className="stat-label">Quality</span>
                                            <div className="quality-bar-track">
                                                <div
                                                    className="quality-bar-fill"
                                                    style={{
                                                        width: `${Math.min(100, breakout.quality_score)}%`,
                                                        background: breakoutColor,
                                                    }}
                                                />
                                            </div>
                                            <span className="stat-value" style={{ color: breakoutColor }}>
                                                {breakout.quality_score.toFixed(0)}/100
                                            </span>
                                        </div>
                                    )}
                                    {breakout.current_price != null && (
                                        <div className="stat-row">
                                            <span className="stat-label">Current</span>
                                            <span className="stat-value">${breakout.current_price.toFixed(2)}</span>
                                        </div>
                                    )}
                                </div>
                            )}
                        </div>
                    ) : (
                        <div className="empty-state">
                            <Sunrise size={28} />
                            <span>No opening range data available</span>
                        </div>
                    )}
                </div>
            )}
        </div>
    );
}
