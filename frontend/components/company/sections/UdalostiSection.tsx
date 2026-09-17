import React, {useEffect, useState} from 'react';
import {Link} from 'react-router-dom';
import type {NotificationEvent} from '../../../types';
import {api} from '../../../api';
import {ROUTES} from '../../../constants';
import {InfoCard} from '../../InfoCard';
import {useAuth} from '../../../context/AuthContext';

/**
 * Udalosti vo firme: what *this account* was told about this company.
 *
 * The heading is the same one FinStat uses, and the honest reading of it here
 * is narrower than it sounds. There is no event log of the company's life in
 * this database -- no table of "what happened to IČO 12345678" that anyone can
 * read. What exists is `NotificationEvent`: one row per notification *we sent*,
 * to one user, about one company, when a watched firm's debt, status or
 * statutory body changed.
 *
 * So the section shows the reader their own history with the company and says
 * so in the first line, rather than dressing a mailbox up as a timeline. Two
 * consequences follow, and both are rendered instead of hidden:
 *
 * - It needs an account. The rest of this page is public; this section is not,
 *   because the answer differs per reader. Signed out, it explains what it
 *   would show and how to get it rather than showing an empty list that reads
 *   as "nothing ever happened here".
 * - An empty list means nothing *was sent*, which is not the same as nothing
 *   having happened. The empty state says which one it is.
 */
export const UdalostiSection: React.FC<{ico: string}> = ({ico}) => {
    const {isAuthenticated} = useAuth();
    const [events, setEvents] = useState<NotificationEvent[] | null>(null);
    const [failed, setFailed] = useState(false);

    useEffect(() => {
        if (!isAuthenticated) return;

        let cancelled = false;
        setEvents(null);
        setFailed(false);

        api.getCompanyEvents(ico)
            .then((rows) => {
                if (!cancelled) setEvents(rows);
            })
            .catch(() => {
                if (!cancelled) setFailed(true);
            });

        return () => {
            cancelled = true;
        };
    }, [ico, isAuthenticated]);

    if (!isAuthenticated) {
        return (
            <InfoCard title="Udalosti vo firme" icon="fa-bell">
                <p className="text-gray-700 dark:text-gray-300 leading-relaxed">
                    Tu sa zobrazujú notifikácie, ktoré sme <strong>tebe</strong> poslali
                    o tejto firme — nie všeobecná história firmy. Preto ich vidíš len po
                    prihlásení a len ak ju máš v sledovaných.
                </p>
                <Link to={ROUTES.LOGIN} className="btn btn-primary mt-4 inline-flex">
                    <i className="fas fa-sign-in-alt"></i> Prihlásiť sa
                </Link>
            </InfoCard>
        );
    }

    if (failed) {
        return (
            <InfoCard title="Udalosti vo firme" icon="fa-bell">
                <p className="text-gray-700 dark:text-gray-300 leading-relaxed">
                    Notifikácie sa nepodarilo načítať. Skús stránku obnoviť.
                </p>
            </InfoCard>
        );
    }

    if (events === null) {
        return (
            <InfoCard title="Udalosti vo firme" icon="fa-bell">
                <div className="flex items-center justify-center h-24 text-gray-500 dark:text-gray-400">
                    <div className="w-4 h-4 border-2 border-blue-500 border-t-transparent rounded-full animate-spin mr-2"/>
                    Načítavam...
                </div>
            </InfoCard>
        );
    }

    if (events.length === 0) {
        return (
            <InfoCard title="Udalosti vo firme" icon="fa-bell">
                <p className="text-gray-700 dark:text-gray-300 leading-relaxed">
                    O tejto firme sme ti zatiaľ nič neposlali.
                </p>
                <p className="mt-3 text-sm text-gray-600 dark:text-gray-400 leading-relaxed">
                    Neznamená to, že sa nič nestalo — notifikáciu posielame len vtedy, keď
                    sa zmení niečo, čo vieme porovnať: evidovaný dlh, stav firmy alebo
                    štatutárny orgán. Ak firma nie je v tvojich sledovaných, nemáme ju
                    odkiaľ porovnať.
                </p>
            </InfoCard>
        );
    }

    return (
        <InfoCard title="Udalosti vo firme" icon="fa-bell">
            <p className="text-sm text-gray-600 dark:text-gray-400 leading-relaxed">
                Notifikácie, ktoré sme poslali tebe o tejto firme. Sú to tri typy zmien,
                ktoré vieme porovnať medzi kontrolami.
            </p>
            <ul className="mt-4 divide-y divide-gray-100 dark:divide-slate-800">
                {events.map((event) => (
                    <li key={event.id} className="flex gap-3 py-3">
                        <span className="mt-0.5 text-gray-400 dark:text-gray-500">
                            <i className={`fas ${EVENT_ICON[event.eventType] ?? 'fa-circle-info'}`}/>
                        </span>
                        <div className="min-w-0 flex-1">
                            <p className="text-gray-900 dark:text-white">{event.title}</p>
                            <p className="mt-0.5 text-xs text-gray-500 dark:text-gray-400">
                                {event.eventTypeDisplay} · {formatDateTime(event.createdAt)}
                                {!event.sentEmail && ' · e-mail sme neposlali'}
                            </p>
                        </div>
                    </li>
                ))}
            </ul>
        </InfoCard>
    );
};

/** One icon per event type the model can produce. */
const EVENT_ICON: Record<string, string> = {
    debt_change: 'fa-hand-holding-usd',
    status_change: 'fa-toggle-on',
    executive_change: 'fa-user-tie',
};

/**
 * `created_at` as the reader's local date and time.
 *
 * `toLocaleString` and not a hand-built format: the API sends UTC ISO, and the
 * browser is the only thing here that knows which timezone the reader is in.
 */
export function formatDateTime(iso: string): string {
    const date = new Date(iso);
    if (Number.isNaN(date.getTime())) return iso;
    return date.toLocaleString('sk-SK', {
        day: 'numeric',
        month: 'numeric',
        year: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
    });
}
