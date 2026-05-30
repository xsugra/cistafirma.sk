import React, { useState, useEffect } from 'react';
import type { Company } from '../../types';
import { StatusBadge } from '../StatusBadge';
import { api } from '../../api';
import { DetailItem } from './DetailItem';
import { formatDate } from './helpers';
import type { LegalFormProfile } from '../../utils/legalFormProfile';

interface CompanyHeaderProps {
    company: Company;
    profile: LegalFormProfile;
}

export const CompanyHeader: React.FC<CompanyHeaderProps> = ({ company, profile }) => {
    const [isWatching, setIsWatching] = useState(false);
    const [watchLoading, setWatchLoading] = useState(false);
    const orsrProfile = company.orsr_profile;

    useEffect(() => {
        let cancelled = false;
        api.getWatchlist().then(list => {
            if (!cancelled) {
                setIsWatching(list.some(entry => entry.ico === company.ico));
            }
        }).catch(() => {});
        return () => { cancelled = true; };
    }, [company.ico]);

    const handleWatchToggle = async () => {
        setWatchLoading(true);
        try {
            if (isWatching) {
                const list = await api.getWatchlist();
                const entry = list.find(e => e.ico === company.ico);
                if (entry) await api.removeFromWatchlist(entry.id);
            } else {
                await api.addToWatchlist(company.ico);
            }
            setIsWatching(!isWatching);
        } catch (e) {
            console.error("Watch toggle failed", e);
        } finally {
            setWatchLoading(false);
        }
    };

    return (
        <div className="app-card p-6">
            <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
                <div>
                    <h2 className="text-3xl font-bold text-gray-900 dark:text-white">{company.name}</h2>
                    <p className="text-gray-500 dark:text-gray-400">
                        {company.legalForm || profile.label}
                    </p>
                    {orsrProfile?.oddiel && orsrProfile?.vlozka_cislo && (
                        <p className="text-xs text-gray-400 dark:text-gray-500 mt-1">
                            Oddiel: {orsrProfile.oddiel} • Vložka číslo: {orsrProfile.vlozka_cislo} • {profile.label}
                        </p>
                    )}
                </div>
                <div className="flex items-center gap-4">
                    <StatusBadge status={company.status} />
                    <button
                        onClick={handleWatchToggle}
                        disabled={watchLoading}
                        className={`btn ${isWatching ? 'bg-green-600 hover:bg-green-700 text-white' : 'btn-primary'}`}
                    >
                        {watchLoading ? (
                            <i className="fas fa-spinner animate-spin"></i>
                        ) : (
                            <i className={`fas ${isWatching ? 'fa-check' : 'fa-bell'}`}></i>
                        )}
                        {isWatching ? 'Sledované' : 'Sledovať'}
                    </button>
                </div>
            </div>
            <div className="mt-6 grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 border-t border-gray-200 dark:border-slate-800 pt-6">
                <DetailItem label="IČO" value={company.ico} icon="fa-hashtag" />
                <DetailItem label="Adresa"
                    value={orsrProfile?.sidlo || `${company.address.street}, ${company.address.city}`}
                    icon="fa-map-marker-alt" />
                <DetailItem label="Dátum vzniku"
                    value={formatDate(orsrProfile?.den_zapisu) || new Date(company.registrationDate).toLocaleDateString('sk-SK')}
                    icon="fa-calendar-alt" />
                <DetailItem label="Posledná aktualizácia"
                    value={formatDate(orsrProfile?.orsr_aktualizacia_dat) || new Date(company.lastUpdatedFromSource).toLocaleString('sk-SK')}
                    icon="fa-sync-alt" />
            </div>
        </div>
    );
};
