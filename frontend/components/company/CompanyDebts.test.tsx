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
    taxCheckedOn: string | null,
    socialListedWithoutAmount: boolean | null = false
) =>
    renderWithProviders(
        <CompanyDebts
            debts={debts}
            insuranceCheckedOn={insuranceCheckedOn}
            taxCheckedOn={taxCheckedOn}
            socialListedWithoutAmount={socialListedWithoutAmount}
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

/**
 * The other half of the SP register.
 *
 * Sociálna poisťovňa carries two populations under one heading: employers owing
 * at least 5,00 €, and employers that did not file the výkaz poistného a
 * príspevkov (plus foreign SZČO that did not report income and expenses),
 * listed with a bare hyphen where the sum would be. Measured 2026-09-15 on the
 * live register: 43 of 50 rows carried a sum and a hyphen in the periods column,
 * 5 carried a hyphen in the sum column and the missing periods beside it. So the
 * populations are complementary, and the second one has no money in it at all.
 *
 * The defect these tests pin: a `LISTED_NO_AMOUNT` company has `debt_soc_poist`
 * NULL, so it built no debt row, so it was rendered as a company with no
 * social-insurance debt -- with the green tick when both check dates happened to
 * be set. The money really is zero and the listing really is not.
 */
describe('CompanyDebts — SP lists the company without a sum', () => {
    const LISTED = /uvádza túto spoločnosť vo svojom zozname dlžníkov bez\s+zverejnenej sumy/;

    it('refuses the green tick even when both sources were read', () => {
        // The exact case that was wrong: both dates present, no debt rows, and
        // the section printed "Neboli nájdené žiadne aktuálne dlhy." over a
        // company the register does list.
        render([], '2026-09-10T12:00:00Z', '2026-09-12T12:00:00Z', true);

        expect(screen.queryByText(TICK)).not.toBeInTheDocument();
        expect(screen.getByText(LISTED)).toBeInTheDocument();
    });

    it('separates the listing from the money instead of merging them', () => {
        // Two different facts, and the one the reader must not misread is the
        // second: no sum is published, so the amount is not "unknown" -- it is
        // absent, and the reason is a filing breach rather than a debt.
        render([], '2026-09-10T12:00:00Z', '2026-09-12T12:00:00Z', true);

        expect(screen.getByText(/Nejde o peňažný nedoplatok/)).toBeInTheDocument();
        expect(screen.getByText(/nesplnená vykazovacia povinnosť/)).toBeInTheDocument();
        expect(
            screen.getByText(/Peňažné nedoplatky voči VšZP, Sociálnej poisťovni ani Finančnej\s+správe sme nezistili/)
        ).toBeInTheDocument();
    });

    it('does not claim the money question was answered when it was not', () => {
        // Only the insurers were read. Saying "no monetary arrears" here would be
        // the same unearned all-clear the empty state exists to refuse, just in a
        // different sentence.
        render([], '2026-09-10T12:00:00Z', null, true);

        expect(screen.getByText(LISTED)).toBeInTheDocument();
        expect(screen.getByText(/Či dlží aj/)).toBeInTheDocument();
        expect(
            screen.queryByText(/Peňažné nedoplatky voči VšZP, Sociálnej poisťovni ani Finančnej\s+správe sme nezistili/)
        ).not.toBeInTheDocument();
    });

    it('keeps the listing visible when the company owes someone else', () => {
        // A company can be listed for a filing breach *and* owe VšZP. The total
        // is money and the listing is not, so they stay separate -- but the
        // listing must not vanish from the screen where a reader looks hardest
        // at debts.
        render([debt], '2026-09-10T12:00:00Z', '2026-09-12T12:00:00Z', true);

        expect(screen.getByText('Celkový dlh')).toBeInTheDocument();
        expect(screen.getByText(/nie je zahrnutá v celkovej sume/)).toBeInTheDocument();
    });

    it('says nothing extra when the register did list a sum', () => {
        // The 43 of 50. `false` is the register answering "not this population",
        // and the section is then the ordinary earned green tick.
        render([], '2026-09-10T12:00:00Z', '2026-09-12T12:00:00Z', false);

        expect(screen.getByText(TICK)).toBeInTheDocument();
        expect(screen.queryByText(LISTED)).not.toBeInTheDocument();
    });

    it('reads an unread register as the unread panel, not as a listing', () => {
        // `null` is "we have not read it", which is the state the insurance pass
        // leaves 92 % of the register in. It is not a listing, and it must not
        // borrow the listing's sentence.
        render([], null, null, null);

        expect(screen.getByText(NOT_CHECKED)).toBeInTheDocument();
        expect(screen.queryByText(LISTED)).not.toBeInTheDocument();
    });
});
