import {describe, expect, it} from 'vitest';
import {PersonCoverageNote} from './PersonCoverageNote';
import {renderWithProviders} from '../../test/testUtils';

/**
 * NBSP is what `Intl.NumberFormat('sk-SK')` groups with. The test compares the
 * sentence, not the separator, so it normalises the one and not the other.
 */
const NBSP = '\u00A0';
const bodyText = () => document.body.textContent!.split(NBSP).join(' ');

describe('PersonCoverageNote', () => {
    it('says how much of the register our person data covers', () => {
        renderWithProviders(
            <PersonCoverageNote
                coverage={{companies_with_persons: 19906, companies_total: 445626}}
            />,
        );

        expect(bodyText()).toContain('Osoby máme pre 19 906 z 445 626 firiem.');
    });

    it('reads the counts from the response, so a changed coverage changes the words', () => {
        // A hardcoded pair would be wrong the first time the ORSR sync moved it,
        // and it moves every day.
        renderWithProviders(
            <PersonCoverageNote coverage={{companies_with_persons: 7, companies_total: 12}}/>,
        );

        expect(bodyText()).toContain('Osoby máme pre 7 z 12 firiem.');
    });

    it('says it cannot quantify rather than claiming zero coverage', () => {
        // `null` is "the response did not carry the counts". Substituting 0
        // would print "0 z 0 firiem" -- a statement about the register that no
        // response made.
        renderWithProviders(<PersonCoverageNote coverage={null}/>);

        const text = bodyText();
        expect(text).toContain('táto odpoveď neuvádza');
        expect(text).not.toContain('Osoby máme pre');
    });
});
