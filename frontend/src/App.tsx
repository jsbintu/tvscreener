import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { useCallback, useEffect, useState } from 'react';
import { BrowserRouter, Route, Routes } from 'react-router-dom';
import client from './api/client';
import { installToastInterceptor } from './api/toastInterceptor';
import ErrorBoundary from './components/Layout/ErrorBoundary';
import Header from './components/Layout/Header';
import ProtectedRoute from './components/Layout/ProtectedRoute';
import Sidebar from './components/Layout/Sidebar';
import SplashScreen from './components/Layout/SplashScreen';
import { ToastProvider, useToast } from './components/Layout/ToastContext';
import { AuthProvider } from './context/AuthContext';
import { ThemeProvider } from './hooks/useTheme';
import Chat from './pages/Chat/Chat';
import Dashboard from './pages/Dashboard/Dashboard';
import Login from './pages/Login/Login';
import OptionsFlow from './pages/OptionsFlow/OptionsFlow';
import PatternScanner from './pages/PatternScanner/PatternScanner';
import Register from './pages/Register/Register';
import Screener from './pages/Screener/Screener';
import Settings from './pages/Settings/Settings';
import StockDetail from './pages/StockDetail/StockDetail';
import Watchlist from './pages/Watchlist/Watchlist';

const queryClient = new QueryClient({
    defaultOptions: {
        queries: {
            refetchOnWindowFocus: true,
            retry: 1,
            staleTime: 30_000,
        },
    },
});

/** Wires the toast interceptor into the API client once mounted. */
function ApiToastWiring() {
    const toast = useToast();
    useEffect(() => {
        installToastInterceptor(client, toast);
    }, [toast]);
    return null;
}

export default function App() {
    const [showSplash, setShowSplash] = useState(true);
    const dismissSplash = useCallback(() => setShowSplash(false), []);

    return (
        <ErrorBoundary>
            <ThemeProvider>
                {showSplash && <SplashScreen onComplete={dismissSplash} />}
                <QueryClientProvider client={queryClient}>
                    <BrowserRouter>
                        <AuthProvider>
                            <ToastProvider>
                                <ApiToastWiring />
                                <Routes>
                                    {/* Public routes */}
                                    <Route path="/login" element={<Login />} />
                                    <Route path="/register" element={<Register />} />

                                    {/* Protected routes */}
                                    <Route
                                        path="/*"
                                        element={
                                            <ProtectedRoute>
                                                <div className="app-layout">
                                                    <Sidebar />
                                                    <Header />
                                                    <main className="main-content">
                                                        <Routes>
                                                            <Route path="/" element={<Dashboard />} />
                                                            <Route path="/stock/:ticker" element={<StockDetail />} />
                                                            <Route path="/screener" element={<Screener />} />
                                                            <Route path="/watchlist" element={<Watchlist />} />
                                                            <Route path="/chat" element={<Chat />} />
                                                            <Route path="/scanner" element={<PatternScanner />} />
                                                            <Route path="/flow" element={<OptionsFlow />} />
                                                            <Route path="/settings" element={<Settings />} />
                                                        </Routes>
                                                    </main>
                                                </div>
                                            </ProtectedRoute>
                                        }
                                    />
                                </Routes>
                            </ToastProvider>
                        </AuthProvider>
                    </BrowserRouter>
                </QueryClientProvider>
            </ThemeProvider>
        </ErrorBoundary>
    );
}
