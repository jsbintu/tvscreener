/**
 * AuthContext tests — login/logout state, token storage
 */

import { act, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { AuthProvider, useAuth } from '../context/AuthContext';

// Mock the authApi module
vi.mock('../api/client', () => ({
    authApi: {
        login: vi.fn(),
        register: vi.fn(),
        refresh: vi.fn(),
        me: vi.fn(),
    },
}));

// Helper component that exposes auth state for testing
function AuthConsumer() {
    const { user, isAuthenticated, isLoading, login, logout } = useAuth();

    return (
        <div>
            <div data-testid="loading">{String(isLoading)}</div>
            <div data-testid="authenticated">{String(isAuthenticated)}</div>
            <div data-testid="user">{user ? user.display_name : 'null'}</div>
            <button type="button" onClick={() => login('test@example.com', 'password')}>
                Login
            </button>
            <button type="button" onClick={logout}>
                Logout
            </button>
        </div>
    );
}

describe('AuthContext', () => {
    beforeEach(() => {
        localStorage.clear();
        vi.clearAllMocks();
    });

    it('throws when useAuth is used outside AuthProvider', () => {
        // Suppress console.error for expected error
        const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {});
        expect(() => render(<AuthConsumer />)).toThrow('useAuth must be used within <AuthProvider>');
        consoleSpy.mockRestore();
    });

    it('starts with isAuthenticated=false when no token stored', async () => {
        render(
            <AuthProvider>
                <AuthConsumer />
            </AuthProvider>,
        );

        // After mount resolves, loading should be false
        await vi.waitFor(() => {
            expect(screen.getByTestId('loading').textContent).toBe('false');
        });
        expect(screen.getByTestId('authenticated').textContent).toBe('false');
        expect(screen.getByTestId('user').textContent).toBe('null');
    });

    it('clears state on logout', async () => {
        const user = userEvent.setup();
        localStorage.setItem('mp_access_token', 'test-token');
        localStorage.setItem('mp_refresh_token', 'test-refresh');

        // Mock authApi.me to return a user
        const { authApi } = await import('../api/client');
        (authApi.me as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
            data: {
                id: '123',
                email: 'test@example.com',
                display_name: 'Test User',
                is_active: true,
                created_at: '2026-01-01',
            },
        });

        render(
            <AuthProvider>
                <AuthConsumer />
            </AuthProvider>,
        );

        await vi.waitFor(() => {
            expect(screen.getByTestId('authenticated').textContent).toBe('true');
        });
        expect(screen.getByTestId('user').textContent).toBe('Test User');

        // Logout
        await act(async () => {
            await user.click(screen.getByText('Logout'));
        });

        expect(screen.getByTestId('authenticated').textContent).toBe('false');
        expect(screen.getByTestId('user').textContent).toBe('null');
        expect(localStorage.getItem('mp_access_token')).toBeNull();
        expect(localStorage.getItem('mp_refresh_token')).toBeNull();
    });

    it('login stores tokens and sets user', async () => {
        const user = userEvent.setup();
        const { authApi } = await import('../api/client');

        (authApi.login as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
            data: { access_token: 'new-access', refresh_token: 'new-refresh' },
        });
        (authApi.me as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
            data: {
                id: '456',
                email: 'test@example.com',
                display_name: 'Logged In User',
                is_active: true,
                created_at: '2026-01-01',
            },
        });

        render(
            <AuthProvider>
                <AuthConsumer />
            </AuthProvider>,
        );

        await vi.waitFor(() => {
            expect(screen.getByTestId('loading').textContent).toBe('false');
        });

        await act(async () => {
            await user.click(screen.getByText('Login'));
        });

        await vi.waitFor(() => {
            expect(screen.getByTestId('authenticated').textContent).toBe('true');
        });
        expect(screen.getByTestId('user').textContent).toBe('Logged In User');
        expect(localStorage.getItem('mp_access_token')).toBe('new-access');
        expect(localStorage.getItem('mp_refresh_token')).toBe('new-refresh');
    });
});
