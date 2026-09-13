import {beforeEach, describe, expect, it, vi} from 'vitest';
import {screen, waitFor} from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import {OrsrRegisterGroup} from './OrsrRegisterGroup';
import {renderWithProviders} from '../../test/testUtils';
import type {OrsrPersonSearchResponse} from '../../types';

const mocks = vi.hoisted(() => ({
    api: {searchOrsrPersons: vi.fn()},
}));

vi.mock('../../api', () => ({api: mocks.api}));

const answer = (
    overrides: Partial<OrsrPersonSearchResponse> = {},
): OrsrPersonSearchResponse => ({
    query: 'Miroslav Trnka',
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
    note: 'Register vracia len mená firiem, nie funkciu — na to by bol jeden výpis pre každú firmu.',
    detail: null,
    cached: false,
    ...overrides,
});

const button = () => screen.getByRole('button', {name: /ORSR/});

describe('OrsrRegisterGroup', () => {
    beforeEach(() => {
        mocks.api.searchOrsrPersons.mockReset();
    });

    it('does not touch the register until the button is pressed', () => {
        // orsr.sk is somebody else's server, rate-limited to 60 requests an hour
        // per caller with no API at all. Rendering the group must cost it
        // nothing.
        renderWithProviders(<OrsrRegisterGroup name="Miroslav Trnka"/>);

        expect(mocks.api.searchOrsrPersons).not.toHaveBeenCalled();
        expect(screen.getByText(/nie sú to naše dáta/i)).toBeInTheDocument();
    });

    it('asks the register once, on the click, for the name it was given', async () => {
        const user = userEvent.setup();
        mocks.api.searchOrsrPersons.mockResolvedValue(answer());

        renderWithProviders(<OrsrRegisterGroup name="Miroslav Trnka"/>);
        await user.click(button());

        await waitFor(() =>
            expect(mocks.api.searchOrsrPersons).toHaveBeenCalledWith('Miroslav Trnka'),
        );
        expect(mocks.api.searchOrsrPersons).toHaveBeenCalledTimes(1);
    });

    it('labels the register’s rows as the register’s, apart from our own data', async () => {
        const user = userEvent.setup();
        mocks.api.searchOrsrPersons.mockResolvedValue(answer());

        renderWithProviders(<OrsrRegisterGroup name="Miroslav Trnka"/>);
        await user.click(button());

        // The heading, the total, the note about what the register does not
        // publish, and the source credited -- all four, because a list of
        // companies without them reads as a list of offices.
        expect(await screen.findByRole('heading', {name: /Register ORSR/})).toBeInTheDocument();
        expect(screen.getByText('18')).toBeInTheDocument();
        expect(screen.getByText(/Register vracia len mená firiem/)).toBeInTheDocument();
        expect(screen.getByRole('link', {name: /tento výpis priamo na orsr\.sk/})).toHaveAttribute(
            'href',
            'https://www.orsr.sk/hladaj_osoba.asp?PR=Trnka',
        );
    });

    it('links each hit to its výpis, and the full one as the second link', async () => {
        const user = userEvent.setup();
        mocks.api.searchOrsrPersons.mockResolvedValue(answer());

        renderWithProviders(<OrsrRegisterGroup name="Miroslav Trnka"/>);
        await user.click(button());

        expect(await screen.findByRole('link', {name: 'Výpis'})).toHaveAttribute(
            'href',
            'https://www.orsr.sk/vypis.asp?ID=1&SID=2&P=0',
        );
        expect(screen.getByRole('link', {name: 'Úplný výpis'})).toHaveAttribute(
            'href',
            'https://www.orsr.sk/vypis.asp?ID=1&SID=2&P=1',
        );
    });

    it('says a cached answer is remembered, not read now', async () => {
        const user = userEvent.setup();
        mocks.api.searchOrsrPersons.mockResolvedValue(answer({cached: true}));

        renderWithProviders(<OrsrRegisterGroup name="Miroslav Trnka"/>);
        await user.click(button());

        expect(await screen.findByText('z pamäte')).toBeInTheDocument();
    });

    it('renders an unreadable register as unreadable, never as no records', async () => {
        // The distinction the payload carries in `error`. Rendering it as an
        // empty list would state, as a fact about the person, something that is
        // really a fact about our request.
        const user = userEvent.setup();
        mocks.api.searchOrsrPersons.mockResolvedValue(
            answer({hits: [], total: 0, error: 'ConnectionError: register timed out'}),
        );

        renderWithProviders(<OrsrRegisterGroup name="Miroslav Trnka"/>);
        await user.click(button());

        expect(await screen.findByText(/Register sa nepodarilo prečítať/)).toBeInTheDocument();
        expect(screen.getByText(/ConnectionError: register timed out/)).toBeInTheDocument();
        expect(screen.queryByText(/Register pre toto meno nič nevrátil/)).not.toBeInTheDocument();
    });

    it('shows an empty register answer as its own case, and says both spellings were tried', async () => {
        const user = userEvent.setup();
        mocks.api.searchOrsrPersons.mockResolvedValue(answer({hits: [], total: 0}));

        renderWithProviders(<OrsrRegisterGroup name="Miroslav Trnka"/>);
        await user.click(button());

        // The wording matters: the endpoint already retries without diacritics
        // when the first attempt returns nothing, so telling the reader to "try
        // it without diacritics" would be advice that cannot help -- it was
        // already taken. The sentence has to say so, and has to say that the
        // register keeps current records only, which is the other reason a name
        // that is genuinely there does not appear.
        expect(await screen.findByText(/skúsili aj bez diakritiky/)).toBeInTheDocument();
        expect(screen.getByText(/len aktuálne záznamy/)).toBeInTheDocument();
    });

    it('surfaces a failed request as a failure, not as an answer of none', async () => {
        const user = userEvent.setup();
        mocks.api.searchOrsrPersons.mockRejectedValue(new Error('429 Too Many Requests'));

        renderWithProviders(<OrsrRegisterGroup name="Miroslav Trnka"/>);
        await user.click(button());

        expect(await screen.findByText(/Registra sa nepodarilo opýtať/)).toBeInTheDocument();
        expect(screen.getByText('429 Too Many Requests')).toBeInTheDocument();
    });

    it('shows the API’s own detail when the question was never asked', async () => {
        const user = userEvent.setup();
        mocks.api.searchOrsrPersons.mockResolvedValue(
            answer({hits: [], total: 0, detail: 'Zadajte aspoň 2 znaky.'}),
        );

        renderWithProviders(<OrsrRegisterGroup name="T"/>);
        await user.click(button());

        expect(await screen.findByText('Zadajte aspoň 2 znaky.')).toBeInTheDocument();
    });
});
