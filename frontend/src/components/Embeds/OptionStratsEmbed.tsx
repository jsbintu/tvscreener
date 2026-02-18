/**
 * OptionStratsEmbed — Renders OptionStrats pages in an iframe
 *
 * Supports strategy builder, flow news, insider flow, and more
 * via URL mappings from the backend's STRATEGY_CATALOG.
 */

import { useEffect, useState } from 'react';
import { marketApi } from '../../api/client';

interface OptionStratsEmbedProps {
    ticker: string;
    strategy?: string;
    height?: number | string;
    className?: string;
}

export default function OptionStratsEmbed({
    ticker,
    strategy = 'optimizer',
    height = 500,
    className = '',
}: OptionStratsEmbedProps) {
    const [url, setUrl] = useState<string | null>(null);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        if (!ticker) return;

        marketApi
            .getOptionStratsUrls(ticker, strategy)
            .then((res) => {
                const data = res.data;
                // Backend returns { urls: { strategy: url, ... } } or { url: string }
                const resolved = typeof data === 'string' ? data : (data?.urls?.[strategy] ?? data?.url ?? null);
                setUrl(resolved);
                setError(null);
            })
            .catch(() => {
                setError(`Failed to load OptionStrats ${strategy}`);
            });
    }, [ticker, strategy]);

    if (error) {
        return (
            <div className={`card ${className}`} style={{ textAlign: 'center', padding: 32 }}>
                <div className="text-muted">{error}</div>
            </div>
        );
    }

    if (!url) {
        return (
            <div
                className="skeleton"
                style={{
                    height: typeof height === 'number' ? height : 500,
                    borderRadius: 'var(--radius-md)',
                }}
            />
        );
    }

    return (
        <div className={`optionstrats-embed ${className}`}>
            <iframe
                src={url}
                title={`OptionStrats ${strategy} — ${ticker}`}
                width="100%"
                height={height}
                style={{
                    border: 'none',
                    borderRadius: 'var(--radius-md)',
                    background: 'var(--bg-secondary)',
                }}
                sandbox="allow-scripts allow-same-origin allow-popups"
                loading="lazy"
            />
        </div>
    );
}
