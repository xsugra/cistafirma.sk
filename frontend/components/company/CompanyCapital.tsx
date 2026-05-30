import React from 'react';
import type { OrsrProfile, OrsrStructured, OrsrContribution, OrsrPredmet } from '../../types';
import { InfoCard } from '../InfoCard';
import { normalizeAmountText } from './helpers';
import type { LegalFormProfile } from '../../utils/legalFormProfile';

interface CompanyCapitalProps {
    orsrProfile?: OrsrProfile;
    structured: OrsrStructured;
    profile: LegalFormProfile;
}

const formatAmount = (raw: string, currency?: string): { amount: string; currency: string } => {
    const cleaned = raw.replace(/\s+/g, ' ').trim();
    return { amount: cleaned, currency: currency || 'EUR' };
};

const ACCENT_STYLES: Record<string, string> = {
    blue: 'bg-blue-50 dark:bg-blue-900/20 border-blue-200 dark:border-blue-800/40',
    green: 'bg-green-50 dark:bg-green-900/20 border-green-200 dark:border-green-800/40',
};

const CapitalBlock: React.FC<{ label: string; amount: string; currency: string; accent?: string }> = ({
    label, amount, currency, accent = 'blue',
}) => (
    <div className={`rounded-xl border p-4 ${ACCENT_STYLES[accent] || ACCENT_STYLES.blue}`}>
        <p className="text-xs font-medium uppercase tracking-wider text-gray-500 dark:text-gray-400 mb-1">{label}</p>
        <div className="flex items-baseline gap-2">
            <span className="text-2xl font-bold text-gray-900 dark:text-white tabular-nums">{amount}</span>
            <span className="text-sm font-medium text-gray-500 dark:text-gray-400">{currency}</span>
        </div>
    </div>
);

const ContributionRow: React.FC<{ contribution: OrsrContribution; index: number }> = ({ contribution, index }) => {
    const name = contribution.name || `Vklad #${index + 1}`;
    const amount = contribution.vklad ? contribution.vklad.replace(/\s+/g, ' ').trim() : null;
    const paid = contribution.splatene ? contribution.splatene.replace(/\s+/g, ' ').trim() : null;
    const currency = contribution.currency || 'EUR';

    return (
        <div className="flex items-center justify-between py-3 border-b border-gray-100 dark:border-gray-700/50 last:border-0">
            <div className="flex items-center gap-3 min-w-0">
                <div className="flex-shrink-0 w-8 h-8 rounded-full bg-blue-100 dark:bg-blue-900/30 flex items-center justify-center">
                    <i className="fas fa-user text-blue-500 dark:text-blue-400 text-xs"></i>
                </div>
                <span className="text-sm font-medium text-gray-900 dark:text-white truncate">{name}</span>
            </div>
            {amount && (
                <div className="flex-shrink-0 text-right ml-4">
                    <span className="text-sm font-semibold text-gray-900 dark:text-white tabular-nums">{amount}</span>
                    <span className="text-xs text-gray-500 dark:text-gray-400 ml-1">{currency}</span>
                    {paid && (
                        <p className="text-xs text-green-600 dark:text-green-400">
                            <i className="fas fa-check text-[10px] mr-1"></i>splatené {paid} {currency}
                        </p>
                    )}
                </div>
            )}
        </div>
    );
};

interface ParsedShare {
    pocet: string;
    druh?: string;
    podoba?: string;
    forma?: string;
    menovitaHodnota?: string;
    obmedzenie?: string;
    od?: string;
}

