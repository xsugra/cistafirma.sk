import React, { useState } from 'react';
import { api } from '../../api';
import type { OrsrPersonSearchResponse } from '../../types';
import { formatNumber } from '../../utils/format';

interface OrsrRegisterGroupProps {
    /** The name to ask about -- the person's own name, as we hold it. */
    name: string;
}

type RequestState =
    | { kind: 'idle' }
    | { kind: 'loading' }
    // The request itself failed (throttled, offline, a 502). Different from the
    // register answering that it could not be read, which arrives as 200 with
    // `error` filled in, and different again from the register holding nothing.
    | { kind: 'failed'; message: string }
    | { kind: 'answered'; result: OrsrPersonSearchResponse };

/**
 * The live register's answer, in its own group, on request only.
 *
 * Three rules shape this component, and each one is a way the screen could
 * otherwise lie:
 *
 * 1. **Nothing calls the register until a button is pressed.** `orsr.sk` is
 *    somebody else's server with no API; a request per keystroke would be our
 *    traffic on their budget. This is the only caller of
 *    `api.searchOrsrPersons`, and `SearchBar` must not become the second one.
 * 2. **It never reads as one list with our own data.** Our relations come from
 *    our own tables and carry roles, dates and the tri-state answer; the
 *    register's rows carry a name and a company and nothing else. Rendering
 *    them in one list would let a reader attribute our coverage to the
 *    register, or the register's completeness to us.
 * 3. **"We could not ask" is not "there are none."** An unreachable register
 *    renders as the register being unreachable, never as an empty result.
 */
export const OrsrRegisterGroup: React.FC<OrsrRegisterGroupProps> = ({ name }) => {
    const [state, setState] = useState<RequestState>({ kind: 'idle' });

    const ask = async () => {
        setState({ kind: 'loading' });
        try {
            const result = await api.searchOrsrPersons(name);
            setState({ kind: 'answered', result });
        } catch (err) {
            setState({
                kind: 'failed',
                message:
                    err instanceof Error && err.message
                        ? err.message
                        : 'Registra ORSR sa nepodarilo opýtať.',
            });
        }
    };

    return (
        <section
            aria-label="Register ORSR"
            className="overflow-hidden rounded-xl border border-amber-200 bg-white shadow-lg dark:border-amber-900/40 dark:bg-slate-900 dark:shadow-none"
        >
            <div className="flex flex-wrap items-center justify-between gap-2 border-b border-amber-200 bg-amber-50/60 px-6 py-4 dark:border-amber-900/40 dark:bg-amber-900/10">
                <h2 className="flex items-center gap-3 text-lg font-bold text-gray-900 dark:text-white">
                    <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-amber-500/10">
                        <i className="fas fa-landmark text-amber-600 dark:text-amber-400"></i>
                    </span>
                    Register ORSR
                </h2>
                <span className="rounded-full border border-amber-300 bg-white px-2 py-0.5 text-[10px] font-bold uppercase tracking-wide text-amber-700 dark:border-amber-800 dark:bg-slate-900 dark:text-amber-400">
                    Nie sú to naše dáta
                </span>
            </div>

            <div className="space-y-4 p-6">
                <p className="text-sm text-gray-600 dark:text-gray-300">
                    Obchodný register vie hľadať podľa mena osoby. Odpovie zoznam firiem, v
                    ktorých je meno zapísané — čo náš graf nemusí mať, ak sme tie firmy ešte
                    nečítali. Register oslovíme až keď kliknete; je to cudzí server a jeho
                    limity sú jeho.
                </p>

                <button
                    type="button"
                    onClick={ask}
                    disabled={state.kind === 'loading'}
                    className="btn btn-primary inline-flex items-center gap-2 disabled:cursor-not-allowed disabled:opacity-60"
                >
                    {state.kind === 'loading' ? (
                        <i className="fas fa-circle-notch animate-spin" aria-hidden="true"></i>
                    ) : (
                        <i className="fas fa-up-right-from-square" aria-hidden="true"></i>
                    )}
                    {state.kind === 'loading' ? 'Overujem v registri…' : 'Overiť v registri ORSR'}
                </button>

                {state.kind === 'failed' && (
                    <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm dark:border-red-900/50 dark:bg-red-900/20">
                        <p className="font-medium text-red-700 dark:text-red-400">
                            <i className="fas fa-exclamation-triangle mr-2"></i>
                            Registra sa nepodarilo opýtať.
                        </p>
                        <p className="mt-1 text-red-600 dark:text-red-300">{state.message}</p>
                        <p className="mt-1 text-red-600 dark:text-red-300">
                            Nie je to tvrdenie o osobe — odpoveď jednoducho nemáme.
                        </p>
                    </div>
                )}

                {state.kind === 'answered' && <OrsrAnswer result={state.result} />}
            </div>
        </section>
    );
};

