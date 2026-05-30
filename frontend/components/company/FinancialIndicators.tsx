import React from 'react';
import type { Financials } from '../../types';
import { InfoCard } from '../InfoCard';
import { formatCurrency } from '../../utils/format';

interface FinancialIndicatorsProps {
    data: Financials[];
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

export const FinancialIndicators: React.FC<FinancialIndicatorsProps> = ({ data }) => {
    const sorted = [...data].sort((a, b) => a.year - b.year);
    const latest = sorted.at(-1);
    const prev = sorted.at(-2);

    if (!latest) return null;

    const hasBalanceSheet = latest.assetsTotal > 0;

    const valueColor = (value: number) =>
        value >= 0 ? 'text-gray-900 dark:text-white' : 'text-red-600 dark:text-red-400';

    const indicators = [
        {
            label: 'Celkové výnosy',
            value: latest.totalRevenue || latest.revenue,
            prevValue: prev ? (prev.totalRevenue || prev.revenue) : 0,
            format: 'currency' as const,
            icon: 'fa-coins',
        },
        {
            label: 'Zisk po zdanení',
            value: latest.profit,
            prevValue: prev?.profit || 0,
            format: 'currency' as const,
            icon: 'fa-chart-line',
        },
        ...(hasBalanceSheet ? [
            {
                label: 'Aktíva',
                value: latest.assetsTotal,
                prevValue: prev?.assetsTotal || 0,
                format: 'currency' as const,
                icon: 'fa-building',
            },
            {
                label: 'Vlastný kapitál',
                value: latest.equity,
                prevValue: prev?.equity || 0,
                format: 'currency' as const,
                icon: 'fa-shield-halved',
            },
            {
                label: 'Celková zadlženosť',
                value: latest.debtRatio,
                prevValue: prev?.debtRatio || 0,
                format: 'percent' as const,
                icon: 'fa-percent',
                inverse: true,
            },
            {
                label: 'Hrubá marža',
                value: latest.grossMargin,
                prevValue: prev?.grossMargin || 0,
                format: 'percent' as const,
                icon: 'fa-chart-bar',
            },
        ] : []),
    ];

    return (
        <InfoCard title={`Kľúčové ukazovatele ${latest.year}`} icon="fa-table">
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
                {indicators.map((ind) => {
                    const displayValue = ind.value == null
                        ? '—'
                        : ind.format === 'percent'
                            ? `${ind.value.toFixed(2)}%`
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
