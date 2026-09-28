import React from 'react';
import {beforeEach, describe, expect, it, vi} from 'vitest';
import {screen, waitFor, within} from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import {Route, Routes, useLocation} from 'react-router-dom';
import {Monitoring} from './Monitoring';
import {renderWithProviders} from '../test/testUtils';
import type {PersonCoverage, PersonSummary} from '../types';

const mocks = vi.hoisted(() => ({
    api: {
        searchCompanies: vi.fn(),
        searchPersons: vi.fn(),
    },
}));

vi.mock('../api', () => ({api: mocks.api}));

/** NBSP is what `Intl.NumberFormat('sk-SK')` groups with; the words are not. */
const NBSP = ' ';
const bodyText = () => document.body.textContent!.split(NBSP).join(' ');

const coverage: PersonCoverage = {companies_with_persons: 19906, companies_total: 445626};

const person = (overrides: Partial<PersonSummary> = {}): PersonSummary => ({
    id: 12345,
    name: 'Miroslav Trnka',
    title: 'Ing.',
    person_ico: '',
    records: 1,
    companies: [
        {
            ico: '35757442',
            name: 'ESET, spol. s r. o.',
            role: 'konatel',
            role_display: 'Konateľ',
            is_active: true,
            vznik_funkcie: '2010-01-01',
            zanik_funkcie: null,
            intervals: 1,
        },
    ],
    ...overrides,
});

const company = (ico: string, nazov: string) => ({
    ico,
    nazov_UJ: nazov,
    mesto: 'Bratislava',
    legal_form_short: 's. r. o.',
});

const personResponse = (results: PersonSummary[], overrides: Record<string, unknown> = {}) => ({
    query: 'trnka',
    role: '',
    results,
    total_matches: results.length,
    total_people: results.length,
    truncated: false,
    detail: null,
    coverage,
    ...overrides,
});

/** The URL the router is on -- the destination is the assertion. */
const LocationProbe: React.FC = () => {
    const location = useLocation();
    return <div data-testid="location">{`${location.pathname}${location.search}`}</div>;
};

const renderMonitoring = () =>
    renderWithProviders(
        <>
            <LocationProbe/>
            <Routes>
                <Route path="/" element={<Monitoring/>}/>
                <Route path="/osoba/:id" element={<div>osoba</div>}/>
                <Route path="/firma/:ico/:sekcia" element={<div>firma</div>}/>
            </Routes>
        </>,
    );

/** Type a query into the box and press its button, the way a reader does. */
const search = async (query: string) => {
    const user = userEvent.setup();
    await user.type(screen.getByLabelText('Hľadať firmu alebo osobu'), query);
    await user.click(screen.getByRole('button', {name: /Overiť/}));
};

const location = () => screen.getByTestId('location').textContent;

/**
 * The results card, and not the whole page.
 *
 * The search box above renders its own dropdown with its own copy of these
 * rows and its own coverage sentence, so a page-wide `getByText` here would be
 * answered by the dropdown and would keep passing with the card deleted.
 */
const resultsCard = () =>
    within(screen.getByText(/^Výsledky vyhľadávania/).closest('.app-card') as HTMLElement);

