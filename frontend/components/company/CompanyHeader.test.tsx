import {beforeEach, describe, expect, it, vi} from 'vitest';
import {screen, waitFor} from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import {Route, Routes, useLocation} from 'react-router-dom';
import {CompanyHeader} from './CompanyHeader';
import {makeCompany, makeUser, renderWithProviders} from '../../test/testUtils';
import {getLegalFormProfile} from '../../utils/legalFormProfile';
import {postAuthDestination} from '../../utils/postAuthDestination';
import {ApiError} from '../../lib/apiClient';

const mocks = vi.hoisted(() => ({
    api: {
        getWatchlist: vi.fn(),
        addToWatchlist: vi.fn(),
        removeFromWatchlist: vi.fn(),
        getProfile: vi.fn(),
    },
    adminApi: {
        refreshCompany: vi.fn(),
    },
}));

vi.mock('../../api', () => ({api: mocks.api}));
vi.mock('../../admin/api', () => ({adminApi: mocks.adminApi}));
vi.mock('../../utils/pdfExport', () => ({exportCompanyPDF: vi.fn()}));
// The real map needs a laid-out container jsdom does not have; what this file
// checks is whether the card is there at all.
vi.mock('./SeatMap', () => ({SeatMap: () => null}));

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

describe('CompanyHeader — obnovenie údajov', () => {
    beforeEach(() => {
        mocks.api.getWatchlist.mockReset().mockResolvedValue([]);
        mocks.api.getProfile.mockReset();
        mocks.adminApi.refreshCompany.mockReset();
    });

    /** Signed in, staff, and past the profile fetch the button waits behind. */
    const renderAsStaff = async () => {
        mocks.api.getProfile.mockResolvedValue(makeUser({isStaff: true}));
        renderWithProviders(
            <CompanyHeader company={makeCompany({ico})} profile={profile}/>,
            {authenticated: true},
        );
        return screen.findByRole('button', {name: /Aktualizovať údaje/});
    };

    const dispatch = (overrides: Record<string, unknown> = {}) => ({
        company_id: 1,
        ico,
        dispatched: ['ruz', 'financials', 'orsr', 'vszp', 'social'],
        skipped: [],
        blocked_but_asked: [],
        cooldown_seconds: 900,
        ...overrides,
    });

    it('is absent for an anonymous reader, not disabled', async () => {
        // The page is public: `CompanyViewSet` is `AllowAny` and `/firma/:ico`
        // sits outside `ProtectedRoute`. A control rendered for everyone would
        // be a button that 403s for most readers, and a "len pre adminov" hint
        // would be a second thing that does not exist for them today.
        renderHeader();

        expect(screen.getByText('Posledná aktualizácia')).toBeInTheDocument();
        expect(screen.queryByText(/Aktualizovať údaje/)).not.toBeInTheDocument();
    });

    it('is absent for a signed-in reader who is not staff', async () => {
        mocks.api.getProfile.mockResolvedValue(makeUser({isStaff: false}));
        renderWithProviders(
            <CompanyHeader company={makeCompany({ico})} profile={profile}/>,
            {authenticated: true},
        );

        // Waiting on the watchlist proves the profile landed: without it the
        // assertion below would pass on the signed-out branch instead.
        await waitFor(() => expect(mocks.api.getWatchlist).toHaveBeenCalled());
        expect(screen.queryByRole('button', {name: /Aktualizovať údaje/})).not.toBeInTheDocument();
    });

    it('is an action among the actions, not a value under the date', async () => {
        const button = await renderAsStaff();

        // It used to be nested inside the "Posledná aktualizácia" value, whose
        // style is `font-semibold text-gray-900` -- a *value's* style -- with a
        // button's padding (`px-2 py-0.5 text-xs`) squeezed into it. Measured,
        // that came to 22 px against Apple's 44 px minimum, sitting in a row of
        // text a reader is not looking at for a control. Both halves are the
        // fix, so both are pinned here: it sits with the other actions, and it
        // is a design-system button rather than the one hand-rolled pill on the
        // card. `min-h-11` is the class that actually delivers the 44 px -- the
        // same `.btn` without it measures 38 px.
        expect(screen.getByRole('button', {name: /PDF/}).parentElement)
            .toBe(button.parentElement);
        expect(button).toHaveClass('btn', 'btn-outline', 'min-h-11');
    });

    it('sends the database pk, not the IČO in the URL', async () => {
        const user = userEvent.setup();
        const button = await renderAsStaff();

        await user.click(button);

        // The fixture's IČO and pk differ on purpose: the endpoint is keyed by
        // pk, and the page is keyed by IČO, so the two are one careless line
        // apart and only a test that separates them can tell them apart.
        expect(mocks.adminApi.refreshCompany).toHaveBeenCalledWith('1');
    });

    it('says the pass has started, and that the page has to be reloaded to see it', async () => {
        const user = userEvent.setup();
        mocks.adminApi.refreshCompany.mockResolvedValue(dispatch());
        const button = await renderAsStaff();

        await user.click(button);

        const notice = await screen.findByRole('status');
        // The number in this cell is written by the pass that was just queued,
        // so a message implying the page is now fresh would be a lie about the
        // very value it sits under.
        expect(notice).toHaveTextContent('Obnova spustená');
        expect(notice).toHaveTextContent('obnovení stránky');
    });

    it('names a skipped source instead of leaving it out of the sentence', async () => {
        const user = userEvent.setup();
        mocks.adminApi.refreshCompany.mockResolvedValue(dispatch({
            dispatched: ['ruz', 'financials', 'vszp', 'social'],
            skipped: [{source: 'orsr', reason: 'not_eligible'}],
        }));
        const button = await renderAsStaff();

        await user.click(button);

        expect(await screen.findByRole('status')).toHaveTextContent('Preskočené: ORSR');
    });

    it('warns that a blocked source is asked anyway', async () => {
        const user = userEvent.setup();
        mocks.adminApi.refreshCompany.mockResolvedValue(dispatch({blocked_but_asked: ['orsr']}));
        const button = await renderAsStaff();

        await user.click(button);

        expect(await screen.findByRole('status')).toHaveTextContent('osloví zablokovaný zdroj ORSR');
    });

    it('answers a 409 in its own words, not with the machine token', async () => {
        const user = userEvent.setup();
        // `parseErrors` is what turns the body into that sentence, and it needs
        // the body to do it -- `ApiError` carries only the status, so the
        // component passes the message straight through. The number is real:
        // the server computes it from the moment the first pass started.
        mocks.adminApi.refreshCompany.mockRejectedValue(
            new ApiError('Požiadavka sa už spracúva. Skúste to znova o 12 minút.', 409),
        );
        const button = await renderAsStaff();

        await user.click(button);

        const alert = await screen.findByRole('alert');
        expect(alert).toHaveTextContent('Skúste to znova o 12 minút');
        expect(alert).not.toHaveTextContent('already_running');
    });

    it('shows a failed refresh instead of leaving it in the console', async () => {
        const user = userEvent.setup();
        mocks.adminApi.refreshCompany.mockRejectedValue(new ApiError('Dispatch failed: broker je nedostupný', 502));
        const button = await renderAsStaff();

        await user.click(button);

        expect(await screen.findByRole('alert')).toHaveTextContent('broker je nedostupný');
    });

    it('disables the button while the request is in flight', async () => {
        const user = userEvent.setup();
        let release: (value: unknown) => void = () => {};
        mocks.adminApi.refreshCompany.mockReturnValue(new Promise(resolve => { release = resolve; }));
        const button = await renderAsStaff();

        await user.click(button);

        // A second click during the cooldown window is a 409 at best, and the
        // button is the only thing that can say the request is still out.
        expect(await screen.findByRole('button', {name: /Obnovujem/})).toBeDisabled();

        release(dispatch());
        // Resolved inside `waitFor`, so the update it causes is wrapped in act.
        await waitFor(() => expect(screen.getByRole('button', {name: /Aktualizovať údaje/})).toBeEnabled());
        expect(screen.getByRole('status')).toHaveTextContent('Obnova spustená');
    });
});

describe('CompanyHeader — sídlo na mape', () => {
    const seat = {
        lat: 48.14748,
        lon: 17.14051,
        radiusM: 737,
        psc: '82109',
        precision: 'postal_code' as const,
        pending: false,
    };

    it('leaves the card out entirely when the seat cannot be placed', () => {
        // 1,92 % of our rows carry a PSČ the address register does not list --
        // post-office PSČ with no address point. The address line above is the
        // whole truth for those, and a card reading "poloha neznáma" would be a
        // worse answer than no card at all.
        renderWithProviders(
            <CompanyHeader company={makeCompany({ico, seatLocation: null})} profile={profile}/>,
        );

        expect(screen.queryByText('Sídlo na mape')).not.toBeInTheDocument();
    });

    it('shows the map card for a seat the register can place', () => {
        renderWithProviders(
            <CompanyHeader company={makeCompany({ico, seatLocation: seat})} profile={profile}/>,
        );

        expect(screen.getByText('Sídlo na mape')).toBeInTheDocument();
        expect(screen.getByText(/· presnosť/)).toHaveTextContent('±737 m');
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
