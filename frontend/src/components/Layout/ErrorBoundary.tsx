/**
 * ErrorBoundary — graceful crash recovery
 *
 * Catches render errors and displays a fallback UI with a retry button.
 */

import { Component, type ErrorInfo, type ReactNode } from 'react';

interface Props {
    children: ReactNode;
    fallback?: ReactNode;
}

interface State {
    hasError: boolean;
    error: Error | null;
}

export default class ErrorBoundary extends Component<Props, State> {
    constructor(props: Props) {
        super(props);
        this.state = { hasError: false, error: null };
    }

    static getDerivedStateFromError(error: Error): State {
        return { hasError: true, error };
    }

    componentDidCatch(error: Error, errorInfo: ErrorInfo) {
        console.error('[ErrorBoundary]', error, errorInfo);
    }

    handleRetry = () => {
        this.setState({ hasError: false, error: null });
    };

    render() {
        if (this.state.hasError) {
            if (this.props.fallback) {
                return this.props.fallback;
            }

            return (
                <div className="error-boundary">
                    <div className="error-boundary-card">
                        <div className="error-boundary-icon">⚠️</div>
                        <h2>Something went wrong</h2>
                        <p className="error-boundary-message">
                            {this.state.error?.message || 'An unexpected error occurred'}
                        </p>
                        <button type="button" className="btn btn-primary" onClick={this.handleRetry}>
                            Try Again
                        </button>
                    </div>
                </div>
            );
        }

        return this.props.children;
    }
}
