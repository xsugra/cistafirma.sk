import { API_BASE_URL } from '../constants';
import { clearSession, getAccessToken, getRefreshToken, updateSession } from './tokenStore';

const ERROR_TRANSLATIONS: Record<string, string> = {
  'user with this email address already exists.': 'Používateľ s týmto emailom už existuje.',
  'user with this username already exists.': 'Používateľ s týmto menom už existuje.',
  'This field may not be blank.': 'Toto pole nesmie byť prázdne.',
  'Enter a valid email address.': 'Zadajte platnú emailovú adresu.',
  'Invalid username/password.': 'Nesprávne meno alebo heslo.',
  'No active account found with the given credentials': 'Účet s týmito údajmi neexistuje.',
};

/**
 * A failed request, carrying the status it failed with.
 *
 * The status used to be thrown away with the `Response`: every caller got a
 * plain `Error` and could only read the message. That is enough to show
 * something, and not enough to *decide* anything -- the person page has to tell
 * "this person does not exist" (404, its own screen) from "the server is
 * broken" (its own too), and with only a string the two are the same shape.
 * Matching the server's Slovak sentence instead would make a copy change a bug.
 *
 * Still an `Error`, so every existing `catch (err) { err.message }` keeps
 * working unchanged.
 */
export class ApiError extends Error {
  readonly status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
  }
}

/** Slovak needs three plural forms where English needs two. */
function skPlural(n: number, one: string, few: string, many: string): string {
  if (n === 1) return `1 ${one}`;
  if (n >= 2 && n <= 4) return `${n} ${few}`;
  return `${n} ${many}`;
}

/** A wait in seconds, as a phrase a person reads rather than a number. */
function formatWait(seconds: number): string {
  if (!Number.isFinite(seconds) || seconds <= 0) return 'chvíľu';
  if (seconds < 60) return `${Math.ceil(seconds)} s`;
  const minutes = Math.ceil(seconds / 60);
  if (minutes < 60) return skPlural(minutes, 'minútu', 'minúty', 'minút');
  return skPlural(Math.ceil(minutes / 60), 'hodinu', 'hodiny', 'hodín');
}

/**
 * DRF's throttled body, in Slovak.
 *
 * `ERROR_TRANSLATIONS` is an exact-match table and can never hold this one: the
 * wait is part of the sentence, so "Request was throttled. Expected available in
 * 3600 seconds." is a different string every time it is sent. Left to
 * `data.detail`, it reaches the screen as English under a Slovak heading -- and
 * this is not an exotic path here. The ORSR person search is limited to 60
 * requests an hour per caller, so a reader who trips it is exactly the reader
 * who needs to be told what happened and how long to wait.
 */
function translateThrottle(detail: unknown): string {
  const wait = /Expected available in (\d+) seconds?/.exec(String(detail ?? ''));
  return wait
    ? `Príliš mnoho požiadaviek. Skúste to znova o ${formatWait(Number(wait[1]))}.`
    : 'Príliš mnoho požiadaviek. Skúste to znova neskôr.';
}

async function parseErrors(response: Response): Promise<string> {
  try {
    const text = await response.text();
    let data: any;
    try {
      data = JSON.parse(text);
    } catch {
      if (response.status === 403) {
        if (text.includes('Origin checking failed')) {
          return 'Django Konfigurácia: Pridajte frontend origin do CSRF_TRUSTED_ORIGINS.';
        }
        if (text.includes('CSRF') || text.includes('Forbidden')) {
          return 'Chyba servera: CSRF overenie zlyhalo.';
        }
      }
      return text.slice(0, 150) || `HTTP Error: ${response.status}`;
    }

    if (data.code === 'token_not_valid') return 'Platnosť prihlásenia vypršala.';
    if (response.status === 429) return translateThrottle(data.detail);
    if (data.detail) return data.detail;

    if (typeof data === 'object') {
      const messages = Object.entries(data)
        .map(([key, val]) => {
          if (key === 'code' || key === 'messages') return null;
          const fieldName = key.replace(/_/g, ' ').replace(/^\w/, (c) => c.toUpperCase());
          let errorMsg = Array.isArray(val) ? val.join(' ') : String(val);
          if (ERROR_TRANSLATIONS[errorMsg]) errorMsg = ERROR_TRANSLATIONS[errorMsg];
          return `${fieldName}: ${errorMsg}`;
        })
        .filter(Boolean)
        .join(' | ');
      return messages || 'Neznáma chyba servera.';
    }
    return 'Neznáma chyba servera.';
  } catch {
    return `HTTP Error: ${response.status}`;
  }
}

/**
 * The endpoints that mint tokens.
 *
 * A 401 from either is an answer to what was asked -- a wrong password, a spent
 * refresh token -- and not an expiry to recover from. Refreshing on one of them
 * would spend a request to be told the same thing twice.
 */
const TOKEN_ENDPOINTS = '/auth/token';

/**
 * One refresh, however many requests are refused at once.
 *
 * A page that loads a firm and its people and its financials fires several
 * requests together; when the access token has expired they all answer 401 in
 * the same tick. Without a single shared promise each one would POST its own
 * refresh, and the rotation would leave all but the last response holding a
 * refresh token that has already been superseded.
 */
let refreshInFlight: Promise<string | null> | null = null;

async function refreshAccessToken(): Promise<string | null> {
  const refresh = getRefreshToken();
  if (!refresh) return null;

  if (!refreshInFlight) {
    refreshInFlight = (async () => {
      try {
        const response = await fetch(`${API_BASE_URL}${TOKEN_ENDPOINTS}/refresh/`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ refresh }),
        });
        if (!response.ok) return null;
        const data = await response.json();
        if (!data?.access) return null;
        // The backend rotates: this answer carries a new refresh token with a
        // fresh lifetime, and that is what makes a session slide forward instead
        // of ending one day after it began.
        updateSession({ access: data.access, refresh: data.refresh ?? null });
        return data.access as string;
      } catch {
        return null;
      }
    })();
    refreshInFlight.finally(() => {
      refreshInFlight = null;
    });
  }

  return refreshInFlight;
}

export async function apiRequest<T>(
  endpoint: string,
  options: RequestInit = {},
  baseUrl: string = API_BASE_URL,
): Promise<T> {
  const send = (token: string | null) =>
    fetch(`${baseUrl}${endpoint}`, {
      ...options,
      headers: {
        'Content-Type': 'application/json',
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
        ...((options.headers as Record<string, string>) || {}),
      },
    });

  let response = await send(getAccessToken());

  // An access token lives 30 minutes. A session that is still usable must not
  // end there: refresh once, silently, and repeat the request that was refused.
  if (response.status === 401 && !endpoint.startsWith(TOKEN_ENDPOINTS)) {
    const refreshed = await refreshAccessToken();
    if (refreshed) response = await send(refreshed);
  }

  // Reached when there was no refresh token, when the refresh itself was
  // refused, or when the retry was refused too -- all three mean the same thing
  // to the reader, and none of them is survivable without a sign-in.
  if (response.status === 401) {
    clearSession();
    window.dispatchEvent(new CustomEvent('auth:unauthorized'));
    throw new ApiError('Platnosť prihlásenia vypršala. Prihláste sa prosím znova.', 401);
  }

  if (!response.ok) {
    const errorMessage = await parseErrors(response);
    throw new ApiError(errorMessage, response.status);
  }

  if (response.status === 204) return {} as T;
  return response.json();
}
