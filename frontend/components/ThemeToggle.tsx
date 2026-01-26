import React, { useState, useRef, useEffect } from 'react';
import { useTheme } from '../context/ThemeContext';

export const ThemeToggle: React.FC = () => {
    const { theme, setTheme } = useTheme();
    const [isOpen, setIsOpen] = useState(false);
    const dropdownRef = useRef<HTMLDivElement>(null);

    // Close dropdown when clicking outside
    useEffect(() => {
        const handleClickOutside = (event: MouseEvent) => {
            if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
                setIsOpen(false);
            }
        };
        document.addEventListener('mousedown', handleClickOutside);
        return () => document.removeEventListener('mousedown', handleClickOutside);
    }, []);

    const getIcon = (t: string) => {
        switch(t) {
            case 'light': return 'fa-sun';
            case 'dark': return 'fa-moon';
            case 'system': return 'fa-desktop';
            default: return 'fa-desktop';
        }
    };

    const options = [
        { value: 'light', label: 'Svetlý', icon: 'fa-sun' },
        { value: 'dark', label: 'Tmavý', icon: 'fa-moon' },
        { value: 'system', label: 'Systém', icon: 'fa-desktop' },
    ];

    return (
        <div className="relative" ref={dropdownRef}>
            <button
                onClick={() => setIsOpen(!isOpen)}
                className="flex items-center justify-center w-10 h-10 rounded-full bg-gray-100 dark:bg-slate-800 text-gray-600 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-slate-700 transition-colors focus:outline-none focus:ring-2 focus:ring-brand shadow-sm border border-gray-200 dark:border-slate-700"
                aria-label="Zmeniť motív"
                title="Nastavenie zobrazenia"
            >
                <i className={`fas ${getIcon(theme)}`}></i>
            </button>

            {isOpen && (
                <div className="absolute right-0 mt-2 w-40 bg-white dark:bg-slate-800 rounded-xl shadow-xl border border-gray-200 dark:border-slate-700 py-1 z-50 animate-fade-in overflow-hidden">
                    {options.map((option) => (
                        <button
                            key={option.value}
                            onClick={() => { setTheme(option.value as any); setIsOpen(false); }}
                            className={`w-full text-left px-4 py-2.5 text-sm flex items-center gap-3 transition-colors
                                ${theme === option.value 
                                    ? 'bg-blue-50 dark:bg-blue-900/20 text-brand dark:text-blue-400 font-semibold' 
                                    : 'text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-slate-700'
                                }`}
                        >
                            <i className={`fas ${option.icon} w-5 text-center ${theme === option.value ? 'text-brand dark:text-blue-400' : 'text-gray-400'}`}></i>
                            {option.label}
                        </button>
                    ))}
                </div>
            )}
        </div>
    );
};