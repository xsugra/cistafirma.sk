import {describe, expect, it} from 'vitest';
import {screen, within} from '@testing-library/react';
import {BenchmarkComparison} from './BenchmarkComparison';
import {makeFinancials, renderWithProviders} from '../../test/testUtils';
import type {CompanyBenchmark, RatioSet, YearAnalysis} from '../../types';

const NO_RATIOS: RatioSet = {
    roa: null,
    roe: null,
    ros: null,
    currentRatio: null,
    quickRatio: null,
    cashRatio: null,
    assetTurnover: null,
    receivablesCollection: null,
    debtToEquity: null,
    selfFinancingRatio: null,
};

/**
 * A company whose balance sheet and margins are filed, and whose ratio set
 * carries two figures that are *not* the ones the shared labels name.
 *
 * `debtToEquity` is a multiple (1.2) and `selfFinancingRatio` is equity over
 * assets (77.7 %) -- neither is the debt ratio or the gross margin, and both
 * were being shown under those labels before this.
 */
const analysis: YearAnalysis = {
    year: 2023,
    ratios: {...NO_RATIOS, debtToEquity: 1.2, selfFinancingRatio: 77.7},
    interpretation: {},
    zScore: null,
    zScoreLabel: null,
    zScoreZone: null,
};

const benchmark: CompanyBenchmark = {
    section: 'G',
    sectionName: 'Veľkoobchod a maloobchod',
    divisionName: null,
    naceCode: '46',
    year: 2023,
    companyCount: 1200,
    medians: {
        revenue: null,
        profit: null,
        assetsTotal: 1_500_000,
        equity: 900_000,
        roa: null,
        roe: null,
        ros: null,
        debtRatio: 55,
        grossMargin: 8,
        currentRatio: null,
        // Deliberately *not* the company's 77.7: a row where both cells hold
        // the same figure cannot tell "reads the right side" from "reads
        // either side", which is the whole question these tests ask.
        selfFinancingRatio: 61.4,
    },
};

const financials = makeFinancials({
    year: 2023,
    assetsTotal: 2_000_000,
    equity: 800_000,
    grossMargin: 12.5,
    debtRatio: 60,
});

/** The table row whose label is `label`, so a figure can be read in its own row. */
const row = (label: string): HTMLElement => {
    const cell = screen.getByText(label);
    const tr = cell.closest('tr');
    if (!tr) throw new Error(`no row for ${label}`);
    return tr;
};

describe('BenchmarkComparison', () => {
    it('shows the filed balance-sheet totals instead of an empty cell', () => {
        // These two rows were hardcoded to `null` with a comment saying the
        // ratios would be used instead -- and no ratio is an asset total, so
        // both cells read "—" on every company that ever had a balance sheet.
        renderWithProviders(
            <BenchmarkComparison benchmark={benchmark} analysis={analysis} financials={financials}/>,
        );

        expect(within(row('Aktíva')).getByText('2 000 000 €', {exact: false})).toBeInTheDocument();
        expect(within(row('Vlastný kapitál')).getByText('800 000 €', {exact: false})).toBeInTheDocument();
    });

    it('shows the gross margin under the gross-margin label', () => {
        renderWithProviders(
            <BenchmarkComparison benchmark={benchmark} analysis={analysis} financials={financials}/>,
        );

        // 12.5 % is the filed gross margin. 77.7 % is the self-financing ratio,
        // which used to be shown here; it belongs to its own row below, and
        // must not appear in this one.
        expect(within(row('Hrubá marža')).getByText('12.5%')).toBeInTheDocument();
        expect(within(row('Hrubá marža')).queryByText('77.7%')).not.toBeInTheDocument();
        // ...and the row it does belong to is untouched: company 77.7 against
        // the sector's 61.4, both still fed by the ratio set.
        expect(within(row('Samofinancovanie')).getByText('77.7%')).toBeInTheDocument();
        expect(within(row('Samofinancovanie')).getByText('61.4%')).toBeInTheDocument();
    });

    it('compares the debt ratio with the sector debt ratio, not a multiple with a percentage', () => {
        // The sector median is a percentage (55 %). The company's D/E multiple
        // is 1.2, and showing "1.2 %" beside "55.0 %" made almost every company
        // look under-indebted.
        renderWithProviders(
            <BenchmarkComparison benchmark={benchmark} analysis={analysis} financials={financials}/>,
        );

        const debtRow = row('Zadĺženosť');
        expect(within(debtRow).getByText('60.0%')).toBeInTheDocument();
        expect(within(debtRow).queryByText('1.2%')).not.toBeInTheDocument();
    });

    it('shows a dash rather than a substitute when the statement is missing', () => {
        // A company can have an analysis without the row behind it. Every one
        // of the four figures then has to read "not known", which is a dash --
        // never the nearest ratio, and never zero.
        renderWithProviders(
            <BenchmarkComparison benchmark={benchmark} analysis={analysis} financials={null}/>,
        );

        for (const label of ['Aktíva', 'Vlastný kapitál', 'Hrubá marža', 'Zadĺženosť']) {
            expect(within(row(label)).getAllByText('—').length).toBeGreaterThan(0);
        }
        // The ratios that do not need the statement still render.
        expect(within(row('Samofinancovanie')).getByText('77.7%')).toBeInTheDocument();
        expect(screen.queryByText('0 €')).not.toBeInTheDocument();
    });
});
