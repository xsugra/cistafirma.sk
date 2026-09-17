import React from 'react';
import type { Company, Financials } from '../../../types';
import { InfoCard } from '../../InfoCard';
import { formatCurrency } from '../../../utils/format';
import { EmptyFinancialsNotice } from './EmptyFinancialsNotice';

interface ProfitLossSectionProps {
    company: Company;
}

/** One line of the income statement. */
interface PlRow {
    label: string;
    value: (f: Financials) => number | null;
    /** The two headline aggregates get emphasis and drive the change table. */
    total?: boolean;
    /** Shown under the label, for the lines whose name alone is ambiguous. */
    hint?: string;
}

const PL_ROWS: PlRow[] = [
    {
        label: 'Tržby',
        value: (f) => f.revenue,
        total: true,
        hint: 'Výnosy z hlavnej činnosti, ako ich nesie závierka.',
    },
    { label: 'Náklady', value: (f) => f.costs },
    { label: 'Pridaná hodnota', value: (f) => f.addedValue },
    { label: 'Daň z príjmu', value: (f) => f.incomeTax },
    { label: 'Splatná daň', value: (f) => f.incomeTaxPaid },
    // The statement's own order, and two rows because there are two rows in the
    // statement. `profit` was labelled "Zisk po zdanení" here while holding the
    // operating result for 86 % of the rows where a non-zero tax makes the two
    // distinguishable -- so the table printed the same figure twice under
    // different names, or printed a pre-tax number as the bottom line.
    {
        label: 'Výsledok hospodárenia z hospodárskej činnosti',
        value: (f) => f.profit,
        total: true,
    },
    {
        label: 'Zisk po zdanení',
        value: (f) => f.profitAfterTax,
        total: true,
    },
];

/**
 * The income statement, year by year, and what changed between the last two.
 *
 * The figures were already being read correctly — the analysis section draws
 * ratios from them — but the statement itself was only visible as a chart. A
 * chart answers "which way is this going"; it does not answer "what were the
 * costs", which is a question the reader of a company page actually has.
 *
 * The year-over-year table computes a change only where both years filed the
 * line and the earlier one is not zero: dividing by a filed zero is not a
 * percentage, and neither is dividing by an absent line.
 */
