import {render} from '@testing-library/react';
import type {ReactElement} from 'react';
import {MemoryRouter} from 'react-router-dom';
import {ThemeProvider} from '../context/ThemeContext';
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
    lastUpdatedFromSource: '2026-01-01T00:00:00Z',
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

/** Router + ThemeProvider wrapper. Auth is supplied per-spec via vi.mock of AuthContext. */
export const renderWithProviders = (ui: ReactElement, {route = '/'}: {route?: string} = {}) =>
    render(
        <MemoryRouter initialEntries={[route]}>
            <ThemeProvider>{ui}</ThemeProvider>
        </MemoryRouter>
    );