const parseShareText = (entry: OrsrPredmet): ParsedShare => {
    const text = entry.text;
    const result: ParsedShare = { pocet: '', od: entry.od };

    const patterns: { key: keyof ParsedShare; regex: RegExp }[] = [
        { key: 'pocet', regex: /Počet:\s*(\d[\d\s]*\d|\d)(?=\s|$)/i },
        { key: 'druh', regex: /Druh:\s*(.+?)(?=\s+(?:Podoba|Forma|Menovitá|Obmedzenie)|$)/i },
        { key: 'podoba', regex: /Podoba:\s*(.+?)(?=\s+(?:Forma|Menovitá|Obmedzenie)|$)/i },
        { key: 'forma', regex: /Forma:\s*(.+?)(?=\s+(?:Menovitá|Obmedzenie)|$)/i },
        { key: 'menovitaHodnota', regex: /Menovitá hodnota:\s*(.+?)(?=\s+Obmedzenie|$)/i },
        { key: 'obmedzenie', regex: /Obmedzenie prevoditeľnosti[^:]*:\s*(.+)/i },
    ];

    for (const { key, regex } of patterns) {
        const match = text.match(regex);
        if (match) {
            result[key] = match[1].trim();
        }
    }

    return result;
};

const ShareCard: React.FC<{ share: ParsedShare; index: number; total: number }> = ({ share, index, total }) => {
    const pocet = parseInt(share.pocet.replace(/\s/g, ''), 10);
    const formattedPocet = isNaN(pocet) ? share.pocet : pocet.toLocaleString('sk-SK');

    return (
        <div className="rounded-lg border border-amber-200/60 dark:border-amber-800/30 bg-amber-50/50 dark:bg-amber-900/10 p-4">
            <div className="flex items-center justify-between mb-3">
                <div className="flex items-center gap-2">
                    <div className="w-7 h-7 rounded-md bg-amber-100 dark:bg-amber-900/30 flex items-center justify-center">
                        <i className="fas fa-certificate text-amber-600 dark:text-amber-400 text-xs"></i>
                    </div>
                    {total > 1 && (
                        <span className="text-xs font-medium text-amber-600/70 dark:text-amber-400/60">
                            Emisia {index + 1}
                        </span>
                    )}
                </div>
                {share.od && (
                    <span className="text-[11px] text-gray-400 dark:text-gray-500">od {share.od}</span>
                )}
            </div>

            <div className="grid grid-cols-2 gap-x-4 gap-y-2">
                <div>
                    <p className="text-[11px] uppercase tracking-wider text-gray-400 dark:text-gray-500">Počet</p>
                    <p className="text-lg font-bold text-gray-900 dark:text-white tabular-nums">{formattedPocet}</p>
                </div>
                {share.menovitaHodnota && (
                    <div>
                        <p className="text-[11px] uppercase tracking-wider text-gray-400 dark:text-gray-500">Menovitá hodnota</p>
                        <p className="text-lg font-bold text-gray-900 dark:text-white tabular-nums">{share.menovitaHodnota}</p>
                    </div>
                )}
                {share.druh && (
                    <div>
                        <p className="text-[11px] uppercase tracking-wider text-gray-400 dark:text-gray-500">Druh</p>
                        <p className="text-sm text-gray-700 dark:text-gray-300">{share.druh}</p>
                    </div>
                )}
                {share.forma && (
                    <div>
                        <p className="text-[11px] uppercase tracking-wider text-gray-400 dark:text-gray-500">Forma</p>
                        <p className="text-sm text-gray-700 dark:text-gray-300">{share.forma}</p>
                    </div>
                )}
                {share.podoba && (
                    <div className="col-span-2">
                        <p className="text-[11px] uppercase tracking-wider text-gray-400 dark:text-gray-500">Podoba</p>
                        <p className="text-sm text-gray-700 dark:text-gray-300">{share.podoba}</p>
                    </div>
                )}
            </div>

            {share.obmedzenie && (
                <div className="mt-3 pt-3 border-t border-amber-200/40 dark:border-amber-800/20">
                    <p className="text-xs text-gray-500 dark:text-gray-400 leading-relaxed">
                        <i className="fas fa-lock text-[10px] mr-1.5 text-amber-500/70"></i>
                        {share.obmedzenie}
                    </p>
                </div>
            )}
        </div>
    );
};

