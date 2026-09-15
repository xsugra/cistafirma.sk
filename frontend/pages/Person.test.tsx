import {beforeEach, describe, expect, it, vi} from 'vitest';
import {screen, waitFor} from '@testing-library/react';
import {Route, Routes} from 'react-router-dom';
import {Person} from './Person';
import {ApiError} from '../lib/apiClient';
import {renderWithProviders} from '../test/testUtils';
import {ROLE_STATE_SENTENCE, ROLE_STATE_WORD} from '../components/person/roleState';
import type {PersonDetail} from '../types';

const mocks = vi.hoisted(() => ({
    api: {
        getPerson: vi.fn(),
        searchOrsrPersons: vi.fn(),
    },
}));

vi.mock('../api', () => ({api: mocks.api}));

/** NBSP is what `Intl.NumberFormat('sk-SK')` groups with; the words are not. */
const NBSP = '\u00A0';
const bodyText = () => document.body.textContent!.split(NBSP).join(' ');

const person = (overrides: Partial<PersonDetail> = {}): PersonDetail => ({
    id: 12345,
    name: 'Miroslav Trnka',
    title: 'Ing.',
    person_ico: '',
    records: 1,
    members: [],
    companies: [
        {
            ico: '35757442',
            name: 'ESET, spol. s r. o.',
            role: 'konatel',
            role_display: 'Konateľ',
            is_active: true,
            vznik_funkcie: '2010-01-01',
            zanik_funkcie: null,
            intervals: 12,
        },
        {
            ico: '31333532',
            name: 'Neznáma Firma, s. r. o.',
            role: 'konatel',
            role_display: 'Konateľ',
            is_active: null,
            vznik_funkcie: null,
            zanik_funkcie: null,
            intervals: 1,
        },
    ],
    coverage: {companies_with_persons: 19906, companies_total: 445626},
    ...overrides,
});

const renderPerson = (id = '12345') =>
    renderWithProviders(
        <Routes>
            <Route path="/osoba/:id" element={<Person/>}/>
        </Routes>,
        {route: `/osoba/${id}`},
    );

