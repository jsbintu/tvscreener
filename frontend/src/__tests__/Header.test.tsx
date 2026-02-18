/**
 * Header — Unit Tests
 */

import { fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import Header from '../components/Layout/Header';

// Mock auth context
vi.mock('../context/AuthContext', () => ({
    useAuth: () => ({ user: { username: 'testuser' }, logout: vi.fn() }),
}));

// Mock WebSocket hooks — must match shape used by both Header and ConnectionStatus
vi.mock('../hooks/useWebSocket', () => ({
    useAlertStream: () => ({ connected: false, status: 'disconnected' }),
}));

function renderHeader() {
    return render(
        <MemoryRouter>
            <Header />
        </MemoryRouter>,
    );
}

describe('Header', () => {
    beforeEach(() => {
        document.body.removeAttribute('data-sidebar-open');
    });

    it('renders the search input', () => {
        renderHeader();
        const searchInput = screen.getByPlaceholderText(/search ticker/i);
        expect(searchInput).toBeTruthy();
    });

    it('renders the notification bell icon', () => {
        const { container } = renderHeader();
        // Bell icon button inside notification-wrapper
        const bellBtn = container.querySelector('.notification-wrapper button');
        expect(bellBtn).toBeTruthy();
    });

    it('renders the hamburger button', () => {
        const { container } = renderHeader();
        const hamburger = container.querySelector('.header-hamburger');
        expect(hamburger).toBeTruthy();
    });

    it('toggles sidebar open attribute on hamburger click', () => {
        const { container } = renderHeader();
        const hamburger = container.querySelector('.header-hamburger') as HTMLElement;

        // Initially no data-sidebar-open
        expect(document.body.getAttribute('data-sidebar-open')).toBeNull();

        // Click to open
        fireEvent.click(hamburger);
        expect(document.body.getAttribute('data-sidebar-open')).toBe('true');

        // Click again to close
        fireEvent.click(hamburger);
        expect(document.body.getAttribute('data-sidebar-open')).toBe('false');
    });

    it('handles search input changes', () => {
        renderHeader();
        const searchInput = screen.getByPlaceholderText(/search ticker/i) as HTMLInputElement;
        fireEvent.change(searchInput, { target: { value: 'AAPL' } });
        expect(searchInput.value).toBe('AAPL');
    });
});
