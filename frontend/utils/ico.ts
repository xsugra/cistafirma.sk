/**
 * "Is this a query someone typed an IČO into, rather than a name?"
 *
 * The answer is not "eight digits", which is what this codebase assumed in two
 * places. RUZ returns organizational units a **twelve**-character IČO
 * (`001781521576` — the parent's `00178152` plus a four-digit serial), so an
 * eight-digit test sent a perfectly valid IČO down the *name* search path: the
 * reader typed an IČO, got a list of companies whose names contain those digits,
 * and no page for the company they asked for.
 *
 * Six to twenty digits, matching the backend's own `_ICO_RE` in
 * `backend/notifications/views.py`. That is deliberately the same range rather
 * than a second opinion about what an IČO looks like: an input this accepts and
 * the API rejects is a redirect into a 404, and an input this rejects while the
 * API accepts it is the bug above.
 *
 * Whitespace is trimmed, because it arrives from a URL or a text field.
 */
const ICO_QUERY = /^\d{6,20}$/;

export const looksLikeIco = (value: string | null | undefined): boolean =>
    ICO_QUERY.test((value ?? '').trim());
