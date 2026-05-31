import React, { useState, useEffect, useCallback } from 'react';
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
    const [copied, setCopied] = useState(false);
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

    const handleCopyIco = useCallback(() => {
        navigator.clipboard.writeText(company.ico).then(() => {
            setCopied(true);
            setTimeout(() => setCopied(false), 2000);
        }).catch(() => {});
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

    const handleExportPDF = () => {
        const url = `/api/companies/${company.ico}/report/`;
        window.open(url, '_blank');
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
                        onClick={handleExportPDF}
                        className="btn bg-gray-100 hover:bg-gray-200 dark:bg-slate-800 dark:hover:bg-slate-700 text-gray-700 dark:text-gray-300"
                        title="Stiahnuť PDF report"
                    >
                        <i className="fas fa-file-pdf"></i> PDF
                    </button>
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
                <div className="flex items-start space-x-3">
                    <i className="fas fa-hashtag text-blue-500 dark:text-blue-400 mt-1 w-4 text-center"></i>
                    <div>
                        <p className="text-sm text-gray-500 dark:text-gray-400">IČO</p>
                        <div className="flex items-center gap-1.5">
                            <span className="font-semibold text-gray-900 dark:text-white">{company.ico}</span>
                            <button
                                onClick={handleCopyIco}
                                className="text-gray-400 hover:text-blue-500 dark:hover:text-blue-400 transition-colors p-0.5"
                                title="Kopírovať IČO"
                            >
                                <i className={`fas ${copied ? 'fa-check text-green-500' : 'fa-copy'} text-xs`}></i>
                            </button>
                        </div>
                    </div>
                </div>
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
