import {afterEach, describe, expect, it, vi} from 'vitest';
import {apiRequest, ApiError} from './apiClient';

/**
 * The error path of `apiRequest`, tested where it can actually lie.
 *
 * `parseErrors` returns `data.detail` verbatim, which is right for a serializer
 * that writes Slovak and wrong for DRF's own machinery, which writes English.
 * The throttled body is the case that reaches a real reader: the ORSR person
 * search allows 60 requests an hour per caller, so anyone who trips it sees the
 * message -- and it used to arrive as "Request was throttled. Expected available
 * in 3600 seconds." under a Slovak heading.
 *
 * The wait is part of DRF's sentence, so it can never be an entry in the
 * exact-match `ERROR_TRANSLATIONS` table. That is why this is a pattern and why
 * it is worth a test: a static key would look correct and match nothing.
 */
const respondWith = (status: number, body: unknown) => {
    vi.stubGlobal(
        'fetch',
        vi.fn().mockResolvedValue({
            ok: status >= 200 && status < 300,
            status,
            text: async () => JSON.stringify(body),
        }),
    );
};

afterEach(() => {
    vi.unstubAllGlobals();
});

describe('apiRequest — the throttled answer', () => {
    it('says it in Slovak, with the wait DRF sent', async () => {
        respondWith(429, {
            detail: 'Request was throttled. Expected available in 3600 seconds.',
        });

        await expect(apiRequest('/persons/orsr/?q=trnka')).rejects.toThrow(
            'Príliš mnoho požiadaviek. Skúste to znova o 1 hodinu.',
        );
    });

    it('reads the wait out of the sentence rather than assuming an hour', async () => {
        // A per-minute throttle sends a different number in the same sentence.
        respondWith(429, {
            detail: 'Request was throttled. Expected available in 45 seconds.',
        });

        await expect(apiRequest('/persons/orsr/?q=trnka')).rejects.toThrow(
            'Príliš mnoho požiadaviek. Skúste to znova o 45 s.',
        );
    });

    it('still says something in Slovak when DRF gives no wait at all', async () => {
        // A proxy or a custom throttle may send a 429 with a body we do not
        // recognise. The one thing it must never do is fall through to English.
        respondWith(429, {detail: 'Too Many Requests'});

        await expect(apiRequest('/persons/orsr/?q=trnka')).rejects.toThrow(
            'Príliš mnoho požiadaviek. Skúste to znova neskôr.',
        );
    });
});

describe('apiRequest — ApiError carries the status', () => {
    it('exposes the status so a caller can tell 404 from a broken server', async () => {
        respondWith(404, {detail: 'Osoba nebola nájdená.'});

        const err = await apiRequest('/persons/999/').catch((e: unknown) => e);

        expect(err).toBeInstanceOf(ApiError);
        expect((err as ApiError).status).toBe(404);
        expect((err as ApiError).message).toBe('Osoba nebola nájdená.');
    });

    it('leaves a Slovak detail alone rather than translating it twice', async () => {
        respondWith(400, {detail: 'Zadajte aspoň 2 znaky.'});

        await expect(apiRequest('/persons/?q=t')).rejects.toThrow('Zadajte aspoň 2 znaky.');
    });
});
