
import React, { useEffect, useRef, useState } from 'react';
import { useTheme } from '../context/ThemeContext';

export const VantaBackground: React.FC = () => {
    const vantaRef = useRef<HTMLDivElement>(null);
    const effectRef = useRef<any>(null);
    const { theme } = useTheme();

    const [systemIsDark, setSystemIsDark] = useState<boolean>(false);

    useEffect(() => {
        if (typeof window !== 'undefined' && window.matchMedia) {
            setSystemIsDark(window.matchMedia('(prefers-color-scheme: dark)').matches);
            const mediaQuery = window.matchMedia('(prefers-color-scheme: dark)');
            const handleChange = (e: MediaQueryListEvent) => setSystemIsDark(e.matches);
            mediaQuery.addEventListener('change', handleChange);
            return () => mediaQuery.removeEventListener('change', handleChange);
        }
    }, []);

    const isDark = theme === 'dark' || (theme === 'system' && systemIsDark);

    useEffect(() => {
        let cancelled = false;

        const initVanta = () => {
            if (!vantaRef.current || !(window as any).VANTA || !(window as any).THREE) {
                return;
            }

            if (effectRef.current) {
                effectRef.current.destroy();
                effectRef.current = null;
            }

            const backgroundColor = isDark ? 0x020617 : 0xffffff;
            const color = 0x2563eb;

            try {
                effectRef.current = (window as any).VANTA.NET({
                    el: vantaRef.current,
                    mouseControls: true,
                    touchControls: true,
                    gyroControls: false,
                    minHeight: 200.00,
                    minWidth: 200.00,
                    scale: 1.00,
                    scaleMobile: 1.00,
                    color: color,
                    backgroundColor: backgroundColor,
                    points: 12.00,
                    maxDistance: 23.00,
                    spacing: 18.00,
                    showDots: true,
                    backgroundAlpha: 1.0
                });
            } catch (error) {
                console.error("Vanta JS init error:", error);
            }
        };

        const scriptsLoaded = () => !!(window as any).VANTA && !!(window as any).THREE;

        // If scripts already cached/loaded, init immediately
        if (scriptsLoaded()) {
            initVanta();
            return () => {
                if (effectRef.current) {
                    effectRef.current.destroy();
                    effectRef.current = null;
                }
            };
        }

        // Otherwise, listen for script load events (event-driven, no polling)
        let threeLoaded = false;
        let vantaLoaded = false;

        const tryInit = () => {
            if (!cancelled && threeLoaded && vantaLoaded) {
                initVanta();
            }
        };

        const threeScript = document.querySelector('script[src*="three.min.js"]');
        const vantaScript = document.querySelector('script[src*="vanta.net.min.js"]');

        const onThreeLoad = () => {
            threeLoaded = true;
            tryInit();
        };
        const onVantaLoad = () => {
            vantaLoaded = true;
            tryInit();
        };

        let threeListenerAttached = false;
        let vantaListenerAttached = false;

        // Check if scripts already completed loading before we attached listeners
        if (threeScript) {
            if ((threeScript as HTMLScriptElement).complete || scriptsLoaded()) {
                threeLoaded = true;
            } else {
                threeScript.addEventListener('load', onThreeLoad, { once: true });
                threeListenerAttached = true;
            }
        } else {
            threeLoaded = true;
        }

        if (vantaScript) {
            if ((vantaScript as HTMLScriptElement).complete || scriptsLoaded()) {
                vantaLoaded = true;
            } else {
                vantaScript.addEventListener('load', onVantaLoad, { once: true });
                vantaListenerAttached = true;
            }
        } else {
            vantaLoaded = true;
        }

        tryInit();

        return () => {
            cancelled = true;
            // { once: true } auto-removes listeners after first fire,
            // but we still detach them here in case they haven't fired yet.
            if (threeScript && threeListenerAttached) {
                threeScript.removeEventListener('load', onThreeLoad);
            }
            if (vantaScript && vantaListenerAttached) {
                vantaScript.removeEventListener('load', onVantaLoad);
            }
            if (effectRef.current) {
                effectRef.current.destroy();
                effectRef.current = null;
            }
        };
    }, [isDark]);

    return (
        <div
            ref={vantaRef}
            style={{
                position: 'fixed',
                top: 0,
                left: 0,
                width: '100%',
                height: '100vh',
                zIndex: 0,
                pointerEvents: 'none',
                backgroundColor: isDark ? '#020617' : '#ffffff',
                transition: 'background-color 0.3s ease'
            }}
        />
    );
};
