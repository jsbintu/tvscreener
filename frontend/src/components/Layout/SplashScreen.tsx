/**
 * SplashScreen — Animated intro with Bubby Vision logo
 *
 * Shows the splash image centered on a dark background,
 * fades in with a scale animation, then fades out after 2s.
 */

import { useEffect, useState } from 'react';

interface SplashScreenProps {
    /** Duration in ms before splash starts fading out */
    duration?: number;
    /** Called after the splash is fully dismissed */
    onComplete: () => void;
}

export default function SplashScreen({ duration = 2000, onComplete }: SplashScreenProps) {
    const [phase, setPhase] = useState<'enter' | 'exit' | 'done'>('enter');

    useEffect(() => {
        // After `duration` ms, start the exit animation
        const showTimer = setTimeout(() => setPhase('exit'), duration);
        // After exit animation (600ms), mark as done
        const doneTimer = setTimeout(() => {
            setPhase('done');
            onComplete();
        }, duration + 600);

        return () => {
            clearTimeout(showTimer);
            clearTimeout(doneTimer);
        };
    }, [duration, onComplete]);

    if (phase === 'done') return null;

    return (
        <div className={`splash-screen ${phase === 'exit' ? 'splash-screen--exit' : ''}`}>
            <img src="/splash.png" alt="Bubby Vision" className="splash-logo" />
            <p className="splash-tagline">AI-Powered Trading Analysis</p>
        </div>
    );
}
