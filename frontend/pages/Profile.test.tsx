import {beforeEach, describe, expect, it, vi} from 'vitest';
import {screen} from '@testing-library/react';
import {Profile} from './Profile';
import {makeUser, renderWithProviders} from '../test/testUtils';
import type {User} from '../types';

const mocks = vi.hoisted(() => ({
    api: {
        getWatchlist: vi.fn(),
        getHistory: vi.fn(),
        getNotifications: vi.fn(),
        getNotificationPreferences: vi.fn(),
        updateNotificationPreferences: vi.fn(),
    },
    auth: {useAuth: vi.fn()},
}));

// Same module ids Profile.tsx resolves (this spec lives in pages/, like Profile).
vi.mock('../api', () => ({api: mocks.api}));
// `useAuth` stubbed, the rest of the module real: `renderWithProviders` mounts
// the actual `AuthProvider`, and a partial mock that drops it fails every
// render rather than only the behaviour this spec means to pin.
vi.mock('../context/AuthContext', async (importOriginal) => ({
    ...(await importOriginal<typeof import('../context/AuthContext')>()),
    useAuth: mocks.auth.useAuth,
}));

const user: User = makeUser({
    firstName: 'Jana',
    username: 'jana',
    plan: 'plus',
    apiCallsUsed: 34,
    apiCallsLimit: 50,
});

describe('Profile (pricing-removal regression)', () => {
    beforeEach(() => {
        mocks.api.getWatchlist.mockResolvedValue([]);
        mocks.api.getHistory.mockResolvedValue([]);
        mocks.api.getNotifications.mockResolvedValue([]);
        mocks.api.getNotificationPreferences.mockResolvedValue({
            emailEnabled: true,
            onDebtChange: true,
            onStatusChange: true,
            onExecutiveChange: true,
        });
        mocks.auth.useAuth.mockReturnValue({
            user,
            isAuthenticated: true,
            login: vi.fn(),
            logout: vi.fn(),
            isLoading: false,
        });
    });

    it('shows the API-limit dashboard and Plán row with no "Navýšiť limit" upsell', async () => {
        renderWithProviders(<Profile/>, {route: '/profile'});

        // Dashboard is gated behind isLoadingData, which flips only after the
        // two list fetches resolve — await it so absence assertions have no false positives.
        expect(await screen.findByText('Využitie API Limitov')).toBeInTheDocument();
        expect(screen.getByText('34 / 50')).toBeInTheDocument();
        expect(screen.getByText('Plán')).toBeInTheDocument();
        expect(screen.getByText('plus')).toBeInTheDocument();

        expect(screen.queryAllByText(/navýšiť limit/i)).toHaveLength(0);
        expect(screen.queryByRole('button', {name: /navýšiť limit/i})).not.toBeInTheDocument();

        // Regression: Profile still boots its two dashboard list fetches.
        expect(mocks.api.getWatchlist).toHaveBeenCalledTimes(1);
        expect(mocks.api.getHistory).toHaveBeenCalledTimes(1);
    });

    it('draws no quota when the API reported none', async () => {
        // The real account state: the profile endpoint publishes no search
        // counter, so the mapper maps both fields as null. The page used to
        // print an invented "0 / 10" with a progress bar behind it.
        mocks.auth.useAuth.mockReturnValue({
            user: makeUser({plan: 'free', apiCallsUsed: null, apiCallsLimit: null}),
            isAuthenticated: true,
            login: vi.fn(),
            logout: vi.fn(),
            isLoading: false,
        });

        renderWithProviders(<Profile/>, {route: '/profile'});

        expect(await screen.findByText('Využitie API Limitov')).toBeInTheDocument();
        expect(screen.getByText(/Počet vyhľadávaní pre tento účet nesledujeme/)).toBeInTheDocument();
        expect(screen.queryByText('0 / 10')).not.toBeInTheDocument();
        expect(screen.queryByText(/0 \/ null|null \/ null/)).not.toBeInTheDocument();
    });
});
