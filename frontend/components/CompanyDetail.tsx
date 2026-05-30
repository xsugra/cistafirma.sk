import React, {useState} from 'react';
import type {Company, OrsrPerson, OrsrContribution, OrsrCapital, OrsrStructured} from '../types';
import {InfoCard} from './InfoCard';
import {StatusBadge} from './StatusBadge';
import {FinancialChart} from './FinancialChart';
import {RiskDonut} from './RiskDonut';
import {AiSummary} from './AiSummary';
import {api} from '../api';
import {getLegalFormProfile} from '../utils/legalFormProfile';

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

const formatDate = (value?: string): string => {
    if (!value) return '';
    // ISO formát z backendu
    if (/^\d{4}-\d{2}-\d{2}$/.test(value)) {
        const [y, m, d] = value.split('-');
        return `${d}.${m}.${y}`;
    }
    return value;
};

const displayName = (person: OrsrPerson): string => {
    const parts = [person.title, person.name].filter(Boolean);
    return parts.join(' ').trim() || person.name || '';
};

const PersonCard: React.FC<{
    person: OrsrPerson;
    accent: 'blue' | 'purple' | 'amber' | 'green' | 'rose' | 'sky';
    icon: string;
}> = ({person, accent, icon}) => {
    const accentMap: Record<string, string> = {
        blue: 'bg-blue-50 dark:bg-blue-900/20 border-blue-200 dark:border-blue-500/30 text-blue-600 dark:text-blue-400',
        purple: 'bg-purple-50 dark:bg-purple-900/20 border-purple-200 dark:border-purple-500/30 text-purple-600 dark:text-purple-400',
        amber: 'bg-amber-50 dark:bg-amber-900/20 border-amber-200 dark:border-amber-500/30 text-amber-600 dark:text-amber-400',
        green: 'bg-green-50 dark:bg-green-900/20 border-green-200 dark:border-green-500/30 text-green-600 dark:text-green-400',
        rose: 'bg-rose-50 dark:bg-rose-900/20 border-rose-200 dark:border-rose-500/30 text-rose-600 dark:text-rose-400',
        sky: 'bg-sky-50 dark:bg-sky-900/20 border-sky-200 dark:border-sky-500/30 text-sky-600 dark:text-sky-400',
    };
    const name = displayName(person);

    return (
        <div className={`p-3 rounded-lg border ${accentMap[accent]}`}>
            <div className="flex items-start gap-3">
                <i className={`fas ${icon} mt-1`}></i>
                <div className="flex-1 min-w-0">
                    <p className="font-medium text-gray-900 dark:text-white break-words">{name}</p>
                    {person.role && (
                        <p className="text-xs uppercase tracking-wide text-gray-500 dark:text-gray-400 mt-0.5">
                            {person.role}
                        </p>
                    )}
                    {person.address && (
                        <p className="text-sm text-gray-600 dark:text-gray-300 mt-1">
                            <i className="fas fa-map-marker-alt mr-2 text-gray-400"></i>
                            {person.address}
                        </p>
                    )}
                    <div className="flex flex-wrap gap-3 mt-1 text-xs text-gray-500 dark:text-gray-400">
                        {person.vznik_funkcie && (
                            <span><i className="fas fa-calendar-plus mr-1"></i>Vznik funkcie: {person.vznik_funkcie}</span>
                        )}
                        {person.person_ico && (
                            <span><i className="fas fa-hashtag mr-1"></i>IČO: {person.person_ico}</span>
                        )}
                        {person.ine_id && (
                            <span><i className="fas fa-id-card mr-1"></i>{person.ine_id}</span>
                        )}
                    </div>
                </div>
            </div>
        </div>
    );
};

