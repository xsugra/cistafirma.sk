import React from 'react';
import { Link } from 'react-router-dom';
import type { PersonRelation } from '../../types';
import { companyPath } from '../../constants';
// From `company/helpers` and not `utils/format`, which holds only numbers.
// `utils/pdfExport.ts` reaches for it the same way. It is a date formatter, and
// the one that already knows why a date-only `2010-01-01` must not go through
// `new Date()` -- that path moves the day for every reader west of Greenwich.
import { formatDate } from '../company/helpers';
import { RoleStateBadge } from './RoleStateBadge';
import { ROLE_STATE_SENTENCE, roleStateOf } from './roleState';

interface PersonRelationRowProps {
    relation: PersonRelation;
}

/**
 * One company, as a person's relation to it.
 *
 * The dates are rendered only where the register gave them; the state is always
 * rendered, including when the answer is "we do not know", and the `unknown`
 * sentence is spelled out in the row rather than left in a `title` attribute --
 * a reader on a touch screen never sees a tooltip, and this is the one state
 * that must not be mistaken for a no.
 *
 * A row can also stand for more than one register filing, because the register
 * records filings and not functions: it closes an office and reopens it the next
 * day, and the backend folds such a chain into the single tenure it describes
 * (`intervals`). That fold is disclosed here rather than left silent -- a row
 * that replaced twelve filings with one line reads exactly like a row that
 * always was one line, and those are different claims about how the register
 * recorded this person.
 */
export const PersonRelationRow: React.FC<PersonRelationRowProps> = ({ relation }) => {
    const state = roleStateOf(relation.is_active);

    return (
        <li className="flex flex-col gap-2 px-4 py-3 sm:flex-row sm:items-start sm:justify-between sm:gap-4">
            <div className="min-w-0">
                <Link
                    to={companyPath(relation.ico)}
                    className="font-medium text-gray-900 transition-colors hover:text-blue-600 dark:text-white dark:hover:text-blue-400"
                >
                    {relation.name}
                </Link>

                <div className="mt-0.5 flex flex-wrap items-center gap-x-3 gap-y-0.5 text-xs text-gray-500 dark:text-gray-400">
                    {relation.ico && <span className="font-mono">IČO: {relation.ico}</span>}
                    {relation.role_display && (
                        <span className="uppercase tracking-wide">{relation.role_display}</span>
                    )}
                </div>

                {(relation.vznik_funkcie || relation.zanik_funkcie) && (
                    <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">
                        {relation.vznik_funkcie && (
                            <span>
                                <i className="fas fa-calendar-plus mr-1"></i>
                                Vznik funkcie: {formatDate(relation.vznik_funkcie)}
                            </span>
                        )}
                        {relation.vznik_funkcie && relation.zanik_funkcie && (
                            <span className="mx-2 text-gray-300 dark:text-slate-600">•</span>
                        )}
                        {relation.zanik_funkcie && (
                            <span>
                                <i className="fas fa-calendar-minus mr-1"></i>
                                Zánik funkcie: {formatDate(relation.zanik_funkcie)}
                            </span>
                        )}
                    </p>
                )}

                {relation.intervals > 1 && (
                    <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">
                        <i className="fas fa-layer-group mr-1"></i>
                        Spojené z {relation.intervals} po sebe idúcich zápisov v registri
                    </p>
                )}

                {state === 'unknown' && (
                    <p className="mt-1 text-xs text-amber-700 dark:text-amber-400">
                        {ROLE_STATE_SENTENCE.unknown}
                    </p>
                )}
            </div>

            <RoleStateBadge isActive={relation.is_active} />
        </li>
    );
};
