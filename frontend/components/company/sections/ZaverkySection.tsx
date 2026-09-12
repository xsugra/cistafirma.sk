import React from 'react';
import type {Company} from '../../../types';
import {InfoCard} from '../../InfoCard';
import {financialsStateNote} from './EmptyFinancialsNotice';

/**
 * Účtovné závierky: the statements RUZ holds, and the part of them we read.
 *
 * The section exists because two numbers that belong together were being shown
 * apart. Every other financial section on this page reports what is *in this
 * database*, which answers "what do we know" and not "what is there". For a
 * company whose závierky RUZ holds but the financials sync has not reached, the
 * two questions have different answers, and only the second one tells a reader
 * whether coming back later would help. Volkswagen Slovakia is that case in the
 * live data: 37 statements RUZ lists, 0 read here.
 *
 * So the counts are printed together, in the order of the question:
 *
 *   RUZ eviduje 14 závierok  ->  prečítali sme 13 z nich (2013 – 2025)
 *
 * Three things this deliberately does not do:
 *
 * - It does not claim the years we read correspond one-to-one to the IDs RUZ
 *   lists. There is no year on a RUZ statement ID and nothing joins the two
 *   lists, so a reader gets two counts and the plain statement that they are
 *   two counts -- measured on the live register, they agree exactly for 1 071
 *   companies and RUZ lists more for 1 024.
 * - It does not offer a download. No endpoint here fetches a statement's
 *   attachment, so the link goes to the RUZ page where they actually live.
 * - It does not print "0 závierok" for a response that never carried the count.
 *   Absent and zero are different facts and the section says which it has.
 */
export const ZaverkySection: React.FC<{company: Company}> = ({company}) => {
    const years = company.financials.map((row) => row.year).sort((a, b) => b - a);
    const held = company.ruzStatements;
    const reports = company.ruzAnnualReports ?? 0;
    const ifrs = company.usesIfrs;

    const ruzHref = company.ruzPortalUrl;

    return (
        <InfoCard title="Účtovné závierky" icon="fa-file-invoice">
            {held === null ? (
                // Not the same as zero: the response did not say, and a section
                // that turned that into "RUZ nemá pre túto firmu závierku"
                // would be inventing a fact about the register.
                <p className="text-gray-600 dark:text-gray-400 leading-relaxed">
                    Koľko závierok má táto firma v RUZ, sa z tejto odpovede nedozvedáme.
                    Ročníky, ktoré sme prečítali, sú v ostatných sekciách.
                </p>
            ) : (
                <p className="text-gray-700 dark:text-gray-300 leading-relaxed">
                    {held === 0 ? (
                        <>RUZ pre túto firmu neeviduje žiadnu účtovnú závierku.</>
                    ) : (
                        <>
                            RUZ eviduje <strong>{held}</strong>{' '}
                            {plural(held, 'účtovnú závierku', 'účtovné závierky', 'účtovných závierok')}
                            {reports > 0 && (
                                <>
                                    {' '}a <strong>{reports}</strong>{' '}
                                    {plural(reports, 'výročnú správu', 'výročné správy', 'výročných správ')}
                                </>
                            )}
                            .
                        </>
                    )}
                </p>
            )}

            {years.length > 0 ? (
                <>
                    <p className="mt-3 text-gray-700 dark:text-gray-300 leading-relaxed">
                        My sme z nich prečítali <strong>{years.length}</strong>{' '}
                        {plural(years.length, 'ročník', 'ročníky', 'ročníkov')},{' '}
                        {years[years.length - 1]} – {years[0]}. Čísla z nich sú v sekciách
                        Súvaha, Výkaz ziskov a strát a Finančné ukazovatele.
                    </p>
                    <div className="mt-3 flex flex-wrap gap-2">
                        {years.map((year) => (
                            <span
                                key={year}
                                className="rounded-lg border border-slate-200 bg-slate-50 px-2.5 py-1 font-mono text-sm tabular-nums text-slate-700 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-200"
                            >
                                {year}
                            </span>
                        ))}
                    </div>
                </>
            ) : (
                // No year read. `financialsStateNote` already owns the
                // vocabulary for *why* -- not fetched, blocked, nothing in RUZ,
                // IFRS-only -- and this section must not invent a second set of
                // words for the same four facts.
                <p className="mt-3 rounded-lg bg-slate-50 px-4 py-3 text-sm text-gray-600 dark:bg-slate-800/50 dark:text-gray-300">
                    <i className="fas fa-info-circle mr-2"/>
                    {financialsStateNote(company)}
                </p>
            )}

            {held !== null && held > 0 && years.length < held && (
                <p className="mt-3 rounded-lg bg-amber-50 px-4 py-3 text-sm text-amber-800 dark:bg-amber-900/20 dark:text-amber-300">
                    <i className="fas fa-circle-info mr-2"/>
                    RUZ eviduje viac závierok, než sme prečítali. Nie je to chyba
                    konkrétnej firmy — ide o poradie, v akom prechádzame registrom.
                </p>
            )}

            {ifrs && (
                <p className="mt-3 text-sm text-gray-600 dark:text-gray-400 leading-relaxed">
                    Firma účtuje podľa IFRS, a také výkazy RUZ vydáva len ako PDF. Po
                    riadkoch sa z nich načítať nedajú, preto ich tu neuvidíš.
                </p>
            )}

            <p className="mt-4 text-sm text-gray-600 dark:text-gray-400 leading-relaxed">
                Prílohy závierok — správa audítora, výročná správa, samotné PDF — sa do
                tejto databázy nesťahujú a nemáme ich tu odkiaľ stiahnuť.
                {ruzHref && (
                    <>
                        {' '}
                        <a
                            href={ruzHref}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="font-medium text-brand hover:underline"
                        >
                            Otvoriť na RUZ portáli
                            <i className="fas fa-external-link-alt ml-1.5 text-xs"/>
                        </a>
                    </>
                )}
            </p>
        </InfoCard>
    );
};

/**
 * Slovak counted-noun agreement: 1 závierka, 2-4 závierky, 5+ závierok.
 *
 * A plain `n === 1 ? a : b` would print "5 závierky" on the company pages
 * people actually look at, so the three forms travel together at each call
 * site rather than as a lookup table somewhere else.
 */
export function plural(count: number, one: string, few: string, many: string): string {
    if (count === 1) return one;
    if (count >= 2 && count <= 4) return few;
    return many;
}
