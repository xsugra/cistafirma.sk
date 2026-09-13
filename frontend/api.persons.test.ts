import {describe, expect, it} from 'vitest';
import {
    mapOrsrPersonSearchResponse,
    mapPersonDetail,
    mapPersonRelation,
    mapPersonSearchResponse,
} from './api';

/**
 * The person mappers, tested directly for the same reason the company ones are.
 *
 * A mapper is the one place where "the API did not send this" can quietly
 * become a positive claim, and this contract has a third value to lose:
 * `is_active` is `true`, `false` or `null`, where `null` means we have never
 * read that company's history. Every ordinary way of writing a boolean --
 * `Boolean(x)`, `!!x`, `x || false` -- turns that `null` into `false`, which
 * prints "the function ended" about a company nobody checked. The compiler
 * cannot catch it, because the field is *meant* to be a boolean-ish. So it is
 * caught here.
 */
describe('mapPersonRelation', () => {
    const flat = {
        ico: '35757442',
        name: 'ESET, spol. s r. o.',
        role: 'konatel',
        role_display: 'Konateľ',
        is_active: true,
        vznik_funkcie: '2010-01-01',
        zanik_funkcie: null,
    };

    it('keeps the third answer as the third answer', () => {
        const relation = mapPersonRelation({...flat, is_active: null});

        expect(relation.is_active).toBeNull();
        expect(relation.is_active).not.toBe(false);
    });

    it('keeps a stated end as an end', () => {
        // The other half: `null` must not be produced by collapsing `false`.
        const relation = mapPersonRelation({...flat, is_active: false});

        expect(relation.is_active).toBe(false);
    });

    it('reads the flat shape the endpoint actually sends', () => {
        expect(mapPersonRelation(flat)).toMatchObject({
            ico: '35757442',
            name: 'ESET, spol. s r. o.',
            role_display: 'Konateľ',
            vznik_funkcie: '2010-01-01',
            zanik_funkcie: null,
        });
    });

    it('reads a nested company object too, rather than losing every company', () => {
        // The relation was described at one point as
        // `{company: {ico, nazov_UJ}, role, ...}`. Reading only the flat field
        // names would render every person as being in no company at all --
        // the same false claim, in the other direction and harder to spot.
        const relation = mapPersonRelation({
            company: {ico: '35757442', nazov_UJ: 'ESET, spol. s r. o.'},
            role: 'konatel',
            role_display: 'Konateľ',
            is_active: null,
        });

        expect(relation.ico).toBe('35757442');
        expect(relation.name).toBe('ESET, spol. s r. o.');
    });

    it('leaves an absent role label absent instead of printing the enum code', () => {
        const relation = mapPersonRelation({...flat, role_display: undefined});

        expect(relation.role_display).toBe('');
        expect(relation.role_display).not.toBe('konatel');
    });
});

