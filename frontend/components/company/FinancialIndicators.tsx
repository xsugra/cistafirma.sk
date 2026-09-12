import React from 'react';
import type { Financials, YearAnalysis } from '../../types';
import { InfoCard } from '../InfoCard';
import { formatCurrency } from '../../utils/format';

interface FinancialIndicatorsProps {
    data: Financials[];
    analysis?: YearAnalysis;
}

const TrendArrow: React.FC<{ current: number; previous: number; inverse?: boolean }> = ({ current, previous, inverse }) => {
    if (previous === 0 && current === 0) return null;
    if (previous === 0) return <span className="text-xs font-semibold text-blue-500">nový</span>;
    const change = ((current - previous) / Math.abs(previous)) * 100;
    const isPositive = inverse ? change <= 0 : change >= 0;
    return (
        <span className={`inline-flex items-center gap-0.5 text-xs font-semibold ${isPositive ? 'text-green-600 dark:text-green-400' : 'text-red-500 dark:text-red-400'}`}>
            <i className={`fas fa-arrow-${change >= 0 ? 'up' : 'down'} text-[10px]`}></i>
            {Math.abs(change).toFixed(1)}%
        </span>
    );
};

export const FinancialIndicators: React.FC<FinancialIndicatorsProps> = ({ data, analysis }) => {
    const sorted = [...data].sort((a, b) => a.year - b.year);
    const latest = sorted.at(-1);
    const prev = sorted.at(-2);

    if (!latest) return null;

    // The balance-sheet block shows when the statement carried one of its
    // totals -- not when assets happen to be positive. `> 0` hid the block for a
    // dormant association whose filed balance sheet totals 25.88 €, and 0 is a
    // filed figure like any other.
    const hasBalanceSheet =
        latest.assetsTotal != null || latest.equity != null || latest.liabilitiesTotal != null;

    const valueColor = (value: number) =>
        value >= 0 ? 'text-gray-900 dark:text-white' : 'text-red-600 dark:text-red-400';

    const analysisRatios = analysis?.ratios;

    // `inverse` is spelled out on every entry rather than left off the ones that
    // do not use it: TypeScript stops giving the absent property an implicit
    // `undefined` once the array's element types stop being uniform, and
    // `ind.inverse` below then fails to compile.
    const indicators = [
        {
            label: 'Celkové výnosy',
            // `??`, not `||`: a filed total revenue of 0 fell through to the
            // turnover line under a label that says "total".
            value: latest.totalRevenue ?? latest.revenue,
            prevValue: prev ? (prev.totalRevenue ?? prev.revenue) : null,
            format: 'currency' as const,
            icon: 'fa-coins',
            inverse: false,
        },
        {
            label: 'Zisk po zdanení',
            value: latest.profit,
            // `null` means the previous year filed no profit, so no arrow is
            // drawn -- `|| 0` would have shown one against a zero that is not
            // there.
            prevValue: prev?.profit ?? null,
            format: 'currency' as const,
            icon: 'fa-chart-line',
            inverse: false,
        },
        ...(hasBalanceSheet ? [
            {
                label: 'Aktíva',
                value: latest.assetsTotal,
                prevValue: prev?.assetsTotal ?? null,
                format: 'currency' as const,
                icon: 'fa-building',
                inverse: false,
            },
            {
                label: 'Vlastný kapitál',
                value: latest.equity,
                prevValue: prev?.equity ?? null,
                format: 'currency' as const,
                icon: 'fa-shield-halved',
                inverse: false,
            },
            {
                label: 'Celková zadlženosť',
                value: latest.debtRatio,
                prevValue: prev?.debtRatio ?? null,
                format: 'percent' as const,
                icon: 'fa-percent',
                inverse: true,
            },
            {
                label: 'Hrubá marža',
                value: latest.grossMargin,
                prevValue: prev?.grossMargin ?? null,
                format: 'percent' as const,
                icon: 'fa-chart-bar',
                inverse: false,
            },
        ] : []),
        // Additional KPIs from analysis. `prevValue: null`, not 0: these ratios
        // are only computed for the year being looked at, and a zero here made
        // `TrendArrow` print "nový" beside every one of them for any company
        // with two filed years.
        ...(analysisRatios ? [
            {
                label: 'ROA',
                value: analysisRatios.roa,
                prevValue: null,
                format: 'percent' as const,
                icon: 'fa-chart-line',
                inverse: false,
            },
            {
                label: 'ROE',
                value: analysisRatios.roe,
                prevValue: null,
                format: 'percent' as const,
                icon: 'fa-chart-pie',
                inverse: false,
            },
            {
                label: 'L3 Likvidita',
                value: analysisRatios.currentRatio,
                prevValue: null,
                format: 'ratio' as const,
                icon: 'fa-droplet',
                inverse: false,
            },
        ].filter(ind => ind.value != null) : []),
    ];

    return (
        <InfoCard title={`Kľúčové ukazovatele ${latest.year}`} icon="fa-table">
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
                {indicators.map((ind) => {
                    const displayValue = ind.value == null
                        ? '—'
                        : ind.format === 'percent'
                            ? `${ind.value.toFixed(2)}%`
                            : ind.format === 'ratio'
                                ? ind.value.toFixed(2)
                                : formatCurrency(ind.value);

                    return (
                        <div
                            key={ind.label}
                            className="flex items-center gap-3 p-3 rounded-xl border border-gray-100 dark:border-slate-800 bg-white dark:bg-slate-900/50"
                        >
                            <div className="w-9 h-9 rounded-lg bg-blue-50 dark:bg-blue-900/20 flex items-center justify-center flex-shrink-0">
                                <i className={`fas ${ind.icon} text-blue-600 dark:text-blue-400 text-sm`}></i>
                            </div>
                            <div className="min-w-0 flex-1">
                                <p className="text-[11px] font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                                    {ind.label}
                                </p>
                                <div className="flex items-baseline gap-2">
                                    <span className={`text-base font-bold ${ind.value != null ? valueColor(ind.value) : 'text-gray-400'}`}>
                                        {displayValue}
                                    </span>
                                    {prev && ind.prevValue != null && ind.value != null && (
                                        <TrendArrow current={ind.value} previous={ind.prevValue} inverse={ind.inverse} />
                                    )}
                                </div>
                            </div>
                        </div>
                    );
                })}
            </div>
        </InfoCard>
    );
};
