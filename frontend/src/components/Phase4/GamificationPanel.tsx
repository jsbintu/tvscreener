/**
 * GamificationPanel — Streaks, Badges & Leaderboard Stats
 *
 * Shows win/loss streaks, achievement badges, win rate trends,
 * and risk-to-reward ratios across 7/30/90 day windows.
 */

import { useQuery } from '@tanstack/react-query';
import {
    Award,
    BarChart3,
    ChevronDown,
    ChevronUp,
    Flame,
    Loader2,
    Minus,
    RefreshCw,
    Target,
    TrendingDown,
    TrendingUp,
    Trophy,
    Zap,
} from 'lucide-react';
import { useState } from 'react';
import { analysisApi } from '../../api/client';

/* eslint-disable @typescript-eslint/no-explicit-any */

export default function GamificationPanel() {
    const [expanded, setExpanded] = useState(true);

    const {
        data: streakRaw,
        isLoading: loadingStreak,
        refetch: refetchStreak,
    } = useQuery({
        queryKey: ['gamification', 'streaks'],
        queryFn: () => analysisApi.getStreakData(),
        staleTime: 120_000,
    });
    const streak = streakRaw?.data;

    const {
        data: lbRaw,
        isLoading: loadingLb,
        refetch: refetchLb,
    } = useQuery({
        queryKey: ['gamification', 'leaderboard'],
        queryFn: () => analysisApi.getLeaderboardStats(),
        staleTime: 120_000,
    });
    const lb = lbRaw?.data;

    const loading = loadingStreak || loadingLb;

    const handleRefresh = () => {
        refetchStreak();
        refetchLb();
    };

    const trendIcon =
        lb?.trend === 'improving' ? (
            <TrendingUp size={14} />
        ) : lb?.trend === 'declining' ? (
            <TrendingDown size={14} />
        ) : (
            <Minus size={14} />
        );

    return (
        <div className="card phase4-panel gamification-panel">
            <button type="button" className="card-header panel-toggle" onClick={() => setExpanded((o) => !o)}>
                <span className="card-title">
                    <Trophy size={16} /> Performance & Achievements
                </span>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                    {lb?.trend && (
                        <span
                            className={`badge badge-${lb.trend === 'improving' ? 'green' : lb.trend === 'declining' ? 'red' : 'amber'}`}
                            title={`Trend: ${lb.trend}`}
                        >
                            {trendIcon} {lb.trend}
                        </span>
                    )}
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
                    {loading ? (
                        <div className="phase4-loading">
                            <Loader2 size={20} className="spin" />
                            <span>Loading achievements...</span>
                        </div>
                    ) : (
                        <div className="gamification-content">
                            {/* Streak display */}
                            {streak && (
                                <div className="streak-section">
                                    <div className={`streak-card ${streak.is_hot_streak ? 'hot-streak' : ''}`}>
                                        <div className="streak-icon">
                                            {streak.is_hot_streak ? <Flame size={24} /> : <Zap size={24} />}
                                        </div>
                                        <div className="streak-info">
                                            <div className="streak-count">{streak.current_streak ?? 0}</div>
                                            <div className="streak-label">
                                                {streak.streak_type === 'win'
                                                    ? 'Win Streak'
                                                    : streak.streak_type === 'loss'
                                                      ? 'Loss Streak'
                                                      : 'No Active Streak'}
                                            </div>
                                        </div>
                                        <div className="streak-records">
                                            <div className="record">
                                                <span className="record-label">Best Win</span>
                                                <span className="record-value accent-green">
                                                    {streak.best_win_streak ?? 0}
                                                </span>
                                            </div>
                                            <div className="record">
                                                <span className="record-label">Worst Loss</span>
                                                <span className="record-value accent-red">
                                                    {streak.best_loss_streak ?? 0}
                                                </span>
                                            </div>
                                        </div>
                                    </div>
                                </div>
                            )}

                            {/* Win rate trends */}
                            {lb?.periods && (
                                <div className="period-stats">
                                    <div className="section-title">
                                        <BarChart3 size={13} /> Performance by Period
                                    </div>
                                    <div className="period-grid">
                                        {Object.entries(lb.periods).map(([period, stats]: [string, any]) => (
                                            <div key={period} className="period-card">
                                                <div className="period-label">{period}</div>
                                                <div className="period-wr">
                                                    <Target size={12} />
                                                    <span
                                                        className={
                                                            stats.win_rate >= 55
                                                                ? 'accent-green'
                                                                : stats.win_rate <= 45
                                                                  ? 'accent-red'
                                                                  : ''
                                                        }
                                                    >
                                                        {stats.win_rate?.toFixed(1) ?? 0}%
                                                    </span>
                                                </div>
                                                <div className="period-meta">
                                                    <span>R:R {stats.avg_rr?.toFixed(2) ?? '—'}</span>
                                                    <span>{stats.trades ?? 0} trades</span>
                                                </div>
                                                {stats.total_pnl_pct != null && (
                                                    <div
                                                        className={`period-pnl ${stats.total_pnl_pct >= 0 ? 'accent-green' : 'accent-red'}`}
                                                    >
                                                        {stats.total_pnl_pct >= 0 ? '+' : ''}
                                                        {stats.total_pnl_pct.toFixed(2)}%
                                                    </div>
                                                )}
                                            </div>
                                        ))}
                                    </div>
                                </div>
                            )}

                            {/* Badges */}
                            {lb?.badges && lb.badges.length > 0 && (
                                <div className="badges-section">
                                    <div className="section-title">
                                        <Award size={13} /> Achievements
                                    </div>
                                    <div className="badge-grid">
                                        {lb.badges.map((b: any, i: number) => (
                                            <div key={i} className="achievement-badge" title={b.description ?? ''}>
                                                <span className="badge-emoji">{b.name ?? '🏆'}</span>
                                                {b.description && <span className="badge-desc">{b.description}</span>}
                                            </div>
                                        ))}
                                    </div>
                                </div>
                            )}

                            {!streak && !lb && (
                                <div className="empty-state">
                                    <Trophy size={28} />
                                    <span>No trading data for gamification</span>
                                </div>
                            )}
                        </div>
                    )}
                </div>
            )}
        </div>
    );
}
