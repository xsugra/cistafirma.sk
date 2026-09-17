import React from 'react';
import type { CompanyBenchmark, Financials, YearAnalysis } from '../../types';
import { InfoCard } from '../InfoCard';
import { formatCurrency } from '../../utils/format';

interface BenchmarkComparisonProps {
    benchmark: CompanyBenchmark;
    analysis: YearAnalysis;
    /**
     * The statement row for `analysis.year`, when we have it.
     *
     * Four rows below compare a figure the ratio set does not carry, so they
     * read it from here. Optional, because a company can have an analysis
     * without the statement that produced it -- the rows then show `—` rather
     * than a substitute.
     */
    financials?: Financials | null;
}

interface MetricDef {
    label: string;
    companyKey: string;
    benchmarkKey: keyof CompanyBenchmark['medians'];
    unit: string;
    inverse?: boolean;
}

const METRICS: MetricDef[] = [
    { label: 'ROA', companyKey: 'roa', benchmarkKey: 'roa', unit: '%' },
    { label: 'ROE', companyKey: 'roe', benchmarkKey: 'roe', unit: '%' },
    { label: 'ROS', companyKey: 'ros', benchmarkKey: 'ros', unit: '%' },
    { label: 'Aktíva', companyKey: 'assetsTotal', benchmarkKey: 'assetsTotal', unit: '€' },
    { label: 'Vlastný kapitál', companyKey: 'equity', benchmarkKey: 'equity', unit: '€' },
    { label: 'Zadĺženosť', companyKey: 'debtRatio', benchmarkKey: 'debtRatio', unit: '%', inverse: true },
    { label: 'Hrubá marža', companyKey: 'grossMargin', benchmarkKey: 'grossMargin', unit: '%' },
    { label: 'L3 Likvidita', companyKey: 'currentRatio', benchmarkKey: 'currentRatio', unit: '×' },
    { label: 'Samofinancovanie', companyKey: 'selfFinancingRatio', benchmarkKey: 'selfFinancingRatio', unit: '%' },
];

/**
 * Rows that read a filed figure rather than a ratio.
 *
 * The ratio set carries no balance-sheet total, no gross margin and no debt
 * ratio, so before this the two totals were hardcoded to `null` -- the rows
 * always showed `—` -- and the other two borrowed the nearest ratio. The
 * *Zadlzenost* row showed `debtToEquity`, a multiple whose own thresholds are
 * 1.5 and 3.0, against a sector median that is a percentage, which flatters the
 * company almost every time; the *Hruba marza* row showed
 * `selfFinancingRatio`, which is equity over assets and is not gross margin.
 *
 * `Financials.debtRatio` is computed by the same formula the sector median is a
 * median of, so that row now compares like with like.
 */
const STATEMENT_KEYS = ['assetsTotal', 'equity', 'grossMargin', 'debtRatio'];

export const BenchmarkComparison: React.FC<BenchmarkComparisonProps> = ({
    benchmark,
    analysis,
    financials,
}) => {
    const companyRatios = analysis.ratios;

    const getCompanyValue = (key: string): number | null => {
        if (STATEMENT_KEYS.includes(key)) {
            if (!financials) return null;
            return (financials as unknown as Record<string, number | null>)[key] ?? null;
        }
        const ratios = companyRatios as unknown as Record<string, number | null>;
        return ratios[key] ?? null;
    };

    const formatValue = (value: number | null, unit: string): string => {
        if (value == null) return '—';
        if (unit === '%') return `${value.toFixed(1)}%`;
        if (unit === '×') return value.toFixed(2);
        if (unit === '€') return formatCurrency(value);
        return `${value}`;
    };

    const getComparisonColor = (companyVal: number | null, benchVal: number | null, inverse?: boolean): string => {
        if (companyVal == null || benchVal == null || benchVal === 0) return 'text-gray-400';
        const diff = ((companyVal - benchVal) / Math.abs(benchVal)) * 100;
        const isBetter = inverse ? diff <= 0 : diff >= 0;
        if (Math.abs(diff) < 5) return 'text-amber-600 dark:text-amber-400';
        return isBetter ? 'text-green-600 dark:text-green-400' : 'text-red-500 dark:text-red-400';
    };

    const sectionLabel = benchmark.sectionName || benchmark.divisionName || `Sekcia ${benchmark.section}`;

    return (
        <InfoCard
            title="Porovnanie so sektorom"
            icon="fa-building-columns"
        >
            <p className="text-xs text-gray-500 dark:text-gray-400 -mt-1 mb-3">
                {sectionLabel} — medián z {benchmark.companyCount.toLocaleString('sk-SK')} firiem v roku {benchmark.year}
            </p>
            <div className="overflow-hidden rounded-lg border border-gray-100 dark:border-slate-800">
                <table className="w-full text-sm">
                    <thead>
                        <tr className="bg-gray-50 dark:bg-slate-900/50">
                            <th className="text-left px-4 py-2.5 text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                                Ukazovateľ
                            </th>
                            <th className="text-right px-4 py-2.5 text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider w-24">
                                Firma
                            </th>
                            <th className="text-right px-4 py-2.5 text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider w-24">
                                Sektor
                            </th>
                            <th className="text-right px-4 py-2.5 text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider w-28">
                                Rozdiel
                            </th>
                        </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-50 dark:divide-slate-800/50">
                        {METRICS.map((metric) => {
                            const companyVal = getCompanyValue(metric.companyKey);
                            const benchVal = benchmark.medians[metric.benchmarkKey];
                            const colorClass = getComparisonColor(companyVal, benchVal, metric.inverse);
                            const pctDiff =
                                companyVal != null && benchVal != null && benchVal !== 0
                                    ? `${((companyVal - benchVal) / Math.abs(benchVal) * 100).toFixed(0)}%`
                                    : null;

                            return (
                                <tr
                                    key={metric.label}
                                    className="hover:bg-gray-50/50 dark:hover:bg-slate-900/30 transition-colors"
                                >
                                    <td className="px-4 py-2.5 text-gray-700 dark:text-gray-300">
                                        {metric.label}
                                    </td>
                                    <td className="px-4 py-2.5 text-right font-mono font-semibold text-gray-900 dark:text-white">
                                        {formatValue(companyVal, metric.unit)}
                                    </td>
                                    <td className="px-4 py-2.5 text-right font-mono text-gray-500 dark:text-gray-400">
                                        {formatValue(benchVal, metric.unit)}
                                    </td>
                                    <td className={`px-4 py-2.5 text-right font-semibold text-xs ${colorClass}`}>
                                        {pctDiff ? (
                                            <span className="inline-flex items-center gap-0.5">
                                                <i
                                                    className={`fas fa-arrow-${
                                                        companyVal != null && benchVal != null && companyVal >= benchVal
                                                            ? 'up'
                                                            : 'down'
                                                    } text-[8px]`}
                                                ></i>
                                                {pctDiff}
                                            </span>
                                        ) : (
                                            '—'
                                        )}
                                    </td>
                                </tr>
                            );
                        })}
                    </tbody>
                </table>
            </div>

            <p className="text-[10px] text-gray-400 dark:text-gray-500 mt-3 text-center">
                Benchmark počíta mediány v rámci NACE sekcie. Záporný rozdiel neznamená nutne problém —
                hodnoty sa medzi odvetviami výrazne líšia.
            </p>
        </InfoCard>
    );
};
