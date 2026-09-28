import React, {useCallback, useEffect, useState} from 'react';
import {api} from '../../api';
import type {CompanyPersonsResponse} from '../../types';
import {GraphPeriodChips} from '../graph/GraphPeriodChips';
import {periodLabel, undatedNote} from '../graph/period';
import {PersonRecordsNote} from '../person/PersonRecordsNote';
import {PersonRelationRow} from '../person/PersonRelationRow';

interface CompanyPeopleHistoryProps {
    ico: string;
}

/** 1 funkcia, 2-4 funkcie, 5+ funkcií -- Slovak counts in three. */
const officeCount = (n: number): string =>
    `${n} ${n === 1 ? 'funkcia' : n <= 4 ? 'funkcie' : 'funkcií'}`;

/**
 * Everyone who ever acted for this company, not only those there today.
 *
 * The Osoby cards read the register's extract, which is the bodies as they
 * stand now. The ended relations are stored in the same table -- the extractor
 * keeps them and marks them ended -- and no screen read them, so a konateľ who
 * left in 2010 was invisible, and a company whose only officer had left was
 * shown as having none at all.
 *
 * The same rows and the same backend helpers as the company graph, so this list
 * and the picture cannot name different people. `?as_of=` is the graph's period
 * question asked of a list, and the year chips are the graph's own list of the
 * years this company's record actually changes.
 */
export const CompanyPeopleHistory: React.FC<CompanyPeopleHistoryProps> = ({ ico }) => {
    /**
     * The answer, held with the IČO it is an answer *about*.
     *
     * The page under this section re-renders with a new `company` when the
     * reader moves between companies, and the same component instance is reused;
     * a bare `data` would keep the previous company's people on screen under the
     * new company's heading until the new answer landed. The list of who acted
     * for a company is not a thing to show the wrong company's version of.
     */
    const [answer, setAnswer] = useState<{ico: string; data: CompanyPersonsResponse} | null>(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const data = answer && answer.ico === ico ? answer.data : null;

    /**
     * The chosen day, held with the IČO it was chosen for, and *derived* rather
     * than reset in an effect -- exactly as the graph's control does it. A year
     * belongs to one company, and an effect that cleared it would run after the
     * fetch effect had already gone out with the previous company's year: two
     * requests for one move, and a race between their answers. Deriving it means
     * the year is corrected before anything reads it.
     */
    const [period, setPeriod] = useState<{ico: string; asOf: string | null}>({
        ico,
        asOf: null,
    });
    const asOf = period.ico === ico ? period.asOf : null;
    const selectPeriod = useCallback(
        (next: string | null) => setPeriod({ico, asOf: next}),
        [ico],
    );

    useEffect(() => {
        let current = true;
        setLoading(true);
        setError(null);
        api
            .getCompanyPersons(ico, asOf)
            .then((answer) => {
                // A slower answer to an earlier question must not land on top of
                // a newer one: the chips are clickable while a request is in
                // flight, and the last click is the one the reader meant.
                if (current) setAnswer({ico, data: answer});
            })
            .catch((err) => {
                if (current) {
                    setError(
                        err instanceof Error ? err.message : 'Nepodarilo sa načítať históriu osôb',
                    );
                }
            })
            .finally(() => {
                if (current) setLoading(false);
            });
        return () => {
            current = false;
        };
    }, [ico, asOf]);

    const groups = data?.groups ?? [];
    // The answer's own `as_of`, not the year that was clicked: between the click
    // and the answer those are two different days, and a heading reading the
    // requested one would name a period over a list fetched for another. The
    // backend refuses a malformed date for the same reason.
    const drawnAsOf = data?.as_of ?? null;
    const note = undatedNote(data?.undated_excluded ?? 0);

    return (
        <div className="space-y-4">
            <div className="flex flex-wrap items-center justify-between gap-3">
                <p className="text-sm text-gray-500 dark:text-gray-400">
                    <i className="fas fa-clock-rotate-left mr-2" aria-hidden="true"></i>
                    Všetky osoby, ktoré vo firme pôsobili — aj tie, ktoré už skončili.
                </p>
                {(data?.periods.length ?? 0) > 0 && (
                    <GraphPeriodChips
                        periods={data?.periods ?? []}
                        value={asOf}
                        onChange={selectPeriod}
                        busy={loading}
                    />
                )}
            </div>

            {drawnAsOf && (
                <div className="rounded-lg border border-blue-200 bg-blue-50 px-3 py-2 text-sm text-blue-800 dark:border-blue-800 dark:bg-blue-900/20 dark:text-blue-300">
                    <p>
                        <i className="fas fa-calendar-day mr-2" aria-hidden="true"></i>
                        {periodLabel(drawnAsOf)}
                    </p>
                    {note && <p className="mt-1 text-xs">{note}</p>}
                </div>
            )}

            {error && (
                <p className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700 dark:border-red-800 dark:bg-red-900/20 dark:text-red-400">
                    {error}
                </p>
            )}

            {loading && !data && (
                <p className="py-6 text-center text-gray-500 dark:text-gray-400">
                    Načítavam históriu osôb...
                </p>
            )}

            {data && !error && groups.length === 0 && (
                <p className="py-6 text-center text-gray-500 dark:text-gray-400">
                    {drawnAsOf
                        ? 'K tomuto dátumu register neuvádza vo firme žiadnu osobu.'
                        : 'Register pre túto firmu neuvádza žiadne osoby.'}
                </p>
            )}

            {groups.map((group) => (
                <div
                    key={group.id}
                    className="rounded-xl border border-slate-200 bg-white p-4 dark:border-slate-700 dark:bg-slate-900"
                >
                    <div className="flex flex-wrap items-baseline justify-between gap-2">
                        <h4 className="font-medium text-gray-900 dark:text-white">
                            <i className="fas fa-user mr-2 text-gray-400" aria-hidden="true"></i>
                            {group.name}
                        </h4>
                        {group.offices.length > 0 && (
                            <span className="text-xs text-gray-500 dark:text-gray-400">
                                {officeCount(group.offices.length)}
                            </span>
                        )}
                    </div>

                    {group.offices.length > 0 ? (
                        <ul className="mt-3 divide-y divide-slate-100 dark:divide-slate-800">
                            {group.offices.map((office, index) => (
                                <PersonRelationRow
                                    key={`${office.role}-${office.vznik_funkcie}-${index}`}
                                    relation={office}
                                    // Every row here is this company, which the
                                    // reader is already looking at.
                                    showCompany={false}
                                />
                            ))}
                        </ul>
                    ) : (
                        <p className="mt-2 text-sm text-gray-500 dark:text-gray-400">
                            K tomuto dátumu nemala táto osoba vo firme žiadnu funkciu.
                        </p>
                    )}

                    {/*
                      The register rows behind the grouping, where there is more
                      than one. Renders nothing in the ordinary case of a single
                      row. It is the same component the person's own page uses,
                      because it is the same fact -- the register wrote this human
                      down twice -- and the reader who has to check a judgement is
                      the one who cannot be made to learn a second wording for it.
                    */}
                    <PersonRecordsNote members={group.members} className="mt-3" />
                </div>
            ))}
        </div>
    );
};
