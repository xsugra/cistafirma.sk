import React from 'react';
import type { PersonCoverage } from '../../types';
import { formatNumber } from '../../utils/format';

interface PersonCoverageNoteProps {
    coverage: PersonCoverage | null;
    className?: string;
}

/**
 * How much of the register our person data actually covers.
 *
 * This is not decoration and it is not optional wherever person results are
 * shown. The person graph holds relations for a fraction of the companies in
 * the database, so most name searches return nothing *because we have not read
 * those companies yet* -- and an empty list without this sentence reads as
 * "this person is in no company", which is a claim about the person. The
 * answer to "why is this empty" belongs next to the emptiness.
 *
 * The counts come from the response and are never written into the interface:
 * they move with every ORSR sync, and a hardcoded pair would be wrong the first
 * time it stopped being right. When the response carries no counts, this says
 * so instead of substituting zero, which would be the same false claim with a
 * number in front of it.
 */
export const PersonCoverageNote: React.FC<PersonCoverageNoteProps> = ({ coverage, className = '' }) => (
    <p className={`flex items-start gap-2 text-xs text-gray-500 dark:text-gray-400 ${className}`}>
        <i className="fas fa-circle-info mt-0.5 shrink-0" aria-hidden="true"></i>
        {coverage ? (
            <span>
                Osoby máme pre {formatNumber(coverage.companies_with_persons)} z{' '}
                {formatNumber(coverage.companies_total)} firiem.
            </span>
        ) : (
            <span>
                Koľko firiem máme pokrytých osobami, táto odpoveď neuvádza. Prázdny zoznam
                neznamená, že osoba nie je v žiadnej firme.
            </span>
        )}
    </p>
);
