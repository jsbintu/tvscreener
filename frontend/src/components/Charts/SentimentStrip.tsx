/**
 * SentimentStrip — Thin gradient band below chart showing sentiment timeline.
 *
 * Displays a horizontal color strip from red (bearish) through neutral to
 * green (bullish) based on news/social sentiment data over time.
 */
import { useMemo } from 'react';
import './SentimentStrip.css';

export interface SentimentDataPoint {
    time: number; // unix timestamp
    score: number; // -1 (very bearish) to +1 (very bullish)
    label?: string; // e.g. "Earnings Beat", "Downgrade"
}

interface SentimentStripProps {
    data: SentimentDataPoint[];
    visible: boolean;
}

/** Map score (-1..+1) to hsl color */
function scoreToColor(score: number): string {
    // -1 → red (0°), 0 → yellow (55°), +1 → green (140°)
    const hue = Math.round(((score + 1) / 2) * 140);
    const sat = Math.round(60 + Math.abs(score) * 30);
    const light = Math.round(40 + (1 - Math.abs(score)) * 15);
    return `hsl(${hue}, ${sat}%, ${light}%)`;
}

export default function SentimentStrip({ data, visible }: SentimentStripProps) {
    const gradient = useMemo(() => {
        if (!data.length) return 'rgba(255,255,255,0.04)';
        if (data.length === 1) return scoreToColor(data[0].score);

        const stops = data.map((d, i) => {
            const pct = (i / (data.length - 1)) * 100;
            return `${scoreToColor(d.score)} ${pct.toFixed(1)}%`;
        });
        return `linear-gradient(90deg, ${stops.join(', ')})`;
    }, [data]);

    if (!visible || !data.length) return null;

    // Compute average sentiment
    const avgScore = data.reduce((s, d) => s + d.score, 0) / data.length;
    const avgLabel = avgScore > 0.3 ? 'Bullish' : avgScore < -0.3 ? 'Bearish' : 'Neutral';

    return (
        <div
            className="sentiment-strip"
            title={`Avg Sentiment: ${avgLabel} (${avgScore > 0 ? '+' : ''}${avgScore.toFixed(2)})`}
        >
            <div className="sentiment-bar" style={{ background: gradient }} />
            <div className="sentiment-meta">
                <span className="sentiment-label">Sentiment</span>
                <span className="sentiment-value" style={{ color: scoreToColor(avgScore) }}>
                    {avgLabel}
                </span>
            </div>
        </div>
    );
}
