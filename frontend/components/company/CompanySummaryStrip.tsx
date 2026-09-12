import React from 'react';
import type { Company } from '../../types';
import { RiskDonut } from '../RiskDonut';
import { formatDate } from './helpers';
import {
    vatStanding,
    vatReliability,
    vatDeregistrationReason,
    VAT_STANDING_LABEL,
    type ReliabilityTone,
} from '../../utils/vatStatus';

interface CompanySummaryStripProps {
    company: Company;
}

/**
 * Colour for the reliability band.
 *
 * `unknown` is deliberately grey and not green. Half the register has no index
 * at all, and a reassuring colour for "we were not told" is how a risk signal
 * turns into a decoration.
 */
const RELIABILITY_TONE_CLASS: Record<ReliabilityTone, string> = {
    good: 'text-green-600 dark:text-green-400',
    neutral: 'text-gray-600 dark:text-gray-300',
    warn: 'text-amber-600 dark:text-amber-400',
    unknown: 'text-gray-400 dark:text-gray-500',
};

export const CompanySummaryStrip: React.FC<CompanySummaryStripProps> = ({ company }) => {
    const score = company.riskScore.score;
    const totalDebt = company.debts.reduce((sum, d) => sum + d.amountEur, 0);
    const hasDebt = totalDebt > 0;

    const vat = company.vatStatus;
    const standing = vatStanding(vat);
    const reliability = vatReliability(vat.taxReliabilityIndex);
    const deregistrationReason = vatDeregistrationReason(vat.reasonForDeregistration);
    const wasRegistered = vat.registeredOn !== null;

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
                    standing === 'deregistered'
                        ? 'bg-amber-100 dark:bg-amber-900/30 text-amber-600 dark:text-amber-400'
                        : 'bg-blue-100 dark:bg-blue-900/30 text-blue-600 dark:text-blue-400'
                }`}>
                    <i className={`fas ${standing === 'deregistered' ? 'fa-user-slash' : 'fa-percent'} text-xl`}></i>
                </div>
                <div className="min-w-0">
                    <p className="text-xs font-medium uppercase tracking-wider text-gray-500 dark:text-gray-400">DPH Status</p>
                    <p className={`text-lg font-bold ${
                        standing === 'unknown'
                            ? 'text-gray-500 dark:text-gray-400'
                            : 'text-gray-900 dark:text-white'
                    }`}>
                        {VAT_STANDING_LABEL[standing]}
                    </p>
                    <div className="flex flex-wrap items-center gap-x-2 gap-y-0.5 text-sm">
                        <span className={`font-medium ${RELIABILITY_TONE_CLASS[reliability.tone]}`}>
                            {reliability.label}
                        </span>
                        {vat.icDph && <span className="text-gray-400">• {vat.icDph}</span>}
                    </div>
                    {/* Dates, in the order the reader needs them. A company that
                        left the register says when and why; one that is still on
                        it says since when; one we know nothing about says
                        neither, and does not get a date it never had. */}
                    {standing === 'deregistered' && (
                        <p className="text-xs text-amber-600 dark:text-amber-400 mt-0.5">
                            {formatDate(vat.deregisteredOn!)}
                            {deregistrationReason && ` — ${deregistrationReason}`}
                        </p>
                    )}
                    {standing !== 'deregistered' && wasRegistered && (
                        <p className="text-xs text-gray-400 dark:text-gray-500 mt-0.5">
                            od {formatDate(vat.registeredOn!)}
                        </p>
                    )}
                    {vat.lastCheckedAt && (
                        <p className="text-xs text-gray-400 dark:text-gray-500 mt-0.5">
                            K dátumu: {new Date(vat.lastCheckedAt).toLocaleDateString('sk-SK')}
                        </p>
                    )}
                </div>
            </div>
        </div>
    );
};
