import {describe, expect, it} from 'vitest';
import {render, screen} from '@testing-library/react';
import {SectionNotice} from './SectionNotice';
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
