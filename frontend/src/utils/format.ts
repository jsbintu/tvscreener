/** Format a number as currency (e.g. $1,234.56) */
export function formatCurrency(value: number | null | undefined): string {
    if (value == null) return '—';
    return new Intl.NumberFormat('en-US', {
        style: 'currency',
        currency: 'USD',
        minimumFractionDigits: 2,
        maximumFractionDigits: 2,
    }).format(value);
}

/** Format a number as percentage (e.g. +4.25%) */
export function formatPercent(value: number | null | undefined): string {
    if (value == null) return '—';
    const sign = value >= 0 ? '+' : '';
    return `${sign}${value.toFixed(2)}%`;
}

/** Format large numbers compactly (e.g. 1.2M, 450K) */
export function formatCompact(value: number | null | undefined): string {
    if (value == null) return '—';
    return new Intl.NumberFormat('en-US', { notation: 'compact' }).format(value);
}

/** Get color class for price change */
export function priceColorClass(change: number | null | undefined): string {
    if (change == null || change === 0) return 'price-flat';
    return change > 0 ? 'price-up' : 'price-down';
}

/** Format a date string or Date object */
export function formatDate(date: string | Date | null | undefined): string {
    if (!date) return '—';
    const d = date instanceof Date ? date : new Date(date);
    return d.toLocaleDateString('en-US', {
        month: 'short',
        day: 'numeric',
        year: 'numeric',
    });
}

/** Format time ago */
export function timeAgo(date: string | Date): string {
    const d = date instanceof Date ? date : new Date(date);
    const s = Math.floor((Date.now() - d.getTime()) / 1000);
    if (s < 60) return `${s}s ago`;
    if (s < 3600) return `${Math.floor(s / 60)}m ago`;
    if (s < 86400) return `${Math.floor(s / 3600)}h ago`;
    return `${Math.floor(s / 86400)}d ago`;
}
