import {render} from '@testing-library/react';
import type {ReactElement} from 'react';
import {MemoryRouter} from 'react-router-dom';
import {ThemeProvider} from '../context/ThemeContext';
import type {Company, User} from '../types';

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
    vatStatus: {
        icDph: 'SK1234567890',
        isVatPayer: true,
        taxReliabilityIndex: 'Spoľahlivý',
        reasonForDeregistration: null,
        lastCheckedAt: '2026-01-01T00:00:00Z',
    },
    riskScore: {score: 70, summary: 'Nízke riziko', calculationDate: '2026-01-01T00:00:00Z'},
    financials: [],
    // Paired with the empty `financials` above: a fixture that has no rows must
    // not also claim to be `ready`, or a section test could pass by rendering a
    // sentence about figures it never had.
    financialsState: 'not_fetched',
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
