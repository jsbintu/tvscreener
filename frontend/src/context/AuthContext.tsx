/**
 * AuthContext — JWT authentication state management
 *
 * Provides user state, login/register/logout functions, and token management.
 * Stores JWT pair in localStorage and auto-validates on mount.
 */

import { createContext, type ReactNode, useCallback, useContext, useEffect, useRef, useState } from 'react';
import { authApi } from '../api/client';

interface User {
    id: string;
    email: string;
    display_name: string;
    is_active: boolean;
    created_at: string;
}

interface AuthState {
    user: User | null;
    isAuthenticated: boolean;
    isLoading: boolean;
    login: (email: string, password: string) => Promise<void>;
    register: (email: string, password: string, displayName: string) => Promise<void>;
    logout: () => void;
}

const AuthContext = createContext<AuthState | null>(null);

const TOKEN_KEY = 'mp_access_token';
const REFRESH_KEY = 'mp_refresh_token';

function storeTokens(access: string, refresh: string) {
    localStorage.setItem(TOKEN_KEY, access);
    localStorage.setItem(REFRESH_KEY, refresh);
}

function clearTokens() {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(REFRESH_KEY);
}

export function AuthProvider({ children }: { children: ReactNode }) {
    const [user, setUser] = useState<User | null>(null);
    const [isLoading, setIsLoading] = useState(true);
    const initialized = useRef(false);

    // ── Validate stored token on mount ──
    useEffect(() => {
        if (initialized.current) return;
        initialized.current = true;

        const token = localStorage.getItem(TOKEN_KEY);
        if (!token) {
            // Use a microtask to avoid synchronous setState warnings
            queueMicrotask(() => setIsLoading(false));
            return;
        }

        authApi
            .me()
            .then((res) => {
                setUser(res.data);
            })
            .catch(() => {
                // Token invalid or expired — try refresh
                const refresh = localStorage.getItem(REFRESH_KEY);
                if (refresh) {
                    return authApi
                        .refresh(refresh)
                        .then((res) => {
                            storeTokens(res.data.access_token, res.data.refresh_token);
                            return authApi.me();
                        })
                        .then((res) => setUser(res.data))
                        .catch(() => clearTokens());
                }
                clearTokens();
            })
            .finally(() => setIsLoading(false));
    }, []);

    const login = useCallback(async (email: string, password: string) => {
        const res = await authApi.login(email, password);
        storeTokens(res.data.access_token, res.data.refresh_token);
        const me = await authApi.me();
        setUser(me.data);
    }, []);

    const register = useCallback(async (email: string, password: string, displayName: string) => {
        await authApi.register(email, password, displayName);
        // Auto-login after registration
        const res = await authApi.login(email, password);
        storeTokens(res.data.access_token, res.data.refresh_token);
        const me = await authApi.me();
        setUser(me.data);
    }, []);

    const logout = useCallback(() => {
        clearTokens();
        setUser(null);
    }, []);

    return (
        <AuthContext.Provider
            value={{
                user,
                isAuthenticated: !!user,
                isLoading,
                login,
                register,
                logout,
            }}
        >
            {children}
        </AuthContext.Provider>
    );
}

// eslint-disable-next-line react-refresh/only-export-components
export function useAuth(): AuthState {
    const ctx = useContext(AuthContext);
    if (!ctx) throw new Error('useAuth must be used within <AuthProvider>');
    return ctx;
}
