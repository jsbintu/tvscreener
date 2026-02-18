/**
 * Keyboard shortcuts tests
 */

import { fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { useKeyboardShortcuts } from '../hooks/useKeyboardShortcuts';

// Component that activates the shortcuts
function ShortcutsHost() {
    useKeyboardShortcuts();
    const location = useLocation();
    return <div data-testid="location">{location.pathname}</div>;
}

function renderWithRouter(initialPath = '/') {
    return render(
        <MemoryRouter initialEntries={[initialPath]}>
            <Routes>
                <Route path="*" element={<ShortcutsHost />} />
            </Routes>
        </MemoryRouter>,
    );
}

describe('useKeyboardShortcuts', () => {
    afterEach(() => {
        vi.restoreAllMocks();
    });

    it('focuses search input on / key', () => {
        renderWithRouter();

        // Create a mock search input
        const searchInput = document.createElement('input');
        searchInput.className = 'search-input';
        document.body.appendChild(searchInput);

        const focusSpy = vi.spyOn(searchInput, 'focus');
        fireEvent.keyDown(document, { key: '/' });

        expect(focusSpy).toHaveBeenCalled();
        document.body.removeChild(searchInput);
    });

    it('blurs active element on Escape', () => {
        renderWithRouter();

        const input = document.createElement('input');
        document.body.appendChild(input);
        input.focus();

        expect(document.activeElement).toBe(input);
        fireEvent.keyDown(document, { key: 'Escape' });
        expect(document.activeElement).not.toBe(input);

        document.body.removeChild(input);
    });

    it('navigates with g+d to dashboard', () => {
        renderWithRouter('/screener');

        fireEvent.keyDown(document, { key: 'g' });
        fireEvent.keyDown(document, { key: 'd' });

        expect(screen.getByTestId('location').textContent).toBe('/');
    });

    it('navigates with g+s to screener', () => {
        renderWithRouter('/');

        fireEvent.keyDown(document, { key: 'g' });
        fireEvent.keyDown(document, { key: 's' });

        expect(screen.getByTestId('location').textContent).toBe('/screener');
    });
});
