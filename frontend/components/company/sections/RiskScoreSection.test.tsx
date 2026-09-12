import {describe, expect, it} from 'vitest';
import {screen} from '@testing-library/react';
import {RiskScoreSection} from './RiskScoreSection';
import {renderWithProviders} from '../../../test/testUtils';
import type {Company, RiskScore, RiskScoreBreakdown} from '../../../types';

/** Minimal company carrying only what this section reads. */
const makeCompany = (riskScore: RiskScore): Company =>
    ({ico: '12345678', riskScore} as unknown as Company);

const breakdown = (overrides: Partial<RiskScoreBreakdown> = {}): RiskScoreBreakdown => ({
    start: 100,
    floor: 5,
    clamped: false,
    parts: [
        {key: 'debt', label: 'Evidované nedoplatky', delta: -32, detail: '10 000 €'},
        {key: 'zone', label: 'Altman Z-score', delta: -20, detail: 'pásmo bankrotu'},
        {key: 'roa', label: 'Rentabilita aktív', delta: -10, detail: '-3,2 %'},
    ],
    ...overrides,
});

describe('RiskScoreSection', () => {
    it('lists every factor with the weight it carried', () => {
        renderWithProviders(
            <RiskScoreSection
                company={makeCompany({score: 38, summary: 'Vysoké riziko', breakdown: breakdown()})}
            />
        );

        expect(screen.getByText('Evidované nedoplatky')).toBeInTheDocument();
        expect(screen.getByText('10 000 €')).toBeInTheDocument();
        expect(screen.getByText('-32')).toBeInTheDocument();
        expect(screen.getByText('-20')).toBeInTheDocument();
        expect(screen.getByText('-10')).toBeInTheDocument();
    });

    it('tells a factor that cost nothing apart from one it could not read', () => {
        // The distinction the section exists for. "bez vplyvu" claims the model
        // looked and found nothing to charge for; "nevyhodnotené" says we have
        // no závierka and the model never saw this company. Rendering the
        // second as a zero would claim a look that never happened.
        renderWithProviders(
            <RiskScoreSection
                company={makeCompany({
                    score: 100,
                    summary: 'Bez rizika',
                    breakdown: breakdown({
                        parts: [
                            {key: 'debt', label: 'Evidované nedoplatky', delta: 0, detail: 'žiadne'},
                            {key: 'zone', label: 'Altman Z-score', delta: 0, detail: 'bezpečná zóna'},
                            {key: 'roa', label: 'Rentabilita aktív', delta: null, detail: 'nemáme závierku'},
                        ],
                    }),
                })}
            />
        );

        expect(screen.getAllByText('bez vplyvu')).toHaveLength(2);
        expect(screen.getByText('nevyhodnotené')).toBeInTheDocument();
    });

    it('explains a floor that the deductions do not reach', () => {
        // 100 - 80 - 20 - 10 is -10 and the score is 5. A reader adding the
        // column up must be told why, or the table simply does not add up.
        renderWithProviders(
            <RiskScoreSection
                company={makeCompany({
                    score: 5,
                    summary: 'Vysoké riziko',
                    breakdown: breakdown({clamped: true}),
                })}
            />
        );

        expect(screen.getByText(/Súčet odpočtov je vyšší/)).toBeInTheDocument();
        expect(screen.getByText(/spodnej hranici 5/)).toBeInTheDocument();
    });

    it('says how many factors went unread rather than quietly scoring lower', () => {
        renderWithProviders(
            <RiskScoreSection
                company={makeCompany({
                    score: 80,
                    summary: 'Zvýšená opatrnosť',
                    breakdown: breakdown({
                        parts: [
                            {key: 'debt', label: 'Evidované nedoplatky', delta: 0, detail: 'žiadne'},
                            {key: 'zone', label: 'Altman Z-score', delta: -20, detail: 'pásmo bankrotu'},
                            {key: 'roa', label: 'Rentabilita aktív', delta: null, detail: 'nemáme závierku'},
                        ],
                    }),
                })}
            />
        );

        expect(screen.getByText(/1 z 3 faktorov sa nedalo vyhodnotiť/)).toBeInTheDocument();
    });

    it('declines to draw a breakdown the API did not send', () => {
        // `score: null` is what the mapper produces when the response carried no
        // risk score at all. The old mapper defaulted the field to 100, so this
        // case rendered as a perfect score on every company in the registry.
        renderWithProviders(
            <RiskScoreSection company={makeCompany({score: null, summary: '', breakdown: null})} />
        );

        expect(screen.getByText(/Skóre sa pre túto firmu nepodarilo načítať/)).toBeInTheDocument();
    });

    it('gets the Slovak plural of "bod" right', () => {
        // 1 bod, 2-4 body, 5+ bodov -- a decimal takes the genitive singular.
        const withDeduction = (delta: number) =>
            breakdown({
                parts: [{key: 'debt', label: 'Evidované nedoplatky', delta, detail: '1 €'}],
            });

        const {unmount} = renderWithProviders(
            <RiskScoreSection
                company={makeCompany({score: 99, summary: 'x', breakdown: withDeduction(-1)})}
            />
        );
        expect(screen.getByText(/Spolu odpočítané: 1 bod\./)).toBeInTheDocument();
        unmount();

        renderWithProviders(
            <RiskScoreSection
                company={makeCompany({score: 97, summary: 'x', breakdown: withDeduction(-3)})}
            />
        );
        expect(screen.getByText(/Spolu odpočítané: 3 body\./)).toBeInTheDocument();
    });
});
