import {describe, expect, it} from 'vitest';
import {screen} from '@testing-library/react';
import {PersonRelationRow} from './PersonRelationRow';
import {renderWithProviders} from '../../test/testUtils';
import type {PersonRelation} from '../../types';

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

/** NBSP is what `Intl.NumberFormat('sk-SK')` groups with; the words are not. */
const NBSP = '\u00A0';
const bodyText = () => document.body.textContent!.split(NBSP).join(' ');

const row = (overrides: Partial<PersonRelation> = {}) =>
    renderWithProviders(
        <ul>
            <PersonRelationRow relation={relation(overrides)}/>
        </ul>,
    );

describe('PersonRelationRow — the three answers', () => {
    it('says nevieme for an unread company, and never says it ended', () => {
        // The whole point of the feature. `null` is "we have never read this
        // company's history", and rendering it as ended states a fact about a
        // company nobody checked -- which is what the backend itself did until
        // 2026-09-13, when it wrote `true` for every relation it extracted.
        row({is_active: null});

        expect(screen.getByText('nevieme')).toBeInTheDocument();
        expect(screen.queryByText('nie')).not.toBeInTheDocument();
        expect(screen.queryByText('áno')).not.toBeInTheDocument();
    });

    it('spells out what nevieme means, rather than leaving it in a tooltip', () => {
        // Same sentence as the graph legend's tooltip: one absence, one wording.
        row({is_active: null});

        expect(
            screen.getByText('Funkciu sme pre túto firmu ešte neoverili v registri.'),
        ).toBeInTheDocument();
    });

    it('distinguishes an ended function from an unknown one', () => {
        row({is_active: false, zanik_funkcie: '2019-06-30'});

        expect(screen.getByText('nie')).toBeInTheDocument();
        expect(screen.queryByText('nevieme')).not.toBeInTheDocument();
        // The "we never read it" sentence must not be borrowed for "it ended".
        expect(
            screen.queryByText('Funkciu sme pre túto firmu ešte neoverili v registri.'),
        ).not.toBeInTheDocument();
    });

    it('renders a current function as áno', () => {
        row({is_active: true});

        expect(screen.getByText('áno')).toBeInTheDocument();
        expect(screen.queryByText('nevieme')).not.toBeInTheDocument();
    });
});

describe('PersonRelationRow — what it prints', () => {
    it('links the company by its IČO, not by its name', () => {
        row();

        expect(screen.getByRole('link', {name: 'ESET, spol. s r. o.'})).toHaveAttribute(
            'href',
            '/firma/35757442',
        );
    });

    it('prints the role in words and the dates in Slovak form', () => {
        row({is_active: false, vznik_funkcie: '2010-01-01', zanik_funkcie: '2019-06-30'});

        const text = bodyText();
        expect(text).toContain('Konateľ');
        // DD.MM.YYYY and not the raw ISO value: a date-only string taken through
        // `new Date()` shifts by a day west of Greenwich.
        expect(text).toContain('01.01.2010');
        expect(text).toContain('30.06.2019');
    });

    it('leaves the dates out where the register gave none', () => {
        row({vznik_funkcie: null, zanik_funkcie: null});

        expect(bodyText()).not.toContain('Vznik funkcie');
        expect(bodyText()).not.toContain('Zánik funkcie');
    });

    it('says when a row stands for several filings, and stays quiet otherwise', () => {
        // The register files an office once per change; the backend folds a
        // chain of consecutive filings into the one tenure it describes. A
        // reader looking at a 2011 span must be able to tell whether that is
        // one filing or twelve, so the fold is stated. Where there is nothing
        // to state, saying "Spojené z 1" would be noise.
        row({intervals: 12});

        expect(bodyText()).toContain('Spojené z 12 po sebe idúcich zápisov');
    });

    it('does not claim a fold on an ordinary one-filing row', () => {
        row({intervals: 1});

        expect(bodyText()).not.toContain('Spojené');
    });
});
