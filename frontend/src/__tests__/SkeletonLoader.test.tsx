/**
 * SkeletonLoader — Unit Tests
 */

import { render } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import SkeletonLoader from '../components/Data/SkeletonLoader';

describe('SkeletonLoader', () => {
    it('renders the default number of skeleton lines (3)', () => {
        const { container } = render(<SkeletonLoader />);
        const skeletons = container.querySelectorAll('.skeleton');
        expect(skeletons.length).toBe(3);
    });

    it('renders a custom number of lines', () => {
        const { container } = render(<SkeletonLoader lines={5} />);
        const skeletons = container.querySelectorAll('.skeleton');
        expect(skeletons.length).toBe(5);
    });

    it('renders a card variant', () => {
        const { container } = render(<SkeletonLoader variant="card" />);
        const skeleton = container.querySelector('.skeleton');
        expect(skeleton).toBeTruthy();
        // Card variant renders a single skeleton, not multiple
        expect(container.querySelectorAll('.skeleton').length).toBe(1);
    });

    it('applies custom height to card variant', () => {
        const { container } = render(<SkeletonLoader variant="card" height="200px" />);
        const skeleton = container.querySelector('.skeleton') as HTMLElement;
        expect(skeleton.style.height).toBe('200px');
    });

    it('renders a circle variant', () => {
        const { container } = render(<SkeletonLoader variant="circle" size={48} />);
        const skeleton = container.querySelector('.skeleton') as HTMLElement;
        expect(skeleton.style.width).toBe('48px');
        expect(skeleton.style.height).toBe('48px');
        expect(skeleton.style.borderRadius).toBe('50%');
    });

    it('makes the last line shorter (60%) in lines variant', () => {
        const { container } = render(<SkeletonLoader lines={3} />);
        const skeletons = container.querySelectorAll('.skeleton');
        const lastSkeleton = skeletons[skeletons.length - 1] as HTMLElement;
        expect(lastSkeleton.style.width).toBe('60%');
    });

    it('applies custom width to lines variant', () => {
        const { container } = render(<SkeletonLoader lines={2} width="80%" />);
        const skeletons = container.querySelectorAll('.skeleton');
        // First line should use custom width
        expect((skeletons[0] as HTMLElement).style.width).toBe('80%');
    });
});
