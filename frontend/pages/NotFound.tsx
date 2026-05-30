import React from 'react';
import { useNavigate } from 'react-router-dom';
import { ROUTES } from '../constants';

export const NotFound: React.FC = () => {
    const navigate = useNavigate();
    const currentPath = typeof window !== 'undefined' ? window.location.pathname : 'unknown';

    return (
        <div className="flex flex-col items-center justify-center min-h-[60vh] text-center animate-fade-in relative overflow-hidden">
            <h1 className="text-[10rem] md:text-[16rem] font-bold text-gray-100 dark:text-slate-800/50 absolute z-0 select-none pointer-events-none">
                404
            </h1>

            <div className="relative z-10 flex flex-col items-center">
                <div className="w-24 h-24 bg-red-100 dark:bg-red-900/20 rounded-full flex items-center justify-center mb-6 text-red-500 dark:text-red-400 shadow-xl shadow-red-500/10">
                     <i className="fas fa-unlink text-4xl"></i>
                </div>

                <h2 className="text-3xl md:text-4xl font-bold text-gray-900 dark:text-white mb-3">
                    Stránka nenájdená
                </h2>

                <p className="text-lg text-gray-600 dark:text-gray-400 mb-8 max-w-lg mx-auto leading-relaxed">
                    Ospravedlňujeme sa, ale požadovaná stránka neexistuje, bola presunutá alebo ste zadali nesprávnu URL adresu.
                </p>

                <div className="w-full max-w-md bg-gray-50 dark:bg-slate-900 border border-gray-200 dark:border-slate-800 rounded-lg p-4 mb-8 text-left font-mono text-xs md:text-sm shadow-inner">
                    <p className="text-gray-500 dark:text-gray-500 mb-1 uppercase tracking-wider text-[10px] font-bold">Debug Info:</p>
                    <div className="flex justify-between items-center text-gray-700 dark:text-gray-300">
                        <span>Path:</span>
                        <span className="text-red-500 font-semibold truncate ml-2" title={currentPath}>
                            {currentPath}
                        </span>
                    </div>
                </div>

                <div className="flex flex-col sm:flex-row gap-4">
                    <button
                        onClick={() => navigate(ROUTES.HOME)}
                        className="btn btn-primary px-8 py-3 rounded-full shadow-lg shadow-blue-600/20"
                    >
                        <i className="fas fa-home mr-2"></i> Späť na domov
                    </button>

                    <button
                        onClick={() => navigate(-1)}
                        className="btn btn-outline border-gray-300 dark:border-slate-700 text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-slate-800 px-8 py-3 rounded-full"
                    >
                        <i className="fas fa-arrow-left mr-2"></i> Vrátiť sa späť
                    </button>
                </div>
            </div>
        </div>
    );
};
