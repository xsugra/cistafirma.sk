import React, { useState, useEffect, useCallback } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import type { Company } from '../../types';
import { StatusBadge } from '../StatusBadge';
import { api } from '../../api';
import { useAuth } from '../../context/AuthContext';
import { ROUTES } from '../../constants';
import { DetailItem } from './DetailItem';
import { formatDate } from './helpers';
import { exportCompanyPDF } from '../../utils/pdfExport';
import type { LegalFormProfile } from '../../utils/legalFormProfile';

interface CompanyHeaderProps {
    company: Company;
    profile: LegalFormProfile;
}

export const CompanyHeader: React.FC<CompanyHeaderProps> = ({ company, profile }) => {
    const { isAuthenticated } = useAuth();
    const navigate = useNavigate();
    const location = useLocation();
    const [isWatching, setIsWatching] = useState(false);
    const [watchLoading, setWatchLoading] = useState(false);
    const [watchError, setWatchError] = useState<string | null>(null);
    const [pdfLoading, setPdfLoading] = useState(false);
    const [copied, setCopied] = useState(false);
    const orsrProfile = company.orsr_profile;

    // Only ask which companies are watched when there is an account to ask
    // about. `getWatchlist` is `IsAuthenticated`, so for an anonymous visitor
    // this was a guaranteed 401 on every company page -- which the client
    // turned into a global `auth:unauthorized` event and a console warning, for
    // a question nobody had asked.
    useEffect(() => {
        if (!isAuthenticated) {
            setIsWatching(false);
            return;
        }
        let cancelled = false;
        api.getWatchlist().then(list => {
            if (!cancelled) {
                setIsWatching(list.some(entry => entry.ico === company.ico));
            }
        }).catch(() => {});
        return () => { cancelled = true; };
    }, [company.ico, isAuthenticated]);

    const handleCopyIco = useCallback(() => {
        navigator.clipboard.writeText(company.ico).then(() => {
            setCopied(true);
            setTimeout(() => setCopied(false), 2000);
        }).catch(() => {});
    }, [company.ico]);

    /**
     * Watch, or send the visitor to sign in first.
     *
     * A watch belongs to an account -- `POST /api/watchlist/` is
     * `IsAuthenticated` -- so an anonymous click used to do nothing at all: the
     * request 401'd, the catch logged it to a console nobody was reading, and
     * the button sat there looking like it had worked. That is the silent
     * failure this project treats as a defect class, and here it cost the
     * reader the only thing they had asked for.
     *
     * So the click now leads to sign-in, carrying where they were. The watch
     * itself is deliberately **not** re-issued automatically once they are
     * back: it is a write to their account, and replaying it from a remembered
     * intent means a change they confirmed on one page happening silently after
     * a login page they may have reached for an unrelated reason. They land
     * back on this company and click again -- one click, and it is theirs.
     */
    const handleWatchToggle = async () => {
        if (!isAuthenticated) {
            navigate(ROUTES.LOGIN, {
                state: { from: location.pathname + location.search },
            });
            return;
        }

        setWatchLoading(true);
        setWatchError(null);
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
            // Shown, not swallowed. The button is the only feedback this action
            // has, so a failure that stays in the console is a failure the
            // reader reads as success.
            setWatchError(
                e instanceof Error ? e.message : 'Sledovanie sa nepodarilo zmeniť.',
            );
        } finally {
            setWatchLoading(false);
        }
    };

    const handleExportPDF = async () => {
        setPdfLoading(true);
        try {
            await exportCompanyPDF(company);
        } catch (e) {
            console.error("PDF export failed", e);
        } finally {
            setPdfLoading(false);
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
                        onClick={handleExportPDF}
                        disabled={pdfLoading}
                        className="btn bg-gray-100 hover:bg-gray-200 dark:bg-slate-800 dark:hover:bg-slate-700 text-gray-700 dark:text-gray-300"
                        title="Stiahnuť PDF report"
                    >
                        {pdfLoading ? (
                            <i className="fas fa-spinner animate-spin"></i>
                        ) : (
                            <i className="fas fa-file-pdf"></i>
                        )}
                        {' '}PDF
                    </button>
                    <button
                        onClick={handleWatchToggle}
                        disabled={watchLoading}
                        className={`btn ${isWatching ? 'bg-green-600 hover:bg-green-700 text-white' : 'btn-primary'}`}
                        title={
                            isAuthenticated
                                ? undefined
                                : 'Na sledovanie firmy sa musíš prihlásiť'
                        }
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
            {watchError && (
                <p
                    role="alert"
                    className="mt-3 rounded-lg bg-amber-50 px-4 py-3 text-sm text-amber-800 dark:bg-amber-900/20 dark:text-amber-300"
                >
                    <i className="fas fa-circle-exclamation mr-2" aria-hidden="true" />
                    {watchError}
                </p>
            )}
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
                        {/* DIČ, under the IČO because they are the same kind of
                            thing and a reader checking one is usually checking
                            the other. Absent for 50 253 companies, which is why
                            this line disappears rather than printing a label
                            with nothing after it. */}
                        {company.dic && (
                            <p className="text-xs text-gray-500 dark:text-gray-400 mt-0.5">
                                DIČ <span className="font-medium text-gray-700 dark:text-gray-300">{company.dic}</span>
                            </p>
                        )}
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
