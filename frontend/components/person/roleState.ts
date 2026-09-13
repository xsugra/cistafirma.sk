/**
 * The three answers a relation can give about whether a function still runs.
 *
 * The graph got here first: `GraphEdge.isActive` is `boolean | null`, and
 * `GraphCanvas` draws the three states as solid, dashed and dotted while
 * `GraphLegend` names the last two. A list of relations is the same fact in a
 * different shape, so it says the same thing in the same words and the same
 * three treatments -- one vocabulary for one fact, on both screens.
 *
 * `unknown` is not a prettier "no". It means we have never read that company's
 * history, and rendering it as ended would be a claim about a company nobody
 * checked.
 */
export type RoleState = 'current' | 'ended' | 'unknown';

export const roleStateOf = (isActive: boolean | null | undefined): RoleState => {
    if (isActive === true) return 'current';
    if (isActive === false) return 'ended';
    return 'unknown';
};

/** The short answer, next to the row it belongs to. */
export const ROLE_STATE_WORD: Record<RoleState, string> = {
    current: 'áno',
    ended: 'nie',
    unknown: 'nevieme',
};

/**
 * The same answer in a sentence, for a reader who wants to know what it rests
 * on. The `unknown` line is verbatim the graph legend's tooltip: the two
 * screens describe one absence and must not describe it two ways.
 */
export const ROLE_STATE_SENTENCE: Record<RoleState, string> = {
    current: 'Register uvádza funkciu ako aktuálnu.',
    ended: 'Funkcia je v registri ukončená.',
    unknown: 'Funkciu sme pre túto firmu ešte neoverili v registri.',
};

/**
 * The stroke each state is drawn with -- solid for current, dashed for ended,
 * dotted for unknown, the same three as the graph.
 *
 * A line and not a badge colour alone, because colour is the one channel a
 * reader may not have. The Tailwind rule the rest of the app lives by applies
 * here too: a bare `border-t` with no colour resolves to `currentColor` in v4.
 */
export const ROLE_STATE_LINE: Record<RoleState, string> = {
    current: 'border-t-2 border-solid border-blue-500 dark:border-blue-400',
    ended: 'border-t border-dashed border-gray-400 dark:border-gray-500',
    unknown: 'border-t border-dotted border-gray-400 dark:border-gray-500',
};

export const ROLE_STATE_CHIP: Record<RoleState, string> = {
    current:
        'bg-blue-50 dark:bg-blue-900/20 text-blue-700 dark:text-blue-400 border-blue-200 dark:border-blue-800',
    ended:
        'bg-gray-100 dark:bg-slate-800 text-gray-600 dark:text-gray-300 border-gray-200 dark:border-slate-700',
    // Amber, and not the quiet grey the ended state gets: "we do not know" is
    // the answer a reader is most likely to misread as "no".
    unknown:
        'bg-amber-50 dark:bg-amber-900/20 text-amber-700 dark:text-amber-400 border-amber-200 dark:border-amber-800',
};
