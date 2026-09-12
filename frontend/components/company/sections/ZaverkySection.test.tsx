import {describe, expect, it} from 'vitest';
import {screen} from '@testing-library/react';
import {ZaverkySection, plural} from './ZaverkySection';
import {DEFAULT_COMPANY, makeCompany, makeFinancials, renderWithProviders} from '../../../test/testUtils';
import type {Company} from '../../../types';

const company = (overrides: Partial<Company> = {}): Company =>
    makeCompany({
        financials: [makeFinancials({year: 2023}), makeFinancials({year: 2022})],
        financialsState: 'ready',
        ...overrides,
    });

const bodyText = () => document.body.textContent!.replace(/ /g, ' ');

describe('ZaverkySection', () => {
    it('prints what RUZ holds and what we read, in that order', () => {
        renderWithProviders(<ZaverkySection company={company({ruzStatements: 14, ruzAnnualReports: 4})}/>);

        const text = bodyText();
        expect(text).toContain('RUZ eviduje');
        expect(text).toContain('14');
        expect(text).toContain('4');
        // Both counts, and the years we actually have -- the section exists
        // precisely because these answer different questions.
        expect(text).toContain('prečítali 2 ročníky, 2022 – 2023');
    });

    it('agrees the counted noun with the count in all three Slovak forms', () => {
        // 1 závierka, 2-4 závierky, 5+ závierok. A plain `n === 1 ? a : b`
        // prints "5 závierky", which is the mistake this guards.
        const {unmount} = renderWithProviders(
            <ZaverkySection company={company({ruzStatements: 1, ruzAnnualReports: 0})}/>
        );
        expect(bodyText()).toContain('1 účtovnú závierku');
        unmount();

        const few = renderWithProviders(
            <ZaverkySection company={company({ruzStatements: 3, ruzAnnualReports: 0})}/>
        );
        expect(bodyText()).toContain('3 účtovné závierky');
        few.unmount();

        renderWithProviders(<ZaverkySection company={company({ruzStatements: 7, ruzAnnualReports: 0})}/>);
        expect(bodyText()).toContain('7 účtovných závierok');
    });

    it('mentions annual reports only when there are some', () => {
        // The counted forms, not the stem: the closing paragraph names "výročná
        // správa" among the attachments we do not download, and a bare
        // `not.toContain('výročn')` would read that as a count.
        const counted = /výročn(ú správu|é správy|ých správ)/;

        const {unmount} = renderWithProviders(
            <ZaverkySection company={company({ruzStatements: 5, ruzAnnualReports: 0})}/>
        );
        expect(bodyText()).not.toMatch(counted);
        unmount();

        renderWithProviders(<ZaverkySection company={company({ruzStatements: 5, ruzAnnualReports: 2})}/>);
        expect(bodyText()).toContain('2 výročné správy');
    });

    it('says RUZ holds nothing for a company it holds nothing for', () => {
        renderWithProviders(
            <ZaverkySection
                company={company({financials: [], financialsState: 'nothing_recorded', ruzStatements: 0, ruzAnnualReports: 0})}
            />
        );
        expect(bodyText()).toContain('neeviduje žiadnu účtovnú závierku');
    });

    it('does not turn a missing count into a claim about the register', () => {
        // `null` is "the response did not carry the count", not zero, and the
        // difference is the whole reason the field is nullable.
        renderWithProviders(
            <ZaverkySection company={company({ruzStatements: null, ruzAnnualReports: null})}/>
        );

        const text = bodyText();
        expect(text).toContain('sa z tejto odpovede nedozvedáme');
        expect(text).not.toContain('neeviduje žiadnu');
    });

    it('notices when RUZ holds more than we have read', () => {
        renderWithProviders(<ZaverkySection company={company({ruzStatements: 20, ruzAnnualReports: 0})}/>);
        expect(bodyText()).toContain('RUZ eviduje viac závierok, než sme prečítali');
    });

    it('does not raise that notice when we have read everything RUZ lists', () => {
        renderWithProviders(<ZaverkySection company={company({ruzStatements: 2, ruzAnnualReports: 0})}/>);
        expect(bodyText()).not.toContain('viac závierok, než sme prečítali');
    });

    it('explains why there is no year to show, in the same words as the other sections', () => {
        // One vocabulary for the four reasons a statement section is empty, so
        // two sections on one page cannot describe the same fact differently.
        renderWithProviders(
            <ZaverkySection company={company({financials: [], financialsState: 'not_fetched', ruzStatements: 3})}/>
        );
        expect(bodyText()).toContain('sme z RUZ ešte nečítali');
    });

    it('names IFRS as the reason rather than blaming the import', () => {
        renderWithProviders(
            <ZaverkySection
                company={company({financials: [], financialsState: 'not_fetched', usesIfrs: true, ruzStatements: 3})}
            />
        );
        expect(bodyText()).toContain('IFRS');
    });

    it('offers the RUZ portal instead of a download it cannot serve', () => {
        renderWithProviders(
            <ZaverkySection company={company({ruzPortalUrl: 'https://www.ruz.gov.sk/vyhladavanie/12345678'})}/>
        );

        const link = screen.getByRole('link', {name: /RUZ portáli/i});
        expect(link).toHaveAttribute('href', 'https://www.ruz.gov.sk/vyhladavanie/12345678');
        expect(bodyText()).toContain('sa do tejto databázy nesťahujú');
    });

    it('renders without a portal link when the response carried no URL', () => {
        renderWithProviders(<ZaverkySection company={company({ruzPortalUrl: null})}/>);
        expect(screen.queryByRole('link', {name: /RUZ portáli/i})).not.toBeInTheDocument();
    });
});

describe('plural', () => {
    it.each([
        [0, 'závierok'],
        [1, 'závierku'],
        [2, 'závierky'],
        [4, 'závierky'],
        [5, 'závierok'],
        [11, 'závierok'],
        [21, 'závierok'],
    ])('gives %i the form %s', (count, expected) => {
        // 21 is `závierok` and not `závierka`: Slovak counts the last word of
        // the number, and above four it takes the genitive plural regardless of
        // what the digit looks like. The function's job is only the 1-4 window.
        expect(plural(count, 'závierku', 'závierky', 'závierok')).toBe(expected);
    });

    it('is exercised by the default fixture, which is a company that files nothing', () => {
        expect(DEFAULT_COMPANY.ruzStatements).toBe(0);
    });
});
