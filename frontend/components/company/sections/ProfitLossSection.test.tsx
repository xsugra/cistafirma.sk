import {describe, expect, it} from 'vitest';
import {screen} from '@testing-library/react';
import {ProfitLossSection} from './ProfitLossSection';
import {makeCompany, makeFinancials as filed, renderWithProviders} from '../../../test/testUtils';

describe('ProfitLossSection', () => {
    it('computes the year-over-year change only where both years filed the line', () => {
        renderWithProviders(
            <ProfitLossSection
                company={makeCompany({
                    financials: [
                        filed({year: 2022, revenue: 1000, costs: 800, profit: 200}),
                        // Náklady absent this year; tržby and zisk present.
                        filed({year: 2023, revenue: 1500, profit: 300}),
                    ],
                })}
            />,
        );

        // Revenue 1 000 -> 1 500 and profit 200 -> 300 are both computable, so
        // the same +50.0% is reported twice -- once for each line.
        expect(screen.getAllByText('+50.0%')).toHaveLength(2);
        // Costs were not filed for 2023, so there is no change to report.
        expect(screen.getAllByText('—').length).toBeGreaterThan(0);
    });

    it('does not divide by a previous year that filed a zero', () => {
        // A filed 0 in the earlier year makes every percentage infinite, not
        // meaningful. "—" is the honest answer; "0.0%" and "+100%" both lie.
        renderWithProviders(
            <ProfitLossSection
                company={makeCompany({
                    financials: [
                        filed({year: 2022, revenue: 0}),
                        filed({year: 2023, revenue: 500}),
                    ],
                })}
            />,
        );

        expect(screen.queryByText('+100.0%')).not.toBeInTheDocument();
        expect(screen.queryByText('0.0%')).not.toBeInTheDocument();
        expect(screen.getAllByText('—').length).toBeGreaterThan(0);
    });

    it('reports a decline as a decline', () => {
        renderWithProviders(
            <ProfitLossSection
                company={makeCompany({
                    financials: [
                        filed({year: 2022, profit: 400}),
                        filed({year: 2023, profit: 300}),
                    ],
                })}
            />,
        );

        expect(screen.getByText('-25.0%')).toBeInTheDocument();
    });

    it('shows every filed line as a figure, dashes for the rest', () => {
        renderWithProviders(
            <ProfitLossSection
                company={makeCompany({financials: [filed({revenue: 1500, profit: 300})]})}
            />,
        );

        expect(screen.getByText('Tržby')).toBeInTheDocument();
        expect(screen.getByText('Zisk po zdanení')).toBeInTheDocument();
        // Náklady was never filed, so its row is dropped rather than shown as
        // a column of dashes -- and no filed figure is rendered as zero.
        expect(screen.queryByText('Náklady')).not.toBeInTheDocument();
        expect(screen.queryByText('0 €')).not.toBeInTheDocument();
    });

    it('names why the section is empty instead of showing a blank panel', () => {
        renderWithProviders(
            <ProfitLossSection
                company={makeCompany({financials: [], financialsState: 'failed'})}
            />,
        );

        expect(screen.getByText(/pokus zlyhal/)).toBeInTheDocument();
    });
});