const PeopleSection: React.FC<{
    title: string;
    icon: string;
    people: OrsrPerson[];
    accent: 'blue' | 'purple' | 'amber' | 'green' | 'rose' | 'sky';
    personIcon: string;
    emptyLabel: string;
    subtitle?: string;
}> = ({title, icon, people, accent, personIcon, emptyLabel, subtitle}) => (
    <InfoCard title={title} icon={icon}>
        {subtitle && (
            <p className="text-sm text-gray-500 dark:text-gray-400 mb-3 italic">{subtitle}</p>
        )}
        {people.length > 0 ? (
            <div className="space-y-3">
                {people.map((person, idx) => (
                    <PersonCard key={`${person.name}-${idx}`} person={person} accent={accent} icon={personIcon}/>
                ))}
            </div>
        ) : (
            <div className="text-center py-4 text-gray-500 dark:text-gray-400">
                <i className="fas fa-info-circle mr-2"></i>{emptyLabel}
            </div>
        )}
    </InfoCard>
);

const normalizePeople = (value: unknown): OrsrPerson[] => {
    if (!Array.isArray(value)) return [];
    return value
        .map((item): OrsrPerson | null => {
            if (!item) return null;
            if (typeof item === 'string') {
                return item.trim() ? {name: item.trim()} : null;
            }
            if (typeof item === 'object') {
                const person = item as OrsrPerson;
                return person.name ? person : null;
            }
            return null;
        })
        .filter((p): p is OrsrPerson => p !== null);
};

/** Oreže ORSR číselnú hodnotu (napr. "27 882,891855") na max 2 desatinné miesta.
 * ORSR historicky nesie 6-miestne desatinné zvyšky z SKK→EUR konverzie (2009). */
const trimOrsrNumber = (raw: string): string => {
    return raw.replace(/(\d),(\d{2})(\d+)/g, (_m, intPart, twoDec, _rest) => `${intPart},${twoDec}`);
};

/** Znormalizuje celý riadok typu "27 882,891855 EUR Rozsah splatenia: 27 882,891855 EUR". */
const normalizeAmountText = (raw?: string | null): string => {
    if (!raw) return '';
    return trimOrsrNumber(raw).trim();
};

const formatCapital = (capital?: OrsrCapital | null, fallback?: string): string => {
    if (capital && capital.imanie) {
        const imanie = trimOrsrNumber(capital.imanie);
        const currency = capital.currency || 'EUR';
        const parts = [`${imanie} ${currency}`.trim()];
        if (capital.rozsah_splatenia) {
            const splatene = trimOrsrNumber(capital.rozsah_splatenia);
            parts.push(`splatené ${splatene} ${currency}`.trim());
        }
        return parts.join(' • ');
    }
    return normalizeAmountText(fallback);
};

const formatContribution = (contrib: OrsrContribution): string => {
    if (contrib.summary) return contrib.summary;
    const parts = [];
    if (contrib.name) parts.push(contrib.name);
    if (contrib.vklad) parts.push(`vklad ${contrib.vklad} ${contrib.currency || 'EUR'}`);
    if (contrib.splatene) parts.push(`splatené ${contrib.splatene} ${contrib.currency || 'EUR'}`);
    if (contrib.typ) parts.push(`(${contrib.typ})`);
    return parts.join(' • ');
};

