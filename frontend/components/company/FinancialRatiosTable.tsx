import React from 'react';
import type { YearAnalysis } from '../../types';
import { InfoCard } from '../InfoCard';

interface FinancialRatiosTableProps {
    analysis: YearAnalysis;
    prevAnalysis?: YearAnalysis;
}

interface RatioRow {
    section: string;
    key: string;
    label: string;
    unit: string;
    inverse?: boolean;
}

const SECTIONS: { title: string; icon: string; rows: RatioRow[] }[] = [
    {
        title: 'Rentabilita',
        icon: 'fa-chart-line',
        rows: [
            { section: 'Rentabilita', key: 'roa', label: 'ROA (Rentabilita aktív)', unit: '%' },
            { section: 'Rentabilita', key: 'roe', label: 'ROE (Rentabilita vlastného kapitálu)', unit: '%' },
            { section: 'Rentabilita', key: 'ros', label: 'ROS (Rentabilita tržieb)', unit: '%' },
        ],
    },
    {
        title: 'Likvidita',
        icon: 'fa-droplet',
        rows: [
            { section: 'Likvidita', key: 'currentRatio', label: 'L3 — Bežná likvidita', unit: '×' },
            { section: 'Likvidita', key: 'quickRatio', label: 'L2 — Pohotová likvidita', unit: '×' },
            { section: 'Likvidita', key: 'cashRatio', label: 'L1 — Okamžitá likvidita', unit: '×' },
        ],
    },
    {
        title: 'Aktivita',
        icon: 'fa-rotate',
        rows: [
            { section: 'Aktivita', key: 'assetTurnover', label: 'Obrat aktív', unit: '×' },
            { section: 'Aktivita', key: 'receivablesCollection', label: 'Doba inkasa pohľadávok', unit: 'dní', inverse: true },
        ],
    },
    {
        title: 'Zadĺženosť',
        icon: 'fa-scale-balanced',
        rows: [
            { section: 'Zadĺženosť', key: 'debtToEquity', label: 'Zadĺženosť (D/E)', unit: '×', inverse: true },
            { section: 'Zadĺženosť', key: 'selfFinancingRatio', label: 'Miera samofinancovania', unit: '%' },
        ],
    },
];

const INTERPRETATION_LABELS: Record<string, string> = {
    good: 'Priaznivá',
    warning: 'Uspokojivá',
    bad: 'Riziková',
};

const INTERPRETATION_COLORS: Record<string, string> = {
    good: 'text-green-600 dark:text-green-400 bg-green-50 dark:bg-green-900/20',
    warning: 'text-amber-600 dark:text-amber-400 bg-amber-50 dark:bg-amber-900/20',
    bad: 'text-red-600 dark:text-red-400 bg-red-50 dark:bg-red-900/20',
};

const TrendArrowMini: React.FC<{ current: number; previous: number; inverse?: boolean }> = ({
    current,
    previous,
    inverse,
}) => {
    if (previous === 0 && current === 0) return null;
    if (previous === 0) return <span className="text-[10px] text-blue-500 font-semibold">nový</span>;
    const change = ((current - previous) / Math.abs(previous)) * 100;
    const isPositive = inverse ? change <= 0 : change >= 0;
    if (Math.abs(change) < 0.1) return <span className="text-[10px] text-gray-400">—</span>;
    return (
        <span
            className={`inline-flex items-center gap-0.5 text-[10px] font-semibold ${
                isPositive ? 'text-green-600 dark:text-green-400' : 'text-red-500 dark:text-red-400'
            }`}
        >
            <i className={`fas fa-arrow-${change >= 0 ? 'up' : 'down'} text-[8px]`}></i>
            {Math.abs(change).toFixed(1)}%
        </span>
    );
};

