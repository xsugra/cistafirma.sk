import {beforeEach, describe, expect, it, vi} from 'vitest';
import {screen, waitFor} from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import {SearchBar} from './SearchBar';
import {renderWithProviders} from '../test/testUtils';

const mocks = vi.hoisted(() => ({
    api: {
        searchCompanies: vi.fn(),
        searchPersons: vi.fn(),
        searchOrsrPersons: vi.fn(),
    },
}));

vi.mock('../api', () => ({api: mocks.api}));

const company = {
    ico: '35757442',
    nazov_UJ: 'ESET, spol. s r. o.',
    mesto: 'Bratislava',
    legal_form_short: 's. r. o.',
};

const person = {
    id: 12345,
    name: 'Ing. Miroslav Trnka',
    title: 'Ing.',
    person_ico: '',
    companies: [
        {
            ico: '35757442',
            name: 'ESET, spol. s r. o.',
            role: 'konatel',
            role_display: 'Konateľ',
            is_active: null,
            vznik_funkcie: '2010-01-01',
            zanik_funkcie: null,
            intervals: 1,
        },
    ],
};

const coverage = {companies_with_persons: 19906, companies_total: 445626};

/** NBSP is what `Intl.NumberFormat('sk-SK')` groups with; the words are not. */
const NBSP = '\u00A0';
const bodyText = () => document.body.textContent!.split(NBSP).join(' ');

const typeQuery = async (text: string) => {
    renderWithProviders(<SearchBar onSearch={() => {}} isLoading={false} initialIco=""/>);
    const user = userEvent.setup();
    await user.type(screen.getByRole('textbox'), text);
    return user;
};

describe('SearchBar — people alongside companies', () => {
    beforeEach(() => {
        mocks.api.searchCompanies.mockReset();
        mocks.api.searchPersons.mockReset();
        mocks.api.searchOrsrPersons.mockReset();
        mocks.api.searchCompanies.mockResolvedValue({results: [company]});
        mocks.api.searchPersons.mockResolvedValue({
            query: 'trnka',
            role: '',
            results: [person],
            total_matches: 1,
            truncated: false,
            detail: null,
            coverage,
        });
    });

    it('never calls the live register, however much is typed', async () => {
        // `orsr.sk` is a third-party server with no API, rate-limited to 60
        // requests an hour per caller. A request per keystroke would be our
        // traffic on somebody else's budget, so the autocomplete asks our own
        // database and nothing else -- the register is behind a button on the
        // person's page.
        await typeQuery('trnka');

        await waitFor(() => expect(mocks.api.searchPersons).toHaveBeenCalled());
        expect(mocks.api.searchOrsrPersons).not.toHaveBeenCalled();
    });

    it('lists the people our own graph holds, under their own heading', async () => {
        await typeQuery('trnka');

        expect(await screen.findByText('Osoby u nás')).toBeInTheDocument();
        const link = screen.getByRole('link', {name: /Miroslav Trnka/});
        expect(link).toHaveAttribute('href', '/osoba/12345');
    });

    it('still returns the company suggestions it always did', async () => {
        await typeQuery('trnka');

        expect(await screen.findByText('ESET, spol. s r. o.')).toBeInTheDocument();
        expect(screen.getByText(/IČO: 35757442/)).toBeInTheDocument();
    });

    it('says what our person data covers next to the person results', async () => {
        await typeQuery('trnka');

        await waitFor(() =>
            expect(bodyText()).toContain('Osoby máme pre 19 906 z 445 626 firiem.'),
        );
    });

    it('does not let a failed person lookup empty the company suggestions', async () => {
        // The two are separate questions from separate endpoints. One failing
        // must not take the other down with it.
        mocks.api.searchPersons.mockRejectedValue(new Error('503'));

        await typeQuery('trnka');

        expect(await screen.findByText('ESET, spol. s r. o.')).toBeInTheDocument();
    });

    it('shows the API’s Slovak detail instead of an empty person list', async () => {
        mocks.api.searchPersons.mockResolvedValue({
            query: 't',
            role: '',
            results: [],
            total_matches: 0,
            truncated: false,
            detail: 'Zadajte aspoň 2 znaky.',
            coverage,
        });

        await typeQuery('trnka');

        expect(await screen.findByText('Zadajte aspoň 2 znaky.')).toBeInTheDocument();
    });

    it('does not ask anything for a single character', async () => {
        await typeQuery('t');

        // The debounce and the two-character floor are the company behaviour
        // that was there before people were added to it.
        expect(mocks.api.searchCompanies).not.toHaveBeenCalled();
        expect(mocks.api.searchPersons).not.toHaveBeenCalled();
    });
});

describe('SearchBar — the button is placed against the pill, not the wrapper', () => {
    // The geometry itself was measured in a browser, not here: on Home at
    // 393 px the button's right edge sat 10 px *past* the pill's (it overflowed
    // the search box, which is the bug), and 8 px inside it after the fix --
    // with the desktop unchanged to the pixel. jsdom has no layout engine, so
    // what this holds is the invariant those numbers came from, because it is
    // one word wide and easy to lose in a refactor.
    //
    // `right-1.5` is measured from the containing block's *padding* box. The
    // pill carries `overflow-hidden`, which does not save it: an absolutely
    // positioned box is only clipped by an ancestor that is in its containing
    // block chain. With the pill static the containing block was the wrapper,
    // which carries `px-4` on a phone -- so the offset landed outside the pill
    // the reader can actually see.
    const firstPositionedAncestor = (el: HTMLElement): HTMLElement | null => {
        for (let node = el.parentElement; node; node = node.parentElement) {
            if (node.classList.contains('relative') || node.classList.contains('absolute')) return node;
        }
        return null;
    };

    const mount = (variant: 'hero' | 'compact') => {
        const {container} = renderWithProviders(
            <SearchBar onSearch={() => {}} isLoading={false} initialIco="" variant={variant} />,
        );
        return {
            wrapper: container.firstElementChild as HTMLElement,
            pill: container.querySelector('form > div') as HTMLElement,
            button: screen.getByRole('button', {name: /Overiť|Hľadať/}),
        };
    };

    it.each(['hero', 'compact'] as const)('anchors the button to the pill in the %s variant', (variant) => {
        const {wrapper, pill, button} = mount(variant);

        expect(firstPositionedAncestor(button)).toBe(pill);
        // The hazard the assertion above neutralises, stated so that changing
        // it fails here rather than on a phone: a padded pill would move the
        // button inward on every screen size and the offsets would have to be
        // re-measured.
        expect(pill.className).not.toMatch(/\bpx-/);
        if (variant === 'hero') expect(wrapper.className).toContain('px-4');
    });
});
