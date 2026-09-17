import React from 'react';
import type { Company } from '../../../types';
import { InfoCard } from '../../InfoCard';
import { FinancialChart } from '../../FinancialChart';
import { CompanyDebts } from '../CompanyDebts';
import { CompanyCapital } from '../CompanyCapital';
import { FinancialIndicators } from '../FinancialIndicators';
import { AssetsPieChart } from '../AssetsPieChart';
import { LiabilitiesPieChart } from '../LiabilitiesPieChart';
import { useCompanyProfile } from '../useCompanyProfile';

interface OverviewSectionProps {
    company: Company;
}

export const OverviewSection: React.FC<OverviewSectionProps> = ({ company }) => {
    const { orsrProfile, structured, profile, showKonanie, konanie } = useCompanyProfile(company);

    const sorted = [...company.financials].sort((a, b) => a.year - b.year);
    const latestWithAssets = [...sorted].reverse().find((f) => f.assetsTotal > 0);

    return (
        <div className="space-y-6">
            <CompanyDebts
                debts={company.debts}
                insuranceCheckedOn={company.insuranceCheckedOn}
                taxCheckedOn={company.taxCheckedOn}
                socialListedWithoutAmount={company.socialListedWithoutAmount}
            />

            {company.financials.length > 0 ? (
                <FinancialIndicators data={company.financials} analysis={company.analysis?.latest} />
            ) : company.usesIfrs ? (
                <InfoCard title="Finančné údaje" icon="fa-chart-bar">
                    <div className="text-center py-6 text-gray-600 dark:text-gray-300">
                        <i className="fas fa-file-pdf text-2xl mb-3 text-red-400"></i>
                        <p className="mb-1 font-medium">Táto spoločnosť účtuje podľa medzinárodných
                            štandardov (IFRS).</p>
                        <p className="text-sm text-gray-500 dark:text-gray-400 mb-3">Finančné výkazy sú v
                            Registri účtovných závierok dostupné len v PDF forme.</p>
                        {company.ruzPortalUrl && (
                            <a href={company.ruzPortalUrl} target="_blank" rel="noopener noreferrer"
                               className="inline-flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white text-sm rounded-lg transition-colors">
                                <i className="fas fa-external-link-alt"></i>
                                Zobraziť na RUZ portáli
                            </a>
                        )}
                    </div>
                </InfoCard>
            ) : (
                <InfoCard title="Finančné údaje" icon="fa-chart-bar">
                    <div className="text-center py-4 text-gray-500 dark:text-gray-400">
                        <i className="fas fa-info-circle mr-2"></i>
                        Finančné údaje zatiaľ nie sú k dispozícii.
                    </div>
                </InfoCard>
            )}

            <InfoCard title="Hospodárske výsledky" icon="fa-chart-line">
                {company.financials.length > 0 ? (
                    <div className="min-h-[350px]">
                        <FinancialChart data={company.financials} />
                    </div>
                ) : company.usesIfrs ? (
                    <div className="text-center py-6 text-gray-600 dark:text-gray-300">
                        <i className="fas fa-file-pdf text-2xl mb-3 text-red-400"></i>
                        <p className="mb-1 font-medium">Hospodárske výsledky sú súčasťou IFRS závierky.</p>
                        <p className="text-sm text-gray-500 dark:text-gray-400 mb-3">Údaje sú dostupné v PDF
                            výkazoch na portáli Registra účtovných závierok.</p>
                        {company.ruzPortalUrl && (
                            <a href={company.ruzPortalUrl} target="_blank" rel="noopener noreferrer"
                               className="inline-flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white text-sm rounded-lg transition-colors">
                                <i className="fas fa-external-link-alt"></i>
                                Zobraziť na RUZ portáli
                            </a>
                        )}
                    </div>
                ) : (
                    <div className="text-center py-4 text-gray-500 dark:text-gray-400">
                        <i className="fas fa-info-circle mr-2"></i>
                        Hospodárske výsledky zatiaľ nie sú dostupné.
                    </div>
                )}
            </InfoCard>

            {latestWithAssets && (
                <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                    <AssetsPieChart data={latestWithAssets} />
                    <LiabilitiesPieChart data={latestWithAssets} />
                </div>
            )}

            <CompanyCapital orsrProfile={orsrProfile} structured={structured} profile={profile} />

            {showKonanie && (
                <InfoCard title="Konanie menom spoločnosti" icon="fa-signature">
                    <p className="text-gray-700 dark:text-gray-300 whitespace-pre-line leading-relaxed">{konanie}</p>
                </InfoCard>
            )}
        </div>
    );
};
