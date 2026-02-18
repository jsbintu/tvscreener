/**
 * useKeyboardShortcuts — global keyboard navigation
 *
 * Shortcuts:
 *   /       → Focus search input
 *   Escape  → Blur active element
 *   g d     → Navigate to Dashboard
 *   g s     → Navigate to Screener
 *   g w     → Navigate to Watchlist
 *   g c     → Navigate to Chat
 *   g f     → Navigate to Options Flow
 *   g x     → Navigate to Settings
 */

import { useCallback, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';

const NAV_KEYS: Record<string, string> = {
    d: '/',
    s: '/screener',
    w: '/watchlist',
    c: '/chat',
    f: '/flow',
    x: '/settings',
};

export function useKeyboardShortcuts() {
    const navigate = useNavigate();
    const pendingG = useRef(false);
    const gTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

    const handleKeyDown = useCallback(
        (e: KeyboardEvent) => {
            const target = e.target as HTMLElement;
            const isInput =
                target.tagName === 'INPUT' ||
                target.tagName === 'TEXTAREA' ||
                target.tagName === 'SELECT' ||
                target.isContentEditable;

            // Escape — always blur active element
            if (e.key === 'Escape') {
                (document.activeElement as HTMLElement)?.blur();
                return;
            }

            // Skip other shortcuts if user is typing
            if (isInput) return;

            // `/` — focus search
            if (e.key === '/') {
                e.preventDefault();
                const searchInput = document.querySelector<HTMLInputElement>('.search-input');
                searchInput?.focus();
                return;
            }

            // `g` prefix — navigation
            if (e.key === 'g' && !pendingG.current) {
                pendingG.current = true;
                gTimer.current = setTimeout(() => {
                    pendingG.current = false;
                }, 500);
                return;
            }

            if (pendingG.current) {
                pendingG.current = false;
                if (gTimer.current) clearTimeout(gTimer.current);
                const route = NAV_KEYS[e.key];
                if (route) {
                    e.preventDefault();
                    navigate(route);
                }
            }
        },
        [navigate],
    );

    useEffect(() => {
        document.addEventListener('keydown', handleKeyDown);
        return () => {
            document.removeEventListener('keydown', handleKeyDown);
            if (gTimer.current) clearTimeout(gTimer.current);
        };
    }, [handleKeyDown]);
}
