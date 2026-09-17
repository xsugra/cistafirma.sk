import {beforeEach, describe, expect, it, vi} from 'vitest';
import {screen, waitFor} from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import {Route, Routes, useLocation, useParams} from 'react-router-dom';
import {Company} from './Company';
import {Monitoring} from './Monitoring';
import {COMPANY_SECTIONS} from '../companySections';
import {renderWithProviders} from '../test/testUtils';
import type {Company as CompanyType} from '../types';

const mocks = vi.hoisted(() => ({
    api: {
        getCompany: vi.fn(),
        getWatchlist: vi.fn(),
        searchCompanies: vi.fn(),
        // The page's own search box asks the same two endpoints the home page's
        // does, so both have to exist here now that the box is on this page.
        searchPersons: vi.fn(),
    },
}));

vi.mock('../api', () => ({api: mocks.api}));

/** Only the fields CompanyHeader and CompanySummaryStrip read. */
const company = {
    ico: '12345678',
    dic: '1234567890',
    name: 'Testovacia, s.r.o.',
    legalForm: 'Spoločnosť s ručením obmedzeným',
    status: 'Aktívna',
    address: {street: 'Hlavná 1', city: 'Bratislava'},
    registrationDate: '2010-01-01',
    lastUpdatedFromSource: '2026-01-01T00:00:00Z',
    insuranceCheckedOn: '2026-01-01T00:00:00Z',
    taxCheckedOn: '2026-01-01T00:00:00Z',
    orsr_profile: null,
    financials: [],
    analysis: null,
    benchmark: null,
    usesIfrs: false,
    rozPortalUrl: null,
    debts: [],
    vatStatus: {
        isVatPayer: true,
        icDph: 'SK1234567890',
        taxReliabilityIndex: 'spoľahlivý',
        registeredOn: '2010-01-01',
        deregisteredOn: null,
        reasonForDeregistration: null,
        lastCheckedAt: null,
    },
    riskScore: {score: 70, summary: 'Nízke riziko', breakdown: null},
} as unknown as CompanyType;

const SectionProbe: React.FC = () => {
    const {ico, sekcia} = useParams<{ico: string; sekcia: string}>();
    return <div data-testid="probe">{`${ico}/${sekcia}`}</div>;
};

/**
 * The URL the router is on, printed beside whatever route matched.
 *
 * The search box navigates to two different shapes of URL, and one of them
 * (`/firma/:ico/:sekcia`) is the route the page itself is mounted on -- so a
 * probe *route* would have to be registered twice, and the second registration
 * would shadow the page under test. A sibling that only reads `useLocation` has
 * no such problem.
 */
const LocationProbe: React.FC = () => {
    const location = useLocation();
    return <div data-testid="location">{`${location.pathname}${location.search}`}</div>;
};

const renderCompany = (route: string) =>
    renderWithProviders(
        <>
            <LocationProbe/>
            <Routes>
                <Route path="/firma/:ico/:sekcia" element={<Company/>}/>
            </Routes>
        </>,
        {route},
    );

const typeInPageSearch = async (text: string) => {
    const user = userEvent.setup();
    await user.type(screen.getByRole('textbox', {name: 'Hľadať firmu alebo osobu'}), text);
    await user.click(screen.getByRole('button', {name: 'Hľadať'}));
};

describe('Company page', () => {
    beforeEach(() => {
        mocks.api.getCompany.mockResolvedValue(company);
        mocks.api.getWatchlist.mockResolvedValue([]);
        mocks.api.searchCompanies.mockResolvedValue({results: []});
        mocks.api.searchPersons.mockResolvedValue(null);
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

    it('says why every section we cannot fill is empty, not just the one we picked', async () => {
        // A loop over the registry rather than one hard-coded id. This test used
        // to name a single unfilled section and had to be re-pointed each time
        // one of them got a body -- `zaverky` first, then
        // `databaza-zamestnanci`. The claim was never about one section: an
        // empty panel leaves the reader guessing whether the firm has no data or
        // we have no feature, and *every* section without a body has to say
        // which. Naming one of them tested the example, not the rule.
        const unfilled = COMPANY_SECTIONS.filter((section) => section.status !== 'ready');
        // If this ever hits zero the loop below proves nothing, and the honest
        // thing is to delete this test rather than let it pass vacuously.
        expect(unfilled.length).toBeGreaterThan(0);

        for (const section of unfilled) {
            const {unmount} = renderWithProviders(
                <Routes>
                    <Route path="/firma/:ico/:sekcia" element={<Company/>}/>
                </Routes>,
                {route: `/firma/12345678/${section.id}`},
            );

            // The note verbatim, because that sentence is the whole mechanism:
            // the status chip says *that* we cannot fill it, the note says why.
            expect(await screen.findByText(section.note)).toBeInTheDocument();

            unmount();
        }
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
        // rail, so matching the title would pass on the navigation alone. It
        // used to read "sa do tejto databázy nesťahujú" -- true until the
        // register's document routes were found, and false after.
        expect(
            await screen.findByText(/stahujú priamo odtiaľto, z registra účtovných závierok/),
        ).toBeInTheDocument();
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

    it('shows the DIČ, which the payload has always carried and no line named', async () => {
        // 395 373 of 445 626 rows. It travelled in the response from the first
        // day and the header printed only the IČO.
        renderWithProviders(
            <Routes>
                <Route path="/firma/:ico/:sekcia" element={<Company/>}/>
            </Routes>,
            {route: '/firma/12345678/prehlad'},
        );

        expect(await screen.findByText('1234567890')).toBeInTheDocument();
        expect(screen.getByText(/DIČ/)).toBeInTheDocument();
    });

    it('leaves the DIČ line out entirely for a company that has none', async () => {
        // The other 50 253 rows. A label with nothing after it reads as a
        // failed lookup; an absent line reads as a field the register does not
        // keep, which is what it is.
        mocks.api.getCompany.mockResolvedValue({...company, dic: null});

        renderWithProviders(
            <Routes>
                <Route path="/firma/:ico/:sekcia" element={<Company/>}/>
            </Routes>,
            {route: '/firma/12345678/prehlad'},
        );

        // Waited on the name, not the IČO: the IČ DPH in the strip below is
        // `SK1234567890` and contains the IČO as a substring, so an IČO match
        // finds two elements.
        expect(await screen.findByText('Testovacia, s.r.o.')).toBeInTheDocument();
        expect(screen.queryByText(/DIČ/)).not.toBeInTheDocument();
    });

    it('finds the next firm from the firm page itself, without going back', async () => {
        // The search box used to live only on the pages you arrived *from*, so
        // reading one firm and then another meant Back, retype, forward. An IČO
        // typed here goes straight at the firm it names.
        renderCompany('/firma/12345678/prehlad');
        await screen.findByText('Testovacia, s.r.o.');

        await typeInPageSearch('87654321');

        await waitFor(() =>
            expect(screen.getByTestId('location')).toHaveTextContent(
                /^\/firma\/87654321\/prehlad$/,
            ),
        );
    });

    it('hands a name to the search page, which is what can answer a name', async () => {
        // The other half of the same rule: a name is not an IČO, and the page
        // that can turn one into a firm is the search page.
        renderCompany('/firma/12345678/zaverky');
        await screen.findByText('Testovacia, s.r.o.');

        await typeInPageSearch('Iná Firma');

        await waitFor(() =>
            expect(screen.getByTestId('location')).toHaveTextContent(
                '/monitoring?ico=In%C3%A1%20Firma',
            ),
        );
    });
});
