import React, { useState, useEffect, useCallback } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import type { Company } from '../../types';
import { StatusBadge } from '../StatusBadge';
import { api } from '../../api';
import { adminApi } from '../../admin/api';
import { useAuth } from '../../context/AuthContext';
import { ROUTES } from '../../constants';
import { DetailItem } from './DetailItem';
import { SeatLocationCard } from './SeatLocationCard';
import { formatDate } from './helpers';
import { exportCompanyPDF } from '../../utils/pdfExport';
import type { LegalFormProfile } from '../../utils/legalFormProfile';
import type { CompanyRefreshResult, CompanyRefreshSkip } from '../../admin/api';

interface CompanyHeaderProps {
    company: Company;
    profile: LegalFormProfile;
}

/** Source codes as the sentence needs them, shorter than the admin panel's rows. */
const REFRESH_SOURCE_LABELS: Record<string, string> = {
    ruz: 'RUZ',
    financials: 'Finančné výkazy',
    orsr: 'ORSR',
    vszp: 'VšZP',
    social: 'Sociálna poisťovňa',
};

/**
 * The two refusals, as the clause after the source reads.
 *
 * `not_eligible` is named as plainly as the machine reason is: ORSR is asked
 * only for the legal forms it monitors and for a company that is not struck
 * off, and the frontend cannot tell which of the two it was -- so it does not
 * claim either.
 */
const REFRESH_SKIP_REASONS: Record<CompanyRefreshSkip['reason'], string> = {
    not_eligible: 'firma nie je spôsobilá',
    blocked: 'zdroj je zablokovaný',
};

const refreshSourceLabel = (source: string) => REFRESH_SOURCE_LABELS[source] ?? source;

/** Slovak joins the last item with „a"; a single item joins nothing at all. */
const joinSk = (items: string[]) =>
    items.length <= 1 ? items[0] ?? '' : `${items.slice(0, -1).join(', ')} a ${items[items.length - 1]}`;

/**
 * What a started refresh has to say for itself.
 *
 * The number in this cell is written by the pass that has just been queued, so
 * it cannot change for minutes -- the sentence says that rather than implying
 * the page is now fresh. The two lists the response carries are the whole point
 * of the endpoint's shape: a skipped source is named instead of silently
 * missing, and a blocked one the pass asks anyway is named instead of leaving
 * an operator to infer it from a list that looks complete.
 */
function refreshSuccessText(result: CompanyRefreshResult): string {
    const parts = [
        'Obnova spustená — verejné zdroje sa znova načítajú o niekoľko minút. Nové údaje sa prejavia až po obnovení stránky.',
    ];
    if (result.skipped.length) {
        const skipped = result.skipped.map(
            (item) => `${refreshSourceLabel(item.source)} (${REFRESH_SKIP_REASONS[item.reason]})`,
        );
        parts.push(`Preskočené: ${joinSk(skipped)}.`);
    }
    if (result.blocked_but_asked.length) {
        const sources = result.blocked_but_asked.map(refreshSourceLabel);
        const noun = result.blocked_but_asked.length === 1 ? 'zablokovaný zdroj' : 'zablokované zdroje';
        parts.push(`Obnova aj tak osloví ${noun} ${joinSk(sources)}.`);
    }
    return parts.join(' ');
}

/**
 * A refusal, in a sentence a person can act on.
 *
 * Nothing here is endpoint-specific any more: `parseErrors` answers a body that
 * carries `retry_after_seconds` with the wait it named, so the cooldown arrives
 * as Slovak with its number already in it. A 502's `Dispatch failed: …` is left
 * as it is -- that one is a diagnostic, not a sentence.
 */
function refreshErrorText(error: unknown): string {
    return error instanceof Error ? error.message : 'Obnovenie sa nepodarilo spustiť.';
}

