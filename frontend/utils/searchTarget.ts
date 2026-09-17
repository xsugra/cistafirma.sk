import {ROUTES, companyPath} from '../constants';
import {DEFAULT_SECTION_ID} from '../companySections';
import {looksLikeIco} from './ico';

/**
 * Where a typed query sends the reader.
 *
 * The search box stands on four pages -- home, the search page, a firm and a
 * person -- and it makes the same decision on each of them: an IČO is a firm,
 * anything else is a query for the search page to answer. One copy of that rule
 * is what keeps the four from disagreeing, and `looksLikeIco` already carries
 * the half of it that was learned the hard way (a six- or twelve-digit IČO is a
 * real one, and sending it down the name path returned a list of firms whose
 * names merely contain those digits).
 *
 * `null` for an empty box. Submitting nothing is not a failed search, and there
 * is no page to send it to.
 */
export const searchTarget = (query: string): string | null => {
    const trimmed = query.trim();
    if (!trimmed) return null;
    if (looksLikeIco(trimmed)) return companyPath(trimmed, DEFAULT_SECTION_ID);
    return `${ROUTES.MONITORING}?ico=${encodeURIComponent(trimmed)}`;
};
