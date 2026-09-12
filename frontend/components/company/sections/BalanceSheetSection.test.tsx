import {describe, expect, it} from 'vitest';
import {screen} from '@testing-library/react';
import {BalanceSheetSection} from './BalanceSheetSection';
import {makeCompany, renderWithProviders} from '../../../test/testUtils';
import type {Financials} from '../../../types';

/** Every line absent unless the case names it. */
const filed = (overrides: Partial<Financials>): Financials => ({
    year: 2023,
    revenue: null,
    profit: null,
    totalRevenue: null,
    costs: null,
    addedValue: null,
    incomeTax: null,
    incomeTaxPaid: null,
    assetsTotal: null,
    assetsIntangible: null,
    assetsTangible: null,
    assetsFinancial: null,
    assetsInventory: null,
    assetsReceivablesLong: null,
    assetsReceivablesShort: null,
    assetsFinancialAccounts: null,
    assetsAccruals: null,
    equity: null,
    equityBasic: null,
    equityCapitalFunds: null,
    equityProfitFunds: null,
    equityRetained: null,
    liabilitiesTotal: null,
    liabilitiesReserves: null,
    liabilitiesLong: null,
    liabilitiesShort: null,
    liabilitiesAccruals: null,
    debtRatio: null,
    grossMargin: null,
    ...overrides,
});

/** A balanced year: assets 1 000 = equity 400 + liabilities 500 + accruals 100. */
const balanced = (year = 2023) =>
    filed({
        year,
        assetsTotal: 1000,
        equity: 400,
        liabilitiesTotal: 500,
        liabilitiesAccruals: 100,
    });

describe('BalanceSheetSection', () => {
    it('says the sheet balances when the four figures add up', () => {
        renderWithProviders(
            <BalanceSheetSection company={makeCompany({financials: [balanced()]})}/>,
        );

        expect(screen.getByText('sedí')).toBeInTheDocument();
        expect(screen.queryByText('nesedí')).not.toBeInTheDocument();
    });

    it('says the sheet does not balance, and by how much', () => {
        // Assets 1 000 against pasíva 950: this is the row a reader has to be
        // able to spot, because it is the one thing on the page that can be
        // checked without trusting the parser. The difference is 50, which no
        // filed line in this case happens to share -- so the figure the test
        // finds can only be the difference.
        renderWithProviders(
            <BalanceSheetSection
                company={makeCompany({
                    financials: [filed({
                        assetsTotal: 1000,
                        equity: 400,
                        liabilitiesTotal: 450,
                        liabilitiesAccruals: 100,
                    })],
                })}
            />,
        );

        expect(screen.getByText('nesedí')).toBeInTheDocument();
        expect(screen.getByText(/^50/)).toBeInTheDocument();
    });

    it('refuses to call a statement wrong when it cannot be checked', () => {
        // Accruals never filed. Summing the three parts that are present would
        // produce a total that looks authoritative and is not one, and the
        // control row would then report a balance error that does not exist.
        renderWithProviders(
            <BalanceSheetSection
                company={makeCompany({
                    financials: [filed({assetsTotal: 1000, equity: 400, liabilitiesTotal: 500})],
                })}
            />,
        );

        // The card says it cannot be checked rather than drawing a table whose
        // every row repeats that. And it makes no claim in either direction.
        expect(screen.getByText(/nemožno overiť/)).toBeInTheDocument();
        expect(screen.queryByText('sedí')).not.toBeInTheDocument();
        expect(screen.queryByText('nesedí')).not.toBeInTheDocument();
        // Pasíva spolu is deliberately absent rather than showing 900 €.
        expect(screen.queryByText('900 €')).not.toBeInTheDocument();
    });

    it('marks the years it can check and the years it cannot, side by side', () => {
        // One year complete, one missing its accruals. The table is drawn, and
        // the two verdicts have to be told apart in it -- this is the case that
        // would otherwise let a missing line read as a balance error.
        renderWithProviders(
            <BalanceSheetSection
                company={makeCompany({
                    financials: [
                        balanced(2022),
                        filed({year: 2023, assetsTotal: 1000, equity: 400, liabilitiesTotal: 500}),
                    ],
                })}
            />,
        );

        expect(screen.getByText('sedí')).toBeInTheDocument();
        expect(screen.getByText('nedá sa overiť')).toBeInTheDocument();
        expect(screen.queryByText('nesedí')).not.toBeInTheDocument();
    });

    it('shows a filed zero as a figure, not as a missing line', () => {
        renderWithProviders(
            <BalanceSheetSection
                company={makeCompany({
                    financials: [filed({
                        assetsTotal: 0,
                        equity: 0,
                        liabilitiesTotal: 0,
                        liabilitiesAccruals: 0,
                    })],
                })}
            />,
        );

        // Zero assets is a filed balance sheet like any other; the control row
        // has to judge it, not skip it as unreadable.
        expect(screen.queryByText('nedá sa overiť')).not.toBeInTheDocument();
        expect(screen.getByText('sedí')).toBeInTheDocument();
    });

    it('draws a line the year did not carry as a dash, and drops a line no year carried', () => {
        // Two different absences, and they must not look alike.
        //
        // Hmotný majetok is filed for 2022 and absent for 2023, so the row
        // exists and one of its two cells is a dash: the statement for that
        // year did not carry the line. A line that no shown year carried --
        // Zásoby here -- is dropped rather than drawn as a row of dashes,
        // because a row of nothing says less than no row at all. Neither may
        // ever render as 0 €.
        renderWithProviders(
            <BalanceSheetSection
                company={makeCompany({
                    financials: [
                        filed({year: 2022, assetsTotal: 1000, assetsTangible: 1000}),
                        filed({year: 2023, assetsTotal: 1200}),
                    ],
                })}
            />,
        );

        expect(screen.getByText('Hmotný majetok')).toBeInTheDocument();
        expect(screen.queryByText('Zásoby')).not.toBeInTheDocument();
        // Hmotný majetok equals the 2022 total, so that figure appears twice:
        // once as the line, once as Aktíva spolu.
        expect(screen.getAllByText('1 000 €', {exact: false})).toHaveLength(2);
        expect(screen.getByText('1 200 €', {exact: false})).toBeInTheDocument();
        // Exactly one dash: Hmotný majetok for the year that did not file it.
        expect(screen.getAllByText('—')).toHaveLength(1);
        expect(screen.queryByText('0 €')).not.toBeInTheDocument();
    });

    it('names why the section is empty instead of showing a blank panel', () => {
        renderWithProviders(
            <BalanceSheetSection
                company={makeCompany({financials: [], financialsState: 'not_fetched'})}
            />,
        );

        expect(screen.getByText(/ešte nečítali/)).toBeInTheDocument();
    });

    it('sends an IFRS company to its PDF rather than blaming the import', () => {
        renderWithProviders(
            <BalanceSheetSection
                company={makeCompany({
                    financials: [],
                    financialsState: 'nothing_recorded',
                    usesIfrs: true,
                    ruzPortalUrl: 'https://www.registeruz.sk/cruz-public/domain/accountingentity/show/1',
                })}
            />,
        );

        expect(screen.getByText(/medzinárodných štandardov/)).toBeInTheDocument();
        expect(screen.getByRole('link', {name: /RUZ portáli/})).toBeInTheDocument();
    });
});
