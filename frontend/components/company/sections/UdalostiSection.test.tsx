import {beforeEach, describe, expect, it, vi} from 'vitest';
import {screen, waitFor} from '@testing-library/react';
import {UdalostiSection, formatDateTime} from './UdalostiSection';
import {renderWithProviders} from '../../../test/testUtils';
import type {NotificationEvent} from '../../../types';

const mocks = vi.hoisted(() => ({
    getCompanyEvents: vi.fn(),
    useAuth: vi.fn(),
}));

vi.mock('../../../api', () => ({api: {getCompanyEvents: mocks.getCompanyEvents}}));
vi.mock('../../../context/AuthContext', () => ({useAuth: mocks.useAuth}));

const event = (overrides: Partial<NotificationEvent> = {}): NotificationEvent => ({
    id: 1,
    companyIco: '12345678',
    companyName: 'Testovacia, s.r.o.',
    eventType: 'debt_change',
    eventTypeDisplay: 'Zmena dlhu',
    title: 'Nedoplatok voči Sociálnej poisťovni vzrástol o 1 250 €',
    details: {},
    sentEmail: true,
    createdAt: '2026-08-14T09:30:00Z',
    ...overrides,
});

const signedIn = () =>
    mocks.useAuth.mockReturnValue({
        user: {id: 'u-test', email: 'test@example.com'},
        isAuthenticated: true,
        login: vi.fn(),
        logout: vi.fn(),
        isLoading: false,
    });

const signedOut = () =>
    mocks.useAuth.mockReturnValue({
        user: null,
        isAuthenticated: false,
        login: vi.fn(),
        logout: vi.fn(),
        isLoading: false,
    });

const bodyText = () => document.body.textContent!.replace(/ /g, ' ');

beforeEach(() => {
    mocks.getCompanyEvents.mockReset();
    mocks.useAuth.mockReset();
});

describe('UdalostiSection', () => {
    it('shows the reader their own events for this company', async () => {
        signedIn();
        mocks.getCompanyEvents.mockResolvedValue([event()]);

        renderWithProviders(<UdalostiSection ico="12345678"/>);

        expect(await screen.findByText(/Nedoplatok voči Sociálnej poisťovni/)).toBeInTheDocument();
        expect(bodyText()).toContain('Zmena dlhu');
        expect(mocks.getCompanyEvents).toHaveBeenCalledWith('12345678');
    });

    it('asks for an account instead of drawing an empty list when signed out', () => {
        signedOut();

        renderWithProviders(<UdalostiSection ico="12345678"/>);

        expect(bodyText()).toContain('notifikácie, ktoré sme tebe poslali');
        expect(screen.getByRole('link', {name: /Prihlásiť sa/i})).toBeInTheDocument();
        // Nothing was requested: the endpoint is account-scoped, so calling it
        // signed out could only produce a 401 rendered as "no events".
        expect(mocks.getCompanyEvents).not.toHaveBeenCalled();
    });

    it('says nothing was sent without claiming nothing happened', async () => {
        signedIn();
        mocks.getCompanyEvents.mockResolvedValue([]);

        renderWithProviders(<UdalostiSection ico="12345678"/>);

        expect(await screen.findByText('O tejto firme sme ti zatiaľ nič neposlali.')).toBeInTheDocument();
        expect(bodyText()).toContain('Neznamená to, že sa nič nestalo');
    });

    it('marks an event no e-mail was sent for', async () => {
        signedIn();
        mocks.getCompanyEvents.mockResolvedValue([event({sentEmail: false})]);

        renderWithProviders(<UdalostiSection ico="12345678"/>);

        expect(await screen.findByText(/e-mail sme neposlali/)).toBeInTheDocument();
    });

    it('says the events could not be loaded rather than showing none', async () => {
        signedIn();
        mocks.getCompanyEvents.mockRejectedValue(new Error('500'));

        renderWithProviders(<UdalostiSection ico="12345678"/>);

        expect(await screen.findByText(/sa nepodarilo načítať/)).toBeInTheDocument();
        expect(bodyText()).not.toContain('zatiaľ nič neposlali');
    });

    it('refetches when the section is pointed at another company', async () => {
        signedIn();
        mocks.getCompanyEvents.mockResolvedValue([]);

        const {rerender} = renderWithProviders(<UdalostiSection ico="12345678"/>);
        await waitFor(() => expect(mocks.getCompanyEvents).toHaveBeenCalledTimes(1));

        rerender(<UdalostiSection ico="87654321"/>);
        await waitFor(() => expect(mocks.getCompanyEvents).toHaveBeenLastCalledWith('87654321'));
    });
});

describe('formatDateTime', () => {
    it('renders an ISO timestamp as the reader\'s local date and time', () => {
        // Date and clock, either side of a comma ICU may or may not insert --
        // the browser owns the exact separator and this only asserts the shape.
        // 09:30 UTC stays 14 August in every timezone the tests run in.
        expect(formatDateTime('2026-08-14T09:30:00Z')).toMatch(/^\d{1,2}\. 8\. 2026,? \d{1,2}:\d{2}$/);
    });

    it('passes an unparseable value through instead of printing Invalid Date', () => {
        // The test environment's timezone shifts the clock but never the shape,
        // so this asserts the fallback rather than a rendered time.
        expect(formatDateTime('nie je datum')).toBe('nie je datum');
    });
});