describe('Monitoring — a name in the box, and what the page does with it', () => {
    beforeEach(() => {
        mocks.api.searchCompanies.mockReset();
        mocks.api.searchPersons.mockReset();
        mocks.api.searchCompanies.mockResolvedValue({results: []});
        mocks.api.searchPersons.mockResolvedValue(personResponse([]));
    });

    it('finds a person the box already found, and goes to their page', async () => {
        // The bug this page was reported for: the box listed the person, the
        // button said "Nenašli sa žiadne výsledky" -- because the button only
        // ever asked the company endpoint. One person is not a list.
        mocks.api.searchPersons.mockResolvedValue(personResponse([person({id: 7})]));

        renderMonitoring();
        await search('Miroslav Trnka');

        await waitFor(() => expect(location()).toBe('/osoba/7'));
    });

    it('asks the person endpoint itself, and not only its search box', async () => {
        // `expect(searchPersons).toHaveBeenCalled()` is answered here by the
        // search box, which has always asked -- that is the bug, not the fix, so
        // a bare call count is a gate that passes with the page reverted. The
        // box passes an AbortSignal and the page does not, which is the only
        // thing that tells the two callers apart from here.
        renderMonitoring();
        await search('Miroslav Trnka');

        await waitFor(() => expect(mocks.api.searchPersons).toHaveBeenCalled());
        const pageCalls = mocks.api.searchPersons.mock.calls.filter(([, , options]) => options === undefined);
        expect(pageCalls.map(([query]) => query)).toContain('Miroslav Trnka');
    });

    it('lists people beside firms when both matched, with the coverage sentence', async () => {
        mocks.api.searchCompanies.mockResolvedValue({
            results: [company('35757442', 'ESET, spol. s r. o.'), company('31333532', 'Neznáma, s. r. o.')],
        });
        mocks.api.searchPersons.mockResolvedValue(personResponse([person({id: 7}), person({id: 8, name: 'Ján Trnka'})]));

        renderMonitoring();
        await search('Trnka');

        await waitFor(() => expect(screen.getByText('Výsledky vyhľadávania (4)')).toBeInTheDocument());
        expect(resultsCard().getByText('Firmy')).toBeInTheDocument();
        expect(resultsCard().getByText('Osoby u nás')).toBeInTheDocument();
        expect(resultsCard().getByRole('link', {name: /Miroslav Trnka/})).toHaveAttribute('href', '/osoba/7');
        expect(resultsCard().getByRole('link', {name: /Ján Trnka/})).toHaveAttribute('href', '/osoba/8');
        // The contract: coverage travels with every person answer and is printed
        // wherever person results are. `19906` is read from the response, not
        // written into the page.
        expect(bodyText()).toContain('Osoby máme pre 19 906 z 445 626 firiem.');
        expect(resultsCard().getByText(/Osoby máme pre/)).toBeInTheDocument();
        // A list means the reader chooses; nothing was navigated to for them.
        expect(location()).toBe('/');
    });

    it('keeps the old sentence when nothing matched, and says what our person data covers', async () => {
        renderMonitoring();
        await search('Nikto Tu Nie Je');

        await waitFor(() =>
            expect(screen.getByText('Nenašli sa žiadne výsledky pre váš dopyt.')).toBeInTheDocument(),
        );
        // The empty answer is where the coverage sentence is owed: without it
        // the card reads as a claim that this person is in no company.
        expect(bodyText()).toContain('Osoby máme pre 19 906 z 445 626 firiem.');
    });

    it('still goes straight to the only firm that matched, as it did before', async () => {
        // The pre-existing behaviour, held: a single firm was never a list, and
        // adding a person endpoint must not turn it into one.
        mocks.api.searchCompanies.mockResolvedValue({results: [company('35757442', 'ESET, spol. s r. o.')]});
        mocks.api.searchPersons.mockResolvedValue(personResponse([]));

        renderMonitoring();
        await search('ESET');

        await waitFor(() => expect(location()).toBe('/firma/35757442/prehlad'));
    });

    it('shows the firms it found when the person endpoint fails, and does not claim nobody', async () => {
        // One half failing must not empty the other -- and it must not borrow
        // the wording that says we looked and found nobody, which is a different
        // claim about a person. Two firms, so the page renders a list instead of
        // navigating and the sentence is observable.
        mocks.api.searchCompanies.mockResolvedValue({
            results: [company('35757442', 'ESET, spol. s r. o.'), company('31333532', 'Neznáma, s. r. o.')],
        });
        mocks.api.searchPersons.mockRejectedValue(new Error('network down'));

        renderMonitoring();
        await search('Trnka');

        await waitFor(() => expect(screen.getByText('Výsledky vyhľadávania (2)')).toBeInTheDocument());
        expect(resultsCard().getByText('Zoznam osôb sa nepodarilo načítať.')).toBeInTheDocument();
        expect(resultsCard().queryByRole('link', {name: /Miroslav Trnka/})).toBeNull();
        expect(bodyText()).not.toContain('V našich dátach sme k tomuto menu nikoho nenašli.');
        expect(bodyText()).not.toContain('Nenašli sa žiadne výsledky');
    });

    it('shows the people it found when the company endpoint fails', async () => {
        mocks.api.searchCompanies.mockRejectedValue(new Error('network down'));
        mocks.api.searchPersons.mockResolvedValue(personResponse([person({id: 7}), person({id: 8, name: 'Ján Trnka'})]));

        renderMonitoring();
        await search('Trnka');

        await waitFor(() => expect(screen.getByText('Výsledky vyhľadávania (2)')).toBeInTheDocument());
        expect(resultsCard().getByRole('link', {name: /Miroslav Trnka/})).toHaveAttribute('href', '/osoba/7');
        // No empty "Firmy" heading for a half that failed.
        expect(resultsCard().queryByText('Firmy')).toBeNull();
    });

    it('does not claim our coverage when the person endpoint never answered', async () => {
        // Both halves down: the card may say the search failed, but a sentence
        // about how much of the register we cover would be a statement about our
        // data made by a request that never reached it.
        mocks.api.searchCompanies.mockRejectedValue(new Error('network down'));
        mocks.api.searchPersons.mockRejectedValue(new Error('network down'));

        renderMonitoring();
        await search('Trnka');

        await waitFor(() => expect(screen.getByText('Nepodarilo sa vyhľadať. Skúste to znova.')).toBeInTheDocument());
        expect(bodyText()).not.toContain('Osoby máme pre');
    });

    it('says what a short query needs now that people are searchable too', async () => {
        renderMonitoring();
        await search('a');

        await waitFor(() =>
            expect(screen.getByText('Zadajte aspoň 2 znaky (IČO, názov firmy alebo meno osoby).')).toBeInTheDocument(),
        );
    });
});
