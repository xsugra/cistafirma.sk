import React from 'react';
import type { Company } from '../../../types';
import { InfoCard } from '../../InfoCard';
import { FlagChip, FlagCounts, FlagOutcome } from '../../riskFlagState';

interface RedFlagsSectionProps {
    company: Company;
}

/**
 * The risk indicators: patterns the register and the statements actually
 * contain, with the counts of what was and was not examined.
 *
 * This section is named after the two phenomena a reader will have come
 * looking for -- the straw man and the carousel -- and it is the one place
 * those words are written. They are written here, once, in the introduction,
 * as the shape this section does *not* claim to have detected. Everything
 * below them is a fact about a company: a revenue figure with no employees
 * behind it, a VAT registration that was cancelled. None of it is proof of
 * anything, and none of it is a statement about a person.
 *
 * That is not caution for its own sake. Public registers do not hold invoices,
 * the VAT control statement, or the movement of goods, so the chain a carousel
 * is made of is not in the data at all -- what is in the data is the profile of
 * one company that might sit somewhere in such a chain. The server writes the
 * sentences; `riskFlagState` decides only how their state is coloured.
 */
export const RedFlagsSection: React.FC<RedFlagsSectionProps> = ({ company }) => {
    const payload = company.redFlags;

    // `!payload?.flags?.length` and not `=== undefined`: a response mapped
    // before this field existed has no key at all, and a payload whose rules
    // all vanished would draw a confident empty table. Both mean the same thing
    // to the reader -- we cannot show this -- so both get the notice.
    if (!payload?.flags?.length) {
        return (
            <InfoCard title="Rizikové indikátory" icon="fa-flag">
                <p className="leading-relaxed text-gray-700 dark:text-gray-300">
                    Indikátory sa pre túto firmu nepodarilo načítať, preto tu nie je čo
                    vypísať. Skús stránku obnoviť; ak to pretrváva, údaj o firme sa
                    nedoplnil celý.
                </p>
            </InfoCard>
        );
    }

    const { flags, counts, coverage } = payload;

    const coverageRows: { label: string; value: string; missing: boolean }[] = [
        {
            label: 'Prečítané závierky',
            value: coverage.has_financials ? String(coverage.financial_years) : 'žiadne',
            missing: !coverage.has_financials,
        },
        {
            label: 'Prepojené osoby',
            value: coverage.persons_linked > 0 ? String(coverage.persons_linked) : 'žiadne',
            missing: coverage.persons_linked === 0,
        },
        {
            label: 'Veľkostná kategória',
            value: coverage.size_band_known ? 'uvedená v registri' : 'register ju neuvádza',
            missing: !coverage.size_band_known,
        },
        {
            label: 'Registrácia a výmaz z DPH',
            value: coverage.vat_register_dated ? 'dátum evidujeme' : 'dátum neevidujeme',
            missing: !coverage.vat_register_dated,
        },
    ];

    return (
        <div className="space-y-6">
            <InfoCard title="Rizikové indikátory" icon="fa-flag">
                <p className="text-sm leading-relaxed text-gray-600 dark:text-gray-400">
                    Toto sú vzory, ktoré sa v účtovných závierkach a v obchodnom registri
                    opakujú — <strong>nie zistenie protiprávneho konania</strong>. Ani
                    „karusel", ani „biely kôň" sa z verejných registrov preukázať nedajú:
                    fakturačný reťazec, kontrolný výkaz DPH ani pohyb tovaru v žiadnom
                    z nich nie sú. Sekcia preto vypisuje, čo sa v dátach našlo, a necháva
                    na čitateľovi, čo si o tom myslí. Indikátory sa zámerne{' '}
                    <strong>nesčítavajú</strong> do jedného čísla — jediné číslo by bolo
                    to, čo si z tejto stránky odnesieš.
                </p>

                <div className="mt-5">
                    <FlagCounts counts={counts} total={flags.length} />
                </div>

                <div className="mt-6 overflow-x-auto">
                    <table className="w-full text-sm">
                        <thead>
                            <tr className="border-b border-gray-200 dark:border-slate-700">
                                <th className="px-3 py-2 text-left text-xs font-medium uppercase text-gray-500 dark:text-gray-400">
                                    Indikátor
                                </th>
                                <th className="px-3 py-2 text-left text-xs font-medium uppercase text-gray-500 dark:text-gray-400">
                                    Stav
                                </th>
                                <th className="px-3 py-2 text-left text-xs font-medium uppercase text-gray-500 dark:text-gray-400">
                                    Čo sme vyhodnotili
                                </th>
                            </tr>
                        </thead>
                        <tbody className="divide-y divide-gray-50 dark:divide-slate-800/50">
                            {flags.map((flag) => (
                                <tr key={flag.code}>
                                    <td className="px-3 py-2 align-top text-gray-900 dark:text-white">
                                        {flag.label}
                                    </td>
                                    <td className="whitespace-nowrap px-3 py-2 align-top">
                                        <FlagChip flag={flag} />
                                    </td>
                                    <td className="px-3 py-2 align-top text-gray-600 dark:text-gray-300">
                                        <FlagOutcome flag={flag} />
                                    </td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>
            </InfoCard>

            <InfoCard title="Z čoho indikátory vznikajú" icon="fa-database">
                <dl className="grid grid-cols-1 gap-x-6 gap-y-3 sm:grid-cols-2">
                    {coverageRows.map((row) => (
                        <div key={row.label} className="flex items-baseline justify-between gap-4">
                            <dt className="text-gray-600 dark:text-gray-300">{row.label}</dt>
                            <dd
                                className={
                                    row.missing
                                        ? 'text-right text-gray-400 dark:text-gray-500'
                                        : 'text-right font-medium text-gray-900 dark:text-white'
                                }
                            >
                                {row.value}
                            </dd>
                        </div>
                    ))}
                </dl>

                <p className="mt-5 text-xs leading-relaxed text-gray-500 dark:text-gray-400">
                    Niektoré pravidlá čítajú účtovné závierky a niektoré register, a to,
                    čo v ňom nie je, sa vyhodnotiť nedá. V tabuľke to tak aj stojí —
                    prázdne miesto by sa dalo prečítať ako čistý nález, a to by bola
                    lepšia známka, než akú sme si zaslúžili.
                </p>
            </InfoCard>
        </div>
    );
};
