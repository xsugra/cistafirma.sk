import { ROUTES } from '../constants';

/**
 * Where to send a reader after they sign in or register.
 *
 * `from` is set by whatever sent them to the auth pages -- today, the
 * "Sledovať" button on a company page, which is `IsAuthenticated` and used to
 * fail silently for an anonymous visitor. Landing everyone on the home page
 * instead meant that a reader who clicked *watch this company* was, after
 * signing in, no longer looking at the company: the thing they asked for was
 * three clicks back through a search.
 *
 * The path travels in router state rather than a query parameter, so it does
 * not end up in a URL anyone can share or bookmark pointing at somebody else's
 * destination.
 *
 * **Only same-origin paths are accepted.** Router state is client-side, but it
 * is still attacker-influenceable in principle -- a link crafted so that `from`
 * is `https://evil.example` would turn the sign-in page into an open redirect:
 * a phishing hop that begins on a URL the reader trusts. Requiring a leading
 * `/` and rejecting `//` covers both the absolute form and the protocol-relative
 * one, which browsers treat as absolute.
 *
 * One function rather than one per page, because the guard is the part that
 * matters and a second copy is a second place for it to be dropped.
 */
export function postAuthDestination(state: unknown): string {
    const from = (state as { from?: unknown } | null)?.from;
    if (typeof from !== 'string') return ROUTES.HOME;
    if (!from.startsWith('/') || from.startsWith('//')) return ROUTES.HOME;
    return from;
}
