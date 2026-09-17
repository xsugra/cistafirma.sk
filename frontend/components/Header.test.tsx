import {beforeEach, describe, expect, it, vi} from 'vitest';
import {screen} from '@testing-library/react';
import {Header} from './Header';
import {makeUser, renderWithProviders} from '../test/testUtils';
import type {User} from '../types';

// vi.mock factories are hoisted above imports, so mutable handles go through vi.hoisted.
const authMock = vi.hoisted(() => ({useAuth: vi.fn()}));
// `useAuth` is stubbed so a spec can say who is signed in; everything else --
// `AuthProvider` in particular, which `renderWithProviders` mounts -- stays
// real, because a partial mock that drops it breaks every render that mounts
// the provider rather than the one thing the spec meant to control.
vi.mock('../context/AuthContext', async (importOriginal) => ({
    ...(await importOriginal<typeof import('../context/AuthContext')>()),
    useAuth: authMock.useAuth,
}));

const signedInUser: User = makeUser({firstName: 'Ján', username: 'jan', isStaff: false});

const setAuth = (
    {user, isAuthenticated}: {user: User | null; isAuthenticated: boolean} =
    {user: signedInUser, isAuthenticated: true},
) => {
    authMock.useAuth.mockReturnValue({user, isAuthenticated, login: vi.fn(), logout: vi.fn(), isLoading: false});
};

describe('Header (pricing-removal regression)', () => {
    beforeEach(() => setAuth());

    it('shows the primary nav (desktop + mobile overlay) with no CENNÍK for a signed-in user', () => {
        renderWithProviders(<Header/>, {route: '/'});
        // The desktop <nav> and the always-mounted mobile overlay both render
        // these labels, so they appear more than once — assert via getAllBy*.
        for (const label of ['DOMOV', 'MONITORING', 'BLOG', 'API']) {
            expect(screen.getAllByText(label).length).toBeGreaterThan(0);
        }
        expect(screen.queryAllByText(/cenník/i)).toHaveLength(0);
    });

    it('shows auth actions and no CENNÍK for anonymous users', () => {
        setAuth({user: null, isAuthenticated: false});
        renderWithProviders(<Header/>, {route: '/'});
        expect(screen.getAllByText('Prihlásiť sa').length).toBeGreaterThan(0);
        expect(screen.getAllByText('Registrácia').length).toBeGreaterThan(0);
        expect(screen.queryAllByText(/cenník/i)).toHaveLength(0);
    });
});
