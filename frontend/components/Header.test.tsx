import {afterEach, beforeEach, describe, expect, it, vi} from 'vitest';
import {act, fireEvent, screen} from '@testing-library/react';
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

describe('Header — mobilné menu (#176, krok 4)', () => {
    const originalWidth = window.innerWidth;

    const setViewport = (width: number) =>
        Object.defineProperty(window, 'innerWidth', {writable: true, configurable: true, value: width});

    // The overlay carries the id the hamburger points at with `aria-controls`,
    // so it is found the same way a screen reader would find it. `!` is safe:
    // a missing overlay should fail every spec here loudly, not skip them.
    const overlay = () => document.getElementById('mobile-menu')!;
    const toggle = () => screen.getByRole('button', {name: 'Menu'});

    beforeEach(() => {
        setAuth();
        setViewport(393);
    });

    afterEach(() => {
        setViewport(originalWidth);
        // The lock is on `document.body`, which outlives `cleanup()`: without
        // this a spec that fails mid-way leaves the next one scroll-locked.
        document.body.style.overflow = '';
    });

    it('zatvorené menu je `invisible`, nie len priehľadné', () => {
        // `opacity-0` alone leaves every link in the panel focusable and
        // announced. jsdom computes no layout and so cannot verify tab order;
        // what it can verify is the class, and `visibility: hidden` is the
        // mechanism that removes an element from both.
        renderWithProviders(<Header/>, {route: '/'});
        expect(overlay()).toHaveClass('invisible');
        expect(toggle()).toHaveAttribute('aria-expanded', 'false');
        expect(toggle()).toHaveAttribute('aria-controls', 'mobile-menu');
    });

    it('otvorenie zruší `invisible` a prepne `aria-expanded`', () => {
        renderWithProviders(<Header/>, {route: '/'});
        fireEvent.click(toggle());
        expect(overlay()).not.toHaveClass('invisible');
        expect(toggle()).toHaveAttribute('aria-expanded', 'true');
    });

    it('otvorené menu zamkne skrolovanie stránky, zatvorenie ho vráti', () => {
        renderWithProviders(<Header/>, {route: '/'});
        expect(document.body.style.overflow).toBe('');
        fireEvent.click(toggle());
        expect(document.body.style.overflow).toBe('hidden');
        fireEvent.click(toggle());
        expect(document.body.style.overflow).toBe('');
    });

    it('skrolovanie menu sa neprenáša na stránku pod ním', () => {
        // The signed-in menu is ~550 px of content under a 6 rem top pad, so a
        // phone held sideways cannot show it all -- it has to scroll itself.
        renderWithProviders(<Header/>, {route: '/'});
        expect(overlay()).toHaveClass('overflow-y-auto', 'overscroll-contain');
    });

    it('rozšírenie na šírku ≥ lg menu zavrie, aby nezostal zamknutý skrol', () => {
        // The menu is `lg:hidden`, so past `lg` it is not on screen -- but the
        // open state and the body lock would both survive the resize.
        renderWithProviders(<Header/>, {route: '/'});
        fireEvent.click(toggle());
        expect(document.body.style.overflow).toBe('hidden');

        act(() => {
            setViewport(1280);
            window.dispatchEvent(new Event('resize'));
        });

        expect(document.body.style.overflow).toBe('');
        expect(toggle()).toHaveAttribute('aria-expanded', 'false');
    });
});
