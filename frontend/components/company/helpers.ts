import type { OrsrPerson, OrsrContribution, OrsrCapital } from '../../types';

/**
 * A date to `DD.MM.YYYY`, from either a date or a timestamp.
 *
 * The two are handled differently on purpose, and both differences matter:
 *
 * - A **date-only** value (`2015-01-30`, which is what most register fields
 *   hold) is reformatted as a string and never goes near `Date`. `new
 *   Date('2015-01-30')` is parsed as UTC midnight, so for any reader west of
 *   Greenwich it renders as the 29th -- a date moved by the viewer's timezone is
 *   a date that disagrees with the register.
 * - A **timestamp** (`2026-09-12T18:23:36.428310Z`, which is what the two
 *   "when did we last read this source" fields hold) is a moment, and the day it
 *   fell on is the reader's day, so it goes through the local clock. This is
 *   also what the debt rows already did before they were routed through here.
 *
 * Anything unparseable is returned unchanged, which is what the ORSR free-text
 * fields need.
 */
export const formatDate = (value?: string | null): string => {
    if (!value) return '';

    const dateOnly = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value);
    if (dateOnly) {
        const [, y, m, d] = dateOnly;
        return `${d}.${m}.${y}`;
    }

    const parsed = new Date(value);
    if (!Number.isNaN(parsed.getTime())) {
        const pad = (n: number) => String(n).padStart(2, '0');
        return `${pad(parsed.getDate())}.${pad(parsed.getMonth() + 1)}.${parsed.getFullYear()}`;
    }

    return value;
};

export const displayName = (person: OrsrPerson): string => {
    const parts = [person.title, person.name].filter(Boolean);
    return parts.join(' ').trim() || person.name || '';
};

export const normalizePeople = (value: unknown): OrsrPerson[] => {
    if (!Array.isArray(value)) return [];
    return value
        .map((item): OrsrPerson | null => {
            if (!item) return null;
            if (typeof item === 'string') {
                return item.trim() ? { name: item.trim() } : null;
            }
            if (typeof item === 'object') {
                const person = item as OrsrPerson;
                return person.name ? person : null;
            }
            return null;
        })
        .filter((p): p is OrsrPerson => p !== null);
};

export const trimOrsrNumber = (raw: string): string => {
    return raw.replace(/(\d),(\d{2})(\d+)/g, (_m, intPart, twoDec, _rest) => `${intPart},${twoDec}`);
};

export const normalizeAmountText = (raw?: string | null): string => {
    if (!raw) return '';
    return trimOrsrNumber(raw).trim();
};

export const formatCapital = (capital?: OrsrCapital | null, fallback?: string): string => {
    if (capital && capital.imanie) {
        const imanie = trimOrsrNumber(capital.imanie);
        const currency = capital.currency || 'EUR';
        const parts = [`${imanie} ${currency}`.trim()];
        if (capital.rozsah_splatenia) {
            const splatene = trimOrsrNumber(capital.rozsah_splatenia);
            parts.push(`splatené ${splatene} ${currency}`.trim());
        }
        return parts.join(' • ');
    }
    return normalizeAmountText(fallback);
};

export const formatContribution = (contrib: OrsrContribution): string => {
    if (contrib.summary) return contrib.summary;
    const parts = [];
    if (contrib.name) parts.push(contrib.name);
    if (contrib.vklad) parts.push(`vklad ${contrib.vklad} ${contrib.currency || 'EUR'}`);
    if (contrib.splatene) parts.push(`splatené ${contrib.splatene} ${contrib.currency || 'EUR'}`);
    if (contrib.typ) parts.push(`(${contrib.typ})`);
    return parts.join(' • ');
};
