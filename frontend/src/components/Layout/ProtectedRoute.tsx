/**
 * ProtectedRoute — Redirects to /login if not authenticated
 *
 * In development mode (default), auth is bypassed so you can use the app
 * without registering. Set VITE_DEV_BYPASS_AUTH=false to enforce login in dev.
 */

import { Navigate } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';

const DEV_BYPASS = import.meta.env.DEV && import.meta.env.VITE_DEV_BYPASS_AUTH !== 'false';

export default function ProtectedRoute({ children }: { children: React.ReactNode }) {
    const { isAuthenticated, isLoading } = useAuth();

    // In development mode, skip authentication entirely
    if (DEV_BYPASS) {
        return <>{children}</>;
    }

    if (isLoading) {
        return (
            <div className="page-container" style={{ display: 'flex', justifyContent: 'center', paddingTop: '20vh' }}>
                <div className="skeleton" style={{ width: 200, height: 24 }} />
            </div>
        );
    }

    if (!isAuthenticated) {
        return <Navigate to="/login" replace />;
    }

    return <>{children}</>;
}
