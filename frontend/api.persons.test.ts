import {afterEach, describe, expect, it, vi} from 'vitest';
import {
    api,
    mapCompanyPersonsResponse,
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
        intervals: 1,
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

    it('counts a folded row as one filing when the API did not say', () => {
        // A backend that predates the field, or a payload that lost it. Zero
        // would render as "this row stands for nothing"; the honest default is
        // the ordinary case, one filing.
        expect(mapPersonRelation({...flat, intervals: undefined}).intervals).toBe(1);
        expect(mapPersonRelation({...flat, intervals: 0}).intervals).toBe(1);
        expect(mapPersonRelation({...flat, intervals: null}).intervals).toBe(1);
    });

    it('carries the number of filings a folded row stands for', () => {
        expect(mapPersonRelation({...flat, intervals: 12}).intervals).toBe(12);
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

    it('keeps each member row’s own birth date, and its absence', () => {
        // The note on the person page can only contradict a grouping if the
        // date survives the mapper per row. `null` has to stay `null` rather
        // than becoming `''`: a row that stated no date is exactly what the
        // reader compares a dated row against.
        const detail = mapPersonDetail({
            id: 44904,
            name: 'Matej Vácha',
            title: '',
            person_ico: '',
            records: 2,
            members: [
                {id: 44904, name: 'Matej Vácha', address: '', birth_date: '1992-08-20'},
                {id: 45335, name: 'Matej Vácha', address: 'Beniakova, 3100/12', birth_date: null},
            ],
            companies: [],
            coverage: {companies_with_persons: 1, companies_total: 2},
        });

        expect(detail.members.map((m) => m.birth_date)).toEqual(['1992-08-20', null]);
    });

    it('reads a member row from a response that predates the field', () => {
        // The API and the bundle are deployed together, but a browser holding a
        // cached bundle is not the only older reader -- an empty list must not
        // become a row with an undefined date rendered next to a real one.
        const detail = mapPersonDetail({
            id: 1,
            name: 'Ján Novák',
            members: [{id: 1, name: 'Ján Novák', address: 'Hlavná 5'}],
        });

        expect(detail.members).toEqual([
            {id: 1, name: 'Ján Novák', address: 'Hlavná 5', birth_date: null},
        ]);
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

/**
 * One company's people over time, as the endpoint states them.
 *
 * The mapper sits between the API and two screens -- the Osoby history and the
 * company graph -- and every default it invents is one of those screens making
 * a claim the response did not. So each of them is pinned here.
 */
describe('mapCompanyPersonsResponse', () => {
    const office = {
        ico: '35757442',
        name: 'ESET, spol. s r. o.',
        role: 'konatel',
        role_display: 'Konateľ',
        is_active: null,
        vznik_funkcie: '2010-01-01',
        zanik_funkcie: null,
        intervals: 1,
    };

    const flat = {
        ico: '12345678',
        name: 'Testovacia, s.r.o.',
        as_of: null,
        groups: [
            {
                id: 7,
                name: 'Ján Novák',
                records: 2,
                clusters: 1,
                members: [{id: 7, name: 'Ján Novák', address: 'Hlavná 1', birth_date: null}],
                offices: [office],
            },
        ],
        periods: [2015, 2010],
        undated_excluded: 0,
    };

    it('prečíta celú odpoveď do tvaru, ktorý čítajú obrazovky', () => {
        const result = mapCompanyPersonsResponse(flat);

        expect(result.ico).toBe('12345678');
        expect(result.name).toBe('Testovacia, s.r.o.');
        expect(result.as_of).toBeNull();
        expect(result.periods).toEqual([2015, 2010]);
        expect(result.groups).toHaveLength(1);
        expect(result.groups[0]).toMatchObject({id: 7, name: 'Ján Novák', records: 2, clusters: 1});
        expect(result.groups[0].members).toEqual([
            {id: 7, name: 'Ján Novák', address: 'Hlavná 1', birth_date: null},
        ]);
    });

    it('nesploští trojitú odpoveď o funkcii na dve', () => {
        // The offices go through the same mapper a person's page uses -- one
        // relation, one reader. A group mapper that built its own relation
        // shape would be the place where `null` quietly became `false`, and the
        // history would say a function ended at a company nobody has read.
        const result = mapCompanyPersonsResponse(flat);

        expect(result.groups[0].offices[0].is_active).toBeNull();
        expect(result.groups[0].offices[0].role_display).toBe('Konateľ');
    });

    it('nechá `as_of` prázdne, keď ho odpoveď neuviedla', () => {
        // `null` is what the screen reads to decide whether it is showing a
        // period at all; `''` would be a period it cannot name.
        expect(mapCompanyPersonsResponse({...flat, as_of: undefined}).as_of).toBeNull();
        expect(mapCompanyPersonsResponse({...flat, as_of: '2015-12-31'}).as_of).toBe('2015-12-31');
    });

    it('nechá v rokoch len tie, z ktorých je rok', () => {
        // The chips are built from these numbers, so one `NaN` in the list is a
        // button labelled `NaN` that sends an unparseable date. Strings are
        // accepted because JSON has no integer type and the field has been sent
        // both ways.
        expect(mapCompanyPersonsResponse({...flat, periods: [2015, Number.NaN, Infinity]}).periods)
            .toEqual([2015]);
        expect(mapCompanyPersonsResponse({...flat, periods: ['2010']}).periods).toEqual([2010]);
        expect(mapCompanyPersonsResponse({...flat, periods: undefined}).periods).toEqual([]);
        // `null` is the case finite-ness alone does not catch: `Number(null)`
        // is `0`, which is finite, and year `0` is a chip sending `0000-12-31`
        // -- a date the backend refuses. Zero and negatives are not years here.
        expect(mapCompanyPersonsResponse({...flat, periods: [null, 0, -1, 2015]}).periods)
            .toEqual([2015]);
    });

    it('nedovolí záporný počet vynechaných zápisov', () => {
        // The note reads "this many filings could not be placed in the chosen
        // period", and a negative count would print a sentence about minus
        // three filings, which is not a thing that happened.
        expect(mapCompanyPersonsResponse({...flat, undated_excluded: -3}).undated_excluded).toBe(0);
        expect(mapCompanyPersonsResponse({...flat, undated_excluded: undefined}).undated_excluded).toBe(0);
        expect(mapCompanyPersonsResponse({...flat, undated_excluded: 3}).undated_excluded).toBe(3);
    });

    it('počíta skupinu aspoň ako jeden záznam', () => {
        // A group exists because at least one row produced it, so a missing or
        // zero count cannot mean "no rows" -- the card would then be a person
        // the register never wrote down.
        const [group] = mapCompanyPersonsResponse({
            ...flat,
            groups: [{...flat.groups[0], records: 0, clusters: undefined}],
        }).groups;

        expect(group.records).toBe(1);
        expect(group.clusters).toBe(1);
    });

    it('vráti prázdny zoznam namiesto `undefined`, keď odpoveď skupiny nemá', () => {
        const result = mapCompanyPersonsResponse({...flat, groups: undefined});

        expect(result.groups).toEqual([]);
        expect(result.ico).toBe('12345678');
    });
});

describe('api.getCompanyPersons', () => {
    const people = {ico: '12345678', name: 'Testovacia, s.r.o.', groups: []};

    /**
     * One successful answer, and the URL it was asked at -- the whole subject of
     * these specs is which request goes out, and the parameter is a day the
     * backend filters on rather than a display value.
     */
    const calledWith = async (asOf?: string | null): Promise<string> => {
        const fetchMock = vi.fn().mockResolvedValue({
            ok: true,
            status: 200,
            json: async () => people,
            text: async () => JSON.stringify(people),
        });
        vi.stubGlobal('fetch', fetchMock);

        await api.getCompanyPersons('12345678', asOf);

        return fetchMock.mock.calls[0][0];
    };

    afterEach(() => {
        vi.unstubAllGlobals();
    });

    it('pýta sa na firmu bez parametra, keď nie je zvolené obdobie', async () => {
        // No period and "today" are the same request: the backend reads the
        // whole record, which is what the Osoby cards and the graph show. A
        // `?as_of=` carrying today's date would ask a different question.
        expect(await calledWith()).toBe('/api/companies/12345678/persons/');
        expect(await calledWith(null)).toBe('/api/companies/12345678/persons/');
    });

    it('pošle zvolený deň ako `as_of`', async () => {
        expect(await calledWith('2015-12-31')).toBe(
            '/api/companies/12345678/persons/?as_of=2015-12-31',
        );
    });

    it('zakóduje hodnotu, ktorá nie je holý dátum', async () => {
        // Not a formality: the day reaches the query string from a caller, and
        // a value that arrives unencoded is a different request than the one
        // that was meant -- or a broken one.
        expect(await calledWith('2015 12 31')).toBe(
            '/api/companies/12345678/persons/?as_of=2015%2012%2031',
        );
    });

    it('vráti zmapovanú odpoveď, nie surové telo', async () => {
        // The screens read fields the response does not have; a method that
        // handed the body straight back would compile and render nothing.
        const body = {
            ico: '12345678',
            name: 'Testovacia, s.r.o.',
            as_of: '2015-12-31',
            groups: [
                {
                    id: 7,
                    name: 'Ján Novák',
                    records: 1,
                    clusters: 1,
                    members: [],
                    offices: [
                        {
                            ico: '35757442',
                            name: 'ESET, spol. s r. o.',
                            role_display: 'Konateľ',
                            is_active: false,
                        },
                    ],
                },
            ],
            periods: [2015],
            undated_excluded: 1,
        };
        vi.stubGlobal(
            'fetch',
            vi.fn().mockResolvedValue({
                ok: true,
                status: 200,
                json: async () => body,
                text: async () => JSON.stringify(body),
            }),
        );

        const result = await api.getCompanyPersons('12345678', '2015-12-31');

        expect(result.as_of).toBe('2015-12-31');
        expect(result.periods).toEqual([2015]);
        expect(result.groups[0].offices[0]).toMatchObject({is_active: false, intervals: 1});
    });
});