export const CompanyDetail: React.FC<CompanyDetailProps> = ({company}) => {
    const totalDebt = company.debts.reduce((sum, debt) => sum + debt.amountEur, 0);
    const [isWatching, setIsWatching] = useState(false);
    const [watchLoading, setWatchLoading] = useState(false);
    const [showAllPredmety, setShowAllPredmety] = useState(false);

    const orsrProfile = company.orsr_profile;
    const structured: OrsrStructured = orsrProfile?.structured || {};
    const oddielType = (orsrProfile?.oddiel_type || '').toLowerCase();

    const statutari = normalizePeople(structured.statutarny_organ?.length ? structured.statutarny_organ : orsrProfile?.statutarny_organ);
    const spolocnici = normalizePeople(structured.spolocnici?.length ? structured.spolocnici : orsrProfile?.spolocnici);
    const prokuristy = normalizePeople(structured.prokura?.length ? structured.prokura : orsrProfile?.prokura);
    const predstavenstvo = normalizePeople(structured.predstavenstvo?.length ? structured.predstavenstvo : orsrProfile?.predstavenstvo);
    const kontrolnaKomisia = normalizePeople(structured.kontrolna_komisia?.length ? structured.kontrolna_komisia : orsrProfile?.kontrolna_komisia);
    const dozornaRada = normalizePeople(structured.dozorna_rada || []);
    const akcionari = normalizePeople(structured.akcionari || []);

    const predmety = structured.predmet_podnikania?.length
        ? structured.predmet_podnikania.map(p => p.text)
        : (orsrProfile?.predmet_podnikania || []);
    const predmetyVisible = predmety.slice(0, 3);
    const predmetyHidden = predmety.slice(3);

    const capitalText = formatCapital(structured.vyska_zakladneho_imania, orsrProfile?.vyska_zakladneho_imania);
    const vklady = structured.vklady_spolocnikov || [];
    const konanie = orsrProfile?.konanie_menom_spolocnosti || structured.konanie || orsrProfile?.konanie || '';
    const prokuraOpravnenie = (structured.prokura_oprávnenie as string[] | undefined) || [];

    // Profile driven podľa typu oddielu (Sro / Sa / Dr / Po / Sr / Pš / Pšn / Firm / default).
    const profile = getLegalFormProfile(oddielType);

    // Sekcia sa ukazuje ak:
    //  (a) profil ju má zadefinovanú, A ZÁROVEŇ
    //  (b) máme nejaké dáta alebo chceme zobraziť empty state (iba pri "hlavných" úlohách).
    const showStatutar = Boolean(profile.statutar) && (statutari.length > 0 || !profile.predstavenstvo);
    const showPredstavenstvo = Boolean(profile.predstavenstvo);
    const showDozornaRada = Boolean(profile.dozornaRada) && dozornaRada.length > 0;
    const showKontrolnaKomisia = Boolean(profile.kontrolnaKomisia);
    const showSpolocnici = Boolean(profile.spolocnici) && (spolocnici.length > 0 || !profile.akcionari);
    const showAkcionari = Boolean(profile.akcionari);
    const showProkura = Boolean(profile.prokura) && (prokuristy.length > 0 || prokuraOpravnenie.length > 0);
    const showKonanie = Boolean(profile.konanie) && Boolean(konanie);

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
                        <p className="text-gray-500 dark:text-gray-400">
                            {company.legalForm || profile.label}
                        </p>
                        {orsrProfile?.oddiel && orsrProfile?.vlozka_cislo && (
                            <p className="text-xs text-gray-400 dark:text-gray-500 mt-1">
                                Oddiel: {orsrProfile.oddiel} • Vložka číslo: {orsrProfile.vlozka_cislo} • {profile.label}
                            </p>
                        )}
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
                    <DetailItem label="Adresa"
                                value={orsrProfile?.sidlo || `${company.address.street}, ${company.address.city}`}
                                icon="fa-map-marker-alt"/>
                    <DetailItem label="Dátum vzniku"
                                value={formatDate(orsrProfile?.den_zapisu) || new Date(company.registrationDate).toLocaleDateString('sk-SK')}
                                icon="fa-calendar-alt"/>
                    <DetailItem label="Posledná aktualizácia"
                                value={formatDate(orsrProfile?.orsr_aktualizacia_dat) || new Date(company.lastUpdatedFromSource).toLocaleString('sk-SK')}
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

                    {/* Predstavenstvo (a.s., družstvo) – má prioritu pred statutármi */}
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

                    {/* Štatutárny orgán (s.r.o., v.o.s., k.s., zahraničné podniky) */}
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

                    {/* Konanie menom spoločnosti */}
                    {showKonanie && (
                        <InfoCard title="Konanie menom spoločnosti" icon="fa-signature">
                            <p className="text-gray-700 dark:text-gray-300 whitespace-pre-line leading-relaxed">{konanie}</p>
                        </InfoCard>
                    )}

                    {/* Dozorná rada (a.s.) */}
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

                    {/* Kontrolná komisia (družstvo) */}
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

                    {/* Spoločníci (s.r.o., v.o.s., k.s.) */}
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

                    {/* Akcionári (a.s.) */}
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

                    {/* Prokúra */}
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

                    {/* Základné imanie a vklady (len ak to má pre danú formu zmysel) */}
                    {(profile.imanie || profile.vkladySpolocnikov || profile.zapisovaneImanie || profile.clenskyVklad || profile.akcie) && (
                    <InfoCard title="Kapitál a Vklady" icon="fa-coins">
                        <div className="space-y-4">
                            {profile.imanie && capitalText && (
                                <DetailItem
                                    label="Základné imanie"
                                    value={capitalText}
                                    icon="fa-building"
                                />
                            )}
                            {profile.zapisovaneImanie && orsrProfile?.zapisovane_zakladne_imanie && (
                                <DetailItem
                                    label="Zapisované základné imanie"
                                    value={normalizeAmountText(orsrProfile.zapisovane_zakladne_imanie)}
                                    icon="fa-building-columns"
                                />
                            )}
                            {profile.clenskyVklad && orsrProfile?.zakladny_clensky_vklad && (
                                <DetailItem
                                    label="Základný členský vklad"
                                    value={<span className="whitespace-pre-line">{normalizeAmountText(orsrProfile.zakladny_clensky_vklad)}</span>}
                                    icon="fa-user-group"
                                />
                            )}
                            {profile.vkladySpolocnikov && vklady.length > 0 && (
                                <div className="border-t border-gray-200 dark:border-gray-700 pt-4">
                                    <p className="text-sm text-gray-500 dark:text-gray-400 mb-2">Vklady spoločníkov:</p>
                                    <div className="space-y-1">
                                        {vklady.slice(0, 5).map((v, idx) => (
                                            <p key={idx} className="text-sm text-gray-700 dark:text-gray-300">
                                                • {formatContribution(v)}
                                            </p>
                                        ))}
                                        {vklady.length > 5 && (
                                            <p className="text-xs text-gray-500 dark:text-gray-400 italic">
                                                ... a {vklady.length - 5} ďalších
                                            </p>
                                        )}
                                    </div>
                                </div>
                            )}
                            {profile.akcie && structured.akcie && structured.akcie.length > 0 && (
                                <div className="border-t border-gray-200 dark:border-gray-700 pt-4">
                                    <p className="text-sm text-gray-500 dark:text-gray-400 mb-2">Akcie:</p>
                                    <div className="space-y-1">
                                        {structured.akcie.slice(0, 5).map((a, idx) => (
                                            <p key={idx} className="text-sm text-gray-700 dark:text-gray-300">
                                                • {a.text}
                                            </p>
                                        ))}
                                    </div>
                                </div>
                            )}
                        </div>
                    </InfoCard>
                    )}

                    {/* Predmety podnikania */}
                    <InfoCard title="Predmety Podnikania" icon="fa-briefcase">
                        {predmety.length > 0 ? (
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
                                <i className="fas fa-info-circle mr-2"></i> Žiadne predmety podnikania
                            </div>
                        )}
                    </InfoCard>

                    {/* Ďalšie právne skutočnosti (podľa profilu: Sro/Sa/Dr/Po/Pš/Pšn) */}
                    {profile.dalsiePravneSkutocnosti && orsrProfile?.dalske_pravne_skutocnosti && (
                        <InfoCard title="Ďalšie právne skutočnosti" icon="fa-scroll">
                            <p className="text-sm text-gray-700 dark:text-gray-300 whitespace-pre-line leading-relaxed">
                                {orsrProfile.dalske_pravne_skutocnosti}
                            </p>
                        </InfoCard>
                    )}
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