describe('mapPersonSearchResponse', () => {
    const base = {
        query: 'trnka',
        role: '',
        results: [
            {
                id: 12345,
                name: 'Ing. Miroslav Trnka',
                title: 'Ing.',
                person_ico: '',
                companies: [],
            },
        ],
        total_matches: 3,
        truncated: false,
        coverage: {companies_with_persons: 19906, companies_total: 445626},
    };

    it('carries the coverage through, so the screen never has to invent it', () => {
        expect(mapPersonSearchResponse(base).coverage).toEqual({
            companies_with_persons: 19906,
            companies_total: 445626,
        });
    });

    it('does not turn a missing coverage into a coverage of zero', () => {
        // `Number(null)` is 0, so a conversion-first mapper would print
        // "0 z 0 firiem" -- a statement about our data that no response made.
        expect(mapPersonSearchResponse({...base, coverage: undefined}).coverage).toBeNull();
        expect(mapPersonSearchResponse({...base, coverage: null}).coverage).toBeNull();
    });

    it('keeps the API’s reason for an empty list', () => {
        const short = mapPersonSearchResponse({
            ...base,
            results: [],
            total_matches: 0,
            detail: 'Zadajte aspoň 2 znaky.',
        });

        expect(short.detail).toBe('Zadajte aspoň 2 znaky.');
        expect(short.results).toEqual([]);
    });

    it('gives a person with no companies an empty list rather than undefined', () => {
        const [person] = mapPersonSearchResponse(base).results;

        expect(person.companies).toEqual([]);
        expect(person.person_ico).toBe('');
    });

    it('does not turn an uncounted number of people into zero', () => {
        // `Number(null)` is 0, so a conversion-first mapper would answer "no
        // people" for a window that simply stopped short -- the opposite of
        // what the response said. Same trap as the coverage counts above.
        const uncounted = {...base, total_people: null};

        expect(mapPersonSearchResponse(uncounted).total_people).toBeNull();
        expect(mapPersonSearchResponse({...base, total_people: undefined}).total_people).toBeNull();
        expect(mapPersonSearchResponse({...base, total_people: 1}).total_people).toBe(1);
    });

    it('says how many rows a grouped answer gathered', () => {
        const grouped = mapPersonSearchResponse({
            ...base,
            results: [{...base.results[0], records: 3}],
        });

        expect(grouped.results[0].records).toBe(3);
    });

    it('reads an answer from before the field as the one row it was', () => {
        // One is the honest floor and not zero: a summary exists because at
        // least one row produced it.
        expect(mapPersonSearchResponse(base).results[0].records).toBe(1);
    });
});

describe('mapPersonDetail', () => {
    it('reads every relation the person endpoint sends', () => {
        const detail = mapPersonDetail({
            id: 12345,
            name: 'Miroslav Trnka',
            title: '',
            person_ico: '',
            companies: [
                {ico: '1', name: 'A', role: 'konatel', role_display: 'Konateľ', is_active: null},
                {ico: '2', name: 'B', role: 'spolocnik', role_display: 'Spoločník', is_active: false},
            ],
            coverage: {companies_with_persons: 1, companies_total: 2},
        });

        expect(detail.companies.map((c) => c.is_active)).toEqual([null, false]);
        expect(detail.coverage).toEqual({companies_with_persons: 1, companies_total: 2});
    });
});

describe('mapOrsrPersonSearchResponse', () => {
    const base = {
        query: 'Trnka',
        hits: [
            {
                person_name: 'Ing. Miroslav Trnka',
                company_name: 'ESET, spol. s r. o.',
                current_url: 'https://www.orsr.sk/vypis.asp?ID=1&SID=2&P=0',
                full_url: 'https://www.orsr.sk/vypis.asp?ID=1&SID=2&P=1',
            },
        ],
        total: 18,
        truncated: false,
        source_url: 'https://www.orsr.sk/hladaj_osoba.asp?PR=Trnka',
        error: '',
        note: 'Register vracia len mená firiem, nie funkciu.',
    };

    it('keeps an unreachable register unreachable instead of defaulting it away', () => {
        // `error` non-empty is the only signal that the register could not be
        // read, and a `|| ''` or a default here would render it as a list with
        // no rows -- a claim about a person invented out of a failed request.
        const failed = mapOrsrPersonSearchResponse({
            ...base,
            hits: [],
            total: 0,
            error: 'ConnectionError: timed out',
        });

        expect(failed.error).toBe('ConnectionError: timed out');
        expect(failed.hits).toEqual([]);
    });

    it('reads an uncached answer as fresh', () => {
        // The flag is only sent when it is true, so its absence means "read
        // now" -- the opposite default would label every fresh answer as
        // remembered.
        expect(mapOrsrPersonSearchResponse(base).cached).toBe(false);
        expect(mapOrsrPersonSearchResponse({...base, cached: true}).cached).toBe(true);
    });

    it('keeps the register’s own note and the source it came from', () => {
        const result = mapOrsrPersonSearchResponse(base);

        expect(result.note).toBe('Register vracia len mená firiem, nie funkciu.');
        expect(result.source_url).toBe('https://www.orsr.sk/hladaj_osoba.asp?PR=Trnka');
        expect(result.total).toBe(18);
    });
});
