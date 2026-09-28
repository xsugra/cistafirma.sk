import {beforeEach, describe, expect, it, vi} from 'vitest';
import {act, screen, waitFor} from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import {CompanyPeopleHistory} from './CompanyPeopleHistory';
import {renderWithProviders} from '../../test/testUtils';
import type {CompanyPersonGroup, CompanyPersonsResponse, PersonRelation} from '../../types';

const mocks = vi.hoisted(() => ({
    api: {getCompanyPersons: vi.fn()},
}));

vi.mock('../../api', () => ({api: mocks.api}));

const office = (overrides: Partial<PersonRelation> = {}): PersonRelation => ({
    ico: '12345678',
    name: 'Testovacia, s.r.o.',
    role: 'konatel',
    role_display: 'Konateľ',
    is_active: true,
    vznik_funkcie: '2010-01-01',
    zanik_funkcie: null,
    intervals: 1,
    ...overrides,
});

const group = (overrides: Partial<CompanyPersonGroup> = {}): CompanyPersonGroup => ({
    id: 1,
    name: 'Ján Novák',
    records: 1,
    clusters: 1,
    members: [],
    offices: [office()],
    ...overrides,
});

const answer = (
    overrides: Partial<CompanyPersonsResponse> = {},
): CompanyPersonsResponse => ({
    ico: '12345678',
    name: 'Testovacia, s.r.o.',
    as_of: null,
    groups: [group()],
    periods: [],
    undated_excluded: 0,
    ...overrides,
});

/** NBSP is what `Intl.NumberFormat('sk-SK')` groups with; the words are not. */
const NBSP = ' ';
const bodyText = () => document.body.textContent!.split(NBSP).join(' ');

const history = (ico = '12345678') =>
    renderWithProviders(<CompanyPeopleHistory ico={ico} />);

const EMPTY_TODAY = 'Register pre túto firmu neuvádza žiadne osoby.';
const EMPTY_AT_DATE = 'K tomuto dátumu register neuvádza vo firme žiadnu osobu.';

describe('CompanyPeopleHistory — čo si vypýta', () => {
    beforeEach(() => {
        mocks.api.getCompanyPersons.mockReset();
    });

    it('pýta sa na firmu, ktorú dostala, a bez obdobia', async () => {
        // `null` is today's answer -- everyone we hold -- and not a missing
        // argument: the same call is made with a period once a chip is clicked,
        // so the two cases must be distinguishable in the request.
        mocks.api.getCompanyPersons.mockResolvedValue(answer());

        history('35757442');

        await waitFor(() =>
            expect(mocks.api.getCompanyPersons).toHaveBeenCalledWith('35757442', null),
        );
        expect(mocks.api.getCompanyPersons).toHaveBeenCalledTimes(1);
    });

    it('pýta sa znova na zvolený rok, keď čitateľ klikne na čip', async () => {
        // The chips are the same years the graph offers, and clicking one is
        // the whole wiring between the control and the request: the label says
        // 2015 and the parameter has to say 31 December 2015.
        const user = userEvent.setup();
        mocks.api.getCompanyPersons.mockResolvedValue(answer({periods: [2015]}));

        history();
        await user.click(await screen.findByRole('button', {name: '2015'}));

        await waitFor(() =>
            expect(mocks.api.getCompanyPersons).toHaveBeenLastCalledWith(
                '12345678',
                '2015-12-31',
            ),
        );
    });
});

