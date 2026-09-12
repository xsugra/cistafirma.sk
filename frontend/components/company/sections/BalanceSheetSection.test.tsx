import {describe, expect, it} from 'vitest';
import {screen} from '@testing-library/react';
import {BalanceSheetSection} from './BalanceSheetSection';
import {makeCompany, makeFinancials as filed, renderWithProviders} from '../../../test/testUtils';

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

    it('reads an absent accruals line as a zero, because the filings say it is one', () => {
        // Measured 2026-09-12: of the 2 336 stored rows carrying assets, equity
        // and liabilities and no accruals line, 2 326 satisfy
        // `assets = equity + liabilities` exactly. An accruals line the filer
        // left out is a line with nothing in it -- and counting it as unread
        // made this control refuse to judge 2 336 rows it can judge.
        renderWithProviders(
            <BalanceSheetSection
                company={makeCompany({
                    financials: [filed({assetsTotal: 900, equity: 400, liabilitiesTotal: 500})],
                })}
            />,
        );

        expect(screen.getByText('sedí')).toBeInTheDocument();
        expect(screen.queryByText('nedá sa overiť')).not.toBeInTheDocument();
        // The total is a real figure now, not withheld: 400 + 500 + 0 = 900,
        // which is what the assets side says too -- so 900 appears twice, once
        // per side, and nowhere else. Withheld it appeared once.
        expect(screen.getAllByText(/900/)).toHaveLength(2);
    });

    it('refuses to judge a statement missing a figure the identity needs, and names it', () => {
        // Equity absent. This one genuinely cannot be evaluated -- no
        // measurement says an absent equity line is a zero -- and summing the
        // parts that happen to be present would compare a real figure against a
        // partial one and call the statement wrong.
        renderWithProviders(
            <BalanceSheetSection
                company={makeCompany({
                    financials: [filed({assetsTotal: 1000, liabilitiesTotal: 500})],
                })}
            />,
        );

        expect(screen.getByText(/nemožno overiť/)).toBeInTheDocument();
        expect(screen.queryByText('sedí')).not.toBeInTheDocument();
        expect(screen.queryByText('nesedí')).not.toBeInTheDocument();
        // The complaint was that this sentence named nothing. It names the
        // figure and the year, so a reader knows what to go and look at.
        expect(screen.getByText(/Chýba: vlastné imanie \(2023\)/)).toBeInTheDocument();
    });

    it('lists each absent figure with the years that are missing it', () => {
        renderWithProviders(
            <BalanceSheetSection
                company={makeCompany({
                    financials: [
                        filed({year: 2021, assetsTotal: 1000, liabilitiesTotal: 500}),
                        filed({year: 2022, assetsTotal: 1000, equity: 400}),
                    ],
                })}
            />,
        );

        expect(
            screen.getByText(/Chýba: vlastné imanie \(2021\); záväzky spolu \(2022\)/),
        ).toBeInTheDocument();
    });

    it('marks the years it can check and the years it cannot, side by side', () => {
        // One year complete, one missing a figure the identity needs. The table
        // is drawn, and the two verdicts have to be told apart in it -- this is
        // the case that would otherwise let a missing line read as a balance
        // error.
        renderWithProviders(
            <BalanceSheetSection
                company={makeCompany({
                    financials: [
                        balanced(2022),
                        filed({year: 2023, assetsTotal: 1000, liabilitiesTotal: 500}),
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
