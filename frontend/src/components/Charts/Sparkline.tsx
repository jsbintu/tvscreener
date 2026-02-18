/**
 * Sparkline — Lightweight SVG sparkline component
 *
 * Renders a polyline from numeric data points. No dependencies.
 * Usage: <Sparkline data={[10, 12, 11, 15, 14]} color="var(--accent-green)" />
 */

import type React from 'react';

interface SparklineProps {
    data: number[];
    width?: number;
    height?: number;
    color?: string;
    strokeWidth?: number;
}

const Sparkline: React.FC<SparklineProps> = ({
    data,
    width = 80,
    height = 24,
    color = 'var(--accent-blue)',
    strokeWidth = 1.5,
}) => {
    if (!data || data.length < 2) return null;

    const min = Math.min(...data);
    const max = Math.max(...data);
    const range = max - min || 1;
    const padding = 2;

    const points = data
        .map((val, i) => {
            const x = padding + (i / (data.length - 1)) * (width - 2 * padding);
            const y = height - padding - ((val - min) / range) * (height - 2 * padding);
            return `${x},${y}`;
        })
        .join(' ');

    // Determine if trending up or down for gradient
    const trending = data[data.length - 1] >= data[0];
    const resolvedColor = color === 'auto' ? (trending ? 'var(--accent-green)' : 'var(--accent-red)') : color;

    return (
        <svg
            className="sparkline-container"
            width={width}
            height={height}
            viewBox={`0 0 ${width} ${height}`}
            style={{ overflow: 'visible' }}
            aria-labelledby="sparkline-title"
        >
            <title id="sparkline-title">Price trend sparkline</title>
            <polyline
                points={points}
                fill="none"
                stroke={resolvedColor}
                strokeWidth={strokeWidth}
                strokeLinecap="round"
                strokeLinejoin="round"
            />
        </svg>
    );
};

export default Sparkline;
