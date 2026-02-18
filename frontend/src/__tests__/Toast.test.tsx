/**
 * Toast tests — render, types, dismiss, auto-dismiss
 */

import { act, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { ToastProvider, useToast } from '../components/Layout/ToastContext';

// Helper that triggers toasts for testing
function ToastTrigger() {
    const toast = useToast();

    return (
        <div>
            <button type="button" onClick={() => toast.success('Success message')}>
                Success
            </button>
            <button type="button" onClick={() => toast.error('Error message')}>
                Error
            </button>
            <button type="button" onClick={() => toast.info('Info message')}>
                Info
            </button>
        </div>
    );
}

describe('Toast', () => {
    beforeEach(() => {
        vi.useFakeTimers();
    });

    afterEach(() => {
        vi.useRealTimers();
    });

    it('throws when useToast is used outside ToastProvider', () => {
        const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {});
        expect(() => render(<ToastTrigger />)).toThrow('useToast must be used within <ToastProvider>');
        consoleSpy.mockRestore();
    });

    it('renders a success toast', () => {
        render(
            <ToastProvider>
                <ToastTrigger />
            </ToastProvider>,
        );

        act(() => {
            fireEvent.click(screen.getByText('Success'));
        });

        expect(screen.getByText('Success message')).toBeInTheDocument();
    });

    it('renders an error toast', () => {
        render(
            <ToastProvider>
                <ToastTrigger />
            </ToastProvider>,
        );

        act(() => {
            fireEvent.click(screen.getByText('Error'));
        });

        expect(screen.getByText('Error message')).toBeInTheDocument();
    });

    it('renders an info toast', () => {
        render(
            <ToastProvider>
                <ToastTrigger />
            </ToastProvider>,
        );

        act(() => {
            fireEvent.click(screen.getByText('Info'));
        });

        expect(screen.getByText('Info message')).toBeInTheDocument();
    });

    it('auto-dismisses after 5 seconds', () => {
        render(
            <ToastProvider>
                <ToastTrigger />
            </ToastProvider>,
        );

        act(() => {
            fireEvent.click(screen.getByText('Success'));
        });

        expect(screen.getByText('Success message')).toBeInTheDocument();

        // Advance time past the 5s auto-dismiss
        act(() => {
            vi.advanceTimersByTime(5100);
        });

        expect(screen.queryByText('Success message')).not.toBeInTheDocument();
    });

    it('dismiss button removes the toast', () => {
        render(
            <ToastProvider>
                <ToastTrigger />
            </ToastProvider>,
        );

        act(() => {
            fireEvent.click(screen.getByText('Info'));
        });

        expect(screen.getByText('Info message')).toBeInTheDocument();

        const dismissBtn = screen.getByRole('button', { name: 'Dismiss' });
        act(() => {
            fireEvent.click(dismissBtn);
        });

        expect(screen.queryByText('Info message')).not.toBeInTheDocument();
    });
});
