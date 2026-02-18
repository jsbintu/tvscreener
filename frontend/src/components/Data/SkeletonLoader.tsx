/**
 * SkeletonLoader — Configurable loading placeholders
 *
 * Renders shimmer-animated skeleton shapes.
 * Usage:
 *   <SkeletonLoader lines={3} />
 *   <SkeletonLoader variant="card" />
 *   <SkeletonLoader variant="circle" size={40} />
 */

import type React from 'react';

interface SkeletonLoaderProps {
    variant?: 'lines' | 'card' | 'circle';
    lines?: number;
    width?: string;
    height?: string;
    size?: number;
}

const SkeletonLoader: React.FC<SkeletonLoaderProps> = ({ variant = 'lines', lines = 3, width, height, size = 40 }) => {
    if (variant === 'circle') {
        return (
            <div
                className="skeleton"
                style={{
                    width: size,
                    height: size,
                    borderRadius: '50%',
                }}
            />
        );
    }

    if (variant === 'card') {
        return (
            <div
                className="skeleton"
                style={{
                    width: width || '100%',
                    height: height || '120px',
                    borderRadius: 'var(--radius-md)',
                }}
            />
        );
    }

    // Default: lines
    return (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            {Array.from({ length: lines }, (_, i) => (
                <div
                    key={i}
                    className="skeleton"
                    style={{
                        width: i === lines - 1 ? '60%' : width || '100%',
                        height: height || '14px',
                    }}
                />
            ))}
        </div>
    );
};

export default SkeletonLoader;
