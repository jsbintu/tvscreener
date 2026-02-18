/**
 * SplashScreen — Unit Tests
 */

import { act, render } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import SplashScreen from '../components/Layout/SplashScreen';

describe('SplashScreen', () => {
    beforeEach(() => {
        vi.useFakeTimers();
    });

    afterEach(() => {
        vi.useRealTimers();
    });

    it('renders the splash logo and tagline', () => {
        const onComplete = vi.fn();
        const { container } = render(<SplashScreen onComplete={onComplete} />);

        const img = container.querySelector('.splash-logo') as HTMLImageElement;
        expect(img).toBeTruthy();
        expect(img.alt).toBe('Bubby Vision');
        expect(img.src).toContain('splash.png');

        const tagline = container.querySelector('.splash-tagline');
        expect(tagline).toBeTruthy();
        expect(tagline?.textContent).toBe('AI-Powered Trading Analysis');
    });

    it('calls onComplete after duration + exit animation', () => {
        const onComplete = vi.fn();
        render(<SplashScreen onComplete={onComplete} duration={1000} />);

        // Not called yet at 999ms
        act(() => {
            vi.advanceTimersByTime(999);
        });
        expect(onComplete).not.toHaveBeenCalled();

        // Called after 1000 + 600 = 1600ms
        act(() => {
            vi.advanceTimersByTime(601);
        });
        expect(onComplete).toHaveBeenCalledTimes(1);
    });

    it('adds exit class during fade-out phase', () => {
        const onComplete = vi.fn();
        const { container } = render(<SplashScreen onComplete={onComplete} duration={500} />);

        // Initially no exit class
        expect(container.querySelector('.splash-screen--exit')).toBeNull();

        // After duration, exit class should appear
        act(() => {
            vi.advanceTimersByTime(500);
        });
        expect(container.querySelector('.splash-screen--exit')).toBeTruthy();
    });

    it('returns null after completion', () => {
        const onComplete = vi.fn();
        const { container } = render(<SplashScreen onComplete={onComplete} duration={500} />);

        act(() => {
            vi.advanceTimersByTime(1100);
        });
        // After done phase, component should render nothing
        expect(container.querySelector('.splash-screen')).toBeNull();
    });

    it('uses default 2000ms duration when none specified', () => {
        const onComplete = vi.fn();
        render(<SplashScreen onComplete={onComplete} />);

        act(() => {
            vi.advanceTimersByTime(1999);
        });
        expect(onComplete).not.toHaveBeenCalled();

        act(() => {
            vi.advanceTimersByTime(601);
        });
        expect(onComplete).toHaveBeenCalledTimes(1);
    });
});
