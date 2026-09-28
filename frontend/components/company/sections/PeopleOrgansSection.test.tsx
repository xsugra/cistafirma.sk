import {describe, expect, it, vi} from 'vitest';
import {render, screen} from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import {PeopleOrgansSection} from './PeopleOrgansSection';
import {makeCompany} from '../../../test/testUtils';

/**
 * The two views are two questions about one company -- "who holds an office
 * now" and "who ever held one" -- and this spec pins the switch between them.
 *
 * The history view is its own fetch and its own screen, mocked here as a
 * marker: what this section owes is that the second view is reachable at all
 * and that the two do not render on top of each other. The cards it stands next
 * to are the real `PeopleSection`, so "the cards are gone" is asserted against
 * something actually rendered.
 */
vi.mock('../CompanyPeopleHistory', async () => {
    const {createElement} = await import('react');
    return {
        CompanyPeopleHistory: ({ico}: {ico: string}) =>
            createElement('p', null, `HISTÓRIA OSÔB pre ${ico}`),
    };
});

/**
 * The derivation from an ORSR payload is `useCompanyProfile`'s own subject and
 * is pinned elsewhere. Here it stands in so one card is on screen without a
 * company fixture that happens to reach the right legal-form profile.
 */
vi.mock('../useCompanyProfile', () => ({
    useCompanyProfile: () => ({
        profile: {
            statutar: {
                title: 'Štatutárny orgán',
                icon: 'fa-badge-check',
                subtitle: '',
                emptyLabel: 'Žiadny štatutárny orgán',
            },
        },
        structured: {},
        statutari: [{name: 'Ján Novák', role: 'Konateľ'}],
        spolocnici: [],
        prokuristy: [],
        predstavenstvo: [],
        kontrolnaKomisia: [],
        dozornaRada: [],
        akcionari: [],
        konanie: '',
        prokuraOpravnenie: [],
        showPredstavenstvo: false,
        showStatutar: true,
        showSpolocnici: false,
        showAkcionari: false,
        showDozornaRada: false,
        showKontrolnaKomisia: false,
        showProkura: false,
        showKonanie: false,
    }),
}));

const COMPANY = makeCompany({ico: '12345678'});

const section = () => render(<PeopleOrgansSection company={COMPANY} />);

const tab = (name: string) => screen.getByRole('button', {name});
const historyMarker = () => screen.queryByText('HISTÓRIA OSÔB pre 12345678');

/**
 * The toggle is always offered, including for a company with no officers today:
 * "nobody holds an office now" and "nobody ever did" are different claims, and
 * the company whose only officer left is exactly the case this view exists for.
 */
describe('PeopleOrgansSection — prepínanie Aktuálne / História', () => {
    it('otvorí karty osôb a históriu nechá zatvorenú', () => {
        section();

        expect(screen.getByText('Ján Novák')).toBeInTheDocument();
        expect(screen.getByText('Štatutárny orgán')).toBeInTheDocument();
        expect(historyMarker()).not.toBeInTheDocument();
    });

    it('pomenuje prepínač, aby sa dal nájsť podľa roly', () => {
        section();

        expect(screen.getByRole('group', {name: 'Zobrazenie osôb'})).toBeInTheDocument();
    });

    it('označí ako stlačené to zobrazenie, ktoré je naozaj otvorené', async () => {
        const user = userEvent.setup();
        section();

        expect(tab('Aktuálne')).toHaveAttribute('aria-pressed', 'true');
        expect(tab('História')).toHaveAttribute('aria-pressed', 'false');

        await user.click(tab('História'));

        expect(tab('História')).toHaveAttribute('aria-pressed', 'true');
        expect(tab('Aktuálne')).toHaveAttribute('aria-pressed', 'false');
    });

    it('vymení karty za históriu a pošle jej IČO firmy', async () => {
        const user = userEvent.setup();
        section();

        await user.click(tab('História'));

        expect(historyMarker()).toBeInTheDocument();
        // The two views are one question asked at two dates, not two sections:
        // showing both would put today's officers above a list that already
        // contains them.
        expect(screen.queryByText('Ján Novák')).not.toBeInTheDocument();
        expect(screen.queryByText('Štatutárny orgán')).not.toBeInTheDocument();
    });

    it('vráti karty, keď sa čitateľ prepne späť na Aktuálne', async () => {
        // The switch is a state and not a one-way door: a reader who looked at
        // the history and wants the current bodies back must not have to leave
        // the section to get them.
        const user = userEvent.setup();
        section();

        await user.click(tab('História'));
        await user.click(tab('Aktuálne'));

        expect(screen.getByText('Ján Novák')).toBeInTheDocument();
        expect(historyMarker()).not.toBeInTheDocument();
    });
});
