import {beforeEach, describe, expect, it, vi} from 'vitest';
import {screen, waitFor} from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import {CompaniesBuilderPage} from './CompaniesBuilderPage';
import {renderWithProviders} from '../../test/testUtils';
import type {CompanyReport} from '../types';

const mocks = vi.hoisted(() => ({
    adminApi: {
        companyPresets: vi.fn(),
        listCompanyFilters: vi.fn(),
        listCompanies: vi.fn(),
        companyReport: vi.fn(),
    },
}));

// Same module id the page resolves (this spec lives in admin/pages/, like the page).
vi.mock('../api', () => ({adminApi: mocks.adminApi}));

/** The report shape the API sends when a preset over a dataset we lack matches nothing. */
const emptyReport = (overrides: Partial<CompanyReport> = {}): CompanyReport => ({
    count: 0,
    active_count: 0,
    inactive_count: 0,
    debt_free_count: 0,
    has_orsr_count: 0,
    has_financials_count: 0,
    blocked_count: 0,
    avg_lead_score: 0,
    avg_confidence: 0,
    revenue_sum: '0',
    profit_sum: '0',
    tax_debt_sum: '0',
    debt_vszp_sum: '0',
    debt_soc_poist_sum: '0',
    lead_score_sum: '0',
    filters_applied: {},
    presets: [],
    top_companies: [],
    ...overrides,
});

const withDiagnosis = () =>
    emptyReport({
        zero_diagnosis: [
            {condition: 'mesto', value: 'Trnava', count_without: 4},
            {condition: 'has_financials', value: '1', count_without: 0},
        ],
    });

/** Open the builder on the preset behind the reported symptom and ask for the summary. */
const openReport = async () => {
    window.history.replaceState({}, '', '/admin/companies?preset=it_trnava_no_debt');
    renderWithProviders(<CompaniesBuilderPage />, {route: '/admin/companies?preset=it_trnava_no_debt'});

    // The summary is only fetched when asked for; the list loads by itself.
    const button = await screen.findByRole('button', {name: 'Obnoviť súhrn'});
    await userEvent.click(button);
};

describe('CompaniesBuilderPage empty-result diagnosis', () => {
    beforeEach(() => {
        mocks.adminApi.companyPresets.mockResolvedValue([]);
        mocks.adminApi.listCompanyFilters.mockResolvedValue({results: [], count: 0});
        mocks.adminApi.listCompanies.mockResolvedValue({results: [], count: 0});
        mocks.adminApi.companyReport.mockResolvedValue(emptyReport());
    });

    it('names the condition that emptied the result instead of only saying "Žiadne výsledky"', async () => {
        mocks.adminApi.companyReport.mockResolvedValue(withDiagnosis());

        await openReport();

        expect(await screen.findByText('Žiadne výsledky')).toBeInTheDocument();
        await waitFor(() => expect(screen.getAllByRole('listitem')).toHaveLength(2));

        // The API names conditions by key; the operator must see them by label.
        const [first, second] = screen.getAllByRole('listitem');
        expect(first).toHaveTextContent('Mesto');
        expect(first).toHaveTextContent('Trnava');
        expect(first).toHaveTextContent('4');
        expect(first).not.toHaveTextContent('mesto');
        expect(second).toHaveTextContent('Financie');
        // A zero is the answer, not a missing value: nothing survives dropping it.
        expect(second).toHaveTextContent('0');
    });

    it('asks the API for the diagnosis with the same preset the table was built from', async () => {
        await openReport();

        await waitFor(() => expect(mocks.adminApi.companyReport).toHaveBeenCalled());
        expect(mocks.adminApi.companyReport).toHaveBeenCalledWith(
            expect.objectContaining({preset: 'it_trnava_no_debt', mode: 'light'}),
            expect.anything(),
        );
    });

    it('stays quiet when the API sends no diagnosis', async () => {
        await openReport();

        expect(await screen.findByText('Žiadne výsledky')).toBeInTheDocument();
        // The report has resolved by now, so an absent panel is a real absence.
        await waitFor(() => expect(mocks.adminApi.companyReport).toHaveBeenCalled());
        expect(screen.queryAllByRole('listitem')).toHaveLength(0);
    });
});
