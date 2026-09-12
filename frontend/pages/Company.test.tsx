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
    riskScore: {score: 70, summary: 'Nízke riziko', breakdown: null},
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
        // The example moved from `zaverky` to `databaza-zamestnanci` when the
        // former got a body: the claim under test is about a section that has
        // none, so the fixture has to be one that still does not.
        renderWithProviders(
            <Routes>
                <Route path="/firma/:ico/:sekcia" element={<Company/>}/>
            </Routes>,
            {route: '/firma/12345678/databaza-zamestnanci'},
        );

        expect(await screen.findByText('Zatiaľ nemáme')).toBeInTheDocument();
        expect(screen.getByText(/Číselný počet zamestnancov nemáme/)).toBeInTheDocument();
    });

    it('renders the body of a section that has one', async () => {
        // The other half of the pair above: `ready` in the registry must mean a
        // body is drawn, not that the notice is drawn in a different colour.
        renderWithProviders(
            <Routes>
                <Route path="/firma/:ico/:sekcia" element={<Company/>}/>
            </Routes>,
            {route: '/firma/12345678/zaverky'},
        );

        // A sentence only the body has: the section's own label is also in the
        // rail, so matching the title would pass on the navigation alone.
        expect(await screen.findByText(/sa do tejto databázy nesťahujú/)).toBeInTheDocument();
        expect(screen.queryByText('Zatiaľ nemáme')).not.toBeInTheDocument();
    });

    it('names which of the four reasons left the balance sheet empty', async () => {
        // The section is built now, so the interesting failure is no longer
        // "there is no table" but "the table has nothing to draw, and the page
        // does not say which of the four reasons applies". `nothing_recorded`
        // promises the opposite of `not_fetched`: one says come back later,
        // the other says we already asked.
        mocks.api.getCompany.mockResolvedValue({
            ...company,
            financials: [],
            financialsState: 'nothing_recorded',
        });

        renderWithProviders(
            <Routes>
                <Route path="/firma/:ico/:sekcia" element={<Company/>}/>
            </Routes>,
            {route: '/firma/12345678/suvaha'},
        );

        expect(await screen.findByText(/pokus je uzavretý/)).toBeInTheDocument();
        expect(screen.queryByText(/ešte nečítali/)).not.toBeInTheDocument();
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
