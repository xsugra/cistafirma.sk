import React, { lazy, Suspense, useState } from 'react';
import type { Company, OrsrStructured } from '../types';
import { InfoCard } from './InfoCard';
import { FinancialChart } from './FinancialChart';

import { getLegalFormProfile } from '../utils/legalFormProfile';
import { normalizePeople } from './company/helpers';
import { PeopleSection } from './company/PersonCard';
import { CompanyHeader } from './company/CompanyHeader';
import { CompanyDebts } from './company/CompanyDebts';
import { CompanyCapital } from './company/CompanyCapital';
import { CompanyBusiness } from './company/CompanyBusiness';
import { CompanySummaryStrip } from './company/CompanySummaryStrip';
import { FinancialIndicators } from './company/FinancialIndicators';
import { FinancialRatiosTable } from './company/FinancialRatiosTable';
import { BenchmarkComparison } from './company/BenchmarkComparison';
import { AssetsPieChart } from './company/AssetsPieChart';
import { LiabilitiesPieChart } from './company/LiabilitiesPieChart';

const ConnectionGraph = lazy(() => import('./graph/ConnectionGraph').then(m => ({ default: m.ConnectionGraph })));

const TABS = [
    { id: 'overview', label: 'Prehľad', icon: 'fa-chart-pie' },
    { id: 'financials', label: 'Finančná analýza', icon: 'fa-calculator' },
    { id: 'people', label: 'Osoby', icon: 'fa-users' },
    { id: 'registers', label: 'Registre', icon: 'fa-briefcase' },
    { id: 'connections', label: 'Prepojenia', icon: 'fa-project-diagram' },
] as const;

type TabId = typeof TABS[number]['id'];

interface CompanyDetailProps {
    company: Company;
}