const OrsrAnswer: React.FC<{ result: OrsrPersonSearchResponse }> = ({ result }) => {
    // The register could not be read. Shown before anything else, because it is
    // the one answer that is not about the person at all.
    if (result.error) {
        return (
            <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm dark:border-red-900/50 dark:bg-red-900/20">
                <p className="font-medium text-red-700 dark:text-red-400">
                    <i className="fas fa-exclamation-triangle mr-2"></i>
                    Register sa nepodarilo prečítať.
                </p>
                <p className="mt-1 break-words text-red-600 dark:text-red-300">{result.error}</p>
                <p className="mt-1 text-red-600 dark:text-red-300">
                    Nie je to tvrdenie o osobe — register nám tentoraz neodpovedal.
                </p>
            </div>
        );
    }

    // The question was never asked (a query the register's form cannot take).
    if (result.detail) {
        return (
            <div className="rounded-lg border border-amber-200 bg-amber-50 p-4 text-sm text-amber-800 dark:border-amber-900/50 dark:bg-amber-900/20 dark:text-amber-300">
                <i className="fas fa-circle-info mr-2"></i>
                {result.detail}
            </div>
        );
    }

    return (
        <div className="space-y-3">
            <div className="flex flex-wrap items-center gap-2 text-sm text-gray-600 dark:text-gray-300">
                <span>
                    Register našiel{' '}
                    <strong className="text-gray-900 dark:text-white">
                        {formatNumber(result.total)}
                    </strong>{' '}
                    záznamov
                    {result.truncated ? ' (zobrazujeme len časť)' : ''}.
                </span>
                {result.cached && (
                    <span
                        className="rounded-full border border-gray-200 bg-gray-100 px-2 py-0.5 text-[10px] font-bold uppercase tracking-wide text-gray-500 dark:border-slate-700 dark:bg-slate-800 dark:text-gray-400"
                        title="Túto odpoveď sme od registra dostali skôr a pamätáme si ju."
                    >
                        z pamäte
                    </span>
                )}
            </div>

            {/* The register's own limitation, in its own words, next to the rows
                it applies to. It is not a footnote: without it, a list of
                companies reads as a list of offices. */}
            {result.note && (
                <p className="rounded-lg border border-amber-200 bg-amber-50/70 p-3 text-xs text-amber-800 dark:border-amber-900/50 dark:bg-amber-900/10 dark:text-amber-300">
                    <i className="fas fa-triangle-exclamation mr-2"></i>
                    {result.note}
                </p>
            )}

            {result.hits.length > 0 ? (
                <ul className="divide-y divide-gray-100 rounded-lg border border-gray-200 dark:divide-slate-800 dark:border-slate-700">
                    {result.hits.map((hit, index) => (
                        <li
                            key={`${hit.person_name}-${hit.company_name}-${index}`}
                            className="flex flex-col gap-1 px-4 py-3 sm:flex-row sm:items-center sm:justify-between sm:gap-4"
                        >
                            <div className="min-w-0">
                                <p className="font-medium text-gray-900 dark:text-white">
                                    {hit.company_name}
                                </p>
                                {hit.person_name && (
                                    <p className="text-xs text-gray-500 dark:text-gray-400">
                                        Zápis: {hit.person_name}
                                    </p>
                                )}
                            </div>
                            <div className="flex shrink-0 items-center gap-3 text-sm">
                                {hit.current_url && (
                                    <a
                                        href={hit.current_url}
                                        target="_blank"
                                        rel="noopener noreferrer"
                                        className="text-blue-600 hover:underline dark:text-blue-400"
                                    >
                                        Výpis
                                    </a>
                                )}
                                {hit.full_url && (
                                    <a
                                        href={hit.full_url}
                                        target="_blank"
                                        rel="noopener noreferrer"
                                        className="text-blue-600 hover:underline dark:text-blue-400"
                                    >
                                        Úplný výpis
                                    </a>
                                )}
                            </div>
                        </li>
                    ))}
                </ul>
            ) : (
                <p className="rounded-lg border border-gray-200 bg-gray-50 p-4 text-sm text-gray-600 dark:border-slate-700 dark:bg-slate-800/50 dark:text-gray-300">
                    Register pre toto meno nič nevrátil — a to sme ho skúsili aj bez
                    diakritiky. Jeho hľadanie totiž rozlišuje diakritiku presne, takže ak
                    meno v registri je, je zapísané inak, než sme sa pýtali. Register
                    navyše vedie len aktuálne záznamy: kto z firmy odišiel, v tomto
                    zozname nie je vôbec.
                </p>
            )}

            {result.source_url && (
                <p className="text-xs text-gray-500 dark:text-gray-400">
                    Zdroj:{' '}
                    <a
                        href={result.source_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="break-all text-blue-600 hover:underline dark:text-blue-400"
                    >
                        Obchodný register SR — tento výpis priamo na orsr.sk
                    </a>
                </p>
            )}
        </div>
    );
};
