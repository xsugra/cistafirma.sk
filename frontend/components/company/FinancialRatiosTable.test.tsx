import {describe, expect, it} from 'vitest';
import {screen} from '@testing-library/react';
import {FinancialRatiosTable} from './FinancialRatiosTable';
import {renderWithProviders} from '../../test/testUtils';
import type {RatioSet, YearAnalysis} from '../../types';

const NO_RATIOS: RatioSet = {
    roa: null,
    roe: null,
    ros: null,
    currentRatio: null,
    quickRatio: null,
    cashRatio: null,
    assetTurnover: null,
    receivablesCollection: null,
    debtToEquity: null,
    selfFinancingRatio: null,
};

const analysis = (
    zScore: number | null,
    zScoreZone: YearAnalysis['zScoreZone'],
    taffler: {
        score: number;
        zone: NonNullable<YearAnalysis['tafflerZone']>;
    } | null = null,
): YearAnalysis => ({
    year: 2023,
    ratios: NO_RATIOS,
    interpretation: {},
    zScore,
    zScoreLabel:
        zScoreZone === 'safe'
            ? 'Bezpečná zóna'
            : zScoreZone === 'grey'
              ? 'Šedá zóna'
              : zScoreZone === 'distress'
                ? 'Pásmo bankrotu'
                : null,
    zScoreZone,
    tafflerScore: taffler?.score ?? null,
    // The backend's own words, as `TAFFLER_ZONE_LABELS` spells them -- not a
    // paraphrase, so a test that passes here is a test about the real contract.
    tafflerLabel: taffler
        ? taffler.zone === 'safe'
            ? 'Nízka pravdepodobnosť bankrotu'
            : taffler.zone === 'grey'
              ? 'Nejednoznačná situácia'
              : 'Vysoká pravdepodobnosť bankrotu'
        : null,
    tafflerZone: taffler?.zone ?? null,
});

/**
 * The banner renders the zone the backend decided, not a ladder of its own.
 *
 * The ladder stood in five places and this file held three of them -- banner,
 * chip and caption, all `> 2.90` / `> 1.23`, the same rule as the service's.
 * These tests are therefore not a regression test for a wrong zone here: the
 * three copies agreed with the service, so this component never painted the
 * wrong colour. What it did was hold a third, fourth and fifth copy of a
 * boundary that lives in `financial_analysis`, which is how the other two
 * copies drifted (`api.ts` and `pdf_report.py` had the mirror, `< 1.23` /
 * `< 2.90`, so a company on exactly 1.23 or exactly 2.90 was called distress
 * by the ratio table and grey by the risk summary printed beside it).
 *
 * So these cases pin the *contract*: the component paints the zone it is
 * given, at the two boundary values where a re-derived ladder would have to
 * agree with the service by luck. A future edit that goes back to reading
 * `zScore` fails here.
 */
describe('FinancialRatiosTable — Altman zone', () => {
    it('paints the distress zone the backend reported for a score of exactly 1.23', () => {
        renderWithProviders(<FinancialRatiosTable analysis={analysis(1.23, 'distress')} />);

        expect(screen.getByText('Zvýšené riziko bankrotu')).toBeTruthy();
        expect(screen.getByText('Pásmo bankrotu')).toBeTruthy();
        expect(screen.queryByText('Nejednoznačná situácia')).toBeNull();
    });

    it('paints the grey zone the backend reported for a score of exactly 2.90', () => {
        renderWithProviders(<FinancialRatiosTable analysis={analysis(2.90, 'grey')} />);

        expect(screen.getByText('Nejednoznačná situácia')).toBeTruthy();
        expect(screen.getByText('Šedá zóna')).toBeTruthy();
        expect(screen.queryByText('Nízke riziko bankrotu')).toBeNull();
    });

    it('paints the safe zone above the upper threshold', () => {
        renderWithProviders(<FinancialRatiosTable analysis={analysis(3.10, 'safe')} />);

        expect(screen.getByText('Nízke riziko bankrotu')).toBeTruthy();
        expect(screen.getByText('Bezpečná zóna')).toBeTruthy();
    });

    it('shows the score itself, to two places', () => {
        renderWithProviders(<FinancialRatiosTable analysis={analysis(1.23, 'distress')} />);

        expect(screen.getByText('1.23')).toBeTruthy();
    });

    it('draws no banner when the statement supported no score', () => {
        renderWithProviders(<FinancialRatiosTable analysis={analysis(null, null)} />);

        expect(screen.queryByText('Altman Z-score')).toBeNull();
        expect(screen.queryByText('Zvýšené riziko bankrotu')).toBeNull();
    });
});

/**
 * The Taffler model renders the zone the backend decided, in the backend's
 * words.
 *
 * There is deliberately no ladder in the component to test: the chip is
 * `tafflerLabel` and the colour is read from `tafflerZone`, both of which are
 * the backend's. So these pin the contract at the two bounds where a
 * re-derived ladder would have to agree with the service by luck -- 0.30 and
 * 0.20, the values the published modified-form model puts in the *lower*
 * zone -- and pin that the model is absent, rather than zero, when the
 * statement did not support it.
 */
describe('FinancialRatiosTable — Taffler model', () => {
    it('paints the safe zone the backend reported for a score above 0.30', () => {
        renderWithProviders(
            <FinancialRatiosTable analysis={analysis(null, null, { score: 0.48, zone: 'safe' })} />,
        );

        expect(screen.getByText('Tafflerov model')).toBeTruthy();
        expect(screen.getByText('0.48')).toBeTruthy();
        expect(screen.getByText('Nízka pravdepodobnosť bankrotu')).toBeTruthy();
    });

    it('paints the grey zone the backend reported for a score of exactly 0.30', () => {
        renderWithProviders(
            <FinancialRatiosTable analysis={analysis(null, null, { score: 0.3, zone: 'grey' })} />,
        );

        expect(screen.getByText('0.30')).toBeTruthy();
        expect(screen.getByText('Nejednoznačná situácia')).toBeTruthy();
        expect(screen.queryByText('Nízka pravdepodobnosť bankrotu')).toBeNull();
    });

    it('paints the distress zone the backend reported for a score of exactly 0.20', () => {
        renderWithProviders(
            <FinancialRatiosTable
                analysis={analysis(null, null, { score: 0.2, zone: 'distress' })}
            />,
        );

        expect(screen.getByText('0.20')).toBeTruthy();
        expect(screen.getByText('Vysoká pravdepodobnosť bankrotu')).toBeTruthy();
        expect(screen.queryByText('Nejednoznačná situácia')).toBeNull();
    });

    it('draws no Taffler banner when the statement supported no score', () => {
        renderWithProviders(<FinancialRatiosTable analysis={analysis(3.1, 'safe')} />);

        expect(screen.getByText('Altman Z-score')).toBeTruthy();
        expect(screen.queryByText('Tafflerov model')).toBeNull();
    });

    it('draws both models when the statement supported both', () => {
        renderWithProviders(
            <FinancialRatiosTable
                analysis={analysis(1.23, 'distress', { score: 0.48, zone: 'safe' })}
            />,
        );

        expect(screen.getByText('Altman Z-score')).toBeTruthy();
        expect(screen.getByText('Tafflerov model')).toBeTruthy();
        // Two verdicts on one statement, each from its own model: the Taffler
        // chip must not have been painted with the Altman caption.
        expect(screen.getByText('Pásmo bankrotu')).toBeTruthy();
        expect(screen.getByText('Nízka pravdepodobnosť bankrotu')).toBeTruthy();
    });
});
