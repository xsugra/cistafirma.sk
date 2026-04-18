import React, {useState} from 'react';
import type {Company} from '../types';
import {InfoCard} from './InfoCard';
import {StatusBadge} from './StatusBadge';
import {FinancialChart} from './FinancialChart';
import {RiskDonut} from './RiskDonut';
import {AiSummary} from './AiSummary';
import {api} from '../api';

interface CompanyDetailProps {
    company: Company;
}

const DetailItem: React.FC<{ label: string; value: React.ReactNode; icon: string }> = ({label, value, icon}) => (
    <div className="flex items-start space-x-3">
        <i className={`fas ${icon} text-blue-500 dark:text-blue-400 mt-1 w-4 text-center`}></i>
        <div>
            <p className="text-sm text-gray-500 dark:text-gray-400">{label}</p>
            <p className="font-semibold text-gray-900 dark:text-white">{value}</p>
        </div>
    </div>
);

const TITLE_PREFIXES = new Set(['ing.', 'mgr.', 'bc.', 'mudr.', 'judr.', 'phdr.', 'rndr.', 'mvdr.', 'doc.', 'prof.', 'arch.', 'paeddr.', 'thdr.', 'pharmdr.']);

const normalizeLine = (value: string) => value.replace(/\s+/g, ' ').trim();

const isMetaLine = (line: string) => /^(?:\(od:.*\)|vznik funkcie:|osoba je stotožnená|prokurista je|konateľ|spoločník|prokúra|predstavenstvo|kontrolná komisia|člen)$/i.test(line.trim());

const isAddressLine = (line: string) =>
    /\b\d{3}\s?\d{2}\b/.test(line) ||
    /^\d+\/\d+[a-zA-Z]?$/i.test(line) ||
    /^\d+[a-zA-Z]?$/i.test(line) ||
    /\b(?:ul\.|ulica|nám\.|mesto)\b/i.test(line);

const startsWithTitle = (tokens: string[]) => {
    const first = (tokens[0] || '').toLowerCase().replace(/\.$/, '.');
    return TITLE_PREFIXES.has(first);
};

const looksLikeNameToken = (text: string) => !!text && !/\d/.test(text) && /^[A-ZÁÄČĎÉÍĹĽŇÓÔÖŘŠŤÚÝŽ]/.test(text);

const stripTrailingRole = (line: string) => normalizeLine(line)
    .replace(/\s*\([^)]*\)\s*$/, '')
    .replace(/\s*-\s*(predseda\s+predstavenstva|člen\s+predstavenstva|predseda|člen|konateľ|prokurista|riaditeľ).*$/i, '')
    .trim();

const extractPeopleFromLines = (lines: string[] = []) => {
    const cleaned: string[] = [];
    const seen = new Set<string>();
    let current: string[] = [];
    let inAddressBlock = false;

    const flush = () => {
        if (current.length < 2) {
            current = [];
            return;
        }
        const limit = startsWithTitle(current) ? 3 : 2;
        if (current.length < limit) {
            current = [];
            return;
        }
        const name = current.slice(0, limit).join(' ');
        current = [];
        if (!seen.has(name)) {
            seen.add(name);
            cleaned.push(name);
        }
    };

    for (const raw of lines) {
        const line = normalizeLine(raw || '');
        if (!line) continue;
        if (isMetaLine(line)) { flush(); inAddressBlock = false; continue; }
        if (inAddressBlock) continue;
        if (isAddressLine(line)) { flush(); inAddressBlock = true; continue; }

        const cleanLine = stripTrailingRole(line);
        if (!cleanLine || isAddressLine(cleanLine) || !looksLikeNameToken(cleanLine)) continue;

        const tokens = cleanLine.split(' ');
        if (tokens.length >= 2) {
            if (startsWithTitle(tokens) && tokens.length === 2) {
                current = tokens;
                continue;
            }
            if (!seen.has(cleanLine)) {
                seen.add(cleanLine);
                cleaned.push(cleanLine);
            }
            current = [];
            inAddressBlock = true;
            continue;
        }

        current.push(cleanLine);
        const requiredTokens = startsWithTitle(current) ? 3 : 2;
        if (current.length === requiredTokens) {
            flush();
            inAddressBlock = true;
        }
    }

    flush();
    return cleaned;
};

const getRawSection = (rawSections: Record<string, string[]> | undefined, ...keys: string[]) => {
    for (const key of keys) {
        const value = rawSections?.[key];
        if (Array.isArray(value) && value.length > 0) return value;
    }
    return [] as string[];
};

