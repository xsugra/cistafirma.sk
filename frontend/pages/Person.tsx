import React, { useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { api } from '../api';
import { ApiError } from '../lib/apiClient';
import type { PersonDetail } from '../types';
import { ROUTES } from '../constants';
import { LoadingSpinner } from '../components/LoadingSpinner';
import { PersonCoverageNote } from '../components/person/PersonCoverageNote';
import { PersonRecordsNote } from '../components/person/PersonRecordsNote';
import { PersonRelationRow } from '../components/person/PersonRelationRow';
import { OrsrRegisterGroup } from '../components/person/OrsrRegisterGroup';
import {
    ROLE_STATE_LINE,
    ROLE_STATE_SENTENCE,
    ROLE_STATE_WORD,
} from '../components/person/roleState';

/** The three states, from the answer we have to the one we do not. */
const ROLE_STATES = ['current', 'ended', 'unknown'] as const;

/**
 * One person, and every company we hold a relation for.
 *
 * The page exists because the register cannot answer this question well: its
 * own person search is diacritics-exact and current-records only, so someone who
 * left a company in 2019 is not in it at all. Ours reads the relations we have
 * imported, with their dates and their three-state answer about whether the
 * function still runs.
 *
 * What it must not do is pretend to be complete. We hold relations for a
 * fraction of the register, so `PersonCoverageNote` is printed above the list
 * and the list's emptiness is never left to speak for itself -- and beside it,
 * clearly apart, sits the register's own live answer, which is a different
 * claim about the same name from a different source.
 */
export const Person: React.FC = () => {
    const { id = '' } = useParams<{ id: string }>();
    const [person, setPerson] = useState<PersonDetail | null>(null);
    const [isLoading, setIsLoading] = useState(true);
    const [notFound, setNotFound] = useState(false);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        let cancelled = false;
        setIsLoading(true);
        setNotFound(false);
        setError(null);
        setPerson(null);

        api.getPerson(id)
            .then((data) => {
                if (!cancelled) setPerson(data);
            })
            .catch((err: unknown) => {
                if (cancelled) return;
                // A 404 is an answer -- there is no such person -- and it gets
                // the page's own state. Anything else is a failure to answer,
                // and a failure is not a person who does not exist.
                if (err instanceof ApiError && err.status === 404) {
                    setNotFound(true);
                    return;
                }
                setError(
                    err instanceof Error && err.message
                        ? err.message
                        : 'Nepodarilo sa načítať údaje o osobe.',
                );
            })
            .finally(() => {
                if (!cancelled) setIsLoading(false);
            });

        return () => {
            cancelled = true;
        };
    }, [id]);

    if (isLoading) {
        return (
            <div className="mx-auto w-full max-w-5xl py-8">
                <LoadingSpinner />
            </div>
        );
    }

    if (notFound) {
        return (
            <div className="mx-auto w-full max-w-2xl animate-fade-in py-16 text-center">
                <div className="mx-auto mb-6 flex h-24 w-24 items-center justify-center rounded-full bg-gray-100 text-gray-400 dark:bg-slate-800 dark:text-gray-500">
                    <i className="fas fa-user-slash text-4xl"></i>
                </div>
                <h1 className="mb-3 text-3xl font-bold text-gray-900 dark:text-white">
                    Osoba nebola nájdená
                </h1>
                <p className="mx-auto mb-8 max-w-lg text-gray-600 dark:text-gray-400">
                    Pre túto adresu nemáme v našich dátach žiadnu osobu. Môže to byť preklep v
                    adrese — alebo firma, ktorej osoby sme ešte nečítali.
                </p>
                <Link to={ROUTES.MONITORING} className="btn btn-primary inline-flex">
                    <i className="fas fa-search mr-2"></i> Hľadať osobu
                </Link>
            </div>
        );
    }

    if (error || !person) {
        return (
            <div className="mx-auto w-full max-w-2xl animate-fade-in py-16 text-center">
                <div className="rounded-xl border border-red-200 bg-white p-8 shadow-lg dark:border-red-900/50 dark:bg-slate-900">
                    <i className="fas fa-exclamation-triangle mb-4 text-3xl text-red-500"></i>
                    <p className="font-medium text-red-600 dark:text-red-400">
                        {error || 'Údaje o osobe sa nepodarilo načítať.'}
                    </p>
                    <p className="mt-2 text-sm text-gray-500 dark:text-gray-400">
                        Toto nie je tvrdenie o osobe — odpoveď sme nedostali.
                    </p>
                    <Link to={ROUTES.MONITORING} className="btn btn-primary mt-6 inline-flex">
                        <i className="fas fa-search"></i> Späť na vyhľadávanie
                    </Link>
                </div>
            </div>
        );
    }

    // The title is its own field, and `name` sometimes already carries it. A
    // chip repeating the first word of the heading reads as a duplicated field,
    // so it is shown only when it adds something -- never invented, only
    // suppressed when it is already there.
    const showTitle = Boolean(person.title) && !person.name.startsWith(person.title);

    return (
        <div className="mx-auto w-full max-w-5xl animate-fade-in space-y-6 py-8">
            <header className="rounded-xl border border-gray-200 bg-white p-6 shadow-lg dark:border-slate-700 dark:bg-slate-900 dark:shadow-none">
                <div className="flex items-start gap-4">
                    <div className="flex h-14 w-14 shrink-0 items-center justify-center rounded-full bg-slate-600 dark:bg-slate-500">
                        <i className="fas fa-user text-xl text-white"></i>
                    </div>
                    <div className="min-w-0">
                        <h1 className="break-words text-2xl font-bold text-gray-900 md:text-3xl dark:text-white">
                            {person.name}
                        </h1>
                        <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1 text-sm text-gray-500 dark:text-gray-400">
                            {showTitle && (
                                <span>
                                    <i className="fas fa-graduation-cap mr-1.5"></i>
                                    {person.title}
                                </span>
                            )}
                            {person.person_ico && (
                                <span>
                                    <i className="fas fa-hashtag mr-1.5"></i>
                                    IČO osoby: <span className="font-mono">{person.person_ico}</span>
                                </span>
                            )}
                            <span>
                                <i className="fas fa-building mr-1.5"></i>
                                {person.companies.length === 1
                                    ? '1 firma v našich dátach'
                                    : `${person.companies.length} firiem v našich dátach`}
                            </span>
                        </div>
                    </div>
                </div>
            </header>

            <PersonRecordsNote members={person.members} />

            <section className="overflow-hidden rounded-xl border border-gray-200 bg-white shadow-lg dark:border-slate-700 dark:bg-slate-900 dark:shadow-none">
                <div className="border-b border-gray-200 bg-gray-50/50 px-6 py-4 dark:border-slate-700 dark:bg-slate-900/50">
                    <h2 className="flex items-center gap-3 text-lg font-bold text-gray-900 dark:text-white">
                        <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-brand/10">
                            <i className="fas fa-building text-brand"></i>
                        </span>
                        Firmy, v ktorých je osoba zapísaná
                    </h2>
                </div>

                <div className="space-y-3 p-6">
                    <PersonCoverageNote coverage={person.coverage} />

                    {person.companies.length > 0 ? (
                        <ul className="divide-y divide-gray-100 rounded-lg border border-gray-200 dark:divide-slate-800 dark:border-slate-700">
                            {person.companies.map((relation, index) => (
                                <PersonRelationRow
                                    key={`${relation.ico}-${relation.role}-${index}`}
                                    relation={relation}
                                />
                            ))}
                        </ul>
                    ) : (
                        <p className="rounded-lg border border-gray-200 bg-gray-50 p-4 text-sm text-gray-600 dark:border-slate-700 dark:bg-slate-800/50 dark:text-gray-300">
                            K tejto osobe nemáme uloženú ani jednu firmu. Nie je to tvrdenie, že
                            nikde nepôsobí — firmy, ktorých osoby sme ešte nečítali, v našich
                            dátach nie sú.
                        </p>
                    )}

                    {/* The three answers the state column gives, spelled out. A
                        reader who meets „nevieme" once should not have to infer
                        what it means from the row it sits in.

                        Both halves come from `roleState`, the one place they are
                        written. This legend used to carry its own third copy of
                        the `unknown` meaning -- „túto firmu sme ešte nečítali"
                        -- and a relation is on this page only because we read
                        that company, so the sentence was false about every row
                        it labelled, including the one printed directly above it.
                        What we have not read is the function's end: ORSR gives
                        current records, and the ended ones arrive with the RPO
                        history. */}
                    <ul className="flex flex-col gap-1.5 pt-1 text-xs text-gray-500 sm:flex-row sm:flex-wrap sm:gap-x-5 sm:gap-y-2 dark:text-gray-400">
                        {ROLE_STATES.map((state) => (
                            <li key={state} className="flex items-center gap-2">
                                <span
                                    className={`h-0.5 w-3.5 shrink-0 ${ROLE_STATE_LINE[state]}`}
                                    aria-hidden="true"
                                ></span>
                                {`${ROLE_STATE_WORD[state]} — ${ROLE_STATE_SENTENCE[state]}`}
                            </li>
                        ))}
                    </ul>
                </div>
            </section>

            <OrsrRegisterGroup name={person.name} />
        </div>
    );
};
