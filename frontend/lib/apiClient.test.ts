import {afterEach, beforeEach, describe, expect, it, vi} from 'vitest';
import {apiRequest, ApiError} from './apiClient';
import {clearSession, getAccessToken, saveSession} from './tokenStore';

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

/**
 * A response good enough for both halves of `apiRequest`: `parseErrors` reads
 * `text()`, the success path reads `json()`.
 */
const answer = (status: number, body: unknown = {}) => ({
    ok: status >= 200 && status < 300,
    status,
    json: async () => body,
    text: async () => JSON.stringify(body),
});

const REFRESH_URL = '/api/auth/token/refresh/';

beforeEach(() => {
    clearSession();
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

/**
 * The other refusal that carries its own length.
 *
 * The company refresh answers a second click with `409 {detail: "already_running",
 * retry_after_seconds: …}` -- a machine token and a number. `data.detail` would
 * put the token on screen and drop the number beside it, which is the half of
 * the answer a reader can use. So the status alone is not enough to recognise
 * this body: it is the field that makes it that refusal, and a 409 from
 * elsewhere that carries only a sentence must still come through as written.
 */
describe('apiRequest — a refusal that states its own wait', () => {
    it('turns the machine token and the number into a sentence', async () => {
        respondWith(409, {detail: 'already_running', retry_after_seconds: 720});

        await expect(apiRequest('/admin/companies/1/refresh/', {method: 'POST'})).rejects.toThrow(
            'Požiadavka sa už spracúva. Skúste to znova o 12 minút.',
        );
    });

    it('says the wait in the unit it is actually in', async () => {
        // The window is fifteen minutes, but the number sent is what is *left* of
        // it -- so a pass most of the way through states seconds, and a sentence
        // that assumed minutes would round it to nothing.
        respondWith(409, {detail: 'already_running', retry_after_seconds: 40});

        await expect(apiRequest('/admin/companies/1/refresh/', {method: 'POST'})).rejects.toThrow(
            'Požiadavka sa už spracúva. Skúste to znova o 40 s.',
        );
    });

    it('leaves a 409 that states no wait alone', async () => {
        // The RUZ pause and cancel guards answer 409 too, with a Slovak sentence
        // and no number. Matching on the status would replace one of those
        // sentences with a cooldown it does not have.
        respondWith(409, {detail: 'Synchronizácia je pozastavená.'});

        await expect(apiRequest('/admin/sync/ruz/cancel/', {method: 'POST'})).rejects.toThrow(
            'Synchronizácia je pozastavená.',
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

/**
 * The session outliving its access token.
 *
 * An access token lives 30 minutes and the app used to treat the first 401 as
 * final, so a reader was signed out 30 minutes after signing in -- which is what
 * "I have to sign in again every time the page loads" was. These tests pin the
 * path that replaced it, and the three ways it must not misbehave: refreshing on
 * a sign-in, refreshing more than once for one expiry, and promoting a session
 * the reader asked not to be remembered.
 */
describe('apiRequest — an expired access token', () => {
    it('refreshes once, then repeats the request that was refused', async () => {
        saveSession({access: 'stale', refresh: 'refresh-1'}, true);
        const fetchMock = vi
            .fn()
            .mockResolvedValueOnce(answer(401, {detail: 'token_not_valid'}))
            .mockResolvedValueOnce(answer(200, {access: 'fresh', refresh: 'refresh-2'}))
            .mockResolvedValueOnce(answer(200, {results: []}));
        vi.stubGlobal('fetch', fetchMock);

        await expect(apiRequest('/companies/?q=eset')).resolves.toEqual({results: []});

        expect(fetchMock).toHaveBeenCalledTimes(3);
        expect(fetchMock.mock.calls[1][0]).toBe(REFRESH_URL);
        // The repeat carries the new token, not the one that was refused.
        expect(fetchMock.mock.calls[2][1].headers.Authorization).toBe('Bearer fresh');
        expect(getAccessToken()).toBe('fresh');
    });

    it('asks once for a refresh when several requests are refused together', async () => {
        // A company page fires its firm, its people and its financials at once;
        // with the access token expired they all answer 401 in the same tick.
        // Each refreshing on its own would rotate the token several times over
        // and leave every response but the last holding a superseded one.
        saveSession({access: 'stale', refresh: 'refresh-1'}, true);
        const notYetRetried = new Set(['/api/one/', '/api/two/']);
        const refreshCalls: string[] = [];
        // The header of every request that got through, so the test can say
        // *which* token the repeats carried rather than only how many there were.
        const repeatedWith: (string | undefined)[] = [];
        vi.stubGlobal(
            'fetch',
            vi.fn(async (url: string, init?: RequestInit) => {
                if (url === REFRESH_URL) {
                    refreshCalls.push(url);
                    return answer(200, {access: 'fresh', refresh: 'refresh-2'});
                }
                if (notYetRetried.delete(url)) return answer(401, {detail: 'token_not_valid'});
                repeatedWith.push(
                    (init?.headers as Record<string, string> | undefined)?.Authorization,
                );
                return answer(200, {ok: true});
            }),
        );

        await Promise.all([apiRequest('/one/'), apiRequest('/two/')]);

        expect(refreshCalls).toHaveLength(1);
        expect(repeatedWith).toEqual(['Bearer fresh', 'Bearer fresh']);
    });

    it('does not refresh a sign-in that was refused', async () => {
        // A 401 from `/auth/token/` is the answer to "is this password right",
        // not an expiry. Refreshing here would spend a request to be told the
        // same thing again -- and with a stale session in storage it would do so
        // on behalf of somebody else's sign-in attempt.
        saveSession({access: 'stale', refresh: 'refresh-1'}, true);
        const fetchMock = vi.fn().mockResolvedValue(answer(401, {detail: 'No active account'}));
        vi.stubGlobal('fetch', fetchMock);

        await expect(
            apiRequest('/auth/token/', {method: 'POST', body: '{}'}),
        ).rejects.toThrow('Platnosť prihlásenia vypršala');

        expect(fetchMock).toHaveBeenCalledTimes(1);
        expect(fetchMock.mock.calls[0][0]).toBe('/api/auth/token/');
    });

    it('clears the session and announces it when the refresh is refused too', async () => {
        // A refresh token lives one day; past that there is nothing left to
        // recover with and the reader has to sign in.
        saveSession({access: 'stale', refresh: 'spent'}, true);
        const unauthorized = vi.fn();
        window.addEventListener('auth:unauthorized', unauthorized);
        const fetchMock = vi
            .fn()
            .mockResolvedValueOnce(answer(401, {detail: 'token_not_valid'}))
            .mockResolvedValueOnce(answer(401, {detail: 'token_not_valid'}));
        vi.stubGlobal('fetch', fetchMock);

        await expect(apiRequest('/companies/?q=eset')).rejects.toThrow(
            'Platnosť prihlásenia vypršala. Prihláste sa prosím znova.',
        );

        expect(getAccessToken()).toBeNull();
        expect(localStorage.getItem('refresh_token')).toBeNull();
        expect(unauthorized).toHaveBeenCalledTimes(1);
        window.removeEventListener('auth:unauthorized', unauthorized);
    });

    it('does not touch the network for a session with no refresh token', async () => {
        // `ENABLE_MOCK_DATA` signs in without one. There is nothing to refresh
        // against, so the request that was refused is not repeated either.
        saveSession({access: 'stale', refresh: null}, true);
        const fetchMock = vi.fn().mockResolvedValue(answer(401, {detail: 'token_not_valid'}));
        vi.stubGlobal('fetch', fetchMock);

        await expect(apiRequest('/companies/?q=eset')).rejects.toThrow(
            'Platnosť prihlásenia vypršala',
        );

        expect(fetchMock).toHaveBeenCalledTimes(1);
    });
});