export const CompanyDetail: React.FC<CompanyDetailProps> = ({ company }) => {
    const [activeTab, setActiveTab] = useState<TabId>('overview');

    const orsrProfile = company.orsr_profile;
    const structured: OrsrStructured = orsrProfile?.structured || {};
    const oddielType = (orsrProfile?.oddiel_type || '').toLowerCase();
    const profile = getLegalFormProfile(oddielType);

    const statutari = normalizePeople(structured.statutarny_organ?.length ? structured.statutarny_organ : orsrProfile?.statutarny_organ);
    const spolocnici = normalizePeople(structured.spolocnici?.length ? structured.spolocnici : orsrProfile?.spolocnici);
    const prokuristy = normalizePeople(structured.prokura?.length ? structured.prokura : orsrProfile?.prokura);
    const predstavenstvo = normalizePeople(structured.predstavenstvo?.length ? structured.predstavenstvo : orsrProfile?.predstavenstvo);
    const kontrolnaKomisia = normalizePeople(structured.kontrolna_komisia?.length ? structured.kontrolna_komisia : orsrProfile?.kontrolna_komisia);
    const dozornaRada = normalizePeople(structured.dozorna_rada || []);
    const akcionari = normalizePeople(structured.akcionari || []);

    const konanie = orsrProfile?.konanie_menom_spolocnosti || structured.konanie || orsrProfile?.konanie || '';
    const prokuraOpravnenie = (structured.prokura_oprávnenie as string[] | undefined) || [];

    const showStatutar = Boolean(profile.statutar) && (statutari.length > 0 || !profile.predstavenstvo);
    const showPredstavenstvo = Boolean(profile.predstavenstvo);
    const showDozornaRada = Boolean(profile.dozornaRada) && dozornaRada.length > 0;
    const showKontrolnaKomisia = Boolean(profile.kontrolnaKomisia);
    const showSpolocnici = Boolean(profile.spolocnici) && (spolocnici.length > 0 || !profile.akcionari);
    const showAkcionari = Boolean(profile.akcionari);
    const showProkura = Boolean(profile.prokura) && (prokuristy.length > 0 || prokuraOpravnenie.length > 0);
    const showKonanie = Boolean(profile.konanie) && Boolean(konanie);

    return (
        <div className="space-y-6 animate-fade-in mt-10">
            <CompanyHeader company={company} profile={profile} />

            <CompanySummaryStrip company={company} />

            {/* Tab Navigation */}
            <div className="tab-nav">
                {TABS.map(tab => (
                    <button
                        key={tab.id}
                        onClick={() => setActiveTab(tab.id)}
                        className={`tab-btn ${activeTab === tab.id ? 'active' : ''}`}
                    >
                        <i className={`fas ${tab.icon}`}></i>
                        {tab.label}
                    </button>
                ))}
            </div>

            {/* Tab Content */}
            {activeTab === 'overview' && (() => {
                const sorted = [...company.financials].sort((a, b) => a.year - b.year);
                const latestWithAssets = [...sorted].reverse().find(f => f.assetsTotal > 0);

                return (
                    <div className="space-y-6">
                        <CompanyDebts debts={company.debts} />

                        {company.financials.length > 0 ? (
                            <FinancialIndicators data={company.financials} analysis={company.analysis?.latest} />
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
            })()}

            {activeTab === 'financials' && (() => {
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
                                            {[
                                                { key: 'roa', label: 'ROA', unit: '%' },
                                                { key: 'roe', label: 'ROE', unit: '%' },
                                                { key: 'ros', label: 'ROS', unit: '%' },
                                                { key: 'currentRatio', label: 'L3 likvidita', unit: '×' },
                                                { key: 'quickRatio', label: 'L2 likvidita', unit: '×' },
                                                { key: 'selfFinancingRatio', label: 'Samofinancovanie', unit: '%' },
                                                { key: 'zScore', label: 'Z-score', unit: '' },
                                            ].map((metric) => (
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
                                                                {value != null
                                                                    ? metric.unit === '%'
                                                                        ? `${value.toFixed(1)}%`
                                                                        : metric.unit === '×'
                                                                          ? value.toFixed(2)
                                                                          : value.toFixed(2)
                                                                    : '—'}
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
            })()}

            {activeTab === 'people' && (
                <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                    {showPredstavenstvo && (
                        <PeopleSection
                            title={profile.predstavenstvo!.title}
                            icon={profile.predstavenstvo!.icon}
                            people={predstavenstvo.length ? predstavenstvo : statutari}
                            accent="blue"
                            personIcon="fa-user-tie"
                            subtitle={profile.predstavenstvo!.subtitle}
                            emptyLabel={profile.predstavenstvo!.emptyLabel || 'Žiadni členovia'}
                        />
                    )}

                    {showStatutar && (
                        <PeopleSection
                            title={profile.statutar!.title}
                            icon={profile.statutar!.icon}
                            people={statutari}
                            accent="blue"
                            personIcon="fa-badge-check"
                            subtitle={
                                profile.statutar!.subtitle ||
                                (structured.statutarny_organ_typ ? `Typ: ${structured.statutarny_organ_typ}` : undefined)
                            }
                            emptyLabel={profile.statutar!.emptyLabel || 'Žiadny štatutárny orgán'}
                        />
                    )}

                    {showSpolocnici && (
                        <PeopleSection
                            title={profile.spolocnici!.title}
                            icon={profile.spolocnici!.icon}
                            people={spolocnici}
                            accent="purple"
                            personIcon="fa-user-tie"
                            subtitle={profile.spolocnici!.subtitle}
                            emptyLabel={profile.spolocnici!.emptyLabel || 'Žiadni spoločníci'}
                        />
                    )}

                    {showAkcionari && (
                        <PeopleSection
                            title={profile.akcionari!.title}
                            icon={profile.akcionari!.icon}
                            people={akcionari}
                            accent="rose"
                            personIcon="fa-building"
                            subtitle={profile.akcionari!.subtitle}
                            emptyLabel={profile.akcionari!.emptyLabel || 'Jediný akcionár sa nezverejňuje'}
                        />
                    )}

                    {showDozornaRada && (
                        <PeopleSection
                            title={profile.dozornaRada!.title}
                            icon={profile.dozornaRada!.icon}
                            people={dozornaRada}
                            accent="sky"
                            personIcon="fa-user-shield"
                            subtitle={profile.dozornaRada!.subtitle}
                            emptyLabel={profile.dozornaRada!.emptyLabel || 'Žiadni členovia'}
                        />
                    )}

                    {showKontrolnaKomisia && (
                        <PeopleSection
                            title={profile.kontrolnaKomisia!.title}
                            icon={profile.kontrolnaKomisia!.icon}
                            people={kontrolnaKomisia}
                            accent="green"
                            personIcon="fa-user-shield"
                            subtitle={profile.kontrolnaKomisia!.subtitle}
                            emptyLabel={profile.kontrolnaKomisia!.emptyLabel || 'Žiadni členovia'}
                        />
                    )}

                    {showProkura && (
                        <PeopleSection
                            title={profile.prokura!.title}
                            icon={profile.prokura!.icon}
                            people={prokuristy}
                            accent="amber"
                            personIcon="fa-pen-fancy"
                            emptyLabel={profile.prokura!.emptyLabel || 'Žiadna prokúra'}
                            subtitle={prokuraOpravnenie.length > 0 ? prokuraOpravnenie.join(' ') : profile.prokura!.subtitle}
                        />
                    )}
                </div>
            )}

            {activeTab === 'registers' && (
                <div className="space-y-6">
                    <CompanyBusiness orsrProfile={orsrProfile} structured={structured} profile={profile} />
                </div>
            )}

            {activeTab === 'connections' && (
                <InfoCard title="Prepojenia osôb a firiem" icon="fa-project-diagram" noPadding>
                    <Suspense fallback={
                        <div className="flex items-center justify-center h-32 text-gray-500 dark:text-gray-400">
                            <div className="w-4 h-4 border-2 border-blue-500 border-t-transparent rounded-full animate-spin mr-2" />
                            Načítavam...
                        </div>
                    }>
                        <ConnectionGraph ico={company.ico} />
                    </Suspense>
                </InfoCard>
            )}
        </div>
    );
};
