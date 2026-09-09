import {describe, expect, it} from 'vitest';
import * as constants from './constants';
import {ROUTES} from './constants';

describe('constants (pricing-removal regression)', () => {
    it('no longer exposes a PRICING route member', () => {
        expect('PRICING' in ROUTES).toBe(false);
        expect(Object.keys(ROUTES)).not.toContain('PRICING');
    });

    it('no longer exposes PRICING_PLANS', () => {
        expect('PRICING_PLANS' in constants).toBe(false);
    });

    it('keeps the canonical navigation routes', () => {
        expect(ROUTES.HOME).toBe('/');
        expect(ROUTES.MONITORING).toBe('/monitoring');
        expect(ROUTES.PROFILE).toBe('/profile');
    });
});
