/**
 * Sparkline — Unit tests
 */

import { render } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import Sparkline from '../components/Charts/Sparkline';

describe('Sparkline', () => {
    it('renders an SVG polyline from data points', () => {
        const { container } = render(<Sparkline data={[10, 12, 11, 15, 14]} />);
        const svg = container.querySelector('svg');
        expect(svg).toBeTruthy();

        const polyline = container.querySelector('polyline');
        expect(polyline).toBeTruthy();
        expect(polyline?.getAttribute('points')).toBeTruthy();
    });

    it('returns null when data has fewer than 2 points', () => {
        const { container } = render(<Sparkline data={[5]} />);
        expect(container.querySelector('svg')).toBeNull();
    });

    it('returns null when data is empty', () => {
        const { container } = render(<Sparkline data={[]} />);
        expect(container.querySelector('svg')).toBeNull();
    });

    it('uses auto color — green for upward trend', () => {
        const { container } = render(<Sparkline data={[10, 11, 12, 13, 14]} color="auto" />);
        const polyline = container.querySelector('polyline');
        expect(polyline?.getAttribute('stroke')).toBe('var(--accent-green)');
    });

    it('uses auto color — red for downward trend', () => {
        const { container } = render(<Sparkline data={[14, 13, 12, 11, 10]} color="auto" />);
        const polyline = container.querySelector('polyline');
        expect(polyline?.getAttribute('stroke')).toBe('var(--accent-red)');
    });

    it('accepts custom width and height', () => {
        const { container } = render(<Sparkline data={[1, 2, 3]} width={120} height={40} />);
        const svg = container.querySelector('svg');
        expect(svg?.getAttribute('width')).toBe('120');
        expect(svg?.getAttribute('height')).toBe('40');
    });

    it('uses custom color instead of auto', () => {
        const { container } = render(<Sparkline data={[5, 10, 15]} color="var(--accent-blue)" />);
        const polyline = container.querySelector('polyline');
        expect(polyline?.getAttribute('stroke')).toBe('var(--accent-blue)');
    });
});
