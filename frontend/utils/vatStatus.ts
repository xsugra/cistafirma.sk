import type { VatStatus } from '../types';

/**
 * What the VAT register says about a company, and the one place that decides it.
 *
 * This module exists because the same four facts are read on two surfaces --
 * the summary strip on the company page and the PDF somebody forwards -- and
 * this codebase has already paid once for letting one decision live in six
 * places (see `docs/SOURCE_DATA_INTEGRITY.md`, "Status vocabulary"). Everything
 * that turns a `VatStatus` into a word lives here; the consumers only choose
 * colours.
 *
 * Every measurement quoted below was taken 2026-09-12 over all 445 626 rows of
 * `"Companies and SZCO"`.
 */

export type VatStanding = 'payer' | 'deregistered' | 'not-payer' | 'unknown';

/**
 * The standing, derived from the dates first and the flag second.
 *
 * The order is the whole point. `Platiteľ DPH` is nullable and 302 713 rows
 * hold no value, of which 27 857 *were* struck off the register and carry the
 * date to prove it -- so a company that left the VAT register is mostly
 * invisible to the flag. The date is a fact the source wrote down; the flag is
 * a hint it often did not. `false` is set on only 4 160 rows, and every one of
 * those carries both a registration and a removal date, so the flag never
 * carries a fact the dates do not already state more completely.
 */
export function vatStanding(vat: VatStatus): VatStanding {
    if (vat.deregisteredOn) return 'deregistered';
    if (vat.isVatPayer === true) return 'payer';
    if (vat.isVatPayer === false) return 'not-payer';
    return 'unknown';
}

/**
 * The headline. Three of these are the register's own words; `Nezistené` is
 * ours, and it is the honest one for the 302 713 rows where Finančná správa
 * published no value -- "Neplatiteľ DPH" would be a claim about a company the
 * source never mentioned.
 */
export const VAT_STANDING_LABEL: Record<VatStanding, string> = {
    payer: 'Platiteľ DPH',
    deregistered: 'Vymazaný z registra DPH',
    'not-payer': 'Neplatiteľ DPH',
    unknown: 'Nezistené',
};

export type ReliabilityTone = 'good' | 'neutral' | 'warn' | 'unknown';

export interface Reliability {
    label: string;
    tone: ReliabilityTone;
}

/**
 * The index as the register spells it, and the band it belongs to.
 *
 * Keyed by the three values the register actually holds, all lowercase. An
 * unrecognised value is returned verbatim with an `unknown` tone rather than
 * defaulted into a band: we would be inventing a severity for a word we have
 * never seen, and the reassuring default is the one that hides a problem. A
 * missing index is its own case -- 218 143 rows, half the register -- and says
 * that Finančná správa rated nobody here, not that it rated them reliable.
 */
const RELIABILITY_BANDS: Record<string, ReliabilityTone> = {
    'vysoko spoľahlivý': 'good',
    'spoľahlivý': 'neutral',
    'menej spoľahlivý': 'warn',
};

export function vatReliability(index: string | null): Reliability {
    if (index === null) {
        return { label: 'bez indexu spoľahlivosti', tone: 'unknown' };
    }
    const tone = RELIABILITY_BANDS[index];
    if (!tone) {
        // Verbatim, because it is the register's word and not ours to classify.
        return { label: index, tone: 'unknown' };
    }
    // "vysoko spoľahlivý" -> "Vysoko spoľahlivý". The register lowercases the
    // whole phrase; Slovak sentences do not start lowercase.
    return { label: index.charAt(0).toUpperCase() + index.slice(1), tone };
}

/** The reason as a reader would say it, or the register's own string. */
export function vatDeregistrationReason(reason: string | null): string | null {
    if (!reason) return null;
    // 32 023 of the 32 043 recorded reasons are exactly `Rok porušenia: YYYY`.
    // The other 20 are left untouched: a shape we did not anticipate is a
    // sentence to print, not a pattern to force.
    const match = /^Rok porušenia:\s*(\d{4})$/.exec(reason);
    if (!match) return reason;
    return `porušenie v roku ${match[1]}`;
}
