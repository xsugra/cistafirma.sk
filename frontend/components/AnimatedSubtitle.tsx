import React, { useState, useEffect } from 'react';

const parts = ["Okamžité overenie.", "Kontinuálny monitoring.", "Vaša ochrana pred rizikom."];

export const AnimatedSubtitle: React.FC = () => {
    const [currentIndex, setCurrentIndex] = useState(0);

    useEffect(() => {
        const intervalId = setInterval(() => {
            setCurrentIndex(prevIndex => (prevIndex + 1) % parts.length);
        }, 3000);

        return () => clearInterval(intervalId);
    }, []);

    return (
        <div className="animated-subtitle-container hero-text-muted text-lg text-gray-600 dark:text-gray-400 text-center mb-8">
            <span key={currentIndex} className="animated-subtitle-text font-medium">
                {parts[currentIndex]}
            </span>
        </div>
    );
};
