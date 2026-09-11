import React from 'react';
import type { Company } from '../../../types';
import { InfoCard } from '../../InfoCard';
import { FinancialRatiosTable } from '../FinancialRatiosTable';
import { BenchmarkComparison } from '../BenchmarkComparison';

interface FinancialAnalysisSectionProps {
    company: Company;
}

/** The metrics worth lining up across years, in the order an analyst reads them. */
const TREND_METRICS = [
    { key: 'roa', label: 'ROA', unit: '%' },
    { key: 'roe', label: 'ROE', unit: '%' },
    { key: 'ros', label: 'ROS', unit: '%' },
    { key: 'currentRatio', label: 'L3 likvidita', unit: '×' },
    { key: 'quickRatio', label: 'L2 likvidita', unit: '×' },
    { key: 'selfFinancingRatio', label: 'Samofinancovanie', unit: '%' },
    { key: 'zScore', label: 'Z-score', unit: '' },
] as const;

const formatMetric = (value: number, unit: string): string =>
    unit === '%' ? `${value.toFixed(1)}%` : value.toFixed(2);

export const FinancialAnalysisSection: React.FC<FinancialAnalysisSectionProps> = ({ company }) => {
    const analysis = company.analysis;
    if (!analysis) {
        return (
            <InfoCard title="Finančná analýza" icon="fa-calculator">
                <div className="text-center py-4 text-gray-500 dark:text-gray-400">
                    <i className="fas fa-info-circle mr-2"></i>
                    Pre finančnú analýzu nie sú k dispozícii dostatočné údaje.
                </div>
            </InfoCard>
        );
    }

    const history = analysis.history || [];
    const prevAnalysis = history.length > 1 ? history[history.length - 2] : undefined;

    return (
        <div className="space-y-6">
            <FinancialRatiosTable analysis={analysis.latest} prevAnalysis={prevAnalysis} />

            {company.benchmark && (
                <BenchmarkComparison benchmark={company.benchmark} analysis={analysis.latest} />
            )}

            {/* Year-over-year comparison */}
            {history.length > 1 && (
                <InfoCard title="Medziročné porovnanie" icon="fa-arrows-left-right">
                    <div className="overflow-x-auto">
                        <table className="w-full text-sm">
                            <thead>
                                <tr className="border-b border-gray-100 dark:border-slate-800">
                                    <th className="text-left px-3 py-2 text-xs font-medium text-gray-500 uppercase">Ukazovateľ</th>
                                    {history.slice(-5).map((y: any) => (
                                        <th key={y.year} className="text-right px-3 py-2 text-xs font-medium text-gray-500 uppercase">
                                            {y.year}
                                        </th>
                                    ))}
                                </tr>
                            </thead>
                            <tbody className="divide-y divide-gray-50 dark:divide-slate-800/50">
                                {TREND_METRICS.map((metric) => (
                                    <tr key={metric.key} className="hover:bg-gray-50/50 dark:hover:bg-slate-900/30">
                                        <td className="px-3 py-2 text-gray-700 dark:text-gray-300 font-medium">
                                            {metric.label}
                                        </td>
                                        {history.slice(-5).map((y: any) => {
                                            let value: number | null = null;
                                            if (metric.key === 'zScore') {
                                                value = y.zScore;
                                            } else {
                                                const ratios = y.ratios as Record<string, number | null>;
                                                value = ratios[metric.key];
                                            }
                                            return (
                                                <td key={y.year} className="text-right px-3 py-2 font-mono text-gray-900 dark:text-white">
                                                    {value != null ? formatMetric(value, metric.unit) : '—'}
                                                </td>
                                            );
                                        })}
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                </InfoCard>
            )}
        </div>
    );
};
