import {beforeEach, describe, expect, it, vi} from 'vitest';
import {screen, waitFor} from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import {ZaverkySection, plural} from './ZaverkySection';
import {DEFAULT_COMPANY, makeCompany, makeFinancials, renderWithProviders} from '../../../test/testUtils';
import type {Company, DocumentListing} from '../../../types';

const mocks = vi.hoisted(() => ({
    api: {getFinancialDocuments: vi.fn()},
}));

vi.mock('../../../api', () => ({api: mocks.api}));

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
        // správa" among the attachments, and a bare `not.toContain('výročn')`
        // would read that sentence as a count.
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

    it('still offers the register’s own page, alongside the downloads', () => {
        // The closing sentence used to read "sa do tejto databázy nesťahujú a
        // nemáme ich tu odkiaľ stiahnuť", which was true until the register's
        // document routes were found. The link stays -- a reader checking our
        // figures against the source should be able to reach it -- but it is no
        // longer offered *instead of* a download.
        renderWithProviders(
            <ZaverkySection company={company({ruzPortalUrl: 'https://www.ruz.gov.sk/vyhladavanie/12345678'})}/>
        );

        const link = screen.getByRole('link', {name: /RUZ portáli/i});
        expect(link).toHaveAttribute('href', 'https://www.ruz.gov.sk/vyhladavanie/12345678');
        expect(bodyText()).toContain('stahujú priamo odtiaľto, z registra účtovných závierok');
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

/**
 * The downloadable years.
 *
 * Four outcomes the section must keep apart, and only one of them is a promise
 * that a download will work. Collapsing any pair would make the section claim
 * something it does not know -- most seriously, rendering an unreachable
 * register as a year with no documents, which states as fact about the company
 * what is really a fact about our connection.
 */
describe('ZaverkySection — downloadable years', () => {
    const ico = '48097781';

    const listing = (overrides: Partial<DocumentListing> = {}): DocumentListing => ({
        year: 2023,
        state: 'listed',
        documents: [],
        ...overrides,
    });

    beforeEach(() => {
        mocks.api.getFinancialDocuments.mockReset();
    });

    it('does not ask the register anything until a year is clicked', () => {
        // Each year costs the backend several calls to registeruz.sk, and a
        // company with 37 statements would spend all of them to render a
        // section most readers scroll past.
        renderWithProviders(<ZaverkySection company={company({ico})}/>);

        expect(mocks.api.getFinancialDocuments).not.toHaveBeenCalled();
    });

    it('lists the documents of the clicked year, pointing at our own site', async () => {
        const user = userEvent.setup();
        mocks.api.getFinancialDocuments.mockResolvedValue(
            listing({
                documents: [
                    {
                        id: 'priloha-10831315',
                        kind: 'priloha',
                        name: 'Príloha k účtovnej závierke MÚJ.PDF',
                        mimeType: 'application/pdf',
                        size: 852398,
                        pages: 4,
                        url: `/api/companies/${ico}/financials/2023/documents/priloha-10831315/`,
                    },
                ],
            }),
        );

        renderWithProviders(<ZaverkySection company={company({ico})}/>);
        await user.click(screen.getByRole('button', {name: /2023/}));

        const link = await screen.findByRole('link', {
            name: /Príloha k účtovnej závierke MÚJ\.PDF/,
        });
        expect(link).toHaveAttribute(
            'href',
            `/api/companies/${ico}/financials/2023/documents/priloha-10831315/`,
        );
        // The whole point of the section: the file arrives from here, not from
        // a link out to the register.
        expect(link.getAttribute('href')).not.toContain('registeruz.sk');
        expect(screen.getByText(/832 kB|833 kB/)).toBeInTheDocument();
    });

    it('renders an unreachable register as not-knowing, never as an empty year', async () => {
        const user = userEvent.setup();
        mocks.api.getFinancialDocuments.mockResolvedValue(listing({state: 'unreachable'}));

        renderWithProviders(<ZaverkySection company={company({ico})}/>);
        await user.click(screen.getByRole('button', {name: /2023/}));

        expect(await screen.findByText(/je momentálne nedostupný/)).toBeInTheDocument();
        expect(screen.getByText(/Nie je to tvrdenie o firme/)).toBeInTheDocument();
    });

    it('says a year we hold no filing for is about our records, not the register', async () => {
        const user = userEvent.setup();
        mocks.api.getFinancialDocuments.mockResolvedValue(listing({state: 'no_statement'}));

        renderWithProviders(<ZaverkySection company={company({ico})}/>);
        await user.click(screen.getByRole('button', {name: /2023/}));

        expect(
            await screen.findByText(/nemáme v našich záznamoch uloženú závierku/),
        ).toBeInTheDocument();
    });

    it('distinguishes a listed-but-empty year from both of those', async () => {
        const user = userEvent.setup();
        mocks.api.getFinancialDocuments.mockResolvedValue(listing({documents: []}));

        renderWithProviders(<ZaverkySection company={company({ico})}/>);
        await user.click(screen.getByRole('button', {name: /2023/}));

        expect(
            await screen.findByText(/neeviduje žiadny dokument, ktorý by sa dal stiahnuť/),
        ).toBeInTheDocument();
    });

    it('shows a failed request as a failure, not as an empty year', async () => {
        const user = userEvent.setup();
        mocks.api.getFinancialDocuments.mockRejectedValue(new Error('503'));

        renderWithProviders(<ZaverkySection company={company({ico})}/>);
        await user.click(screen.getByRole('button', {name: /2023/}));

        expect(await screen.findByText(/sa nepodarilo načítať/)).toBeInTheDocument();
    });

    it('opens one year at a time rather than stacking every list', async () => {
        const user = userEvent.setup();
        mocks.api.getFinancialDocuments.mockImplementation(
            () => new Promise<DocumentListing>(() => {}),
        );

        renderWithProviders(<ZaverkySection company={company({ico})}/>);

        await user.click(screen.getByRole('button', {name: /2023/}));
        await waitFor(() => expect(mocks.api.getFinancialDocuments).toHaveBeenCalledTimes(1));

        await user.click(screen.getByRole('button', {name: /2022/}));
        await waitFor(() =>
            expect(mocks.api.getFinancialDocuments).toHaveBeenLastCalledWith(ico, 2022),
        );

        // Only the newest year is present -- the 2023 panel is replaced, not
        // appended to. The mock never resolves, so both years are stuck in the
        // loading state and the 2023 line is what would linger if they stacked.
        expect(screen.getByText(/Načítavam závierky za rok 2022/)).toBeInTheDocument();
        expect(screen.queryByText(/Načítavam závierky za rok 2023/)).not.toBeInTheDocument();
    });
});