export const CompanyHeader: React.FC<CompanyHeaderProps> = ({ company, profile }) => {
    const { isAuthenticated, user } = useAuth();
    const navigate = useNavigate();
    const location = useLocation();
    const [isWatching, setIsWatching] = useState(false);
    const [watchLoading, setWatchLoading] = useState(false);
    const [watchError, setWatchError] = useState<string | null>(null);
    const [pdfLoading, setPdfLoading] = useState(false);
    const [copied, setCopied] = useState(false);
    const [refreshLoading, setRefreshLoading] = useState(false);
    const [refreshNotice, setRefreshNotice] = useState<{ kind: 'success' | 'error'; text: string } | null>(null);
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

    /**
     * Ask the server for a full pass over this company.
     *
     * The click is only the *request*: the pass runs in Celery, so nothing on
     * this page changes when the request returns, and the answer is shown for
     * what it is. The failure path is shown for the same reason the watch
     * button's is -- a control whose only feedback is itself reads as success
     * when it fails quietly.
     */
    const handleRefresh = async () => {
        setRefreshLoading(true);
        setRefreshNotice(null);
        try {
            const result = await adminApi.refreshCompany(company.id);
            setRefreshNotice({ kind: 'success', text: refreshSuccessText(result) });
        } catch (e) {
            setRefreshNotice({ kind: 'error', text: refreshErrorText(e) });
        } finally {
            setRefreshLoading(false);
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
                    value={
                        <>
                            {formatDate(orsrProfile?.orsr_aktualizacia_dat) || new Date(company.lastUpdatedFromSource).toLocaleString('sk-SK')}
                            {/* Staff only, and absent -- not disabled -- for
                                everyone else. This page is public: the company
                                viewset is `AllowAny` and `/firma/:ico` sits
                                outside `ProtectedRoute`, so a control rendered
                                for all readers would be a button that 403s for
                                most of them. A hint would be a second thing
                                that does not exist for them today. */}
                            {user?.isStaff && (
                                <span className="mt-1 flex">
                                    <button
                                        type="button"
                                        onClick={handleRefresh}
                                        disabled={refreshLoading}
                                        title="Znova načítať údaje z verejných registrov"
                                        className="inline-flex items-center gap-1.5 rounded-md border border-blue-200 bg-blue-50 px-2 py-0.5 text-xs font-medium text-blue-700 transition-colors hover:border-blue-300 hover:bg-blue-100 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-500 disabled:cursor-not-allowed disabled:opacity-60 dark:border-blue-900 dark:bg-blue-950/40 dark:text-blue-300 dark:hover:border-blue-800 dark:hover:bg-blue-900/50"
                                    >
                                        <i className={`fas ${refreshLoading ? 'fa-spinner fa-spin' : 'fa-arrows-rotate'}`} aria-hidden="true" />
                                        {refreshLoading ? 'Obnovujem…' : 'Aktualizovať údaje'}
                                    </button>
                                </span>
                            )}
                        </>
                    }
                    icon="fa-sync-alt" />
            </div>
            {refreshNotice && (
                <p
                    role={refreshNotice.kind === 'error' ? 'alert' : 'status'}
                    className={`mt-4 rounded-lg px-4 py-3 text-sm ${refreshNotice.kind === 'error'
                        ? 'bg-red-50 text-red-800 dark:bg-red-900/20 dark:text-red-300'
                        : 'bg-emerald-50 text-emerald-800 dark:bg-emerald-900/20 dark:text-emerald-300'}`}
                >
                    <i
                        className={`fas ${refreshNotice.kind === 'error' ? 'fa-circle-exclamation' : 'fa-circle-check'} mr-2`}
                        aria-hidden="true"
                    />
                    {refreshNotice.text}
                </p>
            )}
            {/* Absent, not empty, when we cannot place the seat: 1,92 % of our
                rows carry a PSČ the address register does not list, and a card
                saying "poloha neznáma" would be a worse answer than the address
                line above it already being the whole truth. Same shape as the
                DIČ line, which also disappears rather than printing a label with
                nothing after it. */}
            {company.seatLocation && (
                <SeatLocationCard
                    seat={company.seatLocation}
                    address={company.address}
                />
            )}
        </div>
    );
};
