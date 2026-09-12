import {describe, expect, it} from 'vitest';
import {
    vatStanding,
    vatReliability,
    vatDeregistrationReason,
    VAT_STANDING_LABEL,
} from './vatStatus';
import type {VatStatus} from '../types';

/**
 * The vocabulary the VAT register actually uses, pinned.
 *
 * Every value in this file was counted on 2026-09-12 over all 445 626 rows of
 * `"Companies and SZCO"`. They are here rather than in a fixture because the
 * defect that prompted this module was precisely a vocabulary nobody had
 * checked: the type declared three capitalised reliability bands, the register
 * held three different lowercase ones, and the component's `=== 'Nespoľahlivý'`
 * warning branch could therefore never fire.
 */

const vat = (overrides: Partial<VatStatus> = {}): VatStatus => ({
    icDph: 'SK1234567890',
    isVatPayer: true,
    taxReliabilityIndex: 'spoľahlivý',
    registeredOn: '2010-01-01',
    deregisteredOn: null,
    reasonForDeregistration: null,
    lastCheckedAt: '2026-01-01T00:00:00Z',
    ...overrides,
});

describe('vatStanding', () => {
    it('calls a company the register still lists a payer', () => {
        expect(vatStanding(vat())).toBe('payer');
    });

    it('calls a company with a removal date deregistered even when the flag is absent', () => {
        // The case the flag cannot see, and the reason the date decides: 27 857
        // of the 32 050 deregistrations carry no `Platiteľ DPH` value at all,
        // so a flag-first reading calls them unknown -- or, with the old
        // `|| false`, a plain "Neplatiteľ DPH" that loses the violation.
        expect(
            vatStanding(
                vat({
                    isVatPayer: null,
                    deregisteredOn: '2019-03-12',
                    reasonForDeregistration: 'Rok porušenia: 2018',
                })
            )
        ).toBe('deregistered');
    });

    it('calls a company the register rated false a non-payer', () => {
        expect(vatStanding(vat({isVatPayer: false, registeredOn: null}))).toBe('not-payer');
    });

    it('says unknown rather than non-payer when the register said nothing', () => {
        // 302 713 rows -- 68 % of the register. The old mapping turned every one
        // of them into "Neplatiteľ DPH", a claim the tax office never made.
        expect(vatStanding(vat({isVatPayer: null, registeredOn: null}))).toBe('unknown');
        expect(VAT_STANDING_LABEL.unknown).toBe('Nezistené');
        expect(VAT_STANDING_LABEL.unknown).not.toBe(VAT_STANDING_LABEL['not-payer']);
    });
});

describe('vatReliability', () => {
    it('renders each band the register publishes, and gives the worst one a warning tone', () => {
        // The three values measured in the column. 'menej spoľahlivý' (50 620
        // rows) is the worst band that exists, and it used to render in the
        // same colour as 'vysoko spoľahlivý' because the comparison named a
        // value -- 'Nespoľahlivý' -- that no row contains.
        expect(vatReliability('vysoko spoľahlivý')).toEqual({label: 'Vysoko spoľahlivý', tone: 'good'});
        expect(vatReliability('spoľahlivý')).toEqual({label: 'Spoľahlivý', tone: 'neutral'});
        expect(vatReliability('menej spoľahlivý')).toEqual({label: 'Menej spoľahlivý', tone: 'warn'});

        expect(vatReliability('menej spoľahlivý').tone).not.toBe(vatReliability('vysoko spoľahlivý').tone);
    });

    it('does not turn an absent index into a statement that the company is reliable', () => {
        // 218 143 rows carry no index. `data.tax_reliability || 'Spoľahlivý'`
        // printed every one of them as reliable -- the reassuring direction of
        // the absent-vs-zero mistake, and the worse one for a risk tool.
        const absent = vatReliability(null);

        expect(absent.tone).toBe('unknown');
        expect(absent.label).not.toBe('Spoľahlivý');
        expect(absent.label).toMatch(/bez indexu/);
    });

    it('prints a band it has never seen instead of defaulting it into a calm one', () => {
        // Finančná správa may add a value tomorrow. It must render as itself:
        // we would otherwise be assigning a severity to a word we cannot read,
        // and the default would be the reassuring one.
        expect(vatReliability('veľmi spoľahlivý')).toEqual({
            label: 'veľmi spoľahlivý',
            tone: 'unknown',
        });
    });
});

describe('vatDeregistrationReason', () => {
    it('says the reason as a sentence for the shape 32 023 of 32 043 records use', () => {
        expect(vatDeregistrationReason('Rok porušenia: 2018')).toBe('porušenie v roku 2018');
        expect(vatDeregistrationReason('Rok porušenia: 2013')).toBe('porušenie v roku 2013');
    });

    it('leaves a shape it did not anticipate exactly as the register wrote it', () => {
        // The remaining 20 rows. A pattern we did not expect is a sentence to
        // print, not one to force into a template.
        expect(vatDeregistrationReason('Zrušená registrácia')).toBe('Zrušená registrácia');
        expect(vatDeregistrationReason('Rok porušenia: 2018 (dodatočne)')).toBe(
            'Rok porušenia: 2018 (dodatočne)'
        );
    });

    it('has nothing to say when the register recorded no reason', () => {
        expect(vatDeregistrationReason(null)).toBeNull();
        expect(vatDeregistrationReason('')).toBeNull();
    });
});