const uniqueLines = (lines: string[]) => Array.from(new Set(lines.map(normalizeLine).filter(Boolean)));

const extractMoneySummary = (lines: string[]) => {
    const text = uniqueLines(lines).join(' ');
    if (!text) return '';

    const matches = text.match(/\d[\d\s]*(?:[.,]\d+)?\s*(?:EUR|Sk)/gi) || [];
    const deduped = uniqueLines(matches.map(m => m.replace(/\s+/g, ' ').trim()));
    if (deduped.length > 0) return deduped.join(' • ');

    return normalizeLine(text);
};

const formatShareholderContributions = (shareholders: string[], contributionLines: string[]) => {
    const names = uniqueLines(shareholders);
    const moneySummary = extractMoneySummary(contributionLines);

    if (names.length === 0 && !moneySummary) return [] as string[];
    if (names.length === 1 && moneySummary) return [`${names[0]} – vklad ${moneySummary}`];
    if (names.length > 1 && moneySummary) return names.map(name => `${name} – vklad ${moneySummary}`);
    if (names.length > 0) return names;
    return uniqueLines(contributionLines);
};

export const CompanyDetail: React.FC<CompanyDetailProps> = ({company}) => {
    const totalDebt = company.debts.reduce((sum, debt) => sum + debt.amountEur, 0);
    const [isWatching, setIsWatching] = useState(false);
    const [watchLoading, setWatchLoading] = useState(false);
    const [showAllPredmety, setShowAllPredmety] = useState(false);
    const orsrProfile = company.orsr_profile;
    const rawSections = orsrProfile?.raw_sections;

    // Rozdeliť executives po roli
    const statutari = company.executives.filter(e => e.role === 'Konateľ');
    const spolocnici = orsrProfile?.spolocnici?.length
        ? orsrProfile.spolocnici
        : extractPeopleFromLines(getRawSection(rawSections, 'Spoločníci'));
    const prokuristy = orsrProfile?.prokura?.length
        ? orsrProfile.prokura
        : extractPeopleFromLines(getRawSection(rawSections, 'Prokúra'));

    // Predmety podnikania - zobrazovať max 3, ostatné skryť
    const predmetyDisplay = orsrProfile?.predmet_podnikania?.length
        ? orsrProfile.predmet_podnikania
        : getRawSection(rawSections, 'Predmet podnikania (činnosti)');
    const predmetyVisible = predmetyDisplay.slice(0, 3);
    const predmetyHidden = predmetyDisplay.slice(3);
    const capitalText = extractMoneySummary(
        orsrProfile?.vyska_zakladneho_imania
            ? [orsrProfile.vyska_zakladneho_imania]
            : getRawSection(rawSections, 'Výška základného imania')
    );
    const vkladySpolocnikov = orsrProfile?.vklady_spolocnikov?.length
        ? orsrProfile.vklady_spolocnikov
        : getRawSection(rawSections, 'Výška vkladu každého spoločníka');
    const vkladySpolocnikovDisplay = formatShareholderContributions(spolocnici, vkladySpolocnikov);

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
                        <StatusBadge status={company.status}/>

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

                        <button
                            className="btn btn-outline border-gray-300 text-gray-700 dark:text-gray-300 dark:border-gray-600">
                            <i className="fas fa-file-pdf"></i> PDF
                        </button>
                    </div>
                </div>
                <div
                    className="mt-6 grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 border-t border-gray-200 dark:border-slate-800 pt-6">
                    <DetailItem label="IČO" value={company.ico} icon="fa-hashtag"/>
                    <DetailItem label="Adresa" value={`${company.address.street}, ${company.address.city}`}
                                icon="fa-map-marker-alt"/>
                    <DetailItem label="Dátum vzniku"
                                value={new Date(company.registrationDate).toLocaleDateString('sk-SK')}
                                icon="fa-calendar-alt"/>
                    <DetailItem label="Posledná aktualizácia"
                                value={new Date(company.lastUpdatedFromSource).toLocaleString('sk-SK')}
                                icon="fa-sync-alt"/>
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
                                    <div key={debt.id}
                                         className="flex justify-between items-center p-3 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-500/30 rounded-lg">
                                        <div>
                                            <p className="font-semibold text-red-700 dark:text-red-300">{debt.source}</p>
                                            <p className="text-sm text-gray-600 dark:text-gray-400">K
                                                dátumu: {new Date(debt.dateOfRecord).toLocaleDateString('sk-SK')}</p>
                                        </div>
                                        <p className="text-lg font-bold text-red-600 dark:text-red-300">{debt.amountEur.toLocaleString('sk-SK', {
                                            style: 'currency',
                                            currency: 'EUR'
                                        })}</p>
                                    </div>
                                ))}
                                <div
                                    className="flex justify-between items-center p-4 bg-red-100 dark:bg-red-900/50 rounded-lg mt-4">
                                    <p className="font-bold text-gray-900 dark:text-white text-lg">Celkový dlh</p>
                                    <p className="text-xl font-bold text-red-600 dark:text-white">{totalDebt.toLocaleString('sk-SK', {
                                        style: 'currency',
                                        currency: 'EUR'
                                    })}</p>
                                </div>
                            </div>
                        ) : (
                            <div
                                className="text-center py-4 text-green-600 dark:text-green-400 bg-green-50 dark:bg-green-900/20 border border-green-200 dark:border-green-500/30 rounded-lg">
                                <i className="fas fa-check-circle mr-2"></i> Neboli nájdené žiadne aktuálne dlhy.
                            </div>
                        )}
                    </InfoCard>

                    {/* AI Summary */}
                    <AiSummary companyData={company}/>

                    {/* Financials */}
                    <InfoCard title="Hospodárske výsledky" icon="fa-chart-line">
                        {company.financials.length > 0 ? (
                            <FinancialChart data={company.financials}/>
                        ) : (
                            <div className="text-center py-4 text-gray-500 dark:text-gray-400">
                                <i className="fas fa-info-circle mr-2"></i>
                                Hospodárske výsledky zatiaľ nie sú dostupné.
                            </div>
                        )}
                    </InfoCard>

                    {/* Štatutári */}
                    <InfoCard title="Štatutári" icon="fa-gavel">
                        {statutari.length > 0 ? (
                            <div className="space-y-2">
                                {statutari.map((exec, index) => (
                                    <div key={index} className="flex items-center space-x-3 p-3 bg-blue-50 dark:bg-blue-900/20 rounded-lg border border-blue-200 dark:border-blue-500/30">
                                        <i className="fas fa-badge-check text-blue-600 dark:text-blue-400"></i>
                                        <p className="font-medium text-gray-800 dark:text-gray-200">{exec.name}</p>
                                    </div>
                                ))}
                            </div>
                        ) : (
                            <div className="text-center py-4 text-gray-500 dark:text-gray-400">
                                <i className="fas fa-info-circle mr-2"></i> Žiadnych štatutárov
                            </div>
                        )}
                    </InfoCard>

                    {/* Spoločníci */}
                    <InfoCard title="Spoločníci" icon="fa-handshake">
                        {spolocnici.length > 0 ? (
                            <div className="space-y-2">
                                {spolocnici.map((exec, index) => (
                                    <div key={index} className="flex items-center space-x-3 p-3 bg-purple-50 dark:bg-purple-900/20 rounded-lg border border-purple-200 dark:border-purple-500/30">
                                        <i className="fas fa-user-tie text-purple-600 dark:text-purple-400"></i>
                                        <p className="font-medium text-gray-800 dark:text-gray-200">{exec}</p>
                                    </div>
                                ))}
                            </div>
                        ) : (
                            <div className="text-center py-4 text-gray-500 dark:text-gray-400">
                                <i className="fas fa-info-circle mr-2"></i> Žiadnych spoločníkov
                            </div>
                        )}
                    </InfoCard>

                    {/* Prokúra */}
                    <InfoCard title="Prokúra" icon="fa-file-signature">
                        {prokuristy.length > 0 ? (
                            <div className="space-y-2">
                                {prokuristy.map((exec, index) => (
                                    <div key={index} className="flex items-center space-x-3 p-3 bg-amber-50 dark:bg-amber-900/20 rounded-lg border border-amber-200 dark:border-amber-500/30">
                                        <i className="fas fa-pen-fancy text-amber-600 dark:text-amber-400"></i>
                                        <p className="font-medium text-gray-800 dark:text-gray-200">{exec}</p>
                                    </div>
                                ))}
                            </div>
                        ) : (
                            <div className="text-center py-4 text-gray-500 dark:text-gray-400">
                                <i className="fas fa-info-circle mr-2"></i> Žiadnej prokúry
                            </div>
                        )}
                    </InfoCard>

                    {/* Základné imanie a vklady */}
                    <InfoCard title="Kapitál a Vklady" icon="fa-coins">
                        <div className="space-y-4">
                            {capitalText && (
                                <DetailItem
                                    label="Základné imanie"
                                    value={capitalText}
                                    icon="fa-building"
                                />
                            )}
                            {vkladySpolocnikovDisplay.length > 0 && (
                                <div className="border-t border-gray-200 dark:border-gray-700 pt-4">
                                    <p className="text-sm text-gray-500 dark:text-gray-400 mb-2">Vklady spoločníkov:</p>
                                    <div className="space-y-1">
                                        {vkladySpolocnikovDisplay.slice(0, 3).map((vklad, idx) => (
                                            <p key={idx} className="text-sm text-gray-700 dark:text-gray-300">• {vklad}</p>
                                        ))}
                                        {vkladySpolocnikovDisplay.length > 3 && (
                                            <p className="text-xs text-gray-500 dark:text-gray-400 italic">... a {vkladySpolocnikovDisplay.length - 3} ďalších</p>
                                        )}
                                    </div>
                                </div>
                            )}
                        </div>
                    </InfoCard>

                    {/* Predmety podnikania */}
                    <InfoCard title="Predmety Podnikania" icon="fa-briefcase">
                        {predmetyDisplay.length > 0 ? (
                            <div className="space-y-2">
                                {predmetyVisible.map((predmet, index) => (
                                    <div key={index} className="flex items-start space-x-2 p-2">
                                        <i className="fas fa-check text-green-600 dark:text-green-400 mt-1 text-sm"></i>
                                        <p className="text-sm text-gray-700 dark:text-gray-300">{predmet}</p>
                                    </div>
                                ))}
                                {predmetyHidden.length > 0 && !showAllPredmety && (
                                    <button
                                        onClick={() => setShowAllPredmety(true)}
                                        className="w-full mt-3 py-2 text-sm text-blue-600 dark:text-blue-400 hover:bg-gray-100 dark:hover:bg-gray-800 rounded-lg font-medium transition"
                                    >
                                        <i className="fas fa-plus mr-1"></i> Zobraziť všetky ({predmetyHidden.length + predmetyVisible.length})
                                    </button>
                                )}
                                {showAllPredmety && (
                                    <>
                                        {predmetyHidden.map((predmet, index) => (
                                            <div key={index} className="flex items-start space-x-2 p-2">
                                                <i className="fas fa-check text-green-600 dark:text-green-400 mt-1 text-sm"></i>
                                                <p className="text-sm text-gray-700 dark:text-gray-300">{predmet}</p>
                                            </div>
                                        ))}
                                        <button
                                            onClick={() => setShowAllPredmety(false)}
                                            className="w-full mt-3 py-2 text-sm text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-800 rounded-lg font-medium transition"
                                        >
                                            <i className="fas fa-minus mr-1"></i> Skryť
                                        </button>
                                    </>
                                )}
                            </div>
                        ) : (
                            <div className="text-center py-4 text-gray-500 dark:text-gray-400">
                                <i className="fas fa-info-circle mr-2"></i> Žiadnych predmetov podnikania
                            </div>
                        )}
                    </InfoCard>
                </div>
                <div className="lg:col-span-1 space-y-8">
                    <InfoCard title="Risk Skóre" icon="fa-tachometer-alt">
                        <RiskDonut score={company.riskScore.score}/>
                        <p className="text-center text-gray-600 dark:text-gray-300 mt-4 leading-relaxed">{company.riskScore.summary}</p>
                    </InfoCard>
                    <InfoCard title="Status DPH" icon="fa-percent">
                        <div className="space-y-4">
                            <DetailItem label="Platiteľ DPH" value={company.vatStatus.isVatPayer ? 'Áno' : 'Nie'}
                                        icon="fa-check-circle"/>
                            {company.vatStatus.icDph &&
                                <DetailItem label="IČ DPH" value={company.vatStatus.icDph} icon="fa-hashtag"/>}
                            <DetailItem label="Index daňovej spoľahlivosti" value={<span
                                className={`font-bold ${company.vatStatus.taxReliabilityIndex === 'Nespoľahlivý' ? 'text-red-500 dark:text-red-400' : 'text-green-600 dark:text-green-400'}`}>{company.vatStatus.taxReliabilityIndex}</span>}
                                        icon="fa-thumbs-up"/>
                        </div>
                    </InfoCard>
                </div>
            </div>
        </div>
    );
};
