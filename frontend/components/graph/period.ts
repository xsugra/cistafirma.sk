/**
 * The one vocabulary for "which day is this picture about".
 *
 * Three screens ask the same question -- the graph, the Osoby history and the
 * chips they share -- and they must offer the same years and name the chosen
 * one the same way. The years themselves are not computed here: the backend
 * derives them from the company's whole record (`meta.periods`), because a chip
 * list worked out on the client would be a second opinion about when a company
 * changed, and the two would drift the moment the register was re-read.
 */

/** The chip that means "as it stands today", and the absence of a parameter. */
export const TODAY_LABEL = 'Dnes';

/**
 * A year chip is 31 December of that year -- the day the record is read at.
 *
 * Not the year as a bare number: relations end on real days, and a company
 * whose konateľ ended on 3 March 2015 was a different company on 31 December
 * 2014 than it was on 31 December 2015. Reading each year at its end is what
 * makes a chip "the state of the company that year".
 */
export const asOfForYear = (year: number): string =>
    `${String(year).padStart(4, '0')}-12-31`;

/**
 * What the chosen day is called, in one place.
 *
 * `null` is today, and it says so rather than printing a date: the graph drawn
 * without a period is not the company on any particular day, it is the whole
 * record as the register holds it now.
 */
export const periodLabel = (asOf: string | null): string => {
    if (!asOf) return 'Súčasný stav';
    const [year, month, day] = asOf.split('-');
    if (!year || !month || !day) return asOf;
    return `Stav k ${Number(day)}. ${Number(month)}. ${year}`;
};

/**
 * What a period view had to leave out, in words, or the empty string.
 *
 * A relation whose start the register never stated cannot be shown to have been
 * in force on any day, so a period view drops it. Dropping it silently would
 * make the picture the reader is looking at *smaller* than the record it claims
 * to show, with nothing on screen to say so -- which is the one thing a period
 * graph must not do, because the whole reason to ask for 2015 is to see who was
 * there, and "nobody" and "three people we cannot place" look identical.
 *
 * Slovak counts in three, so this does too: 1 zápis, 2-4 zápisy, 5+ zápisov.
 */
export const undatedNote = (count: number): string => {
    if (count <= 0) return '';
    const word = count === 1 ? 'zápis' : count >= 2 && count <= 4 ? 'zápisy' : 'zápisov';
    return `${count} ${word} bez dátumu vzniku sa do zvoleného obdobia nedá priradiť.`;
};
