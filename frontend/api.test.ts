import {describe, expect, it} from 'vitest';
import {mapUserResponse, mapCompanyResponse} from './api';

/**
 * The user mapper, tested because it is where two shapes meet.
 *
 * `UserDetailSerializer` publishes the plan as a nested object; `User['plan']`
 * is a slug. Nothing else in the codebase compares the two, so a wrong reading
 * here compiles happily and fails on screen -- which is exactly what happened:
 * the field was cast to the slug type, `plan` held an object at runtime, and the
 * profile page would have thrown "Objects are not valid as a React child" for
 * any account that had a plan. It went unnoticed only because the single account
 * in the database has none.
 */
describe('mapUserResponse', () => {
    const base = {
        id: 'u-1',
        email: 'jana@example.com',
        username: 'jana',
        first_name: 'Jana',
        last_name: 'Nováková',
    };

    it('reads the plan slug out of the nested plan object', () => {
        const user = mapUserResponse({
            ...base,
            subscription_plan: {
                id: 'p-1',
                name: 'Plus',
                slug: 'plus',
                max_watched_companies: 10,
                price_eur: '29.00',
            },
        });

        expect(user.plan).toBe('plus');
    });

    it('gives an account with no plan the free plan', () => {
        expect(mapUserResponse({...base, subscription_plan: null}).plan).toBe('free');
        expect(mapUserResponse(base).plan).toBe('free');
    });

    it('leaves an unreported quota unreported instead of inventing one', () => {
        // The profile endpoint publishes neither counter, so `|| 0` and `|| 10`
        // printed "0 / 10" under a heading claiming to measure a quota. Zero and
        // "not measured" are different facts, and the page says which it has.
        const user = mapUserResponse(base);

        expect(user.apiCallsUsed).toBeNull();
        expect(user.apiCallsLimit).toBeNull();
    });

    it('passes a quota through when the response does carry one', () => {
        const user = mapUserResponse({...base, api_calls_used: 34, api_calls_limit: 50});

        expect(user.apiCallsUsed).toBe(34);
        expect(user.apiCallsLimit).toBe(50);
    });

    it('turns a missing name into an empty string rather than undefined', () => {
        // The header renders these directly; `undefined` renders as nothing at
        // all, which reads as a rendering bug rather than an absent name.
        const user = mapUserResponse({id: 'u-1', email: 'a@b.c', username: 'a'});

        expect(user.firstName).toBe('');
        expect(user.lastName).toBe('');
    });
});

/**
 * The company mapper, for the same reason and over the fields that were wrong.
 *
 * `CompanyDetailSerializer` uses `exclude`, so it publishes every model field —
 * including the nullable ones. The mapper is the single place where "the API did
 * not send this" can become a positive claim about a company, and the VAT block
 * did it twice: `vat_payer || false` printed 302 713 unrated companies as
 * "Neplatiteľ DPH", and `tax_reliability || 'Spoľahlivý'` printed 218 143 of
 * them as *reliable*.
 */
describe('mapCompanyResponse — the VAT block', () => {
    const base = {
        id: 'c-1',
        ico: '00685399',
        nazov_UJ: 'Testovacia, a. s.',
        datum_zalozenia: '1993-01-01',
        ulica: 'Hlavná 1',
        mesto: 'Bratislava',
        psc: '811 01',
    };

    it('keeps an unrated company unrated instead of calling it a non-payer', () => {
        const company = mapCompanyResponse({...base, vat_payer: null, tax_reliability: null});

        expect(company.vatStatus.isVatPayer).toBeNull();
        expect(company.vatStatus.taxReliabilityIndex).toBeNull();
    });

    it('tells a false apart from an absent', () => {
        // `false` is set on 4 160 rows, all of them registered and later struck
        // off. It is a fact, and it must survive the mapper as one.
        const company = mapCompanyResponse({...base, vat_payer: false});

        expect(company.vatStatus.isVatPayer).toBe(false);
    });

    it('carries the deregistration date, which used to be dropped', () => {
        // The field decides whether a company left the VAT register, and most
        // deregistrations have no `Platiteľ DPH` value to carry that fact.
        const company = mapCompanyResponse({
            ...base,
            vat_payer: null,
            vat_deleted_date: '2019-03-12',
            vat_deleted_reason: 'Rok porušenia: 2018',
        });

        expect(company.vatStatus.deregisteredOn).toBe('2019-03-12');
        expect(company.vatStatus.reasonForDeregistration).toBe('Rok porušenia: 2018');
    });

    it('carries DIČ, which the payload has always sent and nothing named', () => {
        expect(mapCompanyResponse({...base, dic: '2020297950'}).dic).toBe('2020297950');
        expect(mapCompanyResponse(base).dic).toBeNull();
    });
});
