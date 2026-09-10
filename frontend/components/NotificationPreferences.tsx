import React, {useState, useEffect} from 'react';
import {api} from '../api';
import type {NotificationPreferences as NPrefs} from '../types';

export const NotificationPreferences: React.FC = () => {
    const [prefs, setPrefs] = useState<NPrefs | null>(null);
    const [loading, setLoading] = useState(true);
    const [saving, setSaving] = useState(false);
    const [message, setMessage] = useState<{type: 'success' | 'error'; text: string} | null>(null);

    useEffect(() => {
        loadPrefs();
    }, []);

    const loadPrefs = async () => {
        setLoading(true);
        try {
            const data = await api.getNotificationPreferences();
            setPrefs(data);
        } catch {
            setMessage({type: 'error', text: 'Nepodarilo sa načítať predvoľby.'});
        } finally {
            setLoading(false);
        }
    };

    const handleToggle = async (key: keyof NPrefs) => {
        if (!prefs) return;
        const updated = {...prefs, [key]: !prefs[key]};
        setPrefs(updated);

        setSaving(true);
        setMessage(null);
        try {
            const data = await api.updateNotificationPreferences({[key]: updated[key]});
            setPrefs(data);
            setMessage({type: 'success', text: 'Predvoľby uložené.'});
        } catch {
            // revert on failure
            setPrefs(prefs);
            setMessage({type: 'error', text: 'Chyba pri ukladaní.'});
        } finally {
            setSaving(false);
        }
    };

    if (loading) {
        return (
            <div className="flex justify-center py-16">
                <div className="w-10 h-10 border-4 border-brand border-t-transparent rounded-full animate-spin"></div>
            </div>
        );
    }

    if (!prefs) {
        return (
            <div className="app-card p-8 text-center">
                <i className="fas fa-exclamation-triangle text-red-400 text-3xl mb-3 block"></i>
                <p className="text-gray-500">Nepodarilo sa načítať predvoľby.</p>
                <button onClick={loadPrefs} className="btn btn-outline mt-4 text-sm">
                    Skúsiť znova
                </button>
            </div>
        );
    }

    const toggles: {key: keyof NPrefs; label: string; description: string; icon: string}[] = [
        {
            key: 'emailEnabled',
            label: 'Emailové notifikácie',
            description: 'Dostávať upozornenia emailom',
            icon: 'fa-envelope',
        },
        {
            key: 'onDebtChange',
            label: 'Zmena dlhu',
            description: 'Upozorniť pri zmene dlhu sledovanej firmy',
            icon: 'fa-coins',
        },
        {
            key: 'onStatusChange',
            label: 'Zmena statusu',
            description: 'Upozorniť pri zmene statusu (napr. platca DPH)',
            icon: 'fa-flag',
        },
        {
            key: 'onExecutiveChange',
            label: 'Zmena štatutárov',
            description: 'Upozorniť pri zmene konateľov alebo štatutárov',
            icon: 'fa-user-tie',
        },
    ];

    return (
        <div className="app-card animate-fade-in">
            <div className="card-header">
                <h3 className="text-lg font-bold text-gray-900 dark:text-white">Predvoľby notifikácií</h3>
                <p className="text-sm text-gray-500 mt-1">
                    Nastavte, aké upozornenia chcete dostávať pre firmy vo vašom sledovanom zozname.
                </p>
            </div>

            {message && (
                <div
                    className={`mx-6 mt-4 px-4 py-2 rounded-lg text-sm font-medium ${
                        message.type === 'success'
                            ? 'bg-green-50 dark:bg-green-900/20 text-green-700 dark:text-green-400'
                            : 'bg-red-50 dark:bg-red-900/20 text-red-700 dark:text-red-400'
                    }`}
                >
                    {message.text}
                </div>
            )}

            <div className="card-body space-y-1 divide-y divide-gray-100 dark:divide-slate-800">
                {toggles.map((item) => (
                    <div
                        key={item.key}
                        className="flex items-center justify-between py-4 first:pt-0 last:pb-0"
                    >
                        <div className="flex items-center gap-3 min-w-0">
                            <div className="w-9 h-9 rounded-full bg-gray-100 dark:bg-slate-800 flex items-center justify-center flex-shrink-0">
                                <i className={`fas ${item.icon} text-gray-500 dark:text-gray-400`}></i>
                            </div>
                            <div className="min-w-0">
                                <p className="font-medium text-gray-900 dark:text-white">{item.label}</p>
                                <p className="text-sm text-gray-500 dark:text-gray-400 truncate">
                                    {item.description}
                                </p>
                            </div>
                        </div>
                        <button
                            onClick={() => handleToggle(item.key)}
                            disabled={saving}
                            className={`relative inline-flex h-6 w-11 flex-shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out focus:outline-none ${
                                prefs[item.key]
                                    ? 'bg-blue-600'
                                    : 'bg-gray-200 dark:bg-slate-700'
                            } ${saving ? 'opacity-50 cursor-not-allowed' : ''}`}
                            role="switch"
                            aria-checked={prefs[item.key]}
                        >
                            <span
                                className={`pointer-events-none inline-block h-5 w-5 rounded-full bg-white shadow transform ring-0 transition duration-200 ease-in-out ${
                                    prefs[item.key] ? 'translate-x-5' : 'translate-x-0'
                                }`}
                            />
                        </button>
                    </div>
                ))}
            </div>
        </div>
    );
};
