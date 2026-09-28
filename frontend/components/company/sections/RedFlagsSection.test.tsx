import {describe, expect, it} from 'vitest';
import {screen} from '@testing-library/react';
import {RedFlagsSection} from './RedFlagsSection';
import {renderWithProviders} from '../../../test/testUtils';
import type {
    Company,
    CompanyRiskCoverage,
    CompanyRiskIndicators,
    RiskFlag,
} from '../../../types';

/** Minimal company carrying only what this section reads. */
const makeCompany = (redFlags?: CompanyRiskIndicators): Company =>
    ({ico: '12345678', redFlags} as unknown as Company);

const flag = (overrides: Partial<RiskFlag> = {}): RiskFlag => ({
    code: 'trzby_bez_zamestnancov',
    label: 'Tržby bez zamestnancov',
    severity: 'medium',
    state: 'fired',
    detail: '2 400 000 € pri 0 zamestnancoch',
    reason: null,
    evidence: {},
    ...overrides,
});

const coverage = (overrides: Partial<CompanyRiskCoverage> = {}): CompanyRiskCoverage => ({
    financial_years: 3,
    has_financials: true,
    persons_linked: 4,
    size_band_known: true,
    vat_register_dated: true,
    ...overrides,
});

const payload = (overrides: Partial<CompanyRiskIndicators> = {}): CompanyRiskIndicators => ({
    flags: [
        flag(),
        flag({
            code: 'obrat_zasob',
            label: 'Neprimerane rýchly obrat zásob',
            severity: 'medium',
            state: 'clear',
            detail: 'obrat 18 dní',
        }),
        flag({
            code: 'dph_vymazany',
            label: 'Vymazaný z registra DPH',
            severity: 'high',
            state: 'unassessed',
            detail: null,
            reason: 'nemáme ani dátum registrácie, ani dátum výmazu',
        }),
    ],
    counts: {fired: 1, clear: 1, unassessed: 1},
    coverage: coverage(),
    ...overrides,
});

describe('RedFlagsSection', () => {
    it('renders every rule with the sentence the server wrote for it', () => {
        renderWithProviders(<RedFlagsSection company={makeCompany(payload())} />);

        expect(screen.getByText('Tržby bez zamestnancov')).toBeInTheDocument();
        expect(screen.getByText('2 400 000 € pri 0 zamestnancoch')).toBeInTheDocument();
        expect(screen.getByText('Neprimerane rýchly obrat zásob')).toBeInTheDocument();
        expect(screen.getByText('Vymazaný z registra DPH')).toBeInTheDocument();
    });

    it('tells a rule that found nothing apart from one that could not look', () => {
        // The distinction the whole feature is built around, and the one this
        // section must not blur: "bez nálezu" says a rule read the data and had
        // nothing to report, "nevyhodnotené" says it never read anything. Drawn
        // as the same chip, a company with no závierka at all would look
        // examined.
        renderWithProviders(<RedFlagsSection company={makeCompany(payload())} />);

        expect(screen.getByText('bez nálezu')).toBeInTheDocument();
        expect(screen.getByText('nevyhodnotené')).toBeInTheDocument();
        expect(screen.getByText('nájdené')).toBeInTheDocument();
    });

    it('prints the reason in the outcome column for a rule that could not run', () => {
        // The `reason` and not the `detail`: the third column asks "what did we
        // find", and for this row the honest answer is why there is nothing.
        renderWithProviders(<RedFlagsSection company={makeCompany(payload())} />);

        expect(
            screen.getByText('nemáme ani dátum registrácie, ani dátum výmazu'),
        ).toBeInTheDocument();
    });

    it('counts the three outcomes and never sums them into one', () => {
        renderWithProviders(<RedFlagsSection company={makeCompany(payload())} />);

        expect(screen.getByText('nájdené: 1')).toBeInTheDocument();
        expect(screen.getByText('bez nálezu: 1')).toBeInTheDocument();
        expect(screen.getByText('nevyhodnotené: 1')).toBeInTheDocument();
        expect(screen.getByText('z 3 pravidiel')).toBeInTheDocument();
    });

    it('says what it could not examine, so "no flags" is not read as "clean"', () => {
        // The section's own reason for being `partial`. A company with no
        // statement and no person graph has been examined by almost none of the
        // rules, and the panel has to say which -- otherwise the two companies
        // look the same on this page.
        renderWithProviders(
            <RedFlagsSection
                company={makeCompany(
                    payload({
                        flags: [
                            flag({
                                code: 'tržby',
                                state: 'unassessed',
                                detail: null,
                                reason: 'nemáme závierku',
                            }),
                        ],
                        counts: {fired: 0, clear: 0, unassessed: 1},
                        coverage: coverage({
                            financial_years: 0,
                            has_financials: false,
                            persons_linked: 0,
                            size_band_known: false,
                            vat_register_dated: false,
                        }),
                    })
                )}
            />
        );

        expect(screen.getByText('Prečítané závierky')).toBeInTheDocument();
        // Two rows, both empty, so both read `žiadne` -- the count is asserted
        // rather than one of them grabbed, because a panel that printed only one
        // of the two gaps is exactly the failure this test is about.
        expect(screen.getAllByText('žiadne')).toHaveLength(2);
        expect(screen.getByText('register ju neuvádza')).toBeInTheDocument();
        expect(screen.getByText('dátum neevidujeme')).toBeInTheDocument();
    });

    it('names no offence and accuses nobody', () => {
        // §11.22.2, asserted rather than trusted. The section is named after two
        // fraud patterns, and the temptation is to write them beside a company
        // as a finding. They belong in the introduction, as the thing this
        // section does not claim to have detected -- and nowhere else.
        //
        // The intro may name them, so the check is on the *rows*: a reader
        // scrolling to a firm's own line must find a number and a date, never
        // an accusation.
        renderWithProviders(<RedFlagsSection company={makeCompany(payload())} />);

        const rows = document.querySelectorAll('tbody tr');
        expect(rows.length).toBeGreaterThan(0);
        for (const row of Array.from(rows)) {
            const text = (row.textContent ?? '').toLowerCase();
            expect(text).not.toMatch(
                /karusel|biely|kôň|podvod|falš|nastrčen|podozriv|kriminál|trestn/,
            );
        }
    });

    it('declines to draw a payload the API did not send', () => {
        // `undefined` is what a response mapped before this field existed looks
        // like. An empty table under the heading would read as "no indicators",
        // which is a claim about the company rather than about our response.
        renderWithProviders(<RedFlagsSection company={makeCompany(undefined)} />);

        expect(
            screen.getByText(/Indikátory sa pre túto firmu nepodarilo načítať/),
        ).toBeInTheDocument();
    });

    it('declines to draw a payload whose rules all vanished', () => {
        // Not a hypothetical shape: `flag.counts` would still say three rules
        // ran while the table had no rows to show for it.
        renderWithProviders(
            <RedFlagsSection company={makeCompany(payload({flags: []}))} />
        );

        expect(
            screen.getByText(/Indikátory sa pre túto firmu nepodarilo načítať/),
        ).toBeInTheDocument();
    });
});
