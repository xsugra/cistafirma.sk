
import React, { useEffect, useRef, useState } from 'react';
import { useTheme } from '../context/ThemeContext';

export const VantaBackground: React.FC = () => {
    const vantaRef = useRef<HTMLDivElement>(null);
    const effectRef = useRef<any>(null); // Use Ref to track the Vanta instance without triggering re-renders
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
        let interval: any = null;

        const loadVanta = () => {
            // Check dependencies: DOM element, Vanta lib, Three lib
            if (!vantaRef.current || !(window as any).VANTA || !(window as any).THREE) {
                return false;
            }

            // Clean up existing effect before creating a new one
            if (effectRef.current) {
                effectRef.current.destroy();
                effectRef.current = null;
            }

            // Colors
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
                return true;
            } catch (error) {
                console.error("Vanta JS init error:", error);
                return false;
            }
        };

        // Try to load immediately
        if (!loadVanta()) {
            // Poll if scripts aren't loaded yet
            interval = setInterval(() => {
                if (loadVanta()) {
                    clearInterval(interval);
                }
            }, 100);
        }

        return () => {
            if (interval) clearInterval(interval);
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
                // Explicitly set background color to match Vanta to prevent flashing/white filter issues
                backgroundColor: isDark ? '#020617' : '#ffffff',
                transition: 'background-color 0.3s ease'
            }}
        />
    );
};