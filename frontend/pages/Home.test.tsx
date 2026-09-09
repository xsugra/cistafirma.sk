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
});
