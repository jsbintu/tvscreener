import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { describe, expect, it } from 'vitest';
import Sidebar from '../components/Layout/Sidebar';
import { AuthProvider } from '../context/AuthContext';

function renderWithRouter() {
    return render(
        <MemoryRouter initialEntries={['/']}>
            <AuthProvider>
                <Sidebar />
            </AuthProvider>
        </MemoryRouter>,
    );
}

describe('Sidebar', () => {
    it('renders the brand text', () => {
        renderWithRouter();
        expect(screen.getByText(/Bubby Vision/i)).toBeInTheDocument();
    });

    it('renders navigation items', () => {
        renderWithRouter();
        expect(screen.getByText(/Dashboard/i)).toBeInTheDocument();
        expect(screen.getByText(/Screener/i)).toBeInTheDocument();
        expect(screen.getByText(/Watchlist/i)).toBeInTheDocument();
    });

    it('renders chat nav item', () => {
        renderWithRouter();
        expect(screen.getByText(/Chat/i)).toBeInTheDocument();
    });

    it('renders options flow nav item', () => {
        renderWithRouter();
        expect(screen.getByText(/Options/i)).toBeInTheDocument();
    });

    it('contains navigation links', () => {
        renderWithRouter();
        const links = screen.getAllByRole('link');
        expect(links.length).toBeGreaterThanOrEqual(5);
    });
});
