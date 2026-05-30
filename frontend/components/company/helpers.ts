import type { OrsrPerson, OrsrContribution, OrsrCapital } from '../../types';

export const formatDate = (value?: string): string => {
    if (!value) return '';
    if (/^\d{4}-\d{2}-\d{2}$/.test(value)) {
        const [y, m, d] = value.split('-');
        return `${d}.${m}.${y}`;
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