export const CompanyCapital: React.FC<CompanyCapitalProps> = ({ orsrProfile, structured, profile }) => {
    const capital = structured.vyska_zakladneho_imania;
    const fallbackCapital = orsrProfile?.vyska_zakladneho_imania;
    const vklady = structured.vklady_spolocnikov || [];

    const shouldShow = profile.imanie || profile.vkladySpolocnikov || profile.zapisovaneImanie || profile.clenskyVklad || profile.akcie;
    if (!shouldShow) return null;

    const hasCapital = capital?.imanie || fallbackCapital;
    const hasVklady = profile.vkladySpolocnikov && vklady.length > 0;
    const hasAkcie = profile.akcie && structured.akcie && structured.akcie.length > 0;

    if (!hasCapital && !hasVklady && !hasAkcie && !profile.zapisovaneImanie && !profile.clenskyVklad) return null;

    const parsedShares = hasAkcie ? structured.akcie!.map(a => parseShareText(a)) : [];

    return (
        <InfoCard title="Kapitál a Vklady" icon="fa-coins">
            <div className="space-y-5">
                {profile.imanie && hasCapital && (
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                        {capital?.imanie ? (
                            <>
                                <CapitalBlock
                                    label="Základné imanie"
                                    amount={formatAmount(capital.imanie).amount}
                                    currency={capital.currency || 'EUR'}
                                />
                                {capital.rozsah_splatenia && (
                                    <CapitalBlock
                                        label="Splatené"
                                        amount={formatAmount(capital.rozsah_splatenia).amount}
                                        currency={capital.currency || 'EUR'}
                                        accent="green"
                                    />
                                )}
                            </>
                        ) : fallbackCapital ? (
                            <CapitalBlock
                                label="Základné imanie"
                                amount={normalizeAmountText(fallbackCapital)}
                                currency="EUR"
                            />
                        ) : null}
                    </div>
                )}

                {profile.zapisovaneImanie && orsrProfile?.zapisovane_zakladne_imanie && (
                    <CapitalBlock
                        label="Zapisované základné imanie"
                        amount={normalizeAmountText(orsrProfile.zapisovane_zakladne_imanie)}
                        currency="EUR"
                    />
                )}

                {profile.clenskyVklad && orsrProfile?.zakladny_clensky_vklad && (
                    <CapitalBlock
                        label="Základný členský vklad"
                        amount={normalizeAmountText(orsrProfile.zakladny_clensky_vklad)}
                        currency="EUR"
                    />
                )}

                {hasVklady && (
                    <div>
                        <p className="text-xs font-medium uppercase tracking-wider text-gray-500 dark:text-gray-400 mb-2">
                            <i className="fas fa-layer-group mr-1.5"></i>Vklady spoločníkov
                        </p>
                        <div className="bg-gray-50 dark:bg-gray-800/50 rounded-lg px-4">
                            {vklady.slice(0, 10).map((v, idx) => (
                                <ContributionRow key={idx} contribution={v} index={idx} />
                            ))}
                        </div>
                        {vklady.length > 10 && (
                            <p className="text-xs text-gray-500 dark:text-gray-400 italic mt-2 text-center">
                                ... a {vklady.length - 10} ďalších vkladov
                            </p>
                        )}
                    </div>
                )}

                {hasAkcie && (
                    <div>
                        <p className="text-xs font-medium uppercase tracking-wider text-gray-500 dark:text-gray-400 mb-2">
                            <i className="fas fa-certificate mr-1.5"></i>Akcie
                            <span className="ml-2 text-gray-400 dark:text-gray-500 normal-case tracking-normal font-normal">
                                ({parsedShares.length} {parsedShares.length === 1 ? 'emisia' : parsedShares.length < 5 ? 'emisie' : 'emisií'})
                            </span>
                        </p>
                        <div className="space-y-3">
                            {parsedShares.slice(0, 10).map((share, idx) => (
                                <ShareCard key={idx} share={share} index={idx} total={parsedShares.length} />
                            ))}
                        </div>
                        {parsedShares.length > 10 && (
                            <p className="text-xs text-gray-500 dark:text-gray-400 italic mt-2 text-center">
                                ... a {parsedShares.length - 10} ďalších emisií
                            </p>
                        )}
                    </div>
                )}
            </div>
        </InfoCard>
    );
};
