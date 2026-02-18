/**
 * OptimizerPanel — Model Threshold Optimizer Dashboard
 *
 * Shows current confidence thresholds, optimization report,
 * and historical accuracy improvements.
 */

import { useQuery } from '@tanstack/react-query';
import {
    ArrowRight,
    CheckCircle2,
    ChevronDown,
    ChevronUp,
    Loader2,
    RefreshCw,
    Settings2,
    Sliders,
    Target,
    TrendingUp,
} from 'lucide-react';
import { useState } from 'react';
import { analysisApi } from '../../api/client';

/* eslint-disable @typescript-eslint/no-explicit-any */

export default function OptimizerPanel() {
    const [expanded, setExpanded] = useState(true);

    const {
        data: reportRaw,
        isLoading,
        refetch,
    } = useQuery({
        queryKey: ['optimizer', 'report'],
        queryFn: () => analysisApi.getOptimizationReport(),
        staleTime: 600_000, // 10 min — this is expensive
    });
    const report = reportRaw?.data;

    const thresholds = report?.thresholds ?? report?.current_thresholds ?? {};
    const changes = report?.changes ?? report?.threshold_changes ?? [];
    const overall = report?.overall_accuracy ?? report?.accuracy;

    return (
        <div className="card phase4-panel optimizer-panel">
            <button type="button" className="card-header panel-toggle" onClick={() => setExpanded((o) => !o)}>
                <span className="card-title">
                    <Settings2 size={16} /> Model Optimizer
                    {report?.last_run && (
                        <span className="badge badge-green" style={{ marginLeft: 8 }}>
                            <CheckCircle2 size={10} /> Active
                        </span>
                    )}
                </span>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
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
                            <span>Loading optimization report...</span>
                        </div>
                    ) : report ? (
                        <div className="optimizer-content">
                            {/* Overall accuracy */}
                            {overall != null && (
                                <div className="optimizer-summary">
                                    <div className="optimizer-accuracy">
                                        <Target size={18} />
                                        <div>
                                            <div className="optimizer-accuracy-value accent-green">
                                                {typeof overall === 'number' ? `${overall.toFixed(1)}%` : overall}
                                            </div>
                                            <div className="stat-label">Overall Accuracy</div>
                                        </div>
                                    </div>
                                    {report.total_predictions != null && (
                                        <div className="stat-row">
                                            <span className="stat-label">Total Predictions</span>
                                            <span className="stat-value">{report.total_predictions}</span>
                                        </div>
                                    )}
                                    {report.last_run && (
                                        <div className="stat-row">
                                            <span className="stat-label">Last Optimization</span>
                                            <span className="stat-value">{report.last_run}</span>
                                        </div>
                                    )}
                                </div>
                            )}

                            {/* Current thresholds */}
                            {Object.keys(thresholds).length > 0 && (
                                <div className="optimizer-thresholds">
                                    <div className="section-title">
                                        <Sliders size={13} /> Confidence Thresholds
                                    </div>
                                    <div className="threshold-grid">
                                        {Object.entries(thresholds).map(([pattern, value]: [string, any]) => {
                                            const threshold =
                                                typeof value === 'number' ? value : (value?.threshold ?? 0);
                                            return (
                                                <div key={pattern} className="threshold-row">
                                                    <span className="threshold-name">{pattern.replace(/_/g, ' ')}</span>
                                                    <div className="threshold-bar-track">
                                                        <div
                                                            className="threshold-bar-fill"
                                                            style={{ width: `${Math.min(100, threshold * 100)}%` }}
                                                        />
                                                    </div>
                                                    <span className="threshold-value">
                                                        {(threshold * 100).toFixed(0)}%
                                                    </span>
                                                </div>
                                            );
                                        })}
                                    </div>
                                </div>
                            )}

                            {/* Threshold changes */}
                            {Array.isArray(changes) && changes.length > 0 && (
                                <div className="optimizer-changes">
                                    <div className="section-title">
                                        <TrendingUp size={13} /> Recent Changes
                                    </div>
                                    {changes.map((c: any, i: number) => (
                                        <div key={i} className="change-row">
                                            <span className="change-pattern">{c.pattern ?? c.name ?? ''}</span>
                                            <div className="change-values">
                                                <span className="change-old">
                                                    {((c.old ?? c.before ?? 0) * 100).toFixed(0)}%
                                                </span>
                                                <ArrowRight size={12} />
                                                <span
                                                    className={`change-new ${(c.new ?? c.after ?? 0) > (c.old ?? c.before ?? 0) ? 'accent-green' : 'accent-red'}`}
                                                >
                                                    {((c.new ?? c.after ?? 0) * 100).toFixed(0)}%
                                                </span>
                                            </div>
                                        </div>
                                    ))}
                                </div>
                            )}
                        </div>
                    ) : (
                        <div className="empty-state">
                            <Settings2 size={28} />
                            <span>No optimization data — runs weekly on Sundays</span>
                        </div>
                    )}
                </div>
            )}
        </div>
    );
}
