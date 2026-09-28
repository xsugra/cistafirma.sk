import { TODAY_LABEL, asOfForYear, periodLabel } from './period';

interface GraphPeriodChipsProps {
    /** The years worth offering, newest first, from `meta.periods`. */
    periods: number[];
    /** The chosen day, or `null` for today. */
    value: string | null;
    onChange: (asOf: string | null) => void;
    /** Blocks the row while a period is being fetched. */
    busy?: boolean;
}

/**
 * The period control: `Dnes` plus one chip per year the company changed.
 *
 * The years come from the backend and are the *same* years the Osoby history
 * offers, because they are computed once from the company's whole record. A
 * chip for every year the register happens to mention would be twenty-seven
 * chips of which twenty-five draw the identical picture -- the record changes
 * on the days someone joined or left, and only those days are worth a control.
 *
 * Each chip is 31 December of its year (`asOfForYear`), and `Dnes` sends no
 * parameter at all: the graph without a period is the whole record the register
 * holds, which is not the company on any one day.
 */
export function GraphPeriodChips({ periods, value, onChange, busy = false }: GraphPeriodChipsProps) {
    if (periods.length === 0) return null;

    const chip = (active: boolean) =>
        [
            'min-h-8 rounded-full border px-2.5 py-1 text-xs transition-colors',
            active
                ? 'border-blue-300 bg-blue-50 font-medium text-blue-700 dark:border-blue-700 dark:bg-blue-900/40 dark:text-blue-300'
                : 'border-gray-200 bg-white text-gray-600 hover:bg-gray-50 dark:border-gray-700 dark:bg-gray-800 dark:text-gray-300 dark:hover:bg-gray-700',
            busy ? 'opacity-60' : '',
        ].join(' ');

    return (
        <div
            className="pointer-events-auto flex flex-wrap items-center gap-1.5 text-xs text-gray-500 dark:text-gray-400"
            role="group"
            aria-label="Obdobie"
        >
            <span className="mr-0.5">
                <i className="fas fa-clock-rotate-left mr-1" aria-hidden="true"></i>
                Obdobie:
            </span>
            <button
                type="button"
                onClick={() => onChange(null)}
                disabled={busy}
                aria-pressed={value === null}
                title={periodLabel(null)}
                className={chip(value === null)}
            >
                {TODAY_LABEL}
            </button>
            {periods.map((year) => {
                const asOf = asOfForYear(year);
                return (
                    <button
                        key={year}
                        type="button"
                        onClick={() => onChange(asOf)}
                        disabled={busy}
                        aria-pressed={value === asOf}
                        title={periodLabel(asOf)}
                        className={chip(value === asOf)}
                    >
                        {year}
                    </button>
                );
            })}
        </div>
    );
}
