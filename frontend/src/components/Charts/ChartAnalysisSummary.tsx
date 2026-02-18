/**
 * ChartAnalysisSummary — Collapsible panel showing the AI's complete analysis trail.
 *
 * Shows categorized pattern findings, trend lines, emerging patterns,
 * pre-candle setups, signal freshness, health score, and confluence zones.
 * Users can verify every AI finding with confidence scores and descriptions.
 */
import { useMemo, useState } from 'react';
import type { AIOverlayData } from '../../hooks/useChartAI';
import './ChartAnalysisSummary.css';

/* eslint-disable @typescript-eslint/no-explicit-any */

interface AnalysisSection {
    title: string;
    icon: string;
    content: string;
    severity?: string;
    items?: any[];
}

interface AIAnalysis {
    ticker: string;
    price: number;
    timestamp: number;
    sections: AnalysisSection[];
    bias: string;
    pattern_count: number;
}

interface ChartAnalysisSummaryProps {
    visible: boolean;
    onClose: () => void;
    aiAnalysis?: AIAnalysis;
    overlayData: AIOverlayData;
    trendLineCount: number;
    emergingCount: number;
    preCandleCount: number;
}

/* ── Severity badge colors ── */
const SEVERITY_COLORS: Record<string, string> = {
    high: '#ff1744',
    medium: '#ffd54f',
    low: '#69f0ae',
};

const BIAS_COLORS: Record<string, string> = {
    bullish: '#00c853',
    bearish: '#ff1744',
    neutral: '#78909c',
    BULLISH: '#00c853',
    BEARISH: '#ff1744',
    NEUTRAL: '#78909c',
};

/* ── Individual section card ── */
function SectionCard({ section, defaultOpen = false }: { section: AnalysisSection; defaultOpen?: boolean }) {
    const [expanded, setExpanded] = useState(defaultOpen);

    return (
        <div className={`analysis-section-card ${expanded ? 'expanded' : ''}`}>
            <button type="button" className="section-header" onClick={() => setExpanded((e) => !e)}>
                <span className="section-icon">{section.icon}</span>
                <span className="section-title">{section.title}</span>
                {section.severity && (
                    <span
                        className="severity-badge"
                        style={{ background: SEVERITY_COLORS[section.severity] || '#78909c' }}
                    >
                        {section.severity}
                    </span>
                )}
                <span className={`chevron ${expanded ? 'open' : ''}`}>›</span>
            </button>
            {expanded && (
                <div className="section-content">
                    <pre className="section-pre">{section.content}</pre>
                    {section.items && section.items.length > 0 && (
                        <div className="section-items">
                            {section.items.map((item: any, idx: number) => (
                                <div key={idx} className="section-item-row">
                                    <span className={`item-direction ${item.direction || 'neutral'}`}>
                                        {item.direction === 'bullish' ? '▲' : item.direction === 'bearish' ? '▼' : '●'}
                                    </span>
                                    <span className="item-name">{item.name || item.pattern_name || 'Unknown'}</span>
                                    {item.confidence != null && (
                                        <span className="item-confidence">{item.confidence}%</span>
                                    )}
                                    {item.progress != null && (
                                        <div className="progress-bar-mini">
                                            <div
                                                className="progress-fill"
                                                style={{
                                                    width: `${
                                                        typeof item.progress === 'number' && item.progress <= 1
                                                            ? item.progress * 100
                                                            : item.progress
                                                    }%`,
                                                }}
                                            />
                                        </div>
                                    )}
                                    {item.target != null && (
                                        <span className="item-target">T: ${item.target.toFixed(2)}</span>
                                    )}
                                    {item.confirmation_needed && (
                                        <span className="item-confirm">Needs: {item.confirmation_needed}</span>
                                    )}
                                    {item.probability != null && <span className="item-prob">{item.probability}%</span>}
                                </div>
                            ))}
                        </div>
                    )}
                </div>
            )}
        </div>
    );
}

