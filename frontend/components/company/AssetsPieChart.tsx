import React from 'react';
import { ResponsiveContainer, PieChart, Pie, Cell, Tooltip } from 'recharts';
import type { Financials } from '../../types';
import { InfoCard } from '../InfoCard';
import { formatCurrency, formatFullCurrency } from '../../utils/format';

interface AssetsPieChartProps {
    data: Financials;
}

/**
 * The wrapper below is `w-44 h-44`, which is 11rem -- 176px at this app's 16px
 * root. Recharts measures at `{width: -1, height: -1}` until its ResizeObserver
 * answers and logs a warning on the way, in production as well as in dev
 * (Recharts 3 hardcodes `isDev = true`). Handing it the real box means the pie
 * draws at its final size on the first frame and nothing is logged. Keep the two
 * in step: if the class changes, this changes with it.
 */
const PIE_BOX = 176;

const COLORS = [
    '#93c5fd', // blue-300
    '#3b82f6', // blue-500
    '#1d4ed8', // blue-700
    '#60a5fa', // blue-400
    '#2563eb', // blue-600
    '#1e40af', // blue-800
    '#bfdbfe', // blue-200
    '#7dd3fc', // sky-300
    '#0ea5e9', // sky-500
];

const CustomTooltip = ({ active, payload }: any) => {
    if (!active || !payload?.length) return null;
    const { name, value, percent } = payload[0].payload;
    return (
        <div className="rounded-lg shadow-lg px-3 py-2 border bg-white dark:bg-slate-900 border-gray-200 dark:border-slate-700">
            <p className="text-xs font-bold text-gray-900 dark:text-white">{name}</p>
            <p className="text-xs text-gray-500 dark:text-gray-400">
                {formatFullCurrency(value)} ({(percent * 100).toFixed(1)}%)
            </p>
        </div>
    );
};

export const AssetsPieChart: React.FC<AssetsPieChartProps> = ({ data }) => {
    // A pie draws only positive slices, so a line the statement did not carry
    // and a line it filed as zero land in the same place here. The total below
    // keeps the distinction, because `Aktíva celkom` is a figure the statement
    // either filed or did not.
    const segments = [
        { name: 'Nehmotný majetok', value: data.assetsIntangible ?? 0 },
        { name: 'Hmotný majetok', value: data.assetsTangible ?? 0 },
        { name: 'Finančný majetok', value: data.assetsFinancial ?? 0 },
        { name: 'Zásoby', value: data.assetsInventory ?? 0 },
        { name: 'Dlhodobé pohľadávky', value: data.assetsReceivablesLong ?? 0 },
        { name: 'Krátkodobé pohľadávky', value: data.assetsReceivablesShort ?? 0 },
        { name: 'Krátkodobý finančný majetok', value: data.assetsFinancialShort ?? 0 },
        { name: 'Finančné účty', value: data.assetsFinancialAccounts ?? 0 },
        { name: 'Časové rozlíšenie', value: data.assetsAccruals ?? 0 },
    ];

    const total = data.assetsTotal ?? segments.reduce((s, seg) => s + Math.max(0, seg.value), 0);
    const negative = segments.filter(s => s.value < 0);
    const filtered = segments
        .filter(s => s.value > 0)
        .map(s => ({ ...s, percent: total ? s.value / total : 0 }));

    // We have the total and nothing to break it into: template 1164 lists its
    // asset lines without the "súčet" suffix the vocabulary matches on, so a
    // filed balance sheet can arrive with no readable composition. Saying so
    // beats an absent card, which reads as "this company filed nothing".
    if (filtered.length === 0) {
        if (data.assetsTotal == null) return null;
        return (
            <InfoCard title={`Aktíva ${data.year}`} icon="fa-chart-pie">
                <p className="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                    Celkom: <span className="text-gray-900 dark:text-white font-bold">{formatCurrency(total)}</span>
                </p>
                <p className="text-xs text-gray-500 dark:text-gray-400 mt-2">
                    Rozpis na jednotlivé položky sa z tejto závierky nepodarilo prečítať.
                </p>
            </InfoCard>
        );
    }

    return (
        <InfoCard title={`Aktíva ${data.year}`} icon="fa-chart-pie">
            <div className="flex flex-col items-center gap-4">
                <div className="w-44 h-44">
                    <ResponsiveContainer
                        width="100%"
                        height="100%"
                        initialDimension={{ width: PIE_BOX, height: PIE_BOX }}
                    >
                        <PieChart>
                            <Pie
                                data={filtered}
                                dataKey="value"
                                innerRadius="55%"
                                outerRadius="90%"
                                paddingAngle={2}
                                stroke="none"
                            >
                                {filtered.map((entry, i) => (
                                    <Cell key={entry.name} fill={COLORS[segments.findIndex(s => s.name === entry.name) % COLORS.length]} />
                                ))}
                            </Pie>
                            <Tooltip content={<CustomTooltip />} />
                        </PieChart>
                    </ResponsiveContainer>
                </div>
                <p className="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                    Celkom: <span className="text-gray-900 dark:text-white font-bold">{formatCurrency(total)}</span>
                </p>
                <div className="w-full space-y-1.5">
                    {filtered.map((seg) => (
                        <div key={seg.name} className="flex items-center gap-2 text-sm">
                            <span
                                className="w-2.5 h-2.5 rounded-full flex-shrink-0"
                                style={{ backgroundColor: COLORS[segments.findIndex(s => s.name === seg.name) % COLORS.length] }}
                            />
                            <span className="text-gray-600 dark:text-gray-300 flex-1 min-w-0">{seg.name}</span>
                            <span className="text-gray-900 dark:text-white font-semibold tabular-nums whitespace-nowrap">
                                {formatCurrency(seg.value)}
                            </span>
                            <span className="text-gray-400 dark:text-gray-500 text-xs tabular-nums whitespace-nowrap">
                                {(seg.percent * 100).toFixed(1)}%
                            </span>
                        </div>
                    ))}
                </div>
                {negative.length > 0 && (
                    <div className="w-full text-xs text-amber-600 dark:text-amber-400 bg-amber-50 dark:bg-amber-900/20 rounded-lg p-2 mt-1">
                        <i className="fas fa-info-circle mr-1"></i>
                        Nezobrazené: {negative.map(s => `${s.name} (${formatCurrency(s.value)})`).join(', ')}
                    </div>
                )}
            </div>
        </InfoCard>
    );
};
