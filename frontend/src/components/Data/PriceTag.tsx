/**
 * PriceTag — Reusable price display with color-coding and flash animation
 *
 * Displays a formatted price with automatic green/red coloring based on
 * a change value. Flashes briefly when the price updates via WebSocket.
 *
 * Usage:
 *   <PriceTag price={184.25} change={2.31} />
 *   <PriceTag price={184.25} prevPrice={182.10} />
 */

import type React from 'react';
import { useEffect, useRef, useState } from 'react';
import { formatCurrency, priceColorClass } from '../../utils/format';

interface PriceTagProps {
    price: number | null;
    change?: number;
    prevPrice?: number | null;
    size?: 'sm' | 'md' | 'lg';
    showFlash?: boolean;
}

const SIZE_MAP = { sm: '13px', md: '16px', lg: '24px' };

const PriceTag: React.FC<PriceTagProps> = ({ price, change, prevPrice, size = 'md', showFlash = true }) => {
    const prevRef = useRef<number | null>(prevPrice ?? null);
    const flashTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
    const [flashClass, setFlashClass] = useState('');

    useEffect(() => {
        if (!showFlash || price == null) return;

        const prev = prevRef.current;
        prevRef.current = price;

        if (prev != null && prev !== price) {
            const cls = price > prev ? 'price-flash-up' : 'price-flash-down';
            queueMicrotask(() => setFlashClass(cls));
            if (flashTimerRef.current) clearTimeout(flashTimerRef.current);
            flashTimerRef.current = setTimeout(() => setFlashClass(''), 600);
        }

        return () => {
            if (flashTimerRef.current) clearTimeout(flashTimerRef.current);
        };
    }, [price, showFlash]);

    if (price == null) return <span style={{ color: 'var(--text-muted)' }}>—</span>;

    const colorClass = change != null ? priceColorClass(change) : '';

    return (
        <span
            className={`${colorClass} ${flashClass}`}
            style={{
                fontFamily: 'var(--font-mono)',
                fontWeight: 600,
                fontSize: SIZE_MAP[size],
                borderRadius: 'var(--radius-sm)',
                padding: '0 4px',
                transition: 'background 0.3s',
            }}
        >
            {formatCurrency(price)}
        </span>
    );
};

export default PriceTag;
