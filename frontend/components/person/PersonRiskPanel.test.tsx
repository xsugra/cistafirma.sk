import {describe, expect, it} from 'vitest';
import {screen} from '@testing-library/react';
import {PersonRiskPanel} from './PersonRiskPanel';
import {renderWithProviders} from '../../test/testUtils';
import type {
    PersonRiskCoverage,
    PersonRiskIndicators,
    RiskFlag,
} from '../../types';

const flag = (overrides: Partial<RiskFlag> = {}): RiskFlag => ({
    code: 'serialny_statutar',
    label: 'Funkcia vo viacerých firmách',
    severity: 'high',
    state: 'fired',
    detail: 'evidovaná v 14 firmách (14× Konateľ), z toho 5 zrušených',
    reason: null,
    evidence: {},
    ...overrides,
});

const coverage = (overrides: Partial<PersonRiskCoverage> = {}): PersonRiskCoverage => ({
    companies: 14,
    companies_dissolved: 5,
    companies_active_known: 12,
    companies_function_state_unknown: 2,
    relations: 15,
    ...overrides,
});

const payload = (overrides: Partial<PersonRiskIndicators> = {}): PersonRiskIndicators => ({
    flags: [flag()],
    counts: {fired: 1, clear: 0, unassessed: 0},
    coverage: coverage(),
    ...overrides,
});

describe('PersonRiskPanel', () => {
    it('states the counts the server computed for the person', () => {
        renderWithProviders(<PersonRiskPanel indicators={payload()} />);

        expect(screen.getByText('Funkcia vo viacerých firmách')).toBeInTheDocument();
        expect(
            screen.getByText('evidovaná v 14 firmách (14× Konateľ), z toho 5 zrušených'),
        ).toBeInTheDocument();
        expect(screen.getByText('z 1 pravidiel')).toBeInTheDocument();
    });

    it('says in the panel itself that this is not a claim about the person', () => {
        // The one sentence this panel cannot ship without. A count of companies
        // beside a human being's name reads as an assessment of that human
        // unless the panel says otherwise, and the product may write "14
        // companies, 5 struck off" -- a fact with dates -- and may never write
        // "straw man", which is a claim no public register can support.
        renderWithProviders(<PersonRiskPanel indicators={payload()} />);

        expect(screen.getByText(/Nie je to tvrdenie o tejto osobe/)).toBeInTheDocument();
        expect(screen.getByText(/sa z verejných registrov preukázať nedá/)).toBeInTheDocument();
    });

    it('reports our own unread history as a gap, not as an indicator', () => {
        // `is_active is None` means the ORSR history was never read for that
        // company. Among the flags it would dress a hole in our scraping up as
        // a fact about a person, so it is stated separately -- and it is the
        // reason the third count differs from the first.
        renderWithProviders(<PersonRiskPanel indicators={payload()} />);

        expect(
            screen.getByText(/Pri 2 z 14 firiem sme históriu funkcií ešte nečítali/),
        ).toBeInTheDocument();
        expect(screen.getByText(/medzera v našich dátach, nie zistenie o osobe/)).toBeInTheDocument();
    });

    it('says nothing about unknown history when there is none', () => {
        renderWithProviders(
            <PersonRiskPanel
                indicators={payload({
                    coverage: coverage({
                        companies: 3,
                        companies_dissolved: 1,
                        companies_active_known: 3,
                        companies_function_state_unknown: 0,
                    }),
                })}
            />
        );

        expect(screen.queryByText(/históriu funkcií ešte nečítali/)).not.toBeInTheDocument();
    });

    it('renders nothing at all when the response carried no indicators', () => {
        // The panel is the page's fourth section, and it returns `null` rather
        // than an empty frame: a heading over nothing would read as "this person
        // has no indicators", which is a claim about a person invented out of a
        // response we never got. The page's own coverage note is what says we
        // could not answer.
        const {container} = renderWithProviders(<PersonRiskPanel indicators={undefined} />);

        // The panel's own root, not `container`: RTL's container also holds
        // whatever the providers draw, so `toBeEmptyDOMElement` would be
        // asserting about `AuthProvider` and would pass or fail for reasons
        // that have nothing to do with this component.
        expect(container.querySelector('section')).toBeNull();
        expect(screen.queryByText('Rizikové indikátory')).not.toBeInTheDocument();
    });

    it('names no offence and accuses nobody', () => {
        // §11.22.2, asserted rather than trusted -- and it matters more here,
        // where the flags sit beside a natural person's name.
        renderWithProviders(
            <PersonRiskPanel
                indicators={payload({
                    flags: [
                        flag(),
                        flag({
                            code: 'odvetvova_rozptylenost',
                            label: 'Firmy naprieč odvetviami',
                            severity: 'low',
                            state: 'clear',
                            detail: 'firmy v 1 oddieli SK NACE',
                        }),
                    ],
                    counts: {fired: 1, clear: 1, unassessed: 0},
                })}
            />
        );

        const rows = document.querySelectorAll('li');
        expect(rows.length).toBeGreaterThan(0);
        for (const row of Array.from(rows)) {
            const text = (row.textContent ?? '').toLowerCase();
            expect(text).not.toMatch(
                /karusel|biely|kôň|podvod|falš|nastrčen|podozriv|kriminál|trestn/,
            );
        }
    });
});
