import {describe, expect, it} from 'vitest';
import {screen} from '@testing-library/react';
import {CompanyDebts} from './CompanyDebts';
import {renderWithProviders} from '../../test/testUtils';
import type {Debt} from '../../types';

/**
 * The green tick, and whether it was earned.
 *
 * A debt row is only ever built for an amount above zero, so an empty `debts`
 * array meant two opposite things: *we looked and there is nothing* and *we
 * have never looked*. Both used to render as "Neboli nájdené žiadne aktuálne
 * dlhy." Measured 2026-09-12: the insurance pass reached 35 471 of 445 626 rows
 * (8,0 %) and Finančná správa 250 349 (56,2 %); 402 781 of the 411 186 companies
 * shown that tick rested on at least one source nobody had read, and 8 405
 * earned it. In a risk tool that is the one direction the rounding must not go.
 */

const TICK = /Neboli nájdené žiadne aktuálne dlhy/;
const NOT_CHECKED = /ešte nekontrolovali/;

const debt: Debt = {
    id: 'vszp',
    source: 'VšZP',
    amountEur: 1250.75,
    dateOfRecord: '2024-07-15',
};

const render = (
    debts: Debt[],
    insuranceCheckedOn: string | null,
    taxCheckedOn: string | null
) =>
    renderWithProviders(
        <CompanyDebts
            debts={debts}
            insuranceCheckedOn={insuranceCheckedOn}
            taxCheckedOn={taxCheckedOn}
        />
    );

describe('CompanyDebts — the empty state', () => {
    it('gives the all-clear only when both sources were read, and says when', () => {
        // The 8 405 companies that earn it. A finding, not an absence -- and the
        // dates are what let a reader judge how current the finding is.
        render([], '2026-09-10T12:00:00Z', '2026-09-12T12:00:00Z');

        expect(screen.getByText(TICK)).toBeInTheDocument();
        expect(screen.getByText(/Overené u Sociálna poisťovňa a VšZP/)).toBeInTheDocument();
        expect(screen.getByText(/10\.09\.2026/)).toBeInTheDocument();
        expect(screen.queryByText(NOT_CHECKED)).not.toBeInTheDocument();
    });

    it('refuses the all-clear for a company nobody has ever checked', () => {
        // The overwhelming majority. 410 155 rows have no insurance check at all,
        // and printing a green tick over that is a claim no source made.
        render([], null, null);

        expect(screen.queryByText(TICK)).not.toBeInTheDocument();
        expect(screen.getByText(NOT_CHECKED)).toBeInTheDocument();
        expect(screen.getByText(/nič neevidujeme, tu neznamená, že firma nič nedlží/))
            .toBeInTheDocument();
    });

    it('names the source it has not read instead of the pair', () => {
        // Partial coverage is its own state: the tax office answered and the
        // insurers did not, so the tick is still unearned but the sentence
        // should say which half is missing.
        render([], null, '2026-09-12T12:00:00Z');

        expect(screen.queryByText(TICK)).not.toBeInTheDocument();
        expect(screen.getByText(/Sociálna poisťovňa a VšZP/)).toBeInTheDocument();
        expect(screen.getByText(/preverené teda máme len Finančná správa/)).toBeInTheDocument();
    });

    it('does not call a source read on an empty date', () => {
        // `''` is not a date and must not read as one. The backend sends null for
        // "never"; an empty string reaching here would be a bug upstream, and the
        // safe reading of it is the unread one -- the tick stays unearned.
        render([], '', '');

        expect(screen.queryByText(TICK)).not.toBeInTheDocument();
        expect(screen.getByText(NOT_CHECKED)).toBeInTheDocument();
    });
});

describe('CompanyDebts — the debts themselves', () => {
    it('lists a debt with its own date and a total, regardless of coverage', () => {
        // Coverage decides what an empty list means; it never suppresses a debt
        // we did find.
        render([debt], null, null);

        expect(screen.getByText('VšZP')).toBeInTheDocument();
        expect(screen.getByText(/15\.07\.2024/)).toBeInTheDocument();
        expect(screen.getByText('Celkový dlh')).toBeInTheDocument();
        expect(screen.queryByText(NOT_CHECKED)).not.toBeInTheDocument();
    });
});