describe('Person page', () => {
    beforeEach(() => {
        mocks.api.getPerson.mockReset();
        mocks.api.searchOrsrPersons.mockReset();
    });

    it('renders the person’s own coverage sentence, from the response', async () => {
        // Without it an empty list reads as "this person is in no company".
        // Hardcoding the numbers would make the sentence a lie the first time
        // the ORSR sync moved them.
        mocks.api.getPerson.mockResolvedValue(person());

        renderPerson();

        // The sentence is asserted through `bodyText()` because the counts are
        // grouped with NBSP, which a regex written with a plain space misses.
        expect(await screen.findByText(/Osoby máme pre/)).toBeInTheDocument();
        expect(bodyText()).toContain('Osoby máme pre 19 906 z 445 626 firiem.');
    });

    it('prints the coverage the response carried, not the one in the interface', async () => {
        mocks.api.getPerson.mockResolvedValue(
            person({coverage: {companies_with_persons: 7, companies_total: 12}}),
        );

        renderPerson();

        expect(await screen.findByText(/Osoby máme pre/)).toBeInTheDocument();
        expect(bodyText()).toContain('Osoby máme pre 7 z 12 firiem.');
    });

    it('renders an unknown function as nevieme, alongside the ones it knows', async () => {
        mocks.api.getPerson.mockResolvedValue(person());

        renderPerson();

        expect(await screen.findByText('nevieme')).toBeInTheDocument();
        expect(screen.getByText('áno')).toBeInTheDocument();
        expect(screen.queryByText('nie')).not.toBeInTheDocument();
    });

    it('shows the name, the title and the IČO osoby when the register gave one', async () => {
        mocks.api.getPerson.mockResolvedValue(person({person_ico: '12345678'}));

        renderPerson();

        expect(await screen.findByRole('heading', {name: 'Miroslav Trnka'})).toBeInTheDocument();
        expect(screen.getByText('Ing.')).toBeInTheDocument();
        expect(screen.getByText('12345678')).toBeInTheDocument();
    });

    it('leaves the IČO line out rather than printing undefined', async () => {
        mocks.api.getPerson.mockResolvedValue(person({person_ico: '', title: ''}));

        renderPerson();

        expect(await screen.findByRole('heading', {name: 'Miroslav Trnka'})).toBeInTheDocument();
        expect(bodyText()).not.toContain('undefined');
        expect(screen.queryByText(/IČO osoby/)).not.toBeInTheDocument();
    });

    it('links each company to its own page', async () => {
        mocks.api.getPerson.mockResolvedValue(person());

        renderPerson();

        expect(await screen.findByRole('link', {name: 'ESET, spol. s r. o.'})).toHaveAttribute(
            'href',
            '/firma/35757442',
        );
    });

    it('gives a missing person its own state, not a failed-request state', async () => {
        mocks.api.getPerson.mockRejectedValue(new ApiError('Osoba nebola nájdená.', 404));

        renderPerson('999');

        expect(await screen.findByText('Osoba nebola nájdená')).toBeInTheDocument();
        expect(screen.queryByText(/odpoveď sme nedostali/)).not.toBeInTheDocument();
    });

    it('does not turn a broken request into a person who does not exist', async () => {
        // The other direction of the same distinction: a 500 is not an answer
        // about the person.
        mocks.api.getPerson.mockRejectedValue(new ApiError('Server error (500)', 500));

        renderPerson();

        expect(await screen.findByText('Server error (500)')).toBeInTheDocument();
        expect(screen.queryByText('Osoba nebola nájdená')).not.toBeInTheDocument();
    });

    it('shows the rows a grouped person was gathered from', async () => {
        // The register lists one officer under the predstavenstvo and again
        // among the spoločníci, and the two sections carry different addresses,
        // so the extractor stored two rows. Grouping them is a judgement made
        // from a name and a postcode -- the reader who knows these are a father
        // and a son can only correct it if the rows are shown.
        mocks.api.getPerson.mockResolvedValue(
            person({
                records: 3,
                members: [
                    {id: 44903, name: 'Matej Vácha', address: 'Dátum narodenia: 20.08.1992'},
                    {id: 44904, name: 'Matej Vácha', address: ''},
                    {
                        id: 45335,
                        name: 'Matej Vácha',
                        address: 'Beniakova, 3100/12, Bratislava, 841 05',
                    },
                ],
            }),
        );

        renderPerson();

        expect(await screen.findByText(/#44903/)).toBeInTheDocument();
        expect(screen.getByText(/Beniakova, 3100\/12/)).toBeInTheDocument();
        // A row whose address is the empty string says so, rather than printing
        // an empty gap that reads as a rendering fault.
        expect(screen.getByText('bez adresy')).toBeInTheDocument();
    });

    it('says nothing about grouping for the ordinary one-row person', async () => {
        // The note has to be read when it appears, so it cannot appear on every
        // person page.
        mocks.api.getPerson.mockResolvedValue(person());

        renderPerson();

        await screen.findByText(/Osoby máme pre/);
        expect(screen.queryByText(/Zobrazujeme ich spolu/)).not.toBeInTheDocument();
    });

    it('describes the unknown state the way the row above it does', async () => {
        // The legend under the list used to carry its own wording for this
        // state -- „túto firmu sme ešte nečítali" -- while the row itself said
        // the company had been read but not the function's end. A relation is on
        // this page only because we read that company, so the legend was false
        // about every row it labelled. One fact, one sentence: both now come
        // from `roleState`, and this pins them together.
        //
        // (The register-search section does say „ak sme tie firmy ešte
        // nečítali", and truly: that is about which companies our graph holds,
        // not about a relation we are showing.)
        mocks.api.getPerson.mockResolvedValue(person());

        renderPerson();

        await screen.findByText(/Osoby máme pre/);

        // The legend's own line for this state -- the one `li` that opens with
        // the word the badge prints.
        const legendLine = screen.getByText(
            (_, element) =>
                element?.tagName === 'LI' &&
                Boolean(element.textContent?.startsWith(`${ROLE_STATE_WORD.unknown} — `)),
        );
        expect(legendLine).toHaveTextContent(ROLE_STATE_SENTENCE.unknown);

        // Once in the row that carries the state, once in the legend: two
        // places, never two sentences.
        expect(
            screen.getAllByText(new RegExp(ROLE_STATE_SENTENCE.unknown)),
        ).toHaveLength(2);
    });

    it('does not call the live register just by opening the page', async () => {
        // Typing never reaches orsr.sk, and neither does a page load: only the
        // button in `OrsrRegisterGroup` does.
        mocks.api.getPerson.mockResolvedValue(person());

        renderPerson();

        await screen.findByText(/Osoby máme pre/);
        expect(mocks.api.searchOrsrPersons).not.toHaveBeenCalled();
    });

    it('asks for the person the URL names', async () => {
        mocks.api.getPerson.mockResolvedValue(person({id: 777}));

        renderPerson('777');

        await waitFor(() => expect(mocks.api.getPerson).toHaveBeenCalledWith('777'));
    });
});
