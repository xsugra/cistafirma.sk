import React, {useEffect, useState} from 'react';
import {Link} from 'react-router-dom';
import type {PeerList, PeerScope} from '../../../types';
import {api} from '../../../api';
import {companyPath} from '../../../constants';
import {formatCurrency, formatNumber} from '../../../utils/format';
import {InfoCard} from '../../InfoCard';

/** How many rows the backend sends, and how many the section promises. */
const SHOWN = 10;

interface ScopeCopy {
    title: string;
    icon: string;
    intro: string;
}

/**
 * One entry per scope. The heading, the icon and the sentence that says what
 * the list *is* travel together, so a section cannot be given the wrong one of
 * the three.
 */
const SCOPE_COPY: Record<PeerScope, ScopeCopy> = {
    podobne: {
        title: 'Podobné spoločnosti',
        icon: 'fa-clone',
        intro:
            'Firmy v tej istej divízii SK NACE, ktorých obrat je tejto firme najbližšie. ' +
            'Blízkosť sa počíta v pomere, nie v eurách — 10 000 € od firmy s obratom 50 000 € ' +
            'je iná firma než 10 000 € od firmy s obratom 50 000 000 €.',
    },
    kraj: {
        title: 'Firmy v kraji',
        icon: 'fa-map-marker-alt',
        intro: 'Najväčšie firmy v kraji sídla tejto firmy.',
    },
    odvetvie: {
        title: 'Firmy v odvetví',
        icon: 'fa-industry',
        intro:
            'Najväčšie firmy v tej istej divízii SK NACE — prvé dvojčíslie kódu, ' +
            'napríklad 62 pre počítačové programovanie.',
    },
    trzby: {
        title: 'Firmy podľa tržieb',
        icon: 'fa-coins',
        intro: 'Najväčšie firmy v celom registri podľa poslednej zverejnenej závierky.',
    },
};

/**
 * What the two counts mean, in one sentence a reader can check against them.
 *
 * This is the section's whole reason for existing. Only companies that filed a
 * RUZ statement have any revenue, so a list headed "the largest in the region"
 * is a ranking of a small fraction of the region. Printing the pair is what
 * keeps the heading from being an overstatement -- and `total_in_scope` is
 * deliberately the *larger* number, placed second so it reads as the frame and
 * not as the result.
 */
export function populationSentence(
    payload: PeerList,
    scopeLabel: string,
    // Whether this section is about to draw the rows it is counting. The
    // fallback branch below counts a ranking it deliberately does not render,
    // and "Zobrazujeme prvých 10" over no table is a promise the section does
    // not keep.
    {showing = true}: {showing?: boolean} = {}
): string {
    const ranked = payload.total_ranked;
    const inScope = payload.total_in_scope;

    if (ranked === 0) {
        return (
            `V rozsahu ${scopeLabel} máme ${formatNumber(inScope)} firiem a ani jedna z nich ` +
            'nemá zverejnenú závierku s tržbami, takže ich nie je podľa čoho zoradiť.'
        );
    }

    const tail = !showing ? '' : ranked > SHOWN ? ` Zobrazujeme prvých ${SHOWN}.` : ' Zobrazujeme všetky.';
    return (
        `V rozsahu ${scopeLabel} máme ${formatNumber(inScope)} firiem. ` +
        `Zverejnenú závierku s tržbami má ${formatNumber(ranked)} z nich, ` +
        `a práve tie sa dajú zoradiť.${tail}`
    );
}

/** The subject's own name for the scope, falling back to the register itself. */
function scopeLabel(payload: PeerList): string {
    if (payload.subject_label) return payload.subject_label;
    return payload.subject ?? 'celý register';
}

