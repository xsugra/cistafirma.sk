import React, { useState } from 'react';
import {
    ResponsiveContainer, ComposedChart, XAxis, YAxis, Tooltip, Bar, Area,
    CartesianGrid, Line,
} from 'recharts';
import type { Financials } from '../types';
import { useTheme } from '../context/ThemeContext';

interface FinancialChartProps {
    data: Financials[];
}

const formatCurrency = (value: number | null) => {
    if (value == null) return '—';
    if (Math.abs(value) >= 1_000_000) return `${(value / 1_000_000).toFixed(1)}M €`;
    if (Math.abs(value) >= 1_000) return `${(value / 1_000).toFixed(0)}k €`;
    return `${value} €`;
};

const formatFullCurrency = (value: number) =>
    value.toLocaleString('sk-SK', { style: 'currency', currency: 'EUR', maximumFractionDigits: 0 });

const COLORS = {
    light: {
        revenue: '#2563eb',
        revenueMuted: '#93bbfd',
        profitPositive: '#16a34a',
        profitNegative: '#dc2626',
        profitArea: 'rgba(22, 163, 74, 0.08)',
        profitAreaNeg: 'rgba(220, 38, 38, 0.08)',
        grid: '#e2e8f0',
        axis: '#94a3b8',
        tooltipBg: '#ffffff',
        tooltipBorder: '#e2e8f0',
        tooltipText: '#0f172a',
        tooltipMuted: '#64748b',
        cardBg: '#f8fafc',
        cardBorder: '#e2e8f0',
    },
    dark: {
        revenue: '#3b82f6',
        revenueMuted: '#1e3a5f',
        profitPositive: '#4ade80',
        profitNegative: '#f87171',
        profitArea: 'rgba(74, 222, 128, 0.06)',
        profitAreaNeg: 'rgba(248, 113, 113, 0.06)',
        grid: '#1e293b',
        axis: '#64748b',
        tooltipBg: '#0f172a',
        tooltipBorder: '#1e293b',
        tooltipText: '#f1f5f9',
        tooltipMuted: '#94a3b8',
        cardBg: '#0f172a',
        cardBorder: '#1e293b',
    },
};

type ViewMode = 'both' | 'revenue' | 'profit' | 'tax';

const CustomTooltip = ({ active, payload, label, colors }: any) => {
    if (!active || !payload?.length) return null;
    const entries = payload || [];
    return (
        <div
            className="rounded-xl shadow-lg px-4 py-3 border"
            style={{ backgroundColor: colors.tooltipBg, borderColor: colors.tooltipBorder }}
        >
            <p className="text-xs font-bold mb-2 uppercase tracking-wider" style={{ color: colors.tooltipMuted }}>
                Rok {label}
            </p>
            {entries.map((entry: any) => {
                const nameMap: Record<string, string> = {
                    revenue: 'Tržby',
                    // The series is `profit`, which is the operating result --
                    // it was labelled "Zisk" while the field held the after-tax
                    // row for the loss-makers, so the tooltip named a figure the
                    // bar beside it did not always carry.
                    profit: 'VH z hosp. činnosti',
                    incomeTax: 'Daň z príjmu',
                    incomeTaxPaid: 'Splatná daň',
                };
                const colorVal = entry.dataKey === 'profit'
                    ? (entry.value >= 0 ? colors.profitPositive : colors.profitNegative)
                    : entry.color || colors.revenue;
                return (
                    <div key={entry.dataKey} className="flex items-center gap-2 mb-1 last:mb-0">
                        <span className="w-2.5 h-2.5 rounded-full" style={{ backgroundColor: colorVal }}></span>
                        <span className="text-sm" style={{ color: colors.tooltipMuted }}>{nameMap[entry.dataKey] || entry.name}</span>
                        <span className="text-sm font-bold ml-auto" style={{ color: entry.dataKey === 'profit' ? colorVal : colors.tooltipText }}>
                            {formatFullCurrency(entry.value)}
                        </span>
                    </div>
                );
            })}
        </div>
    );
};

