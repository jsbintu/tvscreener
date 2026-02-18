/**
 * CoachingPanel — AI Trading Coach Dashboard
 *
 * Three tabs: Insights, Improvement Plan, Psychology Report
 * Fetches from analysisApi Phase 4 endpoints.
 */

import { useQuery } from '@tanstack/react-query';
import {
    AlertTriangle,
    Brain,
    ChevronDown,
    ChevronUp,
    Flame,
    GraduationCap,
    HeartCrack,
    Lightbulb,
    Loader2,
    RefreshCw,
    ShieldAlert,
    Target,
} from 'lucide-react';
import { useState } from 'react';
import { analysisApi } from '../../api/client';

/* eslint-disable @typescript-eslint/no-explicit-any */

type Tab = 'insights' | 'plan' | 'psychology';

const BIAS_ICONS: Record<string, React.ReactNode> = {
    overtrading: <Flame size={14} />,
    fomo: <AlertTriangle size={14} />,
    revenge_trading: <ShieldAlert size={14} />,
    loss_aversion: <HeartCrack size={14} />,
};

const BIAS_COLORS: Record<string, string> = {
    overtrading: 'var(--accent-amber)',
    fomo: 'var(--accent-red)',
    revenge_trading: 'var(--accent-red)',
    loss_aversion: 'var(--accent-amber)',
};

export default function CoachingPanel() {
    const [tab, setTab] = useState<Tab>('insights');
    const [expanded, setExpanded] = useState(true);

    // For demo, we pass an empty array — real usage would pass actual trade history
    const {
        data: insightsRaw,
        isLoading: loadingInsights,
        refetch: refetchInsights,
    } = useQuery({
        queryKey: ['coaching', 'insights'],
        queryFn: () => analysisApi.getCoachingInsights([]),
        enabled: tab === 'insights',
        staleTime: 300_000,
    });
    const insights = insightsRaw?.data;

    const {
        data: planRaw,
        isLoading: loadingPlan,
        refetch: refetchPlan,
    } = useQuery({
        queryKey: ['coaching', 'plan'],
        queryFn: () => analysisApi.getImprovementPlan([], 4),
        enabled: tab === 'plan',
        staleTime: 300_000,
    });
    const plan = planRaw?.data;

    const {
        data: psychRaw,
        isLoading: loadingPsych,
        refetch: refetchPsych,
    } = useQuery({
        queryKey: ['coaching', 'psychology'],
        queryFn: () => analysisApi.getPsychologyReport([]),
        enabled: tab === 'psychology',
        staleTime: 300_000,
    });
    const psych = psychRaw?.data;

    const loading =
        (tab === 'insights' && loadingInsights) ||
        (tab === 'plan' && loadingPlan) ||
        (tab === 'psychology' && loadingPsych);

    const handleRefresh = () => {
        if (tab === 'insights') refetchInsights();
        else if (tab === 'plan') refetchPlan();
        else refetchPsych();
    };

    return (
        <div className="card phase4-panel coaching-panel">
            <button type="button" className="card-header panel-toggle" onClick={() => setExpanded((o) => !o)}>
                <span className="card-title">
                    <GraduationCap size={16} /> AI Trading Coach
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
                    {/* Tab bar */}
                    <div className="phase4-tabs">
                        <button
                            type="button"
                            className={`phase4-tab ${tab === 'insights' ? 'active' : ''}`}
                            onClick={() => setTab('insights')}
                        >
                            <Lightbulb size={13} /> Insights
                        </button>
                        <button
                            type="button"
                            className={`phase4-tab ${tab === 'plan' ? 'active' : ''}`}
                            onClick={() => setTab('plan')}
                        >
                            <Target size={13} /> Plan
                        </button>
                        <button
                            type="button"
                            className={`phase4-tab ${tab === 'psychology' ? 'active' : ''}`}
                            onClick={() => setTab('psychology')}
                        >
                            <Brain size={13} /> Psychology
                        </button>
                    </div>

                    {loading ? (
                        <div className="phase4-loading">
                            <Loader2 size={20} className="spin" />
                            <span>Analyzing trades...</span>
                        </div>
                    ) : tab === 'insights' ? (
                        <div className="coaching-insights">
                            {insights?.coaching_response ? (
                                <div className="coaching-response">
                                    <p>{insights.coaching_response}</p>
                                </div>
                            ) : insights?.performance_summary ? (
                                <div className="coaching-stats">
                                    <div className="stat-row">
                                        <span className="stat-label">Total Trades</span>
                                        <span className="stat-value">
                                            {insights.performance_summary.total_trades ?? 0}
                                        </span>
                                    </div>
                                    <div className="stat-row">
                                        <span className="stat-label">Win Rate</span>
                                        <span className="stat-value accent-green">
                                            {insights.performance_summary.win_rate?.toFixed(1) ?? 0}%
                                        </span>
                                    </div>
                                    <div className="stat-row">
                                        <span className="stat-label">Avg R:R</span>
                                        <span className="stat-value">
                                            {insights.performance_summary.avg_rr?.toFixed(2) ?? '—'}
                                        </span>
                                    </div>
                                </div>
                            ) : (
                                <div className="empty-state">
                                    <GraduationCap size={28} />
                                    <span>No trade data available for coaching</span>
                                </div>
                            )}
                        </div>
                    ) : tab === 'plan' ? (
                        <div className="coaching-plan">
                            {plan?.weeks && Array.isArray(plan.weeks) ? (
                                plan.weeks.map((week: any, i: number) => (
                                    <div key={i} className="plan-week">
                                        <div className="plan-week-header">
                                            <Target size={13} />
                                            <span>Week {week.week ?? i + 1}</span>
                                        </div>
                                        <div className="plan-week-focus">{week.focus ?? ''}</div>
                                        {week.actions && (
                                            <ul className="plan-actions">
                                                {week.actions.map((a: string, j: number) => (
                                                    <li key={j}>{a}</li>
                                                ))}
                                            </ul>
                                        )}
                                    </div>
                                ))
                            ) : plan?.plan ? (
                                <div className="coaching-response">
                                    <p>{plan.plan}</p>
                                </div>
                            ) : (
                                <div className="empty-state">
                                    <Target size={28} />
                                    <span>Generate a plan from your trade history</span>
                                </div>
                            )}
                        </div>
                    ) : (
                        <div className="coaching-psychology">
                            {psych?.biases && Object.keys(psych.biases).length > 0 ? (
                                <div className="bias-grid">
                                    {Object.entries(psych.biases).map(([key, val]: [string, any]) => (
                                        <div
                                            key={key}
                                            className="bias-card"
                                            style={{ borderColor: BIAS_COLORS[key] ?? 'var(--border)' }}
                                        >
                                            <div className="bias-header">
                                                {BIAS_ICONS[key] ?? <AlertTriangle size={14} />}
                                                <span className="bias-name">{key.replace(/_/g, ' ')}</span>
                                            </div>
                                            <div className="bias-score" style={{ color: BIAS_COLORS[key] }}>
                                                {typeof val === 'object' ? `${val.score ?? val.severity ?? '—'}` : val}
                                            </div>
                                            {typeof val === 'object' && val.description && (
                                                <div className="bias-desc">{val.description}</div>
                                            )}
                                        </div>
                                    ))}
                                </div>
                            ) : psych?.report ? (
                                <div className="coaching-response">
                                    <p>{psych.report}</p>
                                </div>
                            ) : (
                                <div className="empty-state">
                                    <Brain size={28} />
                                    <span>No psychological patterns detected</span>
                                </div>
                            )}
                        </div>
                    )}
                </div>
            )}
        </div>
    );
}
