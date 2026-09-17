/**
 * Where the session's two tokens live.
 *
 * The app kept one access token in `localStorage` and nothing else. The backend
 * has always sent a refresh token alongside it and the frontend dropped it, so
 * there was no way back from an expired access token: 30 minutes after signing
 * in, the next request answered 401, `apiClient` treated that as final and the
 * reader was signed out -- which is what "I have to sign in again every time the
 * page loads" was.
 *
 * Two tokens now, and they are kept together in one of two storages:
 *
 * - `localStorage` when "Zapamätať prihlásenie" is ticked, so the session
 *   survives closing the browser;
 * - `sessionStorage` when it is not, so the session ends with the tab.
 *
 * Every reader goes through this module. Nothing else may touch the keys
 * directly: with two storages there are two places a token can hide, and a
 * component that reads only one of them sees a signed-out reader who is not one.
 */
const ACCESS_KEY = 'token';
const REFRESH_KEY = 'refresh_token';

export interface TokenBundle {
  access: string;
  /** Absent only for a mock sign-in, which has no backend to refresh against. */
  refresh: string | null;
}

/**
 * The storage holding the session, or the one a new session should use.
 *
 * `localStorage` wins when both hold a token, which cannot happen through this
 * module -- `saveSession` empties both before writing -- but a token left behind
 * by an older build can be there, and the remembered session is the one to keep.
 */
function activeStorage(): Storage {
  return localStorage.getItem(ACCESS_KEY) !== null ? localStorage : sessionStorage;
}

export function getAccessToken(): string | null {
  return localStorage.getItem(ACCESS_KEY) ?? sessionStorage.getItem(ACCESS_KEY);
}

export function getRefreshToken(): string | null {
  return localStorage.getItem(REFRESH_KEY) ?? sessionStorage.getItem(REFRESH_KEY);
}

/** Leaves no copy of a session in the other storage. */
export function clearSession(): void {
  for (const storage of [localStorage, sessionStorage]) {
    storage.removeItem(ACCESS_KEY);
    storage.removeItem(REFRESH_KEY);
  }
}

/** A sign-in, which decides where the session will live. */
export function saveSession(tokens: TokenBundle, remember: boolean): void {
  clearSession();
  const storage = remember ? localStorage : sessionStorage;
  storage.setItem(ACCESS_KEY, tokens.access);
  if (tokens.refresh) storage.setItem(REFRESH_KEY, tokens.refresh);
}

/**
 * A refresh replaced the tokens; they stay where the session already is.
 *
 * Not `saveSession`: a reader who did not ask to be remembered must not become
 * remembered because their access token happened to expire.
 */
export function updateSession(tokens: TokenBundle): void {
  const storage = activeStorage();
  storage.setItem(ACCESS_KEY, tokens.access);
  if (tokens.refresh) storage.setItem(REFRESH_KEY, tokens.refresh);
}