const Row: React.FC<{payload: PeerList}> = ({payload}) => (
    <div className="overflow-x-auto">
        <table className="w-full text-sm">
            <thead>
            <tr className="border-b border-gray-200 dark:border-slate-700">
                {['Firma', 'Mesto', 'Odvetvie', 'Rok', 'Tržby', 'Zisk'].map((heading, i) => (
                    <th
                        key={heading}
                        className={`px-3 py-2 text-xs font-medium uppercase text-gray-500 dark:text-gray-400 ${
                            i >= 4 ? 'text-right' : 'text-left'
                        }`}
                    >
                        {heading}
                    </th>
                ))}
            </tr>
            </thead>
            <tbody className="divide-y divide-gray-50 dark:divide-slate-800/50">
            {payload.results.map((row) => (
                <tr key={row.ico}>
                    <td className="px-3 py-2">
                        <Link
                            to={companyPath(row.ico)}
                            className="text-brand hover:underline font-medium"
                        >
                            {row.name}
                        </Link>
                        <span className="ml-2 font-mono text-xs text-gray-400 dark:text-gray-500">
                            {row.ico}
                        </span>
                    </td>
                    <td className="px-3 py-2 text-gray-600 dark:text-gray-300">{row.city || '—'}</td>
                    <td className="px-3 py-2 text-gray-600 dark:text-gray-300">
                        {/* `||` and not `??`: the mapper turns a missing code into
                            an empty string, which is not nullish, so `??` would
                            leave the cell blank. */}
                        {row.nace_name || row.nace_code || '—'}
                    </td>
                    <td className="px-3 py-2 font-mono tabular-nums text-gray-600 dark:text-gray-300">
                        {row.year}
                    </td>
                    <td className="px-3 py-2 text-right font-mono tabular-nums text-gray-900 dark:text-white">
                        {formatCurrency(row.revenue)}
                    </td>
                    <td className="px-3 py-2 text-right font-mono tabular-nums text-gray-600 dark:text-gray-300">
                        {formatCurrency(row.profit)}
                    </td>
                </tr>
            ))}
            </tbody>
        </table>
    </div>
);

interface PeerListSectionProps {
    ico: string;
    scope: PeerScope;
}

/**
 * One of the four "who else is here" lists on a company page.
 *
 * The service behind this answers with two counts and a code for why it could
 * not answer at all, and all three are rendered rather than smoothed over: a
 * list that silently shows ten rows out of a hundred thousand, or that quietly
 * switches from "similar" to "largest", is the kind of claim this page exists
 * to avoid making. See `backend/companies/services/peers.py`.
 */