export default function ChartAnalysisSummary({
    visible,
    onClose,
    aiAnalysis,
    overlayData,
    trendLineCount,
    emergingCount,
    preCandleCount,
}: ChartAnalysisSummaryProps) {
    /* ── Health score breakdown ── */
    const hs = overlayData.healthScore;

    /* ── Stats bar ── */
    const statsLine = useMemo(() => {
        const parts: string[] = [];
        if (aiAnalysis?.pattern_count) parts.push(`${aiAnalysis.pattern_count} patterns`);
        if (trendLineCount > 0) parts.push(`${trendLineCount} trend lines`);
        if (emergingCount > 0) parts.push(`${emergingCount} emerging`);
        if (preCandleCount > 0) parts.push(`${preCandleCount} pre-candle`);
        if (overlayData.confluenceZones.length > 0)
            parts.push(`${overlayData.confluenceZones.length} confluence zones`);
        return parts.join(' · ') || 'No signals detected.';
    }, [aiAnalysis, trendLineCount, emergingCount, preCandleCount, overlayData.confluenceZones.length]);

    if (!visible) return null;

    return (
        <div className="chart-analysis-panel">
            {/* ── Header ── */}
            <div className="analysis-header">
                <div className="header-left">
                    <span className="header-icon">🧠</span>
                    <h3 className="header-title">AI Analysis</h3>
                    {aiAnalysis && (
                        <span className="bias-badge" style={{ background: BIAS_COLORS[aiAnalysis.bias] || '#78909c' }}>
                            {aiAnalysis.bias.toUpperCase()}
                        </span>
                    )}
                </div>
                <button type="button" className="close-btn" onClick={onClose} title="Close">
                    ×
                </button>
            </div>

            {/* ── Stats bar ── */}
            <div className="analysis-stats-bar">{statsLine}</div>

            {/* ── Health Score Card ── */}
            <div className="health-score-card">
                <div className="health-main">
                    <div className="health-gauge" style={{ borderColor: hs.color }}>
                        <span className="health-value" style={{ color: hs.color }}>
                            {hs.overall}
                        </span>
                    </div>
                    <div className="health-info">
                        <span className="health-label" style={{ color: hs.color }}>
                            {hs.label}
                        </span>
                        <span className="health-subtitle">Chart Health</span>
                    </div>
                </div>
                <div className="health-breakdown">
                    <HealthBar label="Trend" value={hs.trendScore} />
                    <HealthBar label="Momentum" value={hs.momentumScore} />
                    <HealthBar label="Volatility" value={hs.volatilityScore} />
                    <HealthBar label="Volume" value={hs.volumeScore} />
                </div>
            </div>

            {/* ── Confluence Zones ── */}
            {overlayData.confluenceZones.length > 0 && (
                <div className="confluence-section">
                    <h4 className="mini-heading">⚡ Confluence Zones</h4>
                    {overlayData.confluenceZones.map((cz) => (
                        <div key={cz.id} className="confluence-row">
                            <span className={`cz-bias ${cz.bias}`}>{cz.bias === 'support' ? '▲' : '▼'}</span>
                            <span className="cz-price">${cz.priceLevel.toFixed(2)}</span>
                            <div className="cz-strength-bar">
                                <div
                                    className="cz-fill"
                                    style={{
                                        width: `${cz.strength}%`,
                                        background: cz.bias === 'support' ? '#00c853' : '#ff1744',
                                    }}
                                />
                            </div>
                            <span className="cz-signals">{cz.signals.join(', ')}</span>
                        </div>
                    ))}
                </div>
            )}

            {/* ── Prediction Zone ── */}
            {overlayData.predictionZone && (
                <div className="prediction-section">
                    <h4 className="mini-heading">🎯 Prediction Zone</h4>
                    <div className="prediction-details">
                        <span className={`pred-bias ${overlayData.predictionZone.bias}`}>
                            {overlayData.predictionZone.bias.toUpperCase()}
                        </span>
                        <span className="pred-range">
                            ${overlayData.predictionZone.lowerBound.toFixed(2)} → $
                            {overlayData.predictionZone.upperBound.toFixed(2)}
                        </span>
                        <span className="pred-conf">{overlayData.predictionZone.confidence}% confidence</span>
                    </div>
                </div>
            )}

            {/* ── AI Sections (from backend narrative) ── */}
            <div className="analysis-sections">
                {aiAnalysis?.sections?.map((section, idx) => (
                    <SectionCard key={idx} section={section} defaultOpen={idx === 0} />
                ))}

                {/* ── Pattern Annotations ── */}
                {overlayData.annotations.length > 0 && (
                    <SectionCard
                        section={{
                            title: `Pattern Annotations (${overlayData.annotations.length})`,
                            icon: '🏷️',
                            content: overlayData.annotations
                                .map((a) => `• ${a.name} (${a.bias}, ${a.confidence}%) — ${a.description}`)
                                .join('\n'),
                            items: overlayData.annotations.map((a) => ({
                                name: a.name,
                                direction: a.bias,
                                confidence: a.confidence,
                                target: a.target,
                                description: a.description,
                            })),
                        }}
                    />
                )}
            </div>

            {/* ── Footer ── */}
            <div className="analysis-footer">
                <span className="footer-time">
                    Analysis at{' '}
                    {aiAnalysis?.timestamp ? new Date(aiAnalysis.timestamp * 1000).toLocaleTimeString() : 'N/A'}
                </span>
                <span className="footer-ticker">{aiAnalysis?.ticker || '—'}</span>
            </div>
        </div>
    );
}

/* ── Health breakdown bar sub-component ── */
function HealthBar({ label, value }: { label: string; value: number }) {
    const color = value >= 75 ? '#00c853' : value >= 55 ? '#42a5f5' : value >= 40 ? '#ffd54f' : '#ef5350';
    return (
        <div className="health-bar-row">
            <span className="hb-label">{label}</span>
            <div className="hb-track">
                <div className="hb-fill" style={{ width: `${value}%`, background: color }} />
            </div>
            <span className="hb-value" style={{ color }}>
                {value}
            </span>
        </div>
    );
}
