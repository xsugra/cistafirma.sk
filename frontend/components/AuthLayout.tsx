import React from 'react';
import {ROUTES} from '../constants';

interface AuthLayoutProps {
    children: React.ReactNode;
    title: string;
    subtitle: string;
}

export const AuthLayout: React.FC<AuthLayoutProps> = ({children, title, subtitle}) => {
    return (
        <div className="flex items-center justify-center min-h-[700px] animate-fade-in py-10 px-4">
            <div
                className="w-full max-w-5xl bg-white dark:bg-slate-900 rounded-3xl shadow-2xl overflow-hidden flex flex-col md:flex-row border border-gray-100 dark:border-slate-800 relative z-10">

                {/* Left Banner Section with Modern Gradient */}
                <div
                    className="md:w-5/12 relative overflow-hidden bg-slate-900 text-white p-8 md:p-12 flex flex-col justify-between">
                    {/* Animated Background Mesh */}
                    <div className="absolute inset-0 z-0 opacity-40">
                        <div
                            className="absolute top-0 left-0 w-full h-full bg-gradient-to-br from-blue-600 via-indigo-700 to-purple-900"></div>
                        <div
                            className="absolute -top-24 -left-24 w-64 h-64 bg-blue-400 rounded-full mix-blend-multiply filter blur-3xl opacity-30 animate-blob"></div>
                        <div
                            className="absolute top-1/2 right-0 w-64 h-64 bg-purple-400 rounded-full mix-blend-multiply filter blur-3xl opacity-30 animate-blob animation-delay-2000"></div>
                        <div
                            className="absolute bottom-0 left-1/4 w-64 h-64 bg-indigo-400 rounded-full mix-blend-multiply filter blur-3xl opacity-30 animate-blob animation-delay-4000"></div>
                    </div>

                    {/* Content */}
                    <div className="relative z-10">
                        <div className="flex items-center gap-3 mb-8">
                            <img
                                src="logo/logo_cistafirma-ikona.png"
                                alt="Logo"
                                className="h-10 w-auto object-contain"
                            />
                            <span
                                className="text-2xl font-bold tracking-tight text-white drop-shadow-sm">cistafirma.sk</span>
                        </div>

                        <h2 className="text-3xl md:text-4xl font-bold leading-tight mb-6 text-transparent bg-clip-text bg-gradient-to-r from-white to-blue-200">
                            Transparentné podnikanie bez rizika.
                        </h2>

                        <p className="text-blue-100 text-sm md:text-base leading-relaxed opacity-90 font-light max-w-sm">
                            Pripojte sa k tisíckam podnikateľov, ktorí využívajú dáta na bezpečné rozhodnutia a
                            minimalizáciu rizík.
                        </p>
                    </div>

                    {/* Glass Cards Feature List */}
                    <div className="relative z-10 mt-12 space-y-4">
                        {[
                            {icon: 'fa-robot', text: 'AI Analýza rizík'},
                            {icon: 'fa-search-dollar', text: 'Monitoring dlhov a DPH'},
                            {icon: 'fa-project-diagram', text: 'Grafické prepojenia'}
                        ].map((item, idx) => (
                            <div key={idx}
                                 className="flex items-center gap-4 p-3 rounded-xl bg-white/5 backdrop-blur-sm border border-white/10 hover:bg-white/10 transition-colors">
                                <div className="w-8 h-8 rounded-lg bg-blue-500/20 flex items-center justify-center">
                                    <i className={`fas ${item.icon} text-blue-200 text-sm`}></i>
                                </div>
                                <span className="font-medium text-sm text-blue-50">{item.text}</span>
                            </div>
                        ))}
                    </div>

                    <div className="relative z-10 mt-8 text-xs text-blue-300/60 font-medium">
                        &copy; {new Date().getFullYear()} cistafirma.sk Inc.
                    </div>
                </div>

                {/* Right Form Section */}
                <div
                    className="md:w-7/12 p-8 md:p-12 lg:p-16 flex flex-col justify-center bg-white dark:bg-slate-950 relative">
                    {/* Subtle grid pattern for tech feel */}
                    <div className="absolute inset-0 opacity-[0.03] pointer-events-none"
                         style={{
                             backgroundImage: 'radial-gradient(#444 1px, transparent 1px)',
                             backgroundSize: '24px 24px'
                         }}>
                    </div>

                    <div className="max-w-md mx-auto w-full relative z-10">
                        <div className="text-center md:text-left mb-10">
                            <h2 className="text-3xl font-bold text-gray-900 dark:text-white mb-3 tracking-tight">{title}</h2>
                            <p className="text-gray-500 dark:text-gray-400 text-lg">{subtitle}</p>
                        </div>
                        {children}
                    </div>
                </div>
            </div>
        </div>
    );
};