export const PeerListSection: React.FC<PeerListSectionProps> = ({ico, scope}) => {
    const copy = SCOPE_COPY[scope];
    const [payload, setPayload] = useState<PeerList | null>(null);
    const [failed, setFailed] = useState(false);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        // `cancelled` and not just a `setState` guard: switching sections
        // quickly leaves two requests in flight, and the slower one must not
        // overwrite the section the reader is now looking at.
        let cancelled = false;
        setLoading(true);
        setFailed(false);
        setPayload(null);

        api.getPeers(ico, scope)
            .then((data) => {
                if (!cancelled) setPayload(data);
            })
            .catch(() => {
                if (!cancelled) setFailed(true);
            })
            .finally(() => {
                if (!cancelled) setLoading(false);
            });

        return () => {
            cancelled = true;
        };
    }, [ico, scope]);

    if (loading) {
        return (
            <InfoCard title={copy.title} icon={copy.icon}>
                <div className="flex items-center justify-center h-24 text-gray-500 dark:text-gray-400">
                    <div className="w-4 h-4 border-2 border-blue-500 border-t-transparent rounded-full animate-spin mr-2"/>
                    Načítavam...
                </div>
            </InfoCard>
        );
    }

    if (failed || !payload) {
        return (
            <InfoCard title={copy.title} icon={copy.icon}>
                <p className="text-gray-700 dark:text-gray-300 leading-relaxed">
                    Zoznam sa nepodarilo načítať. Skús stránku obnoviť.
                </p>
            </InfoCard>
        );
    }

    if (payload.reason === 'no_region') {
        return (
            <InfoCard title={copy.title} icon={copy.icon}>
                <p className="text-gray-700 dark:text-gray-300 leading-relaxed">
                    V registri nemáme pre túto firmu kraj sídla, takže ju nemáme v čom
                    porovnávať. Doplní sa pri najbližšom načítaní firmy z registra.
                </p>
            </InfoCard>
        );
    }

    if (payload.reason === 'no_nace') {
        return (
            <InfoCard title={copy.title} icon={copy.icon}>
                <p className="text-gray-700 dark:text-gray-300 leading-relaxed">
                    V registri nemáme pre túto firmu čitateľný kód SK NACE, takže ju nevieme
                    zaradiť do odvetvia. Doplní sa pri najbližšom načítaní firmy z registra.
                </p>
            </InfoCard>
        );
    }

    const label = scopeLabel(payload);
    // `podobne` is the one scope that can be answered under a different
    // ordering than its heading promises, when the subject has no filed
    // revenue of its own to be similar to.
    const fellBack = scope === 'podobne' && payload.ranked_by === 'revenue';

    if (fellBack) {
        // The fallback used to draw the industry ranking here, under this
        // heading. It is the *same queryset in the same order* as
        // `databaza-odvetvie` -- measured 2026-09-12, `podobne` falls back for
        // every company without a filed revenue figure, which is 323 267 of the
        // 325 337 active ones (99,4 %), and for all of them the two rail entries
        // rendered ten identical rows under two different headings. A reader who
        // clicked both saw the page repeat itself, which makes both sections
        // look broken rather than one of them look honest.
        //
        // So this state no longer draws a table. It says why the question cannot
        // be answered, and points at the section that answers the neighbouring
        // one -- where the same rows appear under the heading that actually
        // describes them.
        return (
            <InfoCard title={copy.title} icon={copy.icon}>
                <p className="text-gray-700 dark:text-gray-300 leading-relaxed">{copy.intro}</p>

                <p className="mt-3 rounded-lg bg-amber-50 px-4 py-3 text-sm text-amber-800 dark:bg-amber-900/20 dark:text-amber-300">
                    <i className="fas fa-circle-info mr-2"/>
                    Táto firma nemá zverejnenú závierku s tržbami, takže nemáme obrat, ku
                    ktorému by sme blízkosť prirovnali. Podobné firmy jej preto určiť
                    nevieme.
                </p>

                <p className="mt-3 text-sm leading-relaxed text-gray-600 dark:text-gray-400">
                    {populationSentence(payload, label, {showing: false})}
                </p>

                <p className="mt-3 text-sm leading-relaxed text-gray-700 dark:text-gray-300">
                    To isté, čo sa o tomto odvetví povedať dá, je zoznam najväčších firiem
                    v ňom — a ten má vlastnú sekciu, aby tie isté riadky nestáli na dvoch
                    miestach.
                </p>

                <Link
                    to={companyPath(ico, 'databaza-odvetvie')}
                    className="btn btn-primary mt-4 inline-flex"
                >
                    <i className="fas fa-industry"/> Firmy v odvetví
                </Link>
            </InfoCard>
        );
    }

    return (
        <InfoCard title={copy.title} icon={copy.icon}>
            <p className="text-gray-700 dark:text-gray-300 leading-relaxed">{copy.intro}</p>

            <p className="mt-3 text-sm leading-relaxed text-gray-600 dark:text-gray-400">
                {populationSentence(payload, label)}
            </p>

            {payload.results.length > 0 && (
                <>
                    <div className="mt-4">
                        <Row payload={payload}/>
                    </div>
                    <p className="mt-3 text-xs text-gray-400 dark:text-gray-500">
                        Každá firma je uvedená v roku svojej poslednej zverejnenej závierky,
                        preto sa roky medzi riadkami líšia. Táto firma v zozname nie je —
                        nebola by svojím vlastným susedom — a zrušené firmy vynechávame.
                    </p>
                </>
            )}
        </InfoCard>
    );
};
