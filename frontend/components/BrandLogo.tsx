
import React, { useState, useEffect } from 'react';
// Imported, not written as a URL, and that difference is the whole bug this
// fixes. `/logo/cistafirma-logo.png` was a hand-written absolute path into a
// directory the bundler never carries: `frontend/logo/` is not `frontend/public/`,
// and `vite build` copies only `publicDir` into `dist/`. So the production image
// shipped no such file -- and `try_files $uri $uri/ /index.html` in
// `nginx.conf.template` answered the request with 200 and the HTML page, which a
// browser draws as an empty image rather than as an error. It looked fine on the
// Vite dev server, which serves files straight out of the project root, so this
// only appeared when production stopped being a dev server (#123).
//
// Importing hands the URL to the bundler: the file lands in `assets/` with a
// content hash, and a renamed or deleted logo fails `npm run build` instead of
// going quietly missing in front of every visitor.
import logoUrl from '../logo/cistafirma-logo.png';

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
                 <img src={logoUrl} alt="Logo" className="h-10 w-auto" />
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
