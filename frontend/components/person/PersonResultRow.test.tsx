import {describe, expect, it} from 'vitest';
import {screen} from '@testing-library/react';
import {PersonResultRow} from './PersonResultRow';
import {renderWithProviders} from '../../test/testUtils';
import type {PersonRelation, PersonSummary} from '../../types';

const relation = (overrides: Partial<PersonRelation> = {}): PersonRelation => ({
    ico: '35757442',
    name: 'ESET, spol. s r. o.',
    role: 'konatel',
    role_display: 'Konateľ',
    is_active: true,
    vznik_funkcie: '2010-01-01',
    zanik_funkcie: null,
    intervals: 1,
    ...overrides,
});

const person = (overrides: Partial<PersonSummary> = {}): PersonSummary => ({
    id: 12345,
    name: 'Miroslav Trnka',
    title: 'Ing.',
    person_ico: '',
    records: 1,
    companies: [relation()],
    ...overrides,
});

const row = (overrides: Partial<PersonSummary> = {}) =>
    renderWithProviders(<PersonResultRow person={person(overrides)}/>);

describe('PersonResultRow — one person, in a list of them', () => {
    it('links the person by id, not by name', () => {
        row();

        expect(screen.getByRole('link')).toHaveAttribute('href', '/osoba/12345');
    });

    it('prints the first company and counts the rest, rather than listing them', () => {
        // A person with forty companies would push every other person off the
        // screen; the row is a row in a list of people.
        row({
            companies: [
                relation(),
                relation({ico: '31333532', name: 'Neznáma, s. r. o.'}),
                relation({ico: '12345678', name: 'Tretia, s. r. o.'}),
            ],
        });

        expect(screen.getByText('Konateľ · ESET, spol. s r. o. a ďalšie 2')).toBeInTheDocument();
    });

    it('does not promise more companies than there are', () => {
        row();

        expect(screen.getByText('Konateľ · ESET, spol. s r. o.')).toBeInTheDocument();
    });

    it('carries the three-valued state, so a name is never shown bare', () => {
        // `null` is "we have never read this company's history" and must not be
        // rendered as either answer. The badge is why the row exists as a
        // component at all: a second rendering of this row would be the one that
        // quietly dropped it.
        row({companies: [relation({is_active: null})]});

        expect(screen.getByText('nevieme')).toBeInTheDocument();
    });

    it('renders a person we hold with no relations at all', () => {
        // Should not happen through the search endpoint, which returns people
        // found *by* their relations -- but a row that threw on it would take
        // the whole list down with it.
        row({companies: []});

        expect(screen.getByRole('link')).toHaveAttribute('href', '/osoba/12345');
        expect(screen.queryByText('nevieme')).not.toBeInTheDocument();
    });
});
