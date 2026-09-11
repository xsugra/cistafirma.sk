import {beforeEach, describe, expect, it, vi} from 'vitest';
import {screen} from '@testing-library/react';
import {Route, Routes, useParams} from 'react-router-dom';
import {Company} from './Company';
import {Monitoring} from './Monitoring';
import {renderWithProviders} from '../test/testUtils';
import type {Company as CompanyType} from '../types';

const mocks = vi.hoisted(() => ({
    api: {
        getCompany: vi.fn(),
        getWatchlist: vi.fn(),
        searchCompanies: vi.fn(),
    },
}));

vi.mock('../api', () => ({api: mocks.api}));

/** Only the fields CompanyHeader and CompanySummaryStrip read. */
const company = {
    ico: '12345678',
    name: 'Testovacia, s.r.o.',
    legalForm: 'Spoločnosť s ručením obmedzeným',
    status: 'Aktívna',
    address: {street: 'Hlavná 1', city: 'Bratislava'},
    registrationDate: '2010-01-01',
    lastUpdatedFromSource: '2026-01-01T00:00:00Z',
    orsr_profile: null,
    financials: [],
    analysis: null,
    benchmark: null,
    usesIfrs: false,
    rozPortalUrl: null,
    debts: [],
    vatStatus: {isVatPayer: true, icDph: 'SK1234567890', taxReliabilityIndex: 'Spoľahlivý', lastCheckedAt: null},
    riskScore: {score: 70, summary: 'Nízke riziko'},
} as unknown as CompanyType;

const SectionProbe: React.FC = () => {
    const {ico, sekcia} = useParams<{ico: string; sekcia: string}>();
    return <div data-testid="probe">{`${ico}/${sekcia}`}</div>;
};

describe('Company page', () => {
    beforeEach(() => {
        mocks.api.getCompany.mockResolvedValue(company);
        mocks.api.getWatchlist.mockResolvedValue([]);
    });

    it('routes an old /monitoring?ico= link to the firm page', async () => {
        // Links written before /firma existed point at Monitoring. A link that
        // used to work and now lands on a search box is a regression, so the
        // query is turned into the firm's URL rather than ignored.
        renderWithProviders(
            <Routes>
                <Route path="/monitoring" element={<Monitoring/>}/>
                <Route path="/firma/:ico/:sekcia" element={<SectionProbe/>}/>
            </Routes>,
            {route: '/monitoring?ico=12345678'},
        );

        expect(await screen.findByTestId('probe')).toHaveTextContent('12345678/prehlad');
    });

    it('says why a section we cannot fill is empty instead of showing a blank panel', async () => {
        renderWithProviders(
            <Routes>
                <Route path="/firma/:ico/:sekcia" element={<Company/>}/>
            </Routes>,
            {route: '/firma/12345678/suvaha'},
        );

        // The asset side of the balance sheet is being read wrongly at the
        // source, so the section states that rather than drawing numbers that
        // do not add up.
        expect(await screen.findByText('Údaje sú nespoľahlivé')).toBeInTheDocument();
        expect(screen.getByText(/nesprávne/)).toBeInTheDocument();
    });

    it('marks a section whose source costs money as such', async () => {
        renderWithProviders(
            <Routes>
                <Route path="/firma/:ico/:sekcia" element={<Company/>}/>
            </Routes>,
            {route: '/firma/12345678/exekucie'},
        );

        expect(await screen.findByText('Len za peniaze')).toBeInTheDocument();
    });

    it('names an unknown section rather than rendering nothing', async () => {
        renderWithProviders(
            <Routes>
                <Route path="/firma/:ico/:sekcia" element={<Company/>}/>
            </Routes>,
            {route: '/firma/12345678/neexistuje'},
        );

        expect(await screen.findByText(/neexistuje/)).toBeInTheDocument();
    });
});
