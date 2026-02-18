/**
 * GhostChartPanel — Historical Pattern Overlays
 *
 * Shows similar historical patterns with similarity scores
 * and overlays for current price action comparison.
 */

import { useQuery } from '@tanstack/react-query';
import {
    BarChart3,
    ChevronDown,
    ChevronUp,
    Clock,
    Eye,
    Ghost,
    Layers,
    Loader2,
    Percent,
    RefreshCw,
} from 'lucide-react';
import { useState } from 'react';
import { analysisApi } from '../../api/client';

/* eslint-disable @typescript-eslint/no-explicit-any */

interface GhostChartPanelProps {
    ticker?: string;
}

export default function GhostChartPanel({ ticker = 'SPY' }: GhostChartPanelProps) {
    const [expanded, setExpanded] = useState(true);
    const [selectedPattern, setSelectedPattern] = useState<string | null>(null);

    const {
        data: patternsRaw,
        isLoading,
        refetch,
    } = useQuery({
        queryKey: ['ghostPatterns', ticker],
        queryFn: () => analysisApi.findGhostPatterns(ticker, '3mo', 5),
        staleTime: 300_000,
        enabled: !!ticker,
    });
    const patterns = patternsRaw?.data?.matches ?? patternsRaw?.data ?? [];

    const { data: overlayRaw, isLoading: loadingOverlay } = useQuery({
        queryKey: ['ghostOverlay', selectedPattern, ticker],
        queryFn: () => analysisApi.getGhostOverlay(selectedPattern!, ticker),
        staleTime: 300_000,
        enabled: !!selectedPattern,
    });
    const overlay = overlayRaw?.data;

    const getSimilarityColor = (score: number) => {
        if (score >= 0.85) return 'var(--accent-green)';
        if (score >= 0.7) return 'var(--accent-amber)';
        return 'var(--text-secondary)';
    };

    return (
        <div className="card phase4-panel ghost-panel">
            <button type="button" className="card-header panel-toggle" onClick={() => setExpanded((o) => !o)}>
                <span className="card-title">
                    <Ghost size={16} /> Ghost Charts
                    <span className="badge badge-purple" style={{ marginLeft: 8 }}>
                        {ticker}
                    </span>
                </span>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                    <span className="badge badge-blue">{Array.isArray(patterns) ? patterns.length : 0}</span>
                    <button
                        type="button"
                        className="icon-btn"
                        onClick={(e) => {
                            e.stopPropagation();
                            refetch();
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
                    {isLoading ? (
                        <div className="phase4-loading">
                            <Loader2 size={20} className="spin" />
                            <span>Searching historical patterns...</span>
                        </div>
                    ) : Array.isArray(patterns) && patterns.length > 0 ? (
                        <div className="ghost-grid">
                            {patterns.map((p: any, i: number) => {
                                const similarity = p.similarity ?? p.score ?? 0;
                                const isSelected = selectedPattern === (p.id ?? p.pattern_id);
                                return (
                                    <button
                                        type="button"
                                        key={i}
                                        className={`ghost-card ${isSelected ? 'selected' : ''}`}
                                        onClick={() => setSelectedPattern(p.id ?? p.pattern_id ?? null)}
                                    >
                                        <div className="ghost-card-header">
                                            <div className="ghost-rank">#{i + 1}</div>
                                            <div
                                                className="ghost-similarity"
                                                style={{ color: getSimilarityColor(similarity) }}
                                            >
                                                <Percent size={12} />
                                                {(similarity * 100).toFixed(1)}%
                                            </div>
                                        </div>

                                        <div className="ghost-meta">
                                            {p.date_range && (
                                                <div className="ghost-meta-row">
                                                    <Clock size={11} />
                                                    <span>{p.date_range}</span>
                                                </div>
                                            )}
                                            {p.pattern_type && (
                                                <div className="ghost-meta-row">
                                                    <BarChart3 size={11} />
                                                    <span>{p.pattern_type}</span>
                                                </div>
                                            )}
                                            {p.outcome && (
                                                <div className="ghost-meta-row">
                                                    <Layers size={11} />
                                                    <span
                                                        className={
                                                            p.outcome === 'bullish'
                                                                ? 'accent-green'
                                                                : p.outcome === 'bearish'
                                                                  ? 'accent-red'
                                                                  : ''
                                                        }
                                                    >
                                                        {p.outcome}
                                                    </span>
                                                </div>
                                            )}
                                        </div>

                                        {isSelected && (
                                            <div className="ghost-overlay-preview">
                                                {loadingOverlay ? (
                                                    <div className="phase4-loading">
                                                        <Loader2 size={14} className="spin" />
                                                    </div>
                                                ) : overlay?.path ? (
                                                    <div className="ghost-path-data">
                                                        <Eye size={12} />
                                                        <span>{overlay.path.length} data points loaded</span>
                                                    </div>
                                                ) : (
                                                    <div className="ghost-path-data">
                                                        <Eye size={12} />
                                                        <span>Overlay ready</span>
                                                    </div>
                                                )}
                                            </div>
                                        )}
                                    </button>
                                );
                            })}
                        </div>
                    ) : (
                        <div className="empty-state">
                            <Ghost size={28} />
                            <span>No similar historical patterns found</span>
                        </div>
                    )}
                </div>
            )}
        </div>
    );
}
