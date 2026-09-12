import React from 'react';
import type { Company } from '../../types';
import { RiskDonut } from '../RiskDonut';

interface CompanySummaryStripProps {
    company: Company;
}

export const CompanySummaryStrip: React.FC<CompanySummaryStripProps> = ({ company }) => {
    const score = company.riskScore.score;
    const totalDebt = company.debts.reduce((sum, d) => sum + d.amountEur, 0);
    const hasDebt = totalDebt > 0;
    const reliabilityIndex = company.vatStatus.taxReliabilityIndex;
    const isUnreliable = reliabilityIndex === 'Nespoľahlivý';

    return (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {/* Risk Score */}
            <div className="app-card p-5 flex items-center gap-5">
                <div className="w-20 h-20 flex-shrink-0">
                    {/* A donut needs a number to draw an arc for. An absent score
                        gets an empty ring rather than a full green one, which is
                        what a donut at 100 would have drawn. */}
                    {score === null
                        ? <div className="w-full h-full rounded-full border-8 border-gray-200 dark:border-slate-700" />
                        : <RiskDonut score={score} size="sm" />}
                </div>
                <div className="min-w-0">
                    <p className="text-xs font-medium uppercase tracking-wider text-gray-500 dark:text-gray-400">Rizikové skóre</p>
                    <p className="text-2xl font-bold text-gray-900 dark:text-white">
                        {score === null
                            ? <span className="text-gray-400 dark:text-gray-500">—</span>
                            : <>{score}<span className="text-sm font-normal text-gray-400"> / 100</span></>}
                    </p>
                    <p className="text-sm text-gray-500 dark:text-gray-400">
                        {company.riskScore.summary || (score === null ? 'Skóre sa nepodarilo načítať.' : '')}
                    </p>
                </div>
            </div>

            {/* Debts */}
            <div className="app-card p-5 flex items-center gap-5">
                <div className={`w-12 h-12 rounded-xl flex items-center justify-center flex-shrink-0 ${
                    hasDebt
                        ? 'bg-red-100 dark:bg-red-900/30 text-red-600 dark:text-red-400'
                        : 'bg-green-100 dark:bg-green-900/30 text-green-600 dark:text-green-400'
                }`}>
                    <i className={`fas ${hasDebt ? 'fa-exclamation-triangle' : 'fa-check-circle'} text-xl`}></i>
                </div>
                <div className="min-w-0">
                    <p className="text-xs font-medium uppercase tracking-wider text-gray-500 dark:text-gray-400">Dlhy</p>
                    <p className={`text-2xl font-bold ${hasDebt ? 'text-red-600 dark:text-red-400' : 'text-green-600 dark:text-green-400'}`}>
                        {totalDebt.toLocaleString('sk-SK', { style: 'currency', currency: 'EUR' })}
                    </p>
                    <p className="text-sm text-gray-500 dark:text-gray-400">
                        {hasDebt ? `${company.debts.length} ${company.debts.length === 1 ? 'záznam' : 'záznamy'}` : 'Bez dlhov'}
                    </p>
                    {hasDebt && company.debts[0]?.dateOfRecord && (
                        <p className="text-xs text-gray-400 dark:text-gray-500 mt-0.5">
                            K dátumu: {new Date(company.debts[0].dateOfRecord).toLocaleDateString('sk-SK')}
                        </p>
                    )}
                </div>
            </div>

            {/* VAT Status */}
            <div className="app-card p-5 flex items-center gap-5">
                <div className={`w-12 h-12 rounded-xl flex items-center justify-center flex-shrink-0 ${
                    isUnreliable
                        ? 'bg-red-100 dark:bg-red-900/30 text-red-600 dark:text-red-400'
                        : 'bg-blue-100 dark:bg-blue-900/30 text-blue-600 dark:text-blue-400'
                }`}>
                    <i className="fas fa-percent text-xl"></i>
                </div>
                <div className="min-w-0">
                    <p className="text-xs font-medium uppercase tracking-wider text-gray-500 dark:text-gray-400">DPH Status</p>
                    <p className="text-lg font-bold text-gray-900 dark:text-white">
                        {company.vatStatus.isVatPayer ? 'Platiteľ DPH' : 'Neplatiteľ DPH'}
                    </p>
                    <div className="flex items-center gap-2 text-sm">
                        <span className={`font-medium ${isUnreliable ? 'text-red-500 dark:text-red-400' : 'text-green-600 dark:text-green-400'}`}>
                            {reliabilityIndex}
                        </span>
                        {company.vatStatus.icDph && (
                            <span className="text-gray-400">• {company.vatStatus.icDph}</span>
                        )}
                    </div>
                    {company.vatStatus.lastCheckedAt && (
                        <p className="text-xs text-gray-400 dark:text-gray-500 mt-0.5">
                            K dátumu: {new Date(company.vatStatus.lastCheckedAt).toLocaleDateString('sk-SK')}
                        </p>
                    )}
                </div>
            </div>
        </div>
    );
};