describe('CompanyPeopleHistory — karty osôb', () => {
    beforeEach(() => {
        mocks.api.getCompanyPersons.mockReset();
    });

    it('vykreslí jednu kartu na skupinu, s menom osoby v hlavičke', async () => {
        mocks.api.getCompanyPersons.mockResolvedValue(
            answer({
                groups: [
                    group({id: 1, name: 'Ján Novák'}),
                    group({id: 2, name: 'Mária Veselá'}),
                ],
            }),
        );

        history();

        expect(await screen.findByText('Ján Novák')).toBeInTheDocument();
        expect(screen.getByText('Mária Veselá')).toBeInTheDocument();
    });

    it('počíta funkcie po slovensky, v troch tvaroch', async () => {
        // The same plural rule as the period note, on the same screen: 1
        // funkcia, 2-4 funkcie, 5+ funkcií. A card that said "4 funkcií" would
        // be the one sentence on this screen a Slovak reader trips over.
        const withOffices = (count: number, name: string) =>
            group({
                // One id per group, as the backend sends: these are four
                // different people and not one person counted four times.
                id: count,
                name,
                offices: Array.from({length: count}, (_, index) =>
                    office({vznik_funkcie: `201${index}-01-01`}),
                ),
            });
        mocks.api.getCompanyPersons.mockResolvedValue(
            answer({
                groups: [
                    withOffices(1, 'Jedna'),
                    withOffices(2, 'Dve'),
                    withOffices(4, 'Štyri'),
                    withOffices(5, 'Päť'),
                ],
            }),
        );

        history();

        expect(await screen.findByText('1 funkcia')).toBeInTheDocument();
        expect(screen.getByText('2 funkcie')).toBeInTheDocument();
        expect(screen.getByText('4 funkcie')).toBeInTheDocument();
        expect(screen.getByText('5 funkcií')).toBeInTheDocument();
    });

    it('vypíše pri funkcii jej názov, ale nie firmu, na ktorú sa čitateľ práve pozerá', async () => {
        // Every row here is this company, which is the company the reader is
        // already on. Twenty former officers would repeat one name and one IČO
        // twenty times and say nothing with any of them. The role is the thing
        // that differs from row to row, so it stays.
        mocks.api.getCompanyPersons.mockResolvedValue(answer());

        history();

        expect(await screen.findByText('Konateľ')).toBeInTheDocument();
        expect(screen.queryByText('IČO: 12345678')).not.toBeInTheDocument();
        // The name is a link on a person's page, where it leads somewhere. Here
        // it would lead to the page the reader is already reading.
        expect(screen.queryByRole('link')).not.toBeInTheDocument();
    });

    it('povie, keď k zvolenému dátumu nemala osoba žiadnu funkciu', async () => {
        mocks.api.getCompanyPersons.mockResolvedValue(
            answer({as_of: '2015-12-31', groups: [group({offices: []})]}),
        );

        history();

        expect(
            await screen.findByText('K tomuto dátumu nemala táto osoba vo firme žiadnu funkciu.'),
        ).toBeInTheDocument();
    });
});

describe('CompanyPeopleHistory — obdobie a čo v ňom chýba', () => {
    beforeEach(() => {
        mocks.api.getCompanyPersons.mockReset();
    });

    it('neukazuje obdobie, keď odpoveď žiadne nemá', async () => {
        // `as_of: null` is the whole record, which is not the company on any
        // particular day -- a banner saying "Súčasný stav" over it would name a
        // date nobody asked about.
        mocks.api.getCompanyPersons.mockResolvedValue(answer({as_of: null}));

        history();

        expect(await screen.findByText('Ján Novák')).toBeInTheDocument();
        expect(screen.queryByText('Súčasný stav')).not.toBeInTheDocument();
    });

    it('pomenuje obdobie dňom z odpovede, nie dňom, ktorý sa pýtal', async () => {
        // Between the click and the answer those are two days, and a heading
        // reading the requested one would name a period over a list fetched for
        // another.
        mocks.api.getCompanyPersons.mockResolvedValue(answer({as_of: '2015-12-31'}));

        history();

        expect(await screen.findByText('Stav k 31. 12. 2015')).toBeInTheDocument();
    });

    it('povie, koľko zápisov sa do obdobia nedalo priradiť', async () => {
        // A relation whose start the register never stated cannot be shown to
        // have been in force on any day, so a period view drops it. Dropping it
        // silently would make the list look complete while it is not.
        mocks.api.getCompanyPersons.mockResolvedValue(
            answer({as_of: '2015-12-31', undated_excluded: 2}),
        );

        history();

        expect(
            await screen.findByText(
                '2 zápisy bez dátumu vzniku sa do zvoleného obdobia nedá priradiť.',
            ),
        ).toBeInTheDocument();
    });

    it('mlčí o vynechaných zápisoch, keď žiadne nevynechalo', async () => {
        mocks.api.getCompanyPersons.mockResolvedValue(
            answer({as_of: '2015-12-31', undated_excluded: 0}),
        );

        history();

        expect(await screen.findByText('Stav k 31. 12. 2015')).toBeInTheDocument();
        expect(bodyText()).not.toContain('bez dátumu vzniku');
    });
});

