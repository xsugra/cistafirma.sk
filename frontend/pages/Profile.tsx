import React, {useState, useEffect} from 'react';
import { useNavigate } from 'react-router-dom';
import {api} from '../api';
import {useAuth} from '../context/AuthContext';
import {StatusBadge} from '../components/StatusBadge';
import {ROUTES} from '../constants';
import {CompanyDetail} from '../components/CompanyDetail';
import type {WatchlistEntry, HistoryEntry, Company} from '../types';

type Tab = 'dashboard' | 'watchlist' | 'history' | 'settings';

export const Profile: React.FC = () => {
    const navigate = useNavigate();
    const {user} = useAuth();
    const [activeTab, setActiveTab] = useState<Tab>('dashboard');

    // Data Lists
    const [watchlist, setWatchlist] = useState<WatchlistEntry[]>([]);
    const [history, setHistory] = useState<HistoryEntry[]>([]);
    const [isLoadingData, setIsLoadingData] = useState(false);

    // Detail View State
    const [selectedCompanyIco, setSelectedCompanyIco] = useState<string | null>(null);
    const [companyDetailData, setCompanyDetailData] = useState<Company | null>(null);
    const [detailLoading, setDetailLoading] = useState(false);

    // Settings State
    const [identity, setIdentity] = useState({
        firstName: user?.firstName || '',
        lastName: user?.lastName || '',
        username: user?.username || '',
        email: user?.email || ''
    });
    const [security, setSecurity] = useState({oldPassword: '', newPassword: '', confirmPassword: ''});
    const [message, setMessage] = useState<{ type: 'success' | 'error', text: string } | null>(null);

    // Update form state if user data loads/changes
    useEffect(() => {
        if (user) {
            setIdentity({
                firstName: user.firstName || '',
                lastName: user.lastName || '',
                username: user.username || '',
                email: user.email || ''
            });
        }
    }, [user]);

    const refreshLists = async () => {
        setIsLoadingData(true);
        const [wResult, hResult] = await Promise.allSettled([
            api.getWatchlist(),
            api.getHistory()
        ]);
        if (wResult.status === 'fulfilled') setWatchlist(wResult.value || []);
        if (hResult.status === 'fulfilled') setHistory(hResult.value || []);
        setIsLoadingData(false);
    };

    useEffect(() => {
        refreshLists();
    }, []);

    useEffect(() => {
        setSelectedCompanyIco(null);
        setCompanyDetailData(null);
    }, [activeTab]);

    const openDetail = async (ico: string) => {
        setSelectedCompanyIco(ico);
        setDetailLoading(true);
        try {
            const data = await api.getCompany(ico);
            setCompanyDetailData(data);
        } catch (e) {
            setMessage({type: 'error', text: 'Nepodarilo sa načítať detail firmy.'});
            setSelectedCompanyIco(null);
        } finally {
            setDetailLoading(false);
        }
    };

    const closeDetail = () => {
        setSelectedCompanyIco(null);
        setCompanyDetailData(null);
    };

    const handleDeleteFromWatchlist = async (id: string, e: React.MouseEvent) => {
        e.stopPropagation();
        if (!window.confirm('Naozaj chcete odstrániť túto firmu zo sledovaných?')) return;
        try {
            await api.removeFromWatchlist(id);
            setWatchlist(prev => prev.filter(item => item.id !== id));
            setMessage({type: 'success', text: 'Firma bola odstránená zo sledovaných.'});
        } catch (error: any) {
            setMessage({type: 'error', text: error.message || 'Chyba pri odstraňovaní.'});
        }
    };

    const handleIdentityChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        setIdentity({...identity, [e.target.name]: e.target.value});
    };

    const handleSecurityChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        setSecurity({...security, [e.target.name]: e.target.value});
    };

    const saveIdentity = async (e: React.FormEvent) => {
        e.preventDefault();
        setMessage(null);
        try {
            await api.updateProfile(identity);
            setMessage({type: 'success', text: 'Profil bol aktualizovaný.'});
        } catch (error: any) {
            setMessage({type: 'error', text: error.message || 'Chyba pri ukladaní údajov.'});
        }
    };

    const savePassword = async (e: React.FormEvent) => {
        e.preventDefault();
        if (security.newPassword !== security.confirmPassword) {
            setMessage({type: 'error', text: 'Nové heslá sa nezhodujú.'});
            return;
        }
        try {
            await api.changePassword(security.oldPassword, security.newPassword);
            setSecurity({oldPassword: '', newPassword: '', confirmPassword: ''});
            setMessage({type: 'success', text: 'Heslo bolo úspešne zmenené.'});
        } catch (error: any) {
            setMessage({type: 'error', text: error.message || 'Chyba pri zmene hesla. Skontrolujte staré heslo.'});
        }
    };

    // Helper for Avatar Initials
    const getInitials = () => {
        if (user?.firstName && user?.lastName) {
            return `${user.firstName.charAt(0)}${user.lastName.charAt(0)}`;
        }
        if (user?.firstName) return user.firstName.charAt(0);
        if (user?.email) return user.email.charAt(0).toUpperCase();
        return '?';
    };

    const getDisplayName = () => {
        if (user?.firstName && user?.lastName) return `${user.firstName} ${user.lastName}`;
        if (user?.firstName) return user.firstName;
        return user?.username || user?.email?.split('@')[0];
    };

    // --- Renders ---

    const renderDetailView = () => {
        if (detailLoading) {
            return (
                <div className="flex flex-col items-center justify-center py-20 animate-fade-in">
                    <div
                        className="w-12 h-12 border-4 border-brand border-t-transparent rounded-full animate-spin mb-4"></div>
                    <p className="text-gray-500">Sťahujem aktuálne dáta...</p>
                </div>
            );
        }
        if (!companyDetailData) return null;
        return (
            <div className="animate-fade-in">
                <button onClick={closeDetail} className="btn btn-ghost mb-4">
                    <i className="fas fa-arrow-left"></i> Späť na zoznam
                </button>
                <CompanyDetail company={companyDetailData}/>
            </div>
        );
    };

    const renderDashboard = () => {
        const percentUsed = user ? (user.apiCallsUsed / user.apiCallsLimit) * 100 : 0;
        return (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6 animate-fade-in">
                <div className="app-card p-6">
                    <div className="flex items-center gap-4 mb-6">
                        <div
                            className="w-16 h-16 rounded-full bg-blue-500/10 text-blue-600 flex items-center justify-center text-2xl font-bold flex-shrink-0">
                            {getInitials()}
                        </div>
                        <div className="overflow-hidden">
                            <h2 className="text-xl md:text-2xl font-bold text-gray-900 dark:text-white truncate">{getDisplayName()}</h2>
                            <p className="text-gray-500 dark:text-gray-400 truncate">@{user?.username}</p>
                        </div>
                    </div>
                    <div className="space-y-3">
                        <div className="flex justify-between p-3 bg-gray-50 dark:bg-slate-800 rounded-lg">
                            <span className="text-gray-600 dark:text-gray-400">Email</span>
                            <span
                                className="font-medium text-gray-900 dark:text-white truncate ml-2">{user?.email}</span>
                        </div>
                        <div className="flex justify-between p-3 bg-gray-50 dark:bg-slate-800 rounded-lg">
                            <span className="text-gray-600 dark:text-gray-400">Plán</span>
                            <span className="font-bold text-blue-600 uppercase">{user?.plan}</span>
                        </div>
                    </div>
                </div>

                <div className="app-card p-6 flex flex-col justify-center">
                    <h3 className="text-lg font-bold text-gray-900 dark:text-white mb-4 flex items-center gap-2">
                        <i className="fas fa-chart-pie text-blue-600"></i> Využitie API Limitov
                    </h3>
                    <div className="mb-2 flex justify-between text-sm">
                        <span className="text-gray-600 dark:text-gray-400">Mesačné vyhľadávania</span>
                        <span
                            className="font-bold text-gray-900 dark:text-white">{user?.apiCallsUsed} / {user?.apiCallsLimit}</span>
                    </div>
                    <div className="w-full bg-gray-200 dark:bg-slate-700 rounded-full h-4 mb-4 overflow-hidden">
                        <div
                            className={`h-4 rounded-full transition-all duration-500 ${percentUsed > 90 ? 'bg-red-500' : 'bg-blue-600'}`}
                            style={{width: `${percentUsed}%`}}
                        ></div>
                    </div>
                    <p className="text-sm text-gray-500 dark:text-gray-400">
                        Limit sa obnoví 1. dňa nasledujúceho mesiaca.
                        {percentUsed > 80 &&
                            <span className="text-red-500 ml-1 block mt-1">Blížite sa k vyčerpaniu limitu!</span>}
                    </p>
                    <button onClick={() => navigate(ROUTES.PRICING)} className="btn btn-outline w-full mt-6">
                        Navýšiť limit
                    </button>
                </div>
            </div>
        );
    };

    const renderWatchlist = () => {
        if (selectedCompanyIco) return renderDetailView();
        return (
            <div className="app-card animate-fade-in">
                <div className="card-header flex justify-between items-center">
                    <h3 className="text-lg font-bold text-gray-900 dark:text-white">Sledované firmy</h3>
                    <span
                        className="text-sm font-medium text-gray-500 bg-gray-100 dark:bg-slate-800 px-3 py-1 rounded-full">{watchlist.length}</span>
                </div>
                <div className="list-divider">
                    {watchlist.length === 0 ? (
                        <div className="p-8 text-center text-gray-500">Zatiaľ nesledujete žiadne firmy.</div>
                    ) : (
                        watchlist.map(item => (
                            <div key={item.id} onClick={() => openDetail(item.ico)}
                                 className="list-item-row group flex flex-col sm:flex-row sm:items-center gap-4">
                                <div className="flex-grow">
                                    <h4 className="text-base font-bold text-gray-900 dark:text-white group-hover:text-blue-600 transition-colors">{item.name}</h4>
                                    <div
                                        className="flex flex-wrap items-center gap-x-3 gap-y-1 text-sm text-gray-500 mt-1">
                                        <span>IČO: {item.ico}</span>
                                        <span className="hidden sm:inline">•</span>
                                        <span>Pridané: {new Date(item.addedAt).toLocaleDateString('sk-SK')}</span>
                                    </div>
                                </div>
                                <div
                                    className="flex items-center justify-between w-full sm:w-auto gap-4 border-t sm:border-t-0 pt-3 sm:pt-0 border-gray-100 dark:border-slate-800">
                                    <div className="flex items-center gap-3">
                                        <div className="flex flex-col items-end">
                                            <span
                                                className="text-[10px] text-gray-500 uppercase font-semibold">Risk</span>
                                            <span
                                                className={`font-bold ${item.riskScore > 70 ? 'text-green-500' : item.riskScore > 40 ? 'text-yellow-500' : 'text-red-500'}`}>
                                                {item.riskScore}/100
                                            </span>
                                        </div>
                                        <StatusBadge status={item.status}/>
                                    </div>
                                    <button
                                        onClick={(e) => handleDeleteFromWatchlist(item.id, e)}
                                        className="btn btn-ghost btn-icon hover:bg-red-50 hover:text-red-500"
                                        title="Odstrániť"
                                    >
                                        <i className="fas fa-trash-alt"></i>
                                    </button>
                                </div>
                            </div>
                        ))
                    )}
                </div>
            </div>
        );
    };

    const renderHistory = () => {
        if (selectedCompanyIco) return renderDetailView();
        return (
            <div className="app-card animate-fade-in">
                <div className="card-header">
                    <h3 className="text-lg font-bold text-gray-900 dark:text-white">Posledné vyhľadávania</h3>
                </div>
                <div className="list-divider">
                    {history.length === 0 ? (
                        <div className="p-8 text-center text-gray-500">Žiadna história.</div>
                    ) : (
                        history.map(item => (
                            <div key={item.id} onClick={() => openDetail(item.ico)} className="list-item-row group">
                                <div className="flex items-center gap-4 w-full">
                                    <div
                                        className="w-10 h-10 rounded-full bg-blue-50 dark:bg-blue-900/20 flex items-center justify-center text-blue-500 flex-shrink-0">
                                        <i className="fas fa-search"></i>
                                    </div>
                                    <div className="overflow-hidden">
                                        <p className="font-medium text-gray-900 dark:text-white group-hover:text-blue-600 transition-colors truncate">{item.name || `Neznáma firma (${item.ico})`}</p>
                                        <p className="text-xs text-gray-500">{new Date(item.searchedAt).toLocaleString('sk-SK')}</p>
                                    </div>
                                </div>
                                <button className="btn btn-ghost text-sm font-medium hidden sm:block">
                                    Detail <i className="fas fa-chevron-right text-xs ml-1"></i>
                                </button>
                            </div>
                        ))
                    )}
                </div>
            </div>
        );
    };

    const renderSettings = () => (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-8 animate-fade-in">
            <div className="app-card">
                <div className="card-header">
                    <h3 className="text-lg font-bold text-gray-900 dark:text-white">Osobné údaje</h3>
                </div>
                <form onSubmit={saveIdentity} className="card-body space-y-4">
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                        <div className="form-group">
                            <label className="form-label">Meno</label>
                            <input name="firstName" value={identity.firstName} onChange={handleIdentityChange}
                                   className="app-input"/>
                        </div>
                        <div className="form-group">
                            <label className="form-label">Priezvisko</label>
                            <input name="lastName" value={identity.lastName} onChange={handleIdentityChange}
                                   className="app-input"/>
                        </div>
                    </div>
                    <div className="form-group">
                        <label className="form-label">Používateľské meno</label>
                        <input name="username" value={identity.username} onChange={handleIdentityChange}
                               className="app-input"/>
                    </div>
                    <button type="submit" className="btn btn-primary w-full">Uložiť zmeny</button>
                </form>
            </div>

            <div className="app-card h-fit">
                <div className="card-header">
                    <h3 className="text-lg font-bold text-gray-900 dark:text-white">Zmena hesla</h3>
                </div>
                <form onSubmit={savePassword} className="card-body space-y-4">
                    <div className="form-group">
                        <label className="form-label">Staré heslo</label>
                        <input name="oldPassword" type="password" value={security.oldPassword}
                               onChange={handleSecurityChange} className="app-input"/>
                    </div>
                    <div className="form-group">
                        <label className="form-label">Nové heslo</label>
                        <input name="newPassword" type="password" value={security.newPassword}
                               onChange={handleSecurityChange} className="app-input"/>
                    </div>
                    <div className="form-group">
                        <label className="form-label">Potvrdiť heslo</label>
                        <input name="confirmPassword" type="password" value={security.confirmPassword}
                               onChange={handleSecurityChange} className="app-input"/>
                    </div>
                    <button type="submit" className="btn btn-primary bg-slate-800 hover:bg-slate-700 w-full">Zmeniť
                        heslo
                    </button>
                </form>
            </div>
        </div>
    );

    return (
        <div className="profile-container animate-fade-in py-6 md:py-10">
            <div className="flex flex-col md:flex-row items-center justify-between mb-8 gap-4 text-center md:text-left">
                <h1 className="text-3xl md:text-4xl font-bold text-gray-900 dark:text-white">Môj Profil</h1>
                {message && (
                    <div
                        className={`px-4 py-2 rounded-lg text-sm font-medium w-full md:w-auto ${message.type === 'success' ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'}`}>
                        {message.text}
                    </div>
                )}
            </div>

            {!selectedCompanyIco && (
                <div className="tab-nav overflow-x-auto pb-1 mb-6 no-scrollbar touch-pan-x">
                    {[
                        {id: 'dashboard', label: 'Prehľad', icon: 'fa-tachometer-alt'},
                        {id: 'watchlist', label: 'Sledované', icon: 'fa-eye'},
                        {id: 'history', label: 'História', icon: 'fa-history'},
                        {id: 'settings', label: 'Nastavenia', icon: 'fa-cog'},
                    ].map((tab) => (
                        <button
                            key={tab.id}
                            onClick={() => setActiveTab(tab.id as Tab)}
                            className={`tab-btn whitespace-nowrap flex-shrink-0 ${activeTab === tab.id ? 'active' : ''}`}
                        >
                            <i className={`fas ${tab.icon}`}></i>
                            {tab.label}
                        </button>
                    ))}
                </div>
            )}

            <div className="min-h-[400px]">
                {isLoadingData ? (
                    <div className="flex justify-center py-20">
                        <div
                            className="w-10 h-10 border-4 border-brand border-t-transparent rounded-full animate-spin"></div>
                    </div>
                ) : (
                    <>
                        {activeTab === 'dashboard' && renderDashboard()}
                        {activeTab === 'watchlist' && renderWatchlist()}
                        {activeTab === 'history' && renderHistory()}
                        {activeTab === 'settings' && renderSettings()}
                    </>
                )}
            </div>
        </div>
    );
};
