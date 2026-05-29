import React from 'react';
import { ResponsiveContainer, PieChart, Pie, Cell, Tooltip } from 'recharts';
import type { Financials } from '../../types';
import { InfoCard } from '../InfoCard';
import { formatCurrency, formatFullCurrency } from '../../utils/format';

interface LiabilitiesPieChartProps {
    data: Financials;
}

const COLORS = [
    '#93c5fd', // blue-300 — equity basic
    '#60a5fa', // blue-400 — capital funds
    '#3b82f6', // blue-500 — profit funds
    '#2563eb', // blue-600 — retained
    '#cbd5e1', // slate-300 — reserves
    '#94a3b8', // slate-400 — long-term liabilities
    '#64748b', // slate-500 — short-term liabilities
    '#475569', // slate-600 — accruals
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

export const LiabilitiesPieChart: React.FC<LiabilitiesPieChartProps> = ({ data }) => {
    const segments = [
        { name: 'Základné imanie', value: data.equityBasic },
        { name: 'Kapitálové fondy', value: data.equityCapitalFunds },
        { name: 'Fondy zo zisku', value: data.equityProfitFunds },
        { name: 'VH minulých rokov', value: data.equityRetained },
        { name: 'Rezervy', value: data.liabilitiesReserves },
        { name: 'Dlhodobé záväzky', value: data.liabilitiesLong },
        { name: 'Krátkodobé záväzky', value: data.liabilitiesShort },
        { name: 'Časové rozlíšenie', value: data.liabilitiesAccruals },
    ];

    const total = data.assetsTotal || segments.reduce((s, seg) => s + Math.max(0, seg.value), 0);
    const negative = segments.filter(s => s.value < 0);
    const filtered = segments
        .filter(s => s.value > 0)
        .map(s => ({ ...s, percent: total ? s.value / total : 0 }));

    if (filtered.length === 0) return null;

    return (
        <InfoCard title={`Pasíva ${data.year}`} icon="fa-chart-pie">
            <div className="flex flex-col items-center gap-4">
                <div className="w-44 h-44">
                    <ResponsiveContainer width="100%" height="100%">
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
                    Vlastný kapitál: <span className={`font-bold ${data.equity >= 0 ? 'text-gray-900 dark:text-white' : 'text-red-500 dark:text-red-400'}`}>
                        {formatCurrency(data.equity)}
                    </span>
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
