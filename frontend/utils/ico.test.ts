import {describe, expect, it} from 'vitest';
import {looksLikeIco} from './ico';

describe('looksLikeIco', () => {
    it('accepts a twelve-character IČO, which is why this exists', () => {
        // `001781521576` is a real RUZ record: the parent's `00178152` plus a
        // four-digit serial for an organizational unit. An eight-digit test sent
        // it to the name search, so the reader typed an IČO and got a list of
        // companies whose names happened to contain those digits.
        expect(looksLikeIco('001781521576')).toBe(true);
    });

    it('accepts a six-digit IČO', () => {
        // Old IČO the register still answers for, padded with zeros on the way
        // out. Storage keeps it stripped, so six digits is the shape we hold.
        expect(looksLikeIco('177474')).toBe(true);
    });

    it('accepts the ordinary eight digits', () => {
        expect(looksLikeIco('48097781')).toBe(true);
    });

    it('trims, because the value arrives from a URL or a text field', () => {
        expect(looksLikeIco('  48097781 ')).toBe(true);
        expect(looksLikeIco('48097781\n')).toBe(true);
    });

    it('refuses anything that is not digits', () => {
        // The point of the predicate: a name must not be answered with a
        // redirect to a company page.
        for (const value of ['ECKLIMA', '4809 7781', 'SK48097781', '48097781a']) {
            expect(looksLikeIco(value)).toBe(false);
        }
    });

    it('refuses a range that would only ever 404', () => {
        // Below six the backend refuses it too (`_ICO_RE` is 6-20 digits), and
        // accepting an input the API rejects turns a search into a dead link.
        expect(looksLikeIco('12345')).toBe(false);
        expect(looksLikeIco('1'.repeat(21))).toBe(false);
    });

    it('refuses empty and absent values', () => {
        expect(looksLikeIco('')).toBe(false);
        expect(looksLikeIco('   ')).toBe(false);
        expect(looksLikeIco(null)).toBe(false);
        expect(looksLikeIco(undefined)).toBe(false);
    });
});
