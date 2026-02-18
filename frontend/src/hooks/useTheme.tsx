/**
 * Theme hook — dark/light mode with Redis + localStorage persistence
 *
 * Toggles `data-theme` attribute on <html>.
 * Default: 'dark'. Persisted to `mp_theme` (localStorage) + Redis via preferencesApi.
 */

import { createContext, type ReactNode, useCallback, useContext, useEffect, useState } from 'react';
import { preferencesApi } from '../api/client';

type Theme = 'dark' | 'light';

interface ThemeContextValue {
    theme: Theme;
    toggleTheme: () => void;
    setTheme: (t: Theme) => void;
}

const ThemeContext = createContext<ThemeContextValue | null>(null);

function getStoredTheme(): Theme {
    try {
        const stored = localStorage.getItem('mp_theme');
        if (stored === 'light' || stored === 'dark') return stored;
    } catch {
        /* ignore */
    }
    return 'dark';
}

export function ThemeProvider({ children }: { children: ReactNode }) {
    const [theme, setThemeState] = useState<Theme>(getStoredTheme);

    // Apply theme to DOM + write-through localStorage on every change
    useEffect(() => {
        document.documentElement.setAttribute('data-theme', theme);
        try {
            localStorage.setItem('mp_theme', theme);
        } catch {
            /* ignore */
        }
    }, [theme]);

    // Hydrate from API on mount (overrides localStorage if server has data)
    useEffect(() => {
        preferencesApi
            .get()
            .then((res) => {
                const apiTheme = res.data?.preferences?.theme;
                if (apiTheme === 'dark' || apiTheme === 'light') {
                    setThemeState(apiTheme);
                }
            })
            .catch(() => {
                /* API unavailable — localStorage stands */
            });
    }, []);

    const toggleTheme = useCallback(() => {
        setThemeState((prev) => {
            const next = prev === 'dark' ? 'light' : 'dark';
            // Persist to API (fire-and-forget)
            preferencesApi.set('theme', next).catch(() => {
                /* ignore */
            });
            return next;
        });
    }, []);

    const setTheme = useCallback((t: Theme) => {
        setThemeState(t);
        preferencesApi.set('theme', t).catch(() => {
            /* ignore */
        });
    }, []);

    return <ThemeContext.Provider value={{ theme, toggleTheme, setTheme }}>{children}</ThemeContext.Provider>;
}

// eslint-disable-next-line react-refresh/only-export-components
export function useTheme() {
    const ctx = useContext(ThemeContext);
    if (!ctx) throw new Error('useTheme must be used within <ThemeProvider>');
    return ctx;
}
