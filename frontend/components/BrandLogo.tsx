
import React, { useState, useEffect } from 'react';

interface BrandLogoProps {
    onClick: () => void;
}

export const BrandLogo: React.FC<BrandLogoProps> = ({ onClick }) => {
    const [animate, setAnimate] = useState(false);

    // Trigger animation on mount
    useEffect(() => {
        setAnimate(true);
        const timer = setTimeout(() => setAnimate(false), 1000);
        return () => clearTimeout(timer);
    }, []);

    const handleClick = () => {
        // Re-trigger animation
        setAnimate(false);
        setTimeout(() => setAnimate(true), 10);
        onClick();
    };

    return (
        <div 
            onClick={handleClick} 
            className="flex items-center gap-3 cursor-pointer group select-none"
            role="button"
            aria-label="cistafirma.sk Domov"
        >
            <div className={`transition-transform duration-300 ${animate ? 'logo-animate' : ''}`}>
                 <img src="/logo/cistafirma-logo.png" alt="Logo" className="h-10 w-auto" />
            </div>
            <span 
                className={`text-2xl font-bold font-heading text-gray-900 dark:text-white tracking-tight group-hover:text-blue-600 dark:group-hover:text-blue-400 transition-colors ${animate ? 'logo-animate' : ''}`}
                style={{ animationDelay: '0.1s' }}
            >
                cistafirma.sk
            </span>
        </div>
    );
};
