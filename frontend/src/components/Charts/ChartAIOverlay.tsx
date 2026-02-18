/**
 * ChartAIOverlay — Renders AI-powered overlays on the chart.
 *
 * Displays:
 *   - Pattern annotation badges (confidence + name + target arrows)
 *   - Confluence zone highlights
 *   - Prediction zone shading
 *   - Chart health gauge (embedded)
 */
import type { AIOverlayData } from '../../hooks/useChartAI';
import './ChartAIOverlay.css';

interface ChartAIOverlayProps {
    data: AIOverlayData;
    visible: boolean;
}

export default function ChartAIOverlay({ data, visible }: ChartAIOverlayProps) {
    if (!visible) return null;

    const { annotations, confluenceZones, predictionZone, healthScore } = data;

    return (
        <div className="ai-overlay">
            {/* Health gauge */}
            <div
                className="ai-health-gauge"
                title={`Trend: ${healthScore.trendScore} • Momentum: ${healthScore.momentumScore} • Volatility: ${healthScore.volatilityScore} • Volume: ${healthScore.volumeScore}`}
            >
                <div className="ai-health-ring">
                    <svg viewBox="0 0 40 40" className="ai-health-svg" aria-labelledby="ai-health-title">
                        <title id="ai-health-title">Chart health score gauge</title>
                        <circle cx="20" cy="20" r="16" fill="none" stroke="rgba(255,255,255,0.06)" strokeWidth="3" />
                        <circle
                            cx="20"
                            cy="20"
                            r="16"
                            fill="none"
                            stroke={healthScore.color}
                            strokeWidth="3"
                            strokeDasharray={`${healthScore.overall} ${100 - healthScore.overall}`}
                            strokeDashoffset="25"
                            strokeLinecap="round"
                            className="ai-health-arc"
                        />
                    </svg>
                    <span className="ai-health-value" style={{ color: healthScore.color }}>
                        {healthScore.overall}
                    </span>
                </div>
                <span className="ai-health-label" style={{ color: healthScore.color }}>
                    {healthScore.label}
                </span>
            </div>

            {/* Pattern annotation badges */}
            {annotations.length > 0 && (
                <div className="ai-annotations">
                    {annotations.slice(0, 5).map((ann) => (
                        <div key={ann.id} className={`ai-annotation-badge ai-bias-${ann.bias}`} title={ann.description}>
                            <span className="ai-ann-name">{ann.name}</span>
                            <span className="ai-ann-conf">{ann.confidence}%</span>
                            {ann.target && <span className="ai-ann-target">→ {ann.target.toFixed(2)}</span>}
                        </div>
                    ))}
                </div>
            )}

            {/* Confluence zones */}
            {confluenceZones.length > 0 && (
                <div className="ai-confluence-list">
                    <div className="ai-section-label">Confluence</div>
                    {confluenceZones.slice(0, 4).map((zone) => (
                        <div key={zone.id} className={`ai-confluence-item ai-cz-${zone.bias}`}>
                            <span className="ai-cz-price">${zone.priceLevel.toFixed(2)}</span>
                            <div className="ai-cz-bar">
                                <div className="ai-cz-fill" style={{ width: `${zone.strength}%` }} />
                            </div>
                            <span className="ai-cz-signals">{zone.signals.join(' · ')}</span>
                        </div>
                    ))}
                </div>
            )}

            {/* Prediction zone summary */}
            {predictionZone && (
                <div className={`ai-prediction-badge ai-bias-${predictionZone.bias}`}>
                    <span className="ai-pred-label">Target Range</span>
                    <span className="ai-pred-range">
                        ${predictionZone.lowerBound.toFixed(2)} — ${predictionZone.upperBound.toFixed(2)}
                    </span>
                    <span className="ai-pred-conf">{predictionZone.confidence}% conf</span>
                </div>
            )}
        </div>
    );
}
