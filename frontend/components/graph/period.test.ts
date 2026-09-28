import {describe, expect, it} from 'vitest';
import {TODAY_LABEL, asOfForYear, periodLabel, undatedNote} from './period';

/**
 * The one vocabulary for "which day is this picture about", pinned where it can
 * be read rather than inferred.
 *
 * Three screens ask the same question with these functions, and the value they
 * produce is not decoration: it is the `?as_of=` the backend filters on. What
 * the reader clicked and what the request says have to be the same day, so the
 * day is computed once here and nowhere else.
 */
describe('asOfForYear — rok je vždy jeho posledný deň', () => {
    it('mení rok na 31. december toho roku', () => {
        // Not the bare year: a relation ends on a real day, and a company whose
        // konateľ left on 3 March 2015 was a different company on 31 December
        // 2014 than on 31 December 2015. A chip labelled 2015 has to mean the
        // end of 2015 or it means nothing in particular.
        expect(asOfForYear(2015)).toBe('2015-12-31');
        expect(asOfForYear(2010)).toBe('2010-12-31');
    });

    it('doplní rok na štyri číslice, ako to chce formát dátumu', () => {
        // `String(year)` alone would send `843-12-31`, and Django's date parsing
        // refuses that -- a chip for a very old record would be a request that
        // always errors.
        expect(asOfForYear(843)).toBe('0843-12-31');
    });
});

describe('periodLabel — čo je zvolený deň', () => {
    it('volá dnešok dneškom, nie dátumom', () => {
        // The graph drawn with no period is not the company on any one day, it
        // is the whole record the register holds now -- so it says that, and
        // `TODAY_LABEL` is the same word the chip carries.
        expect(periodLabel(null)).toBe('Súčasný stav');
        expect(TODAY_LABEL).toBe('Dnes');
    });

    it('píše deň a mesiac bez nuly, ako sa po slovensky píšu', () => {
        // `01. 01. 2010` is a machine's spelling of the date. The numbers are
        // parsed and not sliced for exactly this.
        expect(periodLabel('2010-01-01')).toBe('Stav k 1. 1. 2010');
        expect(periodLabel('2015-12-31')).toBe('Stav k 31. 12. 2015');
    });

    it('vráti vstup, keď sa z neho dátum nedá prečítať', () => {
        // The fallback is `return asOf` on purpose: inventing a date out of a
        // malformed one would label a list with a period nobody asked for. An
        // answer we cannot name is shown as it came.
        expect(periodLabel('2010-01')).toBe('2010-01');
        expect(periodLabel('nevieme')).toBe('nevieme');
    });
});

describe('undatedNote — čo obdobie muselo vynechať', () => {
    it('mlčí, keď nie je čo vynechať', () => {
        // A note on every answer would be noise, and this one has to be read
        // when it appears.
        expect(undatedNote(0)).toBe('');
    });

    it('mlčí aj nad záporným počtom, ktorý nič nevynechal', () => {
        // The count comes from a backend helper; a negative one cannot mean
        // "we left something out", and `-1 zápisov` is not a sentence.
        expect(undatedNote(-3)).toBe('');
    });

    it('skloňuje po slovensky v troch tvaroch', () => {
        // Slovak counts in three: 1 zápis, 2-4 zápisy, 5+ zápisov. The
        // boundaries are the whole content of this function -- 4 and 5 are one
        // apart and take different words, so a rule that read `n > 4` as the
        // only branch would say "4 zápisov".
        expect(undatedNote(1)).toBe(
            '1 zápis bez dátumu vzniku sa do zvoleného obdobia nedá priradiť.',
        );
        expect(undatedNote(2)).toBe(
            '2 zápisy bez dátumu vzniku sa do zvoleného obdobia nedá priradiť.',
        );
        expect(undatedNote(4)).toBe(
            '4 zápisy bez dátumu vzniku sa do zvoleného obdobia nedá priradiť.',
        );
        expect(undatedNote(5)).toBe(
            '5 zápisov bez dátumu vzniku sa do zvoleného obdobia nedá priradiť.',
        );
    });

    it('drží tvar aj pre číslo, ktoré má rovnakú koncovku ako päťka', () => {
        expect(undatedNote(11)).toBe(
            '11 zápisov bez dátumu vzniku sa do zvoleného obdobia nedá priradiť.',
        );
    });
});
