
import React, { useState } from 'react';
import type { Company } from '../types';
import { InfoCard } from './InfoCard';
import { StatusBadge } from './StatusBadge';
import { FinancialChart } from './FinancialChart';
import { RiskDonut } from './RiskDonut';
import { AiSummary } from './AiSummary';
import { api } from '../api';

interface CompanyDetailProps {
  company: Company;
}

const DetailItem: React.FC<{ label: string; value: React.ReactNode; icon: string }> = ({ label, value, icon }) => (
    <div className="flex items-start space-x-3">
        <i className={`fas ${icon} text-blue-500 dark:text-blue-400 mt-1 w-4 text-center`}></i>
        <div>
            <p className="text-sm text-gray-500 dark:text-gray-400">{label}</p>
            <p className="font-semibold text-gray-900 dark:text-white">{value}</p>
        </div>
    </div>
);

export const CompanyDetail: React.FC<CompanyDetailProps> = ({ company }) => {
  const totalDebt = company.debts.reduce((sum, debt) => sum + debt.amountEur, 0);
  const [isWatching, setIsWatching] = useState(false);
  const [watchLoading, setWatchLoading] = useState(false);

  const handleWatchToggle = async () => {
      setWatchLoading(true);
      try {
          await api.addToWatchlist(company.ico);
          setIsWatching(!isWatching);
      } catch (e) {
          console.error("Watch toggle failed", e);
      } finally {
          setWatchLoading(false);
      }
  };

  return (
    <div className="space-y-8 animate-fade-in mt-10">
        {/* Header Section */}
        <div className="app-card p-6">
            <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
                <div>
                    <h2 className="text-3xl font-bold text-gray-900 dark:text-white">{company.name}</h2>
                    <p className="text-gray-500 dark:text-gray-400">{company.legalForm}</p>
                </div>
                <div className="flex items-center gap-4">
                    <StatusBadge status={company.status} />
                    
                    <button 
                        onClick={handleWatchToggle}
                        disabled={watchLoading}
                        className={`btn ${isWatching ? 'bg-green-600 hover:bg-green-700 text-white' : 'btn-primary'}`}
                    >
                        {watchLoading ? (
                            <i className="fas fa-spinner animate-spin"></i>
                        ) : (
                            <i className={`fas ${isWatching ? 'fa-check' : 'fa-bell'}`}></i>
                        )}
                        {isWatching ? 'Sledované' : 'Sledovať'}
                    </button>

                    <button className="btn btn-outline border-gray-300 text-gray-700 dark:text-gray-300 dark:border-gray-600">
                        <i className="fas fa-file-pdf"></i> PDF
                    </button>
                </div>
            </div>
            <div className="mt-6 grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 border-t border-gray-200 dark:border-slate-800 pt-6">
                <DetailItem label="IČO" value={company.ico} icon="fa-hashtag" />
                <DetailItem label="Adresa" value={`${company.address.street}, ${company.address.city}`} icon="fa-map-marker-alt" />
                <DetailItem label="Dátum vzniku" value={new Date(company.registrationDate).toLocaleDateString('sk-SK')} icon="fa-calendar-alt" />
                <DetailItem label="Posledná aktualizácia" value={new Date(company.lastUpdatedFromSource).toLocaleString('sk-SK')} icon="fa-sync-alt" />
            </div>
        </div>

        {/* Main Grid Layout */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
            <div className="lg:col-span-2 space-y-8">
                {/* Debts */}
                <InfoCard title="Dlhy a Nedoplatky" icon="fa-exclamation-triangle">
                    {company.debts.length > 0 ? (
                        <div className="space-y-4">
                            {company.debts.map(debt => (
                                <div key={debt.id} className="flex justify-between items-center p-3 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-500/30 rounded-lg">
                                    <div>
                                        <p className="font-semibold text-red-700 dark:text-red-300">{debt.source}</p>
                                        <p className="text-sm text-gray-600 dark:text-gray-400">K dátumu: {new Date(debt.dateOfRecord).toLocaleDateString('sk-SK')}</p>
                                    </div>
                                    <p className="text-lg font-bold text-red-600 dark:text-red-300">{debt.amountEur.toLocaleString('sk-SK', { style: 'currency', currency: 'EUR' })}</p>
                                </div>
                            ))}
                             <div className="flex justify-between items-center p-4 bg-red-100 dark:bg-red-900/50 rounded-lg mt-4">
                                <p className="font-bold text-gray-900 dark:text-white text-lg">Celkový dlh</p>
                                <p className="text-xl font-bold text-red-600 dark:text-white">{totalDebt.toLocaleString('sk-SK', { style: 'currency', currency: 'EUR' })}</p>
                            </div>
                        </div>
                    ) : (
                        <div className="text-center py-4 text-green-600 dark:text-green-400 bg-green-50 dark:bg-green-900/20 border border-green-200 dark:border-green-500/30 rounded-lg">
                            <i className="fas fa-check-circle mr-2"></i> Neboli nájdené žiadne aktuálne dlhy.
                        </div>
                    )}
                </InfoCard>

                {/* AI Summary */}
                <AiSummary companyData={company} />

                {/* Financials */}
                <InfoCard title="Hospodárske výsledky" icon="fa-chart-line">
                    <FinancialChart data={company.financials} />
                </InfoCard>

                 {/* Connections */}
                <InfoCard title="Prepojenia a Štatutári" icon="fa-project-diagram">
                    <div className="space-y-3">
                        <h4 className="font-semibold text-lg text-gray-900 dark:text-white mb-2">Osoby</h4>
                        {company.executives.map((exec, index) => (
                             <div key={index} className="flex justify-between items-center p-3 bg-gray-50 dark:bg-slate-800/50 rounded-lg">
                                <p className="font-medium text-gray-800 dark:text-gray-200">{exec.name}</p>
                                <p className="text-sm text-gray-500 dark:text-gray-400">{exec.role}</p>
                            </div>
                        ))}
                    </div>
                     <div className="space-y-3 mt-6">
                        <h4 className="font-semibold text-lg text-gray-900 dark:text-white mb-2">Rizikové prepojenia</h4>
                        {company.connections.filter(c => c.status !== 'Aktívna').map((conn, index) => (
                            <div key={index} className="flex justify-between items-center p-3 bg-yellow-50 dark:bg-yellow-900/20 border border-yellow-200 dark:border-yellow-500/30 rounded-lg">
                                <div>
                                    <p className="font-semibold text-yellow-700 dark:text-yellow-300">{conn.companyName}</p>
                                    <p className="text-sm text-gray-600 dark:text-gray-400">{conn.role}</p>
                                </div>
                                <StatusBadge status={conn.status} />
                            </div>
                        ))}
                         {company.connections.filter(c => c.status !== 'Aktívna').length === 0 && (
                            <div className="text-center py-4 text-gray-500 dark:text-gray-400">
                                <i className="fas fa-check-circle mr-2"></i> Neboli nájdené žiadne rizikové prepojenia.
                            </div>
                         )}
                    </div>
                </InfoCard>
            </div>
            <div className="lg:col-span-1 space-y-8">
                <InfoCard title="Risk Skóre" icon="fa-tachometer-alt">
                    <RiskDonut score={company.riskScore.score} />
                     <p className="text-center text-gray-600 dark:text-gray-300 mt-4 leading-relaxed">{company.riskScore.summary}</p>
                </InfoCard>
                <InfoCard title="Status DPH" icon="fa-percent">
                    <div className="space-y-4">
                        <DetailItem label="Platiteľ DPH" value={company.vatStatus.isVatPayer ? 'Áno' : 'Nie'} icon="fa-check-circle" />
                        {company.vatStatus.icDph && <DetailItem label="IČ DPH" value={company.vatStatus.icDph} icon="fa-hashtag" />}
                        <DetailItem label="Index daňovej spoľahlivosti" value={<span className={`font-bold ${company.vatStatus.taxReliabilityIndex === 'Nespoľahlivý' ? 'text-red-500 dark:text-red-400' : 'text-green-600 dark:text-green-400'}`}>{company.vatStatus.taxReliabilityIndex}</span>} icon="fa-thumbs-up" />
                    </div>
                </InfoCard>
            </div>
        </div>
    </div>
  );
};
