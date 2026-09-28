import {describe, expect, it} from 'vitest';
import {render, screen} from '@testing-library/react';
import {SectionNotice, SectionStatusBanner} from './SectionNotice';
import type {CompanySection, SectionStatus} from '../../companySections';

const section = (status: SectionStatus, note: string): CompanySection => ({
    id: 'probe',
    label: 'Skúšobná sekcia',
    icon: 'fa-flask',
    group: 'Financie',
    status,
    note,
});

describe('SectionNotice', () => {
    it('states the reason a section has no body instead of leaving a blank panel', () => {
        render(<SectionNotice section={section('planned', 'Tabuľku ešte nemáme.')} />);
        expect(screen.getByText('Zatiaľ nemáme')).toBeInTheDocument();
        expect(screen.getByText('Tabuľku ešte nemáme.')).toBeInTheDocument();
    });

    it('still says a section is unreliable when its data cannot be trusted', () => {
        // No section carries `unreliable` today — `suvaha` was the last one and
        // the balance-sheet reading was fixed on 2026-09-12. The status stays
        // in the vocabulary because "we have the numbers and they are wrong" is
        // a state this product can reach again, and the one thing worse than
        // showing wrong numbers is showing them without saying so. This keeps
        // that branch exercised rather than leaving it to be discovered.
        render(<SectionNotice section={section('unreliable', 'Čísla nesedia.')} />);
        expect(screen.getByText('Údaje sú nespoľahlivé')).toBeInTheDocument();
        expect(screen.getByText('Čísla nesedia.')).toBeInTheDocument();
    });
});

describe('SectionStatusBanner', () => {
    it('says the same thing as the notice, in the space above a body', () => {
        // The same sentence, because it is the same fact: the registry's `note`
        // is why the section is not `ready`, and a `partial` section has to say
        // it without giving up the part it does have. Two components, one
        // source -- if the wording ever diverges, the chip and the sentence
        // would stop agreeing with the rail that drew the reader here.
        render(<SectionStatusBanner section={section('partial', 'Máme časť registra.')} />);

        expect(screen.getByText('Máme časť')).toBeInTheDocument();
        expect(screen.getByText('Máme časť registra.')).toBeInTheDocument();
    });

    it('is not an empty state: it has no centred placeholder', () => {
        // The distinction that makes it a second component rather than a prop.
        // A centred block above real content reads as a page that failed to
        // load, which is the one impression a section that *did* load must not
        // give. `text-center` is what `SectionNotice` uses to say "there is
        // nothing here"; its absence is the whole difference.
        const {container} = render(
            <SectionStatusBanner section={section('partial', 'Máme časť registra.')} />
        );

        expect(container.querySelector('.text-center')).toBeNull();
        expect(container.querySelector('.py-6')).toBeNull();
    });
});
