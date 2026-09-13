import {beforeEach, describe, expect, it, vi} from 'vitest';
import {screen, waitFor} from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import {Route, Routes, useLocation} from 'react-router-dom';
import {CompanyHeader} from './CompanyHeader';
import {makeCompany, makeUser, renderWithProviders} from '../../test/testUtils';
import {getLegalFormProfile} from '../../utils/legalFormProfile';
import {postAuthDestination} from '../../utils/postAuthDestination';

const mocks = vi.hoisted(() => ({
    api: {
        getWatchlist: vi.fn(),
        addToWatchlist: vi.fn(),
        removeFromWatchlist: vi.fn(),
        getProfile: vi.fn(),
    },
}));

vi.mock('../../api', () => ({api: mocks.api}));
vi.mock('../../utils/pdfExport', () => ({exportCompanyPDF: vi.fn()}));

const ico = '48097781';

/** Stands in for the login page and reports where it was sent from. */
const LoginProbe = () => {
    const location = useLocation();
    const from = (location.state as {from?: string} | null)?.from ?? '(none)';
    return <div data-testid="login-page">{from}</div>;
};

const profile = getLegalFormProfile('sro');

const renderHeader = () => {
    const company = makeCompany({ico});
    return renderWithProviders(
        <Routes>
            <Route path="/" element={<CompanyHeader company={company} profile={profile}/>}/>
            <Route path="/login" element={<LoginProbe/>}/>
        </Routes>,
    );
};

describe('CompanyHeader — Sledovať', () => {
    beforeEach(() => {
        mocks.api.getWatchlist.mockReset().mockResolvedValue([]);
        mocks.api.addToWatchlist.mockReset().mockResolvedValue({success: true});
        mocks.api.getProfile.mockReset();
    });

    it('sends an anonymous visitor to sign in instead of failing silently', async () => {
        // The defect this file exists for. The button called
        // `POST /api/watchlist/`, which is `IsAuthenticated`; the 401 went to a
        // `console.error` and the reader got nothing at all -- no watch, no
        // message, no navigation. It looked like it had worked.
        const user = userEvent.setup();
        renderHeader();

        await user.click(screen.getByRole('button', {name: /Sledovať/}));

        expect(await screen.findByTestId('login-page')).toBeInTheDocument();
        expect(mocks.api.addToWatchlist).not.toHaveBeenCalled();
    });

    it('carries where the reader was, so signing in returns them to the company', async () => {
        const user = userEvent.setup();
        renderHeader();

        await user.click(screen.getByRole('button', {name: /Sledovať/}));

        expect(await screen.findByTestId('login-page')).toHaveTextContent('/');
    });

    it('does not ask the API which companies are watched without an account', () => {
        // `getWatchlist` is `IsAuthenticated`, so for an anonymous reader this
        // was a guaranteed 401 on every company page -- which the API client
        // turns into a global `auth:unauthorized` event. A question nobody
        // asked, costing a request and a console warning each time.
        renderHeader();

        expect(mocks.api.getWatchlist).not.toHaveBeenCalled();
    });

    it('shows a failed watch instead of leaving it in the console', async () => {
        // The same defect one step later: once signed in, a watch that fails
        // must say so, because the button is the only feedback the action has.
        const user = userEvent.setup();
        mocks.api.getProfile.mockResolvedValue(makeUser());
        mocks.api.addToWatchlist.mockRejectedValue(new Error('Server je nedostupný.'));
        renderWithProviders(
            <CompanyHeader company={makeCompany({ico})} profile={profile}/>,
            {authenticated: true},
        );

        // The provider has to finish reading the profile before the header is
        // signed in; until then the click would be treated as anonymous.
        await waitFor(() => expect(mocks.api.getProfile).toHaveBeenCalled());
        await waitFor(() => expect(mocks.api.getWatchlist).toHaveBeenCalled());
        await user.click(screen.getByRole('button', {name: /Sledovať/}));

        expect(await screen.findByRole('alert')).toHaveTextContent('Server je nedostupný.');
    });
});

describe('postAuthDestination', () => {
    it('accepts a path inside this app', () => {
        expect(postAuthDestination({from: '/spolocnost/48097781'})).toBe('/spolocnost/48097781');
    });

    it('falls back to home when there is no destination', () => {
        expect(postAuthDestination(undefined)).toBe('/');
        expect(postAuthDestination({})).toBe('/');
        expect(postAuthDestination({from: 42})).toBe('/');
    });

    it('refuses to become an open redirect', () => {
        // Reaching the sign-in page through a crafted link must not let that
        // link choose where the reader lands afterwards -- a phishing hop that
        // starts on a URL they trust.
        for (const hostile of [
            'https://evil.example',
            '//evil.example',
            'http://evil.example/prihlasenie',
        ]) {
            expect(postAuthDestination({from: hostile})).toBe('/');
        }
    });
});