describe('CompanyPeopleHistory — prázdne odpovede', () => {
    beforeEach(() => {
        mocks.api.getCompanyPersons.mockReset();
    });

    it('povie, že register neuvádza nikoho, keď sa nepýtalo na dátum', async () => {
        mocks.api.getCompanyPersons.mockResolvedValue(answer({groups: [], as_of: null}));

        history();

        expect(await screen.findByText(EMPTY_TODAY)).toBeInTheDocument();
        expect(screen.queryByText(EMPTY_AT_DATE)).not.toBeInTheDocument();
    });

    it('povie, že k dátumu neuvádza nikoho, keď sa na dátum pýtalo', async () => {
        // "Nobody holds an office now" and "nobody held one in 2015" are two
        // claims, and this is the only screen that can make the second one.
        mocks.api.getCompanyPersons.mockResolvedValue(
            answer({groups: [], as_of: '2015-12-31'}),
        );

        history();

        expect(await screen.findByText(EMPTY_AT_DATE)).toBeInTheDocument();
        expect(screen.queryByText(EMPTY_TODAY)).not.toBeInTheDocument();
    });

    it('vypíše dôvod zlyhania a netvrdí pritom, že firma nemá osoby', async () => {
        // A failed fetch and an empty register look identical on screen, and
        // they are opposites: one says the register holds nobody, the other
        // says we never got to read it. The rejection here is not an `Error`,
        // which is the case the fallback sentence exists for.
        mocks.api.getCompanyPersons.mockRejectedValue('výpadok siete');

        history();

        expect(
            await screen.findByText('Nepodarilo sa načítať históriu osôb'),
        ).toBeInTheDocument();
        expect(screen.queryByText(EMPTY_TODAY)).not.toBeInTheDocument();
    });

    it('nechá správu zo servera, keď ju odpoveď priniesla', async () => {
        mocks.api.getCompanyPersons.mockRejectedValue(new Error('Neplatný dátum.'));

        history();

        expect(await screen.findByText('Neplatný dátum.')).toBeInTheDocument();
    });
});

describe('CompanyPeopleHistory — stará odpoveď nesmie prepísať novú', () => {
    beforeEach(() => {
        mocks.api.getCompanyPersons.mockReset();
    });

    it('nechá na obrazovke odpoveď na poslednú otázku', async () => {
        // Two answers can be in the air at once -- the chips stay clickable
        // while a request is in flight, and a new IČO is a second question
        // asked before the first was answered. However that is arranged, the
        // rule is one: what is on screen is the answer to the last question
        // asked, and the slower answer is dropped rather than landing on top.
        let resolveFirst!: (value: CompanyPersonsResponse) => void;
        let resolveSecond!: (value: CompanyPersonsResponse) => void;
        const first = new Promise<CompanyPersonsResponse>((resolve) => (resolveFirst = resolve));
        const second = new Promise<CompanyPersonsResponse>((resolve) => (resolveSecond = resolve));
        mocks.api.getCompanyPersons
            .mockImplementationOnce(() => first)
            .mockImplementationOnce(() => second);
        // Registered on the same promise *after* the component's own handler,
        // so awaiting it is proof the stale answer was delivered and looked at
        // -- without it, "the stale answer is not on screen" would also pass if
        // it had never arrived at all.
        const staleDelivered = first.then(() => undefined);

        const {rerender} = history('11111111');
        // A new IČO is a new question; the period is held with the IČO it was
        // chosen for, so this is one request and not a reset plus a fetch.
        rerender(<CompanyPeopleHistory ico="22222222" />);
        await waitFor(() => expect(mocks.api.getCompanyPersons).toHaveBeenCalledTimes(2));

        resolveSecond(answer({ico: '22222222', groups: [group({name: 'Nová osoba'})]}));
        expect(await screen.findByText('Nová osoba')).toBeInTheDocument();

        await act(async () => {
            resolveFirst(answer({ico: '11111111', groups: [group({name: 'Stará osoba'})]}));
            await staleDelivered;
        });

        expect(screen.queryByText('Stará osoba')).not.toBeInTheDocument();
        expect(screen.getByText('Nová osoba')).toBeInTheDocument();
    });

    it('pýta sa na novú firmu bez roka zvoleného pre starú', async () => {
        // The year belongs to one company's record: sending 2015 chosen on
        // another company's page would filter this one by a date nobody picked
        // for it. The period is derived from the prop rather than cleared in an
        // effect, because an effect runs after the fetch has already gone out.
        mocks.api.getCompanyPersons.mockResolvedValue(answer({periods: [2015]}));

        const {rerender} = history('11111111');
        const user = userEvent.setup();
        await user.click(await screen.findByRole('button', {name: '2015'}));
        await waitFor(() =>
            expect(mocks.api.getCompanyPersons).toHaveBeenLastCalledWith(
                '11111111',
                '2015-12-31',
            ),
        );

        rerender(<CompanyPeopleHistory ico="22222222" />);

        await waitFor(() =>
            expect(mocks.api.getCompanyPersons).toHaveBeenLastCalledWith('22222222', null),
        );
        expect(mocks.api.getCompanyPersons).toHaveBeenCalledTimes(3);
    });
});