export const FinancialChart: React.FC<FinancialChartProps> = ({ data }) => {
    const { isDark } = useTheme();
    const colors = isDark ? COLORS.dark : COLORS.light;
    const [view, setView] = useState<ViewMode>('both');

    const sorted = [...data].sort((a, b) => a.year - b.year);

    const latestYear = sorted.at(-1);
    const prevYear = sorted.at(-2);
    // A change needs both years to have filed the line. Letting an absent figure
    // through as 0 prints a confident "−100 %" for a year whose statement was
    // simply read as carrying no revenue.
    const revenueChange = latestYear?.revenue != null && prevYear?.revenue != null && prevYear.revenue !== 0
        ? ((latestYear.revenue - prevYear.revenue) / Math.abs(prevYear.revenue)) * 100
        : null;
    const profitChange = latestYear?.profit != null && prevYear?.profit != null && prevYear.profit !== 0
        ? ((latestYear.profit - prevYear.profit) / Math.abs(prevYear.profit)) * 100
        : null;
    // The colour of the profit line follows the most recent year that actually
    // filed one: painting the whole history from a year that reported nothing
    // would call a loss a gain.
    const lastFiledProfit = [...sorted].reverse().find(d => d.profit != null)?.profit ?? null;
    const profitIsPositive = lastFiledProfit == null || lastFiledProfit >= 0;

    const showRevenue = view === 'both' || view === 'revenue';
    const showProfit = view === 'both' || view === 'profit';
    const showTax = view === 'tax';

    // `!== 0` alone would be true for every unfiled tax line, so the tab would
    // offer a chart of two flat gaps.
    const hasTaxData = sorted.some(d => (d.incomeTax ?? 0) !== 0 || (d.incomeTaxPaid ?? 0) !== 0);

    const profitAreaColor = profitIsPositive ? colors.profitArea : colors.profitAreaNeg;

    return (
        <div className="space-y-5">
            {/* Summary cards + view toggle */}
            <div className="flex flex-col sm:flex-row sm:items-end justify-between gap-4">
                <div className="flex flex-wrap gap-3">
                    {latestYear && (
                        <>
                            <div className="flex items-center gap-3 px-4 py-2.5 rounded-xl border"
                                 style={{ borderColor: colors.cardBorder, backgroundColor: colors.cardBg }}>
                                <span className="w-2.5 h-2.5 rounded-full" style={{ backgroundColor: colors.revenue }}></span>
                                <div>
                                    <p className="text-[10px] font-medium uppercase tracking-wider text-gray-500 dark:text-gray-400">
                                        Tržby {latestYear.year}
                                    </p>
                                    <div className="flex items-baseline gap-1.5">
                                        <span className="text-base font-bold text-gray-900 dark:text-white">
                                            {formatCurrency(latestYear.revenue)}
                                        </span>
                                        {revenueChange !== null && (
                                            <span className={`text-xs font-semibold ${revenueChange >= 0 ? 'text-green-600 dark:text-green-400' : 'text-red-500 dark:text-red-400'}`}>
                                                {revenueChange >= 0 ? '+' : ''}{revenueChange.toFixed(1)}%
                                            </span>
                                        )}
                                    </div>
                                </div>
                            </div>
                            <div className="flex items-center gap-3 px-4 py-2.5 rounded-xl border"
                                 style={{ borderColor: colors.cardBorder, backgroundColor: colors.cardBg }}>
                                <span className="w-2.5 h-2.5 rounded-full"
                                      style={{ backgroundColor: profitIsPositive ? colors.profitPositive : colors.profitNegative }}></span>
                                <div>
                                    <p className="text-[10px] font-medium uppercase tracking-wider text-gray-500 dark:text-gray-400">
                                        VH z hosp. činnosti {latestYear.year}
                                    </p>
                                    <div className="flex items-baseline gap-1.5">
                                        <span className={`text-base font-bold ${latestYear.profit == null
                                            ? 'text-gray-400 dark:text-gray-500'
                                            : profitIsPositive ? 'text-green-600 dark:text-green-400' : 'text-red-500 dark:text-red-400'}`}>
                                            {formatCurrency(latestYear.profit)}
                                        </span>
                                        {profitChange !== null && (
                                            <span className={`text-xs font-semibold ${profitChange >= 0 ? 'text-green-600 dark:text-green-400' : 'text-red-500 dark:text-red-400'}`}>
                                                {profitChange >= 0 ? '+' : ''}{profitChange.toFixed(1)}%
                                            </span>
                                        )}
                                    </div>
                                </div>
                            </div>
                        </>
                    )}
                </div>

                {/* View toggle */}
                <div className="flex rounded-lg border overflow-hidden self-start sm:self-auto"
                     style={{ borderColor: colors.cardBorder }}>
                    {([
                        { id: 'both', label: 'Všetko' },
                        { id: 'revenue', label: 'Tržby' },
                        { id: 'profit', label: 'VH z hosp. č.' },
                        ...(hasTaxData ? [{ id: 'tax' as const, label: 'Daň' }] : []),
                    ] as const).map(v => (
                        <button
                            key={v.id}
                            onClick={() => setView(v.id)}
                            className={`px-3 py-1.5 text-xs font-medium transition-colors ${
                                view === v.id
                                    ? 'bg-blue-600 text-white'
                                    : 'text-gray-500 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-slate-800'
                            }`}
                        >
                            {v.label}
                        </button>
                    ))}
                </div>
            </div>

            {/* Chart */}
            <div className="w-full h-[320px] sm:h-[380px]">
                <ResponsiveContainer width="100%" height="100%">
                    <ComposedChart data={sorted} margin={{ top: 20, right: 12, left: 0, bottom: 4 }}>
                        <defs>
                            <linearGradient id="revenueGrad" x1="0" y1="0" x2="0" y2="1">
                                <stop offset="0%" stopColor={colors.revenue} stopOpacity={0.9} />
                                <stop offset="100%" stopColor={colors.revenue} stopOpacity={0.6} />
                            </linearGradient>
                            <linearGradient id="profitAreaGrad" x1="0" y1="0" x2="0" y2="1">
                                <stop offset="0%" stopColor={profitAreaColor} stopOpacity={1} />
                                <stop offset="100%" stopColor={profitAreaColor} stopOpacity={0} />
                            </linearGradient>
                        </defs>

                        <CartesianGrid
                            strokeDasharray="3 3"
                            stroke={colors.grid}
                            vertical={false}
                        />
                        <XAxis
                            dataKey="year"
                            stroke={colors.axis}
                            tick={{ fontSize: 12, fill: colors.axis }}
                            tickLine={false}
                            axisLine={{ stroke: colors.grid }}
                        />
                        <YAxis
                            stroke={colors.axis}
                            tick={{ fontSize: 11, fill: colors.axis }}
                            tickFormatter={formatCurrency}
                            tickLine={false}
                            axisLine={false}
                            width={65}
                        />
                        <Tooltip
                            content={<CustomTooltip colors={colors} />}
                            cursor={{ fill: isDark ? 'rgba(255,255,255,0.03)' : 'rgba(0,0,0,0.03)' }}
                        />

                        {showRevenue && (
                            <Bar
                                dataKey="revenue"
                                fill="url(#revenueGrad)"
                                radius={[6, 6, 0, 0]}
                                maxBarSize={48}
                                name="Tržby"
                            />
                        )}

                        {showProfit && (
                            <Area
                                type="monotone"
                                dataKey="profit"
                                fill="url(#profitAreaGrad)"
                                stroke={profitIsPositive ? colors.profitPositive : colors.profitNegative}
                                strokeWidth={2.5}
                                dot={{ r: 4, strokeWidth: 2, fill: isDark ? '#0f172a' : '#ffffff' }}
                                activeDot={{ r: 6, strokeWidth: 2 }}
                                name="VH z hosp. činnosti"
                            />
                        )}

                        {showTax && (
                            <>
                                <Line
                                    type="monotone"
                                    dataKey="incomeTax"
                                    stroke="#ef4444"
                                    strokeWidth={2.5}
                                    dot={{ r: 4, strokeWidth: 2, fill: isDark ? '#0f172a' : '#ffffff' }}
                                    activeDot={{ r: 6, strokeWidth: 2 }}
                                    name="Daň z príjmu"
                                />
                                <Line
                                    type="monotone"
                                    dataKey="incomeTaxPaid"
                                    stroke="#f59e0b"
                                    strokeWidth={2.5}
                                    strokeDasharray="5 3"
                                    dot={{ r: 4, strokeWidth: 2, fill: isDark ? '#0f172a' : '#ffffff' }}
                                    activeDot={{ r: 6, strokeWidth: 2 }}
                                    name="Splatná daň"
                                />
                            </>
                        )}
                    </ComposedChart>
                </ResponsiveContainer>
            </div>
        </div>
    );
};
