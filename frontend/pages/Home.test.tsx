import {beforeEach, describe, expect, it, vi} from 'vitest';
import {screen} from '@testing-library/react';
import {Home} from './Home';
import {renderWithProviders} from '../test/testUtils';

const mocks = vi.hoisted(() => ({
    api: {getLandingStats: vi.fn()},
}));
vi.mock('../api', () => ({api: mocks.api}));

describe('Home (pricing-removal regression)', () => {
    beforeEach(() => {
        mocks.api.getLandingStats.mockResolvedValue({
            companiesIndexed: 1250000,
            dailyChecks: 45000,
            riskyCompaniesDetected: 120,
        });
    });

    it('renders the monitoring hero CTA and no "Pozrieť Cenník" button', async () => {
        renderWithProviders(<Home/>, {route: '/'});
        // findBy* polls inside act(), letting the getLandingStats microtask settle.
        expect(await screen.findByRole('button', {name: /spustiť monitoring/i})).toBeInTheDocument();
        expect(screen.queryByRole('button', {name: /pozrieť cenník/i})).not.toBeInTheDocument();
        expect(mocks.api.getLandingStats).toHaveBeenCalledTimes(1);
    });

    it('does not put a window in a label whose number has none', async () => {
        // `riskyCompaniesDetected` is every company with a recorded debt --
        // cumulative, no date filter anywhere in the view. The label said
        // "Odhalených rizík dnes", so the public homepage claimed a daily figure
        // for an all-time count. This is the whole test: the two have to agree,
        // and nothing else on the page reveals it when they stop.
        renderWithProviders(<Home/>, {route: '/'});

        await screen.findByText(/Indexovaných firiem/);

        const cumulative = screen.getByText('Firiem s evidovaným dlhom');
        // No window word in the label whose number has no window. Asserted on
        // the label itself rather than on the page, because the stat beside it
        // legitimately says "dnes".
        expect(cumulative.textContent).not.toMatch(/dnes|týždeň|za \d+ dní/);
        expect(screen.queryByText('Odhalených rizík dnes')).not.toBeInTheDocument();

        // `dailyChecks` genuinely is a daily figure -- of register changes, which
        // is what its label now says. The old label called them checks; the
        // number comes from RUZ's own record-modification date.
        expect(screen.getByText('Zmien v registri dnes')).toBeInTheDocument();
        expect(screen.queryByText('Denných kontrol')).not.toBeInTheDocument();
    });
});
