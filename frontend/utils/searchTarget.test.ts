import {describe, expect, it} from 'vitest';
import {searchTarget} from './searchTarget';

describe('searchTarget', () => {
    it('sends an IČO straight to the firm, skipping the search page', () => {
        // Straight there, not through `/monitoring?ico=`: a number the reader
        // typed is not a query to be answered with a list.
        expect(searchTarget('35757442')).toBe('/firma/35757442/prehlad');
    });

    it('takes a twelve-character IČO, which is a real one', () => {
        // An organizational unit: the parent's IČO plus a serial. It used to be
        // searched by name, so the reader typed an IČO and got a list of firms
        // whose names contain those digits.
        expect(searchTarget('001781521576')).toBe('/firma/001781521576/prehlad');
    });

    it('sends anything else to the search page as a query', () => {
        expect(searchTarget('ESET')).toBe('/monitoring?ico=ESET');
    });

    it('encodes the query, so a name with a space or a diacritic survives', () => {
        // The value rides in a URL that a human can read and edit. A raw `&` or
        // `#` in a firm's name would otherwise cut the query in half.
        expect(searchTarget('Iná Firma, s. r. o.')).toBe(
            '/monitoring?ico=In%C3%A1%20Firma%2C%20s.%20r.%20o.',
        );
        expect(searchTarget('A & B')).toBe('/monitoring?ico=A%20%26%20B');
    });

    it('trims, and treats an empty box as no destination at all', () => {
        // Submitting nothing is not a failed search, and there is no page to
        // send it to -- the caller is told so rather than handed `/monitoring`.
        expect(searchTarget('  35757442  ')).toBe('/firma/35757442/prehlad');
        expect(searchTarget('')).toBeNull();
        expect(searchTarget('   ')).toBeNull();
    });

    it('does not treat a digit string outside the IČO range as one', () => {
        // Below six digits the API refuses it too, so redirecting there would
        // turn a search into a dead link.
        expect(searchTarget('12345')).toBe('/monitoring?ico=12345');
    });
});
