/**
 * Tests for useTheme hook and ThemeProvider
 */

import { act, render, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { ThemeProvider, useTheme } from '../hooks/useTheme';

function ThemeConsumer() {
    const { theme, toggleTheme } = useTheme();
    return (
        <div>
            <span data-testid="theme-value">{theme}</span>
            <button type="button" data-testid="toggle-btn" onClick={toggleTheme}>
                Toggle
            </button>
        </div>
    );
}

describe('useTheme', () => {
    beforeEach(() => {
        localStorage.clear();
        document.documentElement.removeAttribute('data-theme');
    });

    it('defaults to dark theme', () => {
        render(
            <ThemeProvider>
                <ThemeConsumer />
            </ThemeProvider>,
        );
        expect(screen.getByTestId('theme-value').textContent).toBe('dark');
    });

    it('sets data-theme attribute on html element', () => {
        render(
            <ThemeProvider>
                <ThemeConsumer />
            </ThemeProvider>,
        );
        expect(document.documentElement.getAttribute('data-theme')).toBe('dark');
    });

    it('toggles to light theme', () => {
        render(
            <ThemeProvider>
                <ThemeConsumer />
            </ThemeProvider>,
        );
        act(() => {
            screen.getByTestId('toggle-btn').click();
        });
        expect(screen.getByTestId('theme-value').textContent).toBe('light');
        expect(document.documentElement.getAttribute('data-theme')).toBe('light');
    });

    it('persists theme to localStorage', () => {
        render(
            <ThemeProvider>
                <ThemeConsumer />
            </ThemeProvider>,
        );
        act(() => {
            screen.getByTestId('toggle-btn').click();
        });
        expect(localStorage.getItem('mp_theme')).toBe('light');
    });

    it('reads stored theme from localStorage', () => {
        localStorage.setItem('mp_theme', 'light');
        render(
            <ThemeProvider>
                <ThemeConsumer />
            </ThemeProvider>,
        );
        expect(screen.getByTestId('theme-value').textContent).toBe('light');
    });

    it('throws when used outside ThemeProvider', () => {
        // Suppress React error boundary console output
        const consoleError = vi.spyOn(console, 'error').mockImplementation(() => {});
        expect(() => render(<ThemeConsumer />)).toThrow('useTheme must be used within <ThemeProvider>');
        consoleError.mockRestore();
    });
});
