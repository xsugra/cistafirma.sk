import {describe, expect, it} from 'vitest';
import {screen} from '@testing-library/react';
import {FinancialIndicators} from './FinancialIndicators';
import {renderWithProviders} from '../../test/testUtils';
import type {Financials, RatioSet, YearAnalysis} from '../../types';

// The formatter joins the amount to the currency with a non-breaking
// space. Testing-library normalises the *rendered* text but compares the
// matcher verbatim, so the expectation has to spell it with an ordinary one.
const NBSP = ' ';

/** Every line absent unless the case names it — the shape a statement that
 *  carried a balance sheet and no income statement produces. */
const filed = (overrides: Partial<Financials>): Financials => ({
    year: 2023,
    revenue: null,
    profit: null,
    profitAfterTax: null,
    totalRevenue: null,
    costs: null,
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

const ratios: RatioSet = {
    roa: 5.2,
    roe: 8.1,
    ros: 4.4,
    currentRatio: 1.4,
    quickRatio: 1.1,
    cashRatio: 0.6,
    assetTurnover: 0.9,
    receivablesCollection: 42,
    debtToEquity: 0.8,
    selfFinancingRatio: 55,
};

const analysis: YearAnalysis = {
    year: 2023,
    ratios,
    interpretation: {},
    zScore: null,
    zScoreLabel: null,
    zScoreZone: null,
};

describe('FinancialIndicators', () => {
    it('keeps a filed zero and an absent line apart', () => {
        // A statement can genuinely file zeros — and a balance sheet of 0 is
        // still a balance sheet, which is why the block below is shown at all.
        renderWithProviders(
            <FinancialIndicators
                data={[
                    filed({
                        revenue: 0, totalRevenue: 0, profit: 0, profitAfterTax: 0,
                        assetsTotal: 0, equity: 0,
                        liabilitiesTotal: 0, debtRatio: 0, grossMargin: 0,
                    }),
                ]}
            />
        );

        // Six cards, each printing the figure the statement gave: four in euro,
        // two as percentages.
        expect(screen.getAllByText(`0${NBSP}€`).length).toBe(4);
        expect(screen.getAllByText('0.00%').length).toBe(2);
        expect(screen.queryByText('—')).not.toBeInTheDocument();
    });

    it('says a line was not filed instead of claiming it was zero', () => {
        renderWithProviders(<FinancialIndicators data={[filed({assetsTotal: 328, equity: 328})]} />);

        // Revenue, both profit rows, debt ratio and gross margin were all absent.
        expect(screen.getAllByText('—').length).toBeGreaterThanOrEqual(4);
        expect(screen.queryByText(`0${NBSP}€`)).toBeNull();
    });

    it('reads the after-tax result for the tile that names it', () => {
        // The tile said "Zisk po zdanení" while reading `profit`, which is the
        // pre-tax operating result -- so for 86 % of the rows where a non-zero
        // tax makes the two distinguishable the headline figure was a different
        // quantity from the one named. The two rows must not be interchangeable.
        renderWithProviders(
            <FinancialIndicators data={[filed({profit: 300, profitAfterTax: 240})]} />
        );

        expect(screen.getByText(`240${NBSP}€`)).toBeInTheDocument();
        expect(screen.queryByText(`300${NBSP}€`)).toBeNull();
    });

    it('shows a dash for a year that has no after-tax figure yet', () => {
        // Not back-filled on purpose: a row written before the split carries no
        // after-tax figure, and printing `profit` here would repeat the
        // mislabelling this tile was just corrected for.
        renderWithProviders(<FinancialIndicators data={[filed({profit: 300})]} />);

        expect(screen.queryByText(`300${NBSP}€`)).toBeNull();
        expect(screen.getAllByText('—').length).toBeGreaterThanOrEqual(2);
    });

    it('shows the balance-sheet block for a statement that carried one', () => {
        // `assetsTotal > 0` was the old gate, and it also hid the block for a
        // dormant association whose filed balance sheet adds up to pocket
        // change. The block follows what the statement carried, not its size.
        renderWithProviders(<FinancialIndicators data={[filed({assetsTotal: 25.88, equity: 25.88})]} />);

        expect(screen.getByText('Aktíva')).toBeInTheDocument();
        expect(screen.getByText('Vlastný kapitál')).toBeInTheDocument();
    });

    it('hides the balance-sheet block when the statement carried none', () => {
        renderWithProviders(
            <FinancialIndicators
                data={[filed({revenue: 1200, totalRevenue: 1200, profit: 90, profitAfterTax: 72})]}
            />
        );

        expect(screen.queryByText('Aktíva')).toBeNull();
        expect(screen.queryByText('Vlastný kapitál')).toBeNull();
    });

    it('draws no trend arrow for ratios that only exist for one year', () => {
        // `prevValue: 0` used to stand in for "no previous figure", which
        // `TrendArrow` read as a real zero and answered with "nový" — so every
        // company with two filed years wore it beside ROA, ROE and L3.
        renderWithProviders(
            <FinancialIndicators
                data={[
                    filed({year: 2022, revenue: 1000, totalRevenue: 1000, profit: 100, profitAfterTax: 80}),
                    filed({year: 2023, revenue: 1500, totalRevenue: 1500, profit: 150, profitAfterTax: 120}),
                ]}
                analysis={analysis}
            />
        );

        expect(screen.getByText('ROA')).toBeInTheDocument();
        expect(screen.queryByText('nový')).toBeNull();
        // The year-over-year arrows that *can* be computed are still drawn.
        expect(screen.getAllByText('50.0%').length).toBeGreaterThan(0);
    });

    it('draws no arrow against a previous year that filed no figure', () => {
        renderWithProviders(
            <FinancialIndicators
                data={[
                    filed({year: 2022}),
                    filed({year: 2023, revenue: 1500, totalRevenue: 1500, profit: 150, profitAfterTax: 120}),
                ]}
            />
        );

        // `((1500 - null) / null)` would have printed a −100 % that no
        // statement supports.
        expect(screen.queryByText(/-100\.0%/)).toBeNull();
        expect(screen.queryByText('nový')).toBeNull();
    });
});
