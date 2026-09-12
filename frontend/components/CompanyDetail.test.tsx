import {beforeEach, describe, expect, it, vi} from 'vitest';
import {screen, within} from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import {CompanyDetail} from './CompanyDetail';
import {COMPANY_SECTIONS, DEFAULT_SECTION_ID, getSection} from '../companySections';
import {makeCompany, renderWithProviders} from '../test/testUtils';

const mocks = vi.hoisted(() => ({
    api: {
        getWatchlist: vi.fn(),
        getPeers: vi.fn(),
        getCompanyEvents: vi.fn(),
        addToWatchlist: vi.fn(),
        removeFromWatchlist: vi.fn(),
    },
}));

vi.mock('../api', () => ({api: mocks.api}));

/**
 * The tab bar itself, so a section's label is looked for where a tab would be
 * rather than anywhere on the page -- `Prehľad o firme` is also an InfoCard
 * title, and a match outside the bar would prove nothing about reachability.
 */
const tabBar = (container: HTMLElement): HTMLElement => {
    const bar = container.querySelector('.tab-nav');
    if (!bar) throw new Error('CompanyDetail rendered no tab bar');
    return bar as HTMLElement;
};

const tabLabels = (container: HTMLElement): string[] =>
    Array.from(tabBar(container).querySelectorAll('button'))
        .map((button) => button.textContent?.trim() ?? '');

describe('CompanyDetail', () => {
    beforeEach(() => {
        mocks.api.getWatchlist.mockResolvedValue([]);
        mocks.api.getPeers.mockResolvedValue({results: [], total: 0});
        mocks.api.getCompanyEvents.mockResolvedValue([]);
    });

    it('gives every section in the registry a tab, in registry order', () => {
        // The regression this file exists for. `CompanyDetail` used to carry its
        // own hand-written list of eight tabs under ids of its own invention
        // (`overview`, `financials`, `people`, `registers`, `connections`),
        // which shared the bodies with the company page but not the list -- so
        // twelve of the twenty sections were unreachable from the view most
        // readers use, and nothing failed. This asserts membership against the
        // registry, so a section added there without this view noticing is a red
        // test rather than a section nobody can open.
        const {container} = renderWithProviders(<CompanyDetail company={makeCompany()}/>);

        expect(tabLabels(container)).toEqual(COMPANY_SECTIONS.map((section) => section.label));
    });

    it('answers a tab with no body by stating why, not with a blank panel', async () => {
        // The other half of the rule: the tab stays -- dropping it would make
        // this a list that has everything -- and the registry's own sentence
        // says what is missing. Named by id rather than by index so the test
        // still points at a `planned` section if the registry is reordered.
        const user = userEvent.setup();
        const planned = getSection('platobne-rozkazy')!;
        expect(planned.status).not.toBe('ready');

        const {container} = renderWithProviders(<CompanyDetail company={makeCompany()}/>);
        await user.click(within(tabBar(container)).getByRole('button', {name: planned.label}));

        // Verbatim, because that sentence is the whole mechanism.
        expect(await screen.findByText(planned.note)).toBeInTheDocument();
        expect(screen.getByText('Zatiaľ nemáme')).toBeInTheDocument();
    });

    it('renders the body of a section that has one instead of its note', async () => {
        // Without this, a view that answered *every* tab with a notice would
        // satisfy the test above. `zaverky` is the section the company page's
        // own spec uses for the same claim.
        const user = userEvent.setup();
        const zaverky = getSection('zaverky')!;
        expect(zaverky.status).toBe('ready');

        const {container} = renderWithProviders(<CompanyDetail company={makeCompany()}/>);
        await user.click(within(tabBar(container)).getByRole('button', {name: zaverky.label}));

        expect(await screen.findByText(/sa do tejto databázy nesťahujú/)).toBeInTheDocument();
        expect(screen.queryByText(zaverky.note)).not.toBeInTheDocument();
    });

    it('opens on the registry default, not on a hardcoded first tab', () => {
        // `DEFAULT_SECTION_ID` is the registry's, and the standalone page
        // redirects to the same one -- an inline view that started somewhere
        // else would disagree with the URL a reader shares.
        const {container} = renderWithProviders(<CompanyDetail company={makeCompany()}/>);

        const active = within(tabBar(container)).getByRole('button', {
            name: getSection(DEFAULT_SECTION_ID)!.label,
        });
        expect(active.classList.contains('active')).toBe(true);
    });
});
