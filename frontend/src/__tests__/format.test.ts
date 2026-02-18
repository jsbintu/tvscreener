import { describe, expect, it } from 'vitest';
import { formatCompact, formatCurrency, formatDate, formatPercent, priceColorClass, timeAgo } from '../utils/format';

describe('formatCurrency', () => {
    it('formats positive numbers as USD', () => {
        expect(formatCurrency(1234.56)).toBe('$1,234.56');
    });

    it('formats zero', () => {
        expect(formatCurrency(0)).toBe('$0.00');
    });

    it('returns em-dash for null', () => {
        expect(formatCurrency(null)).toBe('—');
    });

    it('returns em-dash for undefined', () => {
        expect(formatCurrency(undefined)).toBe('—');
    });

    it('formats negative numbers', () => {
        expect(formatCurrency(-42.5)).toBe('-$42.50');
    });
});

describe('formatPercent', () => {
    it('formats positive with + sign', () => {
        expect(formatPercent(4.25)).toBe('+4.25%');
    });

    it('formats negative without + sign', () => {
        expect(formatPercent(-2.1)).toBe('-2.10%');
    });

    it('formats zero with + sign', () => {
        expect(formatPercent(0)).toBe('+0.00%');
    });

    it('returns em-dash for null', () => {
        expect(formatPercent(null)).toBe('—');
    });
});

describe('formatCompact', () => {
    it('formats millions', () => {
        const result = formatCompact(1200000);
        expect(result).toMatch(/1\.2M/);
    });

    it('formats thousands', () => {
        const result = formatCompact(450000);
        expect(result).toMatch(/450K/);
    });

    it('returns em-dash for null', () => {
        expect(formatCompact(null)).toBe('—');
    });
});

describe('priceColorClass', () => {
    it('returns price-up for positive', () => {
        expect(priceColorClass(5)).toBe('price-up');
    });

    it('returns price-down for negative', () => {
        expect(priceColorClass(-3)).toBe('price-down');
    });

    it('returns price-flat for zero', () => {
        expect(priceColorClass(0)).toBe('price-flat');
    });

    it('returns price-flat for null', () => {
        expect(priceColorClass(null)).toBe('price-flat');
    });
});

describe('formatDate', () => {
    it('formats a valid ISO date', () => {
        // Use midday UTC to avoid timezone boundary shifts
        const result = formatDate('2024-06-15T12:00:00Z');
        expect(result).not.toBe('—');
        expect(result).toContain('2024');
        expect(result.length).toBeGreaterThan(4);
    });

    it('returns em-dash for null', () => {
        expect(formatDate(null)).toBe('—');
    });

    it('returns em-dash for undefined', () => {
        expect(formatDate(undefined)).toBe('—');
    });
});

describe('timeAgo', () => {
    it('formats seconds ago', () => {
        const now = new Date();
        now.setSeconds(now.getSeconds() - 30);
        expect(timeAgo(now.toISOString())).toBe('30s ago');
    });

    it('formats minutes ago', () => {
        const now = new Date();
        now.setMinutes(now.getMinutes() - 5);
        expect(timeAgo(now.toISOString())).toMatch(/5m ago/);
    });

    it('formats hours ago', () => {
        const now = new Date();
        now.setHours(now.getHours() - 3);
        expect(timeAgo(now.toISOString())).toMatch(/3h ago/);
    });

    it('formats days ago', () => {
        const now = new Date();
        now.setDate(now.getDate() - 7);
        expect(timeAgo(now.toISOString())).toMatch(/7d ago/);
    });
});