export const ProfitLossSection: React.FC<ProfitLossSectionProps> = ({ company }) => {
    const years = [...company.financials].sort((a, b) => a.year - b.year).slice(-5);

    if (years.length === 0) {
        return (
            <EmptyFinancialsNotice
                company={company}
                title="Výkaz ziskov a strát"
                icon="fa-chart-line"
            />
        );
    }

    const latest = years[years.length - 1];
    const previous = years.length > 1 ? years[years.length - 2] : undefined;

    const change = (row: PlRow): number | null => {
        if (!previous) return null;
        const now = row.value(latest);
        const before = row.value(previous);
        if (now == null || before == null || before === 0) return null;
        return ((now - before) / Math.abs(before)) * 100;
    };

    return (
        <div className="space-y-6">
            <InfoCard title="Výkaz ziskov a strát" icon="fa-chart-line">
                <p className="mb-4 text-sm text-gray-500 dark:text-gray-400">
                    Po rokoch, v eurách. Prázdne pole (—) znamená, že závierka tento riadok
                    neobsahovala — nie že by bol nula.
                </p>

                <div className="overflow-x-auto">
                    <table className="w-full text-sm">
                        <thead>
                            <tr className="border-b border-gray-200 dark:border-slate-700">
                                <th className="px-3 py-2 text-left text-xs font-medium uppercase text-gray-500 dark:text-gray-400">
                                    Riadok
                                </th>
                                {years.map((f) => (
                                    <th
                                        key={f.year}
                                        className="px-3 py-2 text-right text-xs font-medium uppercase text-gray-500 dark:text-gray-400"
                                    >
                                        {f.year}
                                    </th>
                                ))}
                            </tr>
                        </thead>
                        <tbody className="divide-y divide-gray-50 dark:divide-slate-800/50">
                            {PL_ROWS.map((row) => {
                                if (!years.some((f) => row.value(f) != null)) return null;
                                return (
                                    <tr
                                        key={row.label}
                                        className={
                                            row.total
                                                ? 'border-t border-gray-200 bg-gray-50/60 dark:border-slate-700 dark:bg-slate-800/40'
                                                : 'hover:bg-gray-50/50 dark:hover:bg-slate-900/30'
                                        }
                                    >
                                        <td className="px-3 py-2">
                                            <span
                                                className={
                                                    row.total
                                                        ? 'font-semibold text-gray-900 dark:text-white'
                                                        : 'text-gray-700 dark:text-gray-300'
                                                }
                                            >
                                                {row.label}
                                            </span>
                                            {row.hint && (
                                                <span className="block text-xs text-gray-400 dark:text-gray-500">
                                                    {row.hint}
                                                </span>
                                            )}
                                        </td>
                                        {years.map((f) => (
                                            <td
                                                key={f.year}
                                                className={`px-3 py-2 text-right font-mono tabular-nums whitespace-nowrap ${
                                                    row.total
                                                        ? 'font-semibold text-gray-900 dark:text-white'
                                                        : 'text-gray-700 dark:text-gray-300'
                                                }`}
                                            >
                                                {formatCurrency(row.value(f))}
                                            </td>
                                        ))}
                                    </tr>
                                );
                            })}
                        </tbody>
                    </table>
                </div>
            </InfoCard>

            {previous && (
                <InfoCard title={`Zmena ${previous.year} → ${latest.year}`} icon="fa-arrows-left-right">
                    <div className="overflow-x-auto">
                        <table className="w-full text-sm">
                            <thead>
                                <tr className="border-b border-gray-200 dark:border-slate-700">
                                    <th className="px-3 py-2 text-left text-xs font-medium uppercase text-gray-500 dark:text-gray-400">
                                        Riadok
                                    </th>
                                    <th className="px-3 py-2 text-right text-xs font-medium uppercase text-gray-500 dark:text-gray-400">
                                        {previous.year}
                                    </th>
                                    <th className="px-3 py-2 text-right text-xs font-medium uppercase text-gray-500 dark:text-gray-400">
                                        {latest.year}
                                    </th>
                                    <th className="px-3 py-2 text-right text-xs font-medium uppercase text-gray-500 dark:text-gray-400">
                                        Zmena
                                    </th>
                                </tr>
                            </thead>
                            <tbody className="divide-y divide-gray-50 dark:divide-slate-800/50">
                                {PL_ROWS.map((row) => {
                                    const pct = change(row);
                                    const before = row.value(previous);
                                    const now = row.value(latest);
                                    if (before == null && now == null) return null;
                                    return (
                                        <tr
                                            key={row.label}
                                            className="hover:bg-gray-50/50 dark:hover:bg-slate-900/30"
                                        >
                                            <td className="px-3 py-2 text-gray-700 dark:text-gray-300">
                                                {row.label}
                                            </td>
                                            <td className="px-3 py-2 text-right font-mono tabular-nums text-gray-700 dark:text-gray-300">
                                                {formatCurrency(before)}
                                            </td>
                                            <td className="px-3 py-2 text-right font-mono tabular-nums text-gray-900 dark:text-white">
                                                {formatCurrency(now)}
                                            </td>
                                            <td
                                                className={`px-3 py-2 text-right font-mono tabular-nums ${
                                                    pct == null
                                                        ? 'text-gray-400 dark:text-gray-500'
                                                        : pct >= 0
                                                          ? 'text-green-600 dark:text-green-400'
                                                          : 'text-red-600 dark:text-red-400'
                                                }`}
                                                title={
                                                    pct == null
                                                        ? 'Zmenu nemožno spočítať — jeden z rokov tento riadok neobsahoval, alebo predchádzajúci rok vykázal nulu.'
                                                        : undefined
                                                }
                                            >
                                                {pct == null
                                                    ? '—'
                                                    : `${pct >= 0 ? '+' : ''}${pct.toFixed(1)}%`}
                                            </td>
                                        </tr>
                                    );
                                })}
                            </tbody>
                        </table>
                    </div>
                    <p className="mt-3 text-xs text-gray-400 dark:text-gray-500">
                        Zmena sa počíta len tam, kde oba roky ten riadok vykázali a starší rok
                        nevykázal nulu.
                    </p>
                </InfoCard>
            )}
        </div>
    );
};
