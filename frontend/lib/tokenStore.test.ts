import {beforeEach, describe, expect, it} from 'vitest';
import {
    clearSession,
    getAccessToken,
    getRefreshToken,
    saveSession,
    updateSession,
} from './tokenStore';

/**
 * The two storages are the whole point of this module, so every test reads both
 * of them. Asserting only on the one that should hold the token would pass for
 * a store that wrote to both -- which is the bug this exists to prevent: a
 * reader who did not ask to be remembered, left remembered.
 */
const SESSION = {access: 'access-1', refresh: 'refresh-1'};

beforeEach(() => {
    clearSession();
});

describe('tokenStore', () => {
    it('remembers a session in localStorage when asked to', () => {
        saveSession(SESSION, true);

        expect(localStorage.getItem('token')).toBe('access-1');
        expect(localStorage.getItem('refresh_token')).toBe('refresh-1');
        expect(sessionStorage.getItem('token')).toBeNull();
        expect(getAccessToken()).toBe('access-1');
        expect(getRefreshToken()).toBe('refresh-1');
    });

    it('keeps an unremembered session in sessionStorage, so it ends with the tab', () => {
        saveSession(SESSION, false);

        expect(sessionStorage.getItem('token')).toBe('access-1');
        expect(sessionStorage.getItem('refresh_token')).toBe('refresh-1');
        expect(localStorage.getItem('token')).toBeNull();
        expect(localStorage.getItem('refresh_token')).toBeNull();
        expect(getAccessToken()).toBe('access-1');
    });

    it('leaves no copy of the previous session behind on a new sign-in', () => {
        // Sign in remembered, then sign in again unticked. The first session's
        // tokens must not survive in `localStorage`, or the box would be a lie
        // for the rest of that browser's life.
        saveSession(SESSION, true);
        saveSession({access: 'access-2', refresh: 'refresh-2'}, false);

        expect(localStorage.getItem('token')).toBeNull();
        expect(localStorage.getItem('refresh_token')).toBeNull();
        expect(getAccessToken()).toBe('access-2');
    });

    it('does not promote an unremembered session when a refresh replaces its tokens', () => {
        // The one place this could go wrong quietly: a reader who unticked the
        // box, whose access token then expires, must not end up remembered
        // because of it.
        saveSession(SESSION, false);

        updateSession({access: 'access-2', refresh: 'refresh-2'});

        expect(localStorage.getItem('token')).toBeNull();
        expect(sessionStorage.getItem('token')).toBe('access-2');
        expect(sessionStorage.getItem('refresh_token')).toBe('refresh-2');
    });

    it('keeps a remembered session remembered when a refresh replaces its tokens', () => {
        saveSession(SESSION, true);

        updateSession({access: 'access-2', refresh: 'refresh-2'});

        expect(localStorage.getItem('token')).toBe('access-2');
        expect(localStorage.getItem('refresh_token')).toBe('refresh-2');
        expect(sessionStorage.getItem('token')).toBeNull();
    });

    it('clears both storages, whichever one holds the session', () => {
        saveSession(SESSION, false);
        clearSession();
        expect(getAccessToken()).toBeNull();
        expect(getRefreshToken()).toBeNull();

        saveSession(SESSION, true);
        clearSession();
        expect(getAccessToken()).toBeNull();
        expect(getRefreshToken()).toBeNull();
        expect(localStorage.getItem('refresh_token')).toBeNull();
    });

    it('reports no session at all when there is none', () => {
        // The distinction `AuthContext.initAuth` is built on: no token means no
        // request, rather than a request that has to fail first.
        expect(getAccessToken()).toBeNull();
        expect(getRefreshToken()).toBeNull();
    });
});
