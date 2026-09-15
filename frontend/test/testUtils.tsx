import {render} from '@testing-library/react';
import type {ReactElement} from 'react';
import {MemoryRouter} from 'react-router-dom';
import {AuthProvider} from '../context/AuthContext';
import {ThemeProvider} from '../context/ThemeContext';
import {clearSession, saveSession} from '../lib/tokenStore';
import type {Company, Financials, User} from '../types';

export const DEFAULT_USER: User = {
    id: 'u-test',
    email: 'test@example.com',
    username: 'testuser',
    firstName: 'Test',
    lastName: 'User',
    plan: 'plus',
    apiCallsUsed: 34,
    apiCallsLimit: 50,
    isStaff: false,
    isSuperuser: false,
};

export const makeUser = (overrides: Partial<User> = {}): User => ({...DEFAULT_USER, ...overrides});

/**
 * One statement row that filed nothing, for the cases that name what they need.
 *
 * Every line is `null` rather than 0 on purpose -- that is the distinction the
 * statement sections are built around, and a fixture that defaulted to zero
 * would let a test pass while the screen showed a figure the filing never had.
 */
export const DEFAULT_FINANCIALS: Financials = {
    year: 2023,
    revenue: null,
    profit: null,
    profitAfterTax: null,
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
};

export const makeFinancials = (overrides: Partial<Financials> = {}): Financials => ({
    ...DEFAULT_FINANCIALS,
    ...overrides,
});

/** A company with nothing filed anywhere, for the cases that name what they need. */
export const DEFAULT_COMPANY: Company = {
    id: '1',
    ico: '12345678',
    name: 'Testovacia, s.r.o.',
    legalForm: 'Spoločnosť s ručením obmedzeným',
    status: 'Aktívna',
    registrationDate: '2010-01-01',
    address: {street: 'Hlavná 1', city: 'Bratislava', zipCode: '811 01', country: 'SK'},
    // `null`, so the default fixture is the unplaced company. Most tests are
    // about something else and should not have to mount a map -- one that wants
    // the map opts in through `makeCompany({seatLocation: ...})`.
    seatLocation: null,
    lastUpdatedFromSource: '2026-01-01T00:00:00Z',
    // Both sources read, so this fixture's empty `debts` is a finding and not a
    // gap. A fixture that left these null would make every unrelated test
    // exercise the "we never looked" panel.
    insuranceCheckedOn: '2026-01-01T00:00:00Z',
    taxCheckedOn: '2026-01-01T00:00:00Z',
    // `false`, not `null`: the two dates above say the insurance register was
    // read, so the register not listing this company is the answer it gave. A
    // `null` here would be a fixture contradicting itself -- "read, and we know
    // nothing" -- and it would put the SP-listing branch one careless assertion
    // away from firing in an unrelated test.
    socialListedWithoutAmount: false,
    debts: [],
    dic: '1234567890',
    vatStatus: {
        icDph: 'SK1234567890',
        isVatPayer: true,
        // Lowercase, as the register spells it. A fixture that mirrors the
        // source is the only kind that can catch the source's spelling.
        taxReliabilityIndex: 'vysoko spoľahlivý',
        registeredOn: '2010-01-01',
        deregisteredOn: null,
        reasonForDeregistration: null,
        lastCheckedAt: '2026-01-01T00:00:00Z',
    },
    riskScore: {
        score: 70,
        summary: 'Nízke riziko',
        // The strip and the section both read this; a fixture without it would
        // exercise the "could not load" branch in every unrelated test.
        breakdown: {
            start: 100,
            floor: 5,
            clamped: false,
            parts: [
                {key: 'debt', label: 'Evidované nedoplatky', delta: -30, detail: 'žiadne'},
                {key: 'zone', label: 'Altman Z-score', delta: 0, detail: 'bezpečná zóna'},
                {key: 'roa', label: 'Rentabilita aktív', delta: 0, detail: '4,0 %'},
            ],
        },
    },
    financials: [],
    // Paired with the empty `financials` above: a fixture that has no rows must
    // not also claim to be `ready`, or a section test could pass by rendering a
    // sentence about figures it never had.
    financialsState: 'not_fetched',
    // Zero and not null: this fixture is a company that files nothing anywhere
    // (`debts: []`, `financials: []`), so RUZ listing nothing for it is a fact
    // rather than a missing answer. The two mean different things and the
    // Účtovné závierky section says which one it has.
    ruzStatements: 0,
    ruzAnnualReports: 0,
    executives: [],
    connections: [],
    usesIfrs: false,
    ruzPortalUrl: null,
};

export const makeCompany = (overrides: Partial<Company> = {}): Company => ({
    ...DEFAULT_COMPANY,
    ...overrides,
});

/**
 * Render inside the providers a company page actually runs under.
 *
 * `AuthProvider` is here because parts of the page read the session: the
 * "Sledovať" button leads to sign-in when there is no account, and a component
 * that calls `useAuth` outside a provider throws rather than degrading. With no
 * token in `localStorage` -- the state every test starts in -- the provider
 * settles to `isAuthenticated: false` without calling the API, which is the
 * anonymous case and the one most of these tests want.
 */
export const renderWithProviders = (
    ui: ReactElement,
    {route = '/', authenticated = false}: {route?: string; authenticated?: boolean} = {},
) => {
    // Both storages, because these tests start from an unknown one: the store
    // reads whichever holds the token, and a leftover from an earlier test in
    // the same file would otherwise sign in a case that asked to be anonymous.
    clearSession();
    if (authenticated) {
        saveSession({access: 'test-token', refresh: 'test-refresh'}, true);
    }
    return render(
        <MemoryRouter initialEntries={[route]}>
            <AuthProvider>
                <ThemeProvider>{ui}</ThemeProvider>
            </AuthProvider>
        </MemoryRouter>
    );
};
