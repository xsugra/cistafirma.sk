import React from 'react';
import type { RiskFlag, RiskFlagCounts } from '../types';

/**
 * How a risk indicator's state is written and coloured, in one place.
 *
 * Two panels draw these flags -- the company section and the person panel --
 * and they are the same three-state answer from the same server module
 * contract. The words in particular must not diverge: the whole point of the
 * third state is that a reader who meets it once knows what it means the next
 * time, and two panels spelling it two ways is how that stops being true.
 *
 * This file writes the *words and the colours* and nothing else. The sentences
 * -- `label`, `detail`, `reason` -- are the server's; see the `RiskFlag` doc
 * comment in `types.ts` for why that split is deliberate.
 */

/**
 * The word for each state, and the three are deliberately three.
 *
 * "bez nálezu" is not the same fact as "nevyhodnotené": the first says a rule
 * read the data and found nothing to report, the second says it never read
 * anything. Rendering the second as the first is the one mistake this whole
 * feature exists to avoid -- an all-clear we did not earn.
 */
export const STATE_LABEL: Record<RiskFlag['state'], string> = {
    fired: 'nájdené',
    clear: 'bez nálezu',
    unassessed: 'nevyhodnotené',
};

/** Neither a finding nor a clean bill: one colour for everything grey. */
export const NEUTRAL_CHIP =
    'bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-300 border-slate-200 dark:border-slate-700';

/**
 * Colour for the two states that have one colour each.
 *
 * `fired` is absent on purpose: how loudly a finding speaks is what the
 * server's `severity` is for, so that state is coloured from the severity
 * instead. Leaving the key out means there is no second, unreachable answer to
 * the question "what colour is a finding".
 */
export const STATE_CHIP: Record<'clear' | 'unassessed', string> = {
    clear: 'bg-green-50 dark:bg-green-900/20 text-green-700 dark:text-green-400 border-green-200 dark:border-green-800',
    unassessed: NEUTRAL_CHIP,
};

/** The server sends `severity`; the frontend turns it into a colour. That is
 *  the whole division of labour -- it does not decide what "high" means. */
export const SEVERITY_CHIP: Record<RiskFlag['severity'], string> = {
    high: 'bg-red-50 dark:bg-red-900/20 text-red-700 dark:text-red-400 border-red-200 dark:border-red-800',
    medium: 'bg-amber-50 dark:bg-amber-900/20 text-amber-700 dark:text-amber-400 border-amber-200 dark:border-amber-800',
    low: NEUTRAL_CHIP,
};

export const chipClass = (flag: RiskFlag): string =>
    flag.state === 'fired' ? SEVERITY_CHIP[flag.severity] : STATE_CHIP[flag.state];

export const Chip: React.FC<{ className: string; children: React.ReactNode }> = ({
    className,
    children,
}) => (
    <span
        className={`inline-flex items-center rounded-full border px-2 py-0.5 text-xs font-medium ${className}`}
    >
        {children}
    </span>
);

export const FlagChip: React.FC<{ flag: RiskFlag }> = ({ flag }) => (
    <Chip className={chipClass(flag)}>{STATE_LABEL[flag.state]}</Chip>
);

/**
 * The rule that answers a different question from the other two.
 *
 * "Why is there nothing to find" is not "what did we find", and a reader
 * scanning the column should not mistake a hole in our data for the result of a
 * check. Italic is doing the whole job of saying so.
 */
export const FlagOutcome: React.FC<{ flag: RiskFlag }> = ({ flag }) =>
    flag.state === 'unassessed' ? (
        <span className="italic text-gray-500 dark:text-gray-400">{flag.reason}</span>
    ) : (
        <>{flag.detail}</>
    );

/**
 * How the outcomes divide, as three counts and never as one.
 *
 * Both panels print this above their list, and neither sums it: a single
 * "risk number" is the one thing a reader would carry away from the panel, and
 * it would be an accusation dressed as arithmetic.
 *
 * A count of zero findings is painted neutrally rather than red -- `0 nájdené`
 * is the one case where the count is good news, and colouring it like the
 * others would make every clean company wear the same alarm as a dirty one.
 */
export const FlagCounts: React.FC<{ counts: RiskFlagCounts; total: number }> = ({
    counts,
    total,
}) => (
    <div className="flex flex-wrap items-center gap-2">
        <Chip className={counts.fired > 0 ? SEVERITY_CHIP.high : NEUTRAL_CHIP}>
            {STATE_LABEL.fired}: {counts.fired}
        </Chip>
        <Chip className={STATE_CHIP.clear}>
            {STATE_LABEL.clear}: {counts.clear}
        </Chip>
        <Chip className={STATE_CHIP.unassessed}>
            {STATE_LABEL.unassessed}: {counts.unassessed}
        </Chip>
        <span className="text-xs text-gray-500 dark:text-gray-400">z {total} pravidiel</span>
    </div>
);
