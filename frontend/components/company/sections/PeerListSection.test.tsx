import {beforeEach, describe, expect, it, vi} from 'vitest';
import {screen, waitFor} from '@testing-library/react';
import {PeerListSection} from './PeerListSection';
import {renderWithProviders} from '../../../test/testUtils';
import type {PeerList, PeerScope, PeerRow} from '../../../types';

const mocks = vi.hoisted(() => ({getPeers: vi.fn()}));

vi.mock('../../../api', () => ({api: {getPeers: mocks.getPeers}}));

const row = (overrides: Partial<PeerRow> = {}): PeerRow => ({
    ico: '31333532',
    name: 'ESET, spol. s r.o.',
    city: 'Bratislava',
    nace_code: '62010',
    nace_name: 'Počítačové programovanie',
    year: 2021,
    revenue: 571_637_176,
    profit: 100_000,
    ...overrides,
});

const payload = (overrides: Partial<PeerList> = {}): PeerList => ({
    scope: 'kraj',
    subject: 'SK010',
    subject_label: 'Bratislavský kraj',
    reason: null,
    ranked_by: 'revenue',
    total_ranked: 1,
    total_in_scope: 1,
    results: [row()],
    ...overrides,
});

/** NBSP-separated thousands are correct and unreadable in an assertion. */
const render = (scope: PeerScope, data: PeerList | Error) => {
    if (data instanceof Error) mocks.getPeers.mockRejectedValue(data);
    else mocks.getPeers.mockResolvedValue(data);

    return renderWithProviders(<PeerListSection ico="12345678" scope={scope}/>);
};

const bodyText = () => document.body.textContent!.replace(/ /g, ' ');

describe('PeerListSection', () => {
    beforeEach(() => {
        mocks.getPeers.mockReset();
    });

    it('asks the backend for the scope its heading names', async () => {
        // The section id and the scope are wired together by hand in
        // `pages/Company.tsx`, so a copy-paste there would put the region's
        // ranking under the industry's heading. Nothing else would notice.
        render('odvetvie', payload({scope: 'odvetvie', subject: '62'}));

        await waitFor(() =>
            expect(mocks.getPeers).toHaveBeenCalledWith('12345678', 'odvetvie')
        );
    });

    it('lists a row with its own statement year and its figures', async () => {
        render('kraj', payload());

        expect(await screen.findByText('ESET, spol. s r.o.')).toBeInTheDocument();
        expect(screen.getByText('31333532')).toBeInTheDocument();
        expect(screen.getByText('Bratislava')).toBeInTheDocument();
        expect(screen.getByText('Počítačové programovanie')).toBeInTheDocument();
        // The row's own year, not the subject's: every company is shown at its
        // most recent filing, which is a different year per row.
        expect(screen.getByText('2021')).toBeInTheDocument();
        expect(bodyText()).toContain('571 637 176 €');
    });

    it('keeps a missing figure missing instead of showing a zero', async () => {
        // A statement can carry a balance sheet and no income statement, so a
        // row with no profit is a normal row. Rendering it as 0 € would invent a
        // figure the filing never had.
        render('kraj', payload({results: [row({profit: null, revenue: null})]}));

        expect(await screen.findByText('ESET, spol. s r.o.')).toBeInTheDocument();
        expect(screen.getAllByText('—')).toHaveLength(2);
    });

    it('prints the population both numbers describe, not just the ranking', async () => {
        // The reason this section can be trusted at all. 187 of 105 760 is a
        // true sentence; "the largest firms in the region" is not, and the
        // reader is the one who has to be able to tell.
        render('kraj', payload({total_ranked: 187, total_in_scope: 105_760}));

        await screen.findByText(/V rozsahu Bratislavský kraj/);
        expect(bodyText()).toContain('105 760 firiem');
        expect(bodyText()).toContain('187 z nich');
    });

    it('says how many of how many are shown when the list is cut short', async () => {
        render('kraj', payload({total_ranked: 187}));
        expect(await screen.findByText(/Zobrazujeme prvých 10\./)).toBeInTheDocument();
    });

    it('says the list is complete when it is', async () => {
        render('kraj', payload({total_ranked: 1}));
        expect(await screen.findByText(/Zobrazujeme všetky\./)).toBeInTheDocument();
    });

    it('explains an empty ranking as an absence of filings, not an absence of firms', async () => {
        render('kraj', payload({total_ranked: 0, total_in_scope: 412, results: []}));

        await screen.findByText(/ani jedna z nich/);
        expect(bodyText()).toContain('412 firiem');
    });

    it('names the missing region rather than ranking nothing', async () => {
        render('kraj', payload({reason: 'no_region', subject: null, subject_label: null, results: [], total_in_scope: 0}));

        expect(await screen.findByText(/nemáme pre túto firmu kraj sídla/)).toBeInTheDocument();
        expect(screen.queryByRole('table')).not.toBeInTheDocument();
    });

    it('names the missing NACE code rather than ranking nothing', async () => {
        render('odvetvie', payload({reason: 'no_nace', subject: null, subject_label: null, results: []}));

        expect(await screen.findByText(/čitateľný kód SK NACE/)).toBeInTheDocument();
        expect(screen.queryByRole('table')).not.toBeInTheDocument();
    });

    it('admits when "similar" was answered by size instead', async () => {
        // `podobne` falls back to revenue order when the subject has no filed
        // revenue. Same rows, different meaning -- and the section is the only
        // place that difference can reach the reader.
        render('podobne', payload({scope: 'podobne', ranked_by: 'revenue'}));

        expect(await screen.findByText(/nie je zoradený podľa podobnosti/)).toBeInTheDocument();
    });

    it('does not claim a fallback it did not make', async () => {
        render('podobne', payload({scope: 'podobne', ranked_by: 'similarity'}));

        await screen.findByText('ESET, spol. s r.o.');
        expect(screen.queryByText(/nie je zoradený podľa podobnosti/)).not.toBeInTheDocument();
    });

    it('falls back to the register itself when the whole register is the scope', async () => {
        render('trzby', payload({scope: 'trzby', subject: null, subject_label: null}));

        await screen.findByText(/V rozsahu celý register/);
    });

    it('gives every scope its own heading', async () => {
        // `SCOPE_COPY` is a `Record`, so this cannot fail for a missing key --
        // it fails if two scopes are given the same copy, which the type system
        // has no opinion about.
        const titles: Record<PeerScope, string> = {
            podobne: 'Podobné spoločnosti',
            kraj: 'Firmy v kraji',
            odvetvie: 'Firmy v odvetví',
            trzby: 'Firmy podľa tržieb',
        };

        for (const [scope, title] of Object.entries(titles) as [PeerScope, string][]) {
            mocks.getPeers.mockResolvedValue(payload({scope}));
            const {unmount} = renderWithProviders(
                <PeerListSection ico="12345678" scope={scope}/>
            );

            expect(await screen.findByText(title)).toBeInTheDocument();
            unmount();
        }
    });

    it('says the list failed rather than rendering an empty one', async () => {
        // An empty table and a failed request look identical to a reader, and
        // only one of them means "there are no such firms".
        render('kraj', new Error('network'));

        expect(await screen.findByText(/Zoznam sa nepodarilo načítať/)).toBeInTheDocument();
        expect(screen.queryByText(/ani jedna z nich/)).not.toBeInTheDocument();
    });
});