export const FinancialRatiosTable: React.FC<FinancialRatiosTableProps> = ({ analysis, prevAnalysis }) => {
    const formatValue = (value: number | null, unit: string): string => {
        if (value == null) return '—';
        if (unit === '%') return `${value.toFixed(2)} %`;
        if (unit === '×') return value.toFixed(2);
        if (unit === 'dní') return value.toFixed(0);
        return `${value}`;
    };

    const getPrevValue = (key: string): number => {
        if (!prevAnalysis) return 0;
        const ratios = prevAnalysis.ratios as unknown as Record<string, number | null>;
        return ratios[key] ?? 0;
    };

    return (
        <InfoCard title={`Pomerové ukazovatele — ${analysis.year}`} icon="fa-calculator">
            {/* Altman Z-score banner */}
            {analysis.zScore != null && (
                <div
                    className={`mb-4 p-4 rounded-xl border ${
                        analysis.zScore > 2.90
                            ? 'border-green-200 dark:border-green-800 bg-green-50 dark:bg-green-900/20'
                            : analysis.zScore > 1.23
                              ? 'border-amber-200 dark:border-amber-800 bg-amber-50 dark:bg-amber-900/20'
                              : 'border-red-200 dark:border-red-800 bg-red-50 dark:bg-red-900/20'
                    }`}
                >
                    <div className="flex items-center justify-between">
                        <div>
                            <p className="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                                Altman Z-score
                            </p>
                            <p className="text-2xl font-bold text-gray-900 dark:text-white mt-0.5">
                                {analysis.zScore.toFixed(2)}
                            </p>
                        </div>
                        <div className="text-right">
                            <span
                                className={`inline-block px-3 py-1 rounded-full text-xs font-semibold ${
                                    analysis.zScore > 2.90
                                        ? 'text-green-700 dark:text-green-300 bg-green-100 dark:bg-green-900/30'
                                        : analysis.zScore > 1.23
                                          ? 'text-amber-700 dark:text-amber-300 bg-amber-100 dark:bg-amber-900/30'
                                          : 'text-red-700 dark:text-red-300 bg-red-100 dark:bg-red-900/30'
                                }`}
                            >
                                {analysis.zScoreLabel}
                            </span>
                            <p className="text-[10px] text-gray-400 dark:text-gray-500 mt-1">
                                {analysis.zScore > 2.90
                                    ? 'Nízke riziko bankrotu'
                                    : analysis.zScore > 1.23
                                      ? 'Nejednoznačná situácia'
                                      : 'Zvýšené riziko bankrotu'}
                            </p>
                        </div>
                    </div>
                </div>
            )}

            {/* Ratio sections */}
            <div className="space-y-5">
                {SECTIONS.map((section) => (
                    <div key={section.title}>
                        <h4 className="flex items-center gap-2 text-sm font-semibold text-gray-700 dark:text-gray-300 mb-2">
                            <i className={`fas ${section.icon} text-blue-500 dark:text-blue-400 text-xs`}></i>
                            {section.title}
                        </h4>
                        <div className="overflow-hidden rounded-lg border border-gray-100 dark:border-slate-800">
                            <table className="w-full text-sm">
                                <thead>
                                    <tr className="bg-gray-50 dark:bg-slate-900/50">
                                        <th className="text-left px-4 py-2.5 text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                                            Ukazovateľ
                                        </th>
                                        <th className="text-right px-4 py-2.5 text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider w-24">
                                            Hodnota
                                        </th>
                                        <th className="text-right px-4 py-2.5 text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider w-20">
                                            Trend
                                        </th>
                                        <th className="text-right px-4 py-2.5 text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider w-24">
                                            Stav
                                        </th>
                                    </tr>
                                </thead>
                                <tbody className="divide-y divide-gray-50 dark:divide-slate-800/50">
                                    {section.rows.map((row) => {
                                        const ratios = analysis.ratios as unknown as Record<string, number | null>;
                                        const value = ratios[row.key];
                                        // A row with no figure gets no verdict. The
                                        // backend answers `bad` for a value the
                                        // statement never carried, which put a red
                                        // "Riziková" badge beside a dash -- a claim
                                        // about the company rather than the filing.
                                        const interp = value == null
                                            ? null
                                            : (analysis.interpretation[row.key] || 'bad');
                                        const prevVal = getPrevValue(row.key);

                                        return (
                                            <tr
                                                key={row.key}
                                                className="hover:bg-gray-50/50 dark:hover:bg-slate-900/30 transition-colors"
                                            >
                                                <td className="px-4 py-2.5 text-gray-700 dark:text-gray-300">
                                                    {row.label}
                                                </td>
                                                <td className="px-4 py-2.5 text-right font-mono font-semibold text-gray-900 dark:text-white">
                                                    {formatValue(value, row.unit)}
                                                </td>
                                                <td className="px-4 py-2.5 text-right">
                                                    {value != null && prevAnalysis && prevVal !== 0 && (
                                                        <TrendArrowMini
                                                            current={value}
                                                            previous={prevVal}
                                                            inverse={row.inverse}
                                                        />
                                                    )}
                                                </td>
                                                <td className="px-4 py-2.5 text-right">
                                                    {interp ? (
                                                        <span
                                                            className={`inline-block px-2 py-0.5 rounded-full text-[10px] font-semibold ${INTERPRETATION_COLORS[interp]}`}
                                                        >
                                                            {INTERPRETATION_LABELS[interp]}
                                                        </span>
                                                    ) : (
                                                        <span className="text-gray-400 dark:text-gray-500">—</span>
                                                    )}
                                                </td>
                                            </tr>
                                        );
                                    })}
                                </tbody>
                            </table>
                        </div>
                    </div>
                ))}
            </div>
        </InfoCard>
    );
};
