import React from 'react';
import { useNavigate } from 'react-router-dom';
import {AnimatedSubtitle} from '../components/AnimatedSubtitle';
import {SearchBar} from '../components/SearchBar';
import {ROUTES} from '../constants';
import {api} from '../api';
import {useAsyncData} from '../hooks/useAsyncData';

const DEFAULT_STATS = {companiesIndexed: 0, dailyChecks: 0, riskyCompaniesDetected: 0};

export const Home: React.FC = () => {
    const navigate = useNavigate();
    const { data } = useAsyncData(() => api.getLandingStats(), []);
    const stats = data ?? DEFAULT_STATS;

    const handleSearch = (query: string) => {
        navigate(`${ROUTES.MONITORING}?ico=${encodeURIComponent(query)}`);
    };

    const FeatureCard = ({icon, title, text}: { icon: string, title: string, text: string }) => (
        <div
            className="app-card p-8 flex flex-col items-start hover:-translate-y-2 transition-all duration-300 hover:shadow-xl hover:border-blue-200 dark:hover:border-blue-900 group">
            <div
                className="w-14 h-14 rounded-2xl bg-blue-50 dark:bg-slate-800 flex items-center justify-center text-blue-600 dark:text-blue-400 mb-6 group-hover:scale-110 transition-transform duration-300 shadow-sm">
                <i className={`fas ${icon} text-2xl`}></i>
            </div>
            <h3 className="text-xl font-bold text-gray-900 dark:text-white mb-3 group-hover:text-blue-600 dark:group-hover:text-blue-400 transition-colors">{title}</h3>
            <p className="text-gray-600 dark:text-gray-400 leading-relaxed">{text}</p>
        </div>
    );

    return (
        <div className="animate-fade-in">
            {/* HERO SECTION */}
            <section className="relative text-center py-20 md:py-32 max-w-5xl mx-auto px-4 overflow-hidden">
                {/* Soft radial backdrop for text readability over animated background */}
                <div className="hero-backdrop absolute inset-0 -z-10 pointer-events-none"></div>

                <div
                    className="mb-8 inline-flex items-center gap-2 px-4 py-2 rounded-full bg-white/70 dark:bg-slate-800/70 border border-blue-100 dark:border-blue-900 backdrop-blur-md shadow-sm">
                    <span className="flex h-2 w-2 relative">
                        <span
                            className="animate-ping absolute inline-flex h-full w-full rounded-full bg-blue-400 opacity-75"></span>
                        <span className="relative inline-flex rounded-full h-2 w-2 bg-blue-500"></span>
                    </span>
                    <span className="text-sm font-semibold text-gray-700 dark:text-gray-200 tracking-wide">
                        Budúcnosť overovania firiem je tu
                    </span>
                </div>

                <h1 className="hero-text text-5xl sm:text-6xl md:text-8xl font-bold text-gray-900 dark:text-white mb-8 tracking-tight leading-none">
                    Transparentné podnikanie <br/>
                    <span
                        className="text-transparent bg-clip-text bg-gradient-to-r from-blue-600 to-blue-400">bez rizika</span>
                </h1>

                <div className="mb-12 h-12">
                    <AnimatedSubtitle/>
                </div>

                <div className="max-w-2xl mx-auto mb-10 w-full relative z-20">
                    <SearchBar onSearch={handleSearch} isLoading={false} initialIco="" />
                </div>

                <div
                    className="flex flex-col sm:flex-row gap-5 justify-center items-center w-full max-w-md mx-auto sm:max-w-none relative z-10">
                    <button
                        onClick={() => navigate(ROUTES.MONITORING)}
                        className="btn btn-primary text-lg px-10 py-4 rounded-full shadow-lg shadow-blue-600/30 hover:shadow-blue-600/40 w-full sm:w-auto transform hover:scale-105 transition-all duration-300"
                    >
                        Spustiť Monitoring <i className="fas fa-arrow-right ml-2"></i>
                    </button>
                    <button
                        onClick={() => navigate(ROUTES.PRICING)}
                        className="btn bg-white dark:bg-slate-900 text-gray-800 dark:text-white border border-gray-200 dark:border-slate-700 hover:bg-gray-50 dark:hover:bg-slate-800 text-lg px-10 py-4 rounded-full shadow-md hover:shadow-lg w-full sm:w-auto transition-all duration-300"
                    >
                        Pozrieť Cenník
                    </button>
                </div>
            </section>

            {/* STATS SECTION */}
            <section className="container mx-auto px-4 mb-24">
                <div className="grid grid-cols-1 md:grid-cols-3 gap-6 lg:gap-8">
                    {[
                        {val: stats.companiesIndexed, label: 'Indexovaných firiem', icon: 'fa-database'},
                        {val: stats.dailyChecks, label: 'Denných kontrol', icon: 'fa-sync'},
                        {
                            val: stats.riskyCompaniesDetected,
                            label: 'Odhalených rizík dnes',
                            icon: 'fa-shield-virus',
                            plus: true
                        }
                    ].map((stat, i) => (
                        <div key={i}
                             className="app-card p-8 flex items-center justify-between group hover:border-blue-200 dark:hover:border-blue-900 transition-colors">
                            <div>
                                <div
                                    className="text-4xl font-bold text-gray-900 dark:text-white mb-2 font-mono tracking-tight group-hover:text-blue-600 dark:group-hover:text-blue-400 transition-colors">
                                    {stat.val.toLocaleString('sk-SK')}{stat.plus ? '+' : ''}
                                </div>
                                <div
                                    className="text-sm font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">{stat.label}</div>
                            </div>
                            <div
                                className="w-12 h-12 rounded-full bg-gray-50 dark:bg-slate-800 flex items-center justify-center text-gray-400 group-hover:bg-blue-50 dark:group-hover:bg-blue-900/20 group-hover:text-blue-500 transition-all">
                                <i className={`fas ${stat.icon} text-xl`}></i>
                            </div>
                        </div>
                    ))}
                </div>
            </section>

            {/* ABOUT / BLOG SECTION */}
            <section className="grid grid-cols-1 lg:grid-cols-2 gap-8 lg:gap-12 mb-32 px-4 container mx-auto">
                {/* About Card */}
                <div className="app-card p-10 relative overflow-hidden flex flex-col justify-between">
                    <div
                        className="absolute top-0 right-0 w-64 h-64 bg-gradient-to-bl from-blue-50 dark:from-blue-900/20 to-transparent rounded-bl-full pointer-events-none"></div>

                    <div className="relative z-10 space-y-6">
                        <div
                            className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300 text-xs font-bold uppercase tracking-wide">
                            O projekte
                        </div>
                        <h2 className="text-3xl md:text-4xl font-bold text-gray-900 dark:text-white leading-tight">
                            Spoľahlivé dáta pre <br/>vaše podnikanie
                        </h2>
                        <div className="prose prose-lg dark:prose-invert text-gray-600 dark:text-gray-400">
                            <p>
                                V dnešnom dynamickom prostredí je dôvera kľúčová. <strong>cistafirma.sk</strong> prináša
                                radikálnu transparentnosť do slovenského ekosystému.
                            </p>
                            <p>
                                Náš systém využíva pokročilé algoritmy a AI na krížovú kontrolu údajov z viac ako 15
                                verejných zdrojov v reálnom čase.
                            </p>
                        </div>

                        <div className="pt-6 grid grid-cols-1 sm:grid-cols-2 gap-4">
                            {['Real-time dáta', 'AI Analýza', 'Notifikácie', 'API Integrácia'].map((item, i) => (
                                <div key={i}
                                     className="flex items-center gap-3 text-gray-800 dark:text-gray-200 font-medium">
                                    <i className="fas fa-check-circle text-blue-500"></i> {item}
                                </div>
                            ))}
                        </div>
                    </div>
                </div>

                {/* Blog Card */}
                <div className="app-card p-10 relative overflow-hidden flex flex-col bg-slate-50 dark:bg-slate-900/50">
                    <div className="flex justify-between items-end mb-8">
                        <div>
                            <div
                                className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300 text-xs font-bold uppercase tracking-wide mb-4">
                                Blog & Novinky
                            </div>
                            <h3 className="text-3xl font-bold text-gray-900 dark:text-white">Najnovšie z blogu</h3>
                        </div>
                        <button onClick={() => navigate(ROUTES.BLOG)}
                                className="btn btn-ghost text-sm hidden sm:flex">
                            Všetky články <i className="fas fa-arrow-right ml-1"></i>
                        </button>
                    </div>

                    <div className="space-y-6 flex-grow">
                        <div
                            className="group cursor-pointer bg-white dark:bg-slate-900 p-5 rounded-xl shadow-sm border border-gray-100 dark:border-slate-800 hover:border-blue-300 dark:hover:border-blue-700 transition-all"
                            onClick={() => navigate(ROUTES.BLOG)}>
                            <div className="flex justify-between items-start mb-2">
                                <span
                                    className="text-xs font-bold text-blue-600 uppercase tracking-wider">Legislatíva</span>
                                <span className="text-xs text-gray-400">12. Feb</span>
                            </div>
                            <h4 className="font-bold text-lg text-gray-900 dark:text-white group-hover:text-blue-600 transition-colors">
                                Zmeny v DPH od roku 2025: Na čo si dať pozor?
                            </h4>
                        </div>

                        <div
                            className="group cursor-pointer bg-white dark:bg-slate-900 p-5 rounded-xl shadow-sm border border-gray-100 dark:border-slate-800 hover:border-blue-300 dark:hover:border-blue-700 transition-all"
                            onClick={() => navigate(ROUTES.BLOG)}>
                            <div className="flex justify-between items-start mb-2">
                                <span
                                    className="text-xs font-bold text-blue-600 uppercase tracking-wider">Technológie</span>
                                <span className="text-xs text-gray-400">10. Feb</span>
                            </div>
                            <h4 className="font-bold text-lg text-gray-900 dark:text-white group-hover:text-blue-600 dark:group-hover:text-blue-400 transition-colors">
                                Ako AI odhaľuje biele kone vo firmách
                            </h4>
                        </div>
                    </div>
                </div>
            </section>

            {/* FEATURES GRID */}
            <section className="mb-24 px-4 container mx-auto">
                <div className="text-center mb-16 max-w-3xl mx-auto">
                    <h2 className="hero-text text-3xl md:text-5xl font-bold text-gray-900 dark:text-white mb-6">Prečo
                        cistafirma.sk?</h2>
                    <p className="hero-text-muted text-xl text-gray-600 dark:text-gray-400">
                        Komplexný nástroj, ktorý šetrí váš čas, chráni vaše peniaze a dáva vám konkurenčnú výhodu.
                    </p>
                </div>
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-8">
                    <FeatureCard
                        icon="fa-bolt"
                        title="Blesková Rýchlosť"
                        text="Optimalizovaná infraštruktúra zabezpečuje výsledky vyhľadávania a analýzy v milisekundách."
                    />
                    <FeatureCard
                        icon="fa-search-dollar"
                        title="Kontrola dlhov"
                        text="Automatická kontrola zadlženosti voči Sociálnej poisťovni, zdravotnej poisťovni a daňovým úradom."
                    />
                    <FeatureCard
                        icon="fa-history"
                        title="História & Trendy"
                        text="Sledujte vývoj zadlženosti v čase a predikujte potenciálne problémy skôr, než nastanú."
                    />
                    <FeatureCard
                        icon="fa-project-diagram"
                        title="Hĺbkové Prepojenia"
                        text="Interaktívne grafy väzieb medzi osobami a firmami pre odhalenie skrytých konfliktov záujmov."
                    />
                </div>
            </section>
        </div>
    );
};
