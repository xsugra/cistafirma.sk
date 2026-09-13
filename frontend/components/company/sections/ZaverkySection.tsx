import React, {useState} from 'react';
import type {Company, DocumentListing, RuzDocument} from '../../../types';
import {api} from '../../../api';
import {InfoCard} from '../../InfoCard';
import {financialsStateNote} from './EmptyFinancialsNotice';

/**
 * Účtovné závierky: the statements RUZ holds, the part of them we read, and the
 * documents themselves.
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
 * **The years are buttons.** Clicking one asks the backend what can be
 * downloaded for that year and lists it; the files come from this site. This
 * replaces a paragraph that said the attachments "sa do tejto databázy
 * nesťahujú a nemáme ich tu odkiaľ stiahnuť" and sent the reader to the
 * register instead -- which was wrong twice over. The register does publish
 * them, through routes its own API documentation names, and the link that
 * paragraph produced (`home/uctovna-jednotka?id=`) is a route the register's
 * front end rejects: every reader who followed it got a WAF rejection page and
 * a support ID. Both halves of that are fixed; the link that remains is the
 * register's own record of the filing, kept because a reader checking our
 * figures against the source should be able to reach it.
 *
 * Two things it still deliberately does not do:
 *
 * - It does not claim the years we read correspond one-to-one to the IDs RUZ
 *   lists. There is no year on a RUZ statement ID and nothing joins the two
 *   lists, so a reader gets two counts and the plain statement that they are
 *   two counts -- measured on the live register, they agree exactly for 1 071
 *   companies and RUZ lists more for 1 024.
 * - It does not print "0 závierok" for a response that never carried the count,
 *   and it does not render an unreachable register as an empty year. Absent,
 *   zero and unknown are three different facts and the section says which it
 *   has.
 */
export const ZaverkySection: React.FC<{company: Company}> = ({company}) => {
    const years = company.financials.map((row) => row.year).sort((a, b) => b - a);
    const held = company.ruzStatements;
    const reports = company.ruzAnnualReports ?? 0;
    const ifrs = company.usesIfrs;

    const ruzHref = company.ruzPortalUrl;

    // One year open at a time. The list is fetched per click rather than all at
    // once: each year costs the backend several calls to the register, and a
    // company with 37 statements would spend them all to render a section most
    // readers scroll past.
    const [openYear, setOpenYear] = useState<number | null>(null);

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
                        {years.map((year) => {
                            const isOpen = openYear === year;
                            return (
                                <button
                                    key={year}
                                    type="button"
                                    onClick={() => setOpenYear(isOpen ? null : year)}
                                    aria-expanded={isOpen}
                                    className={`rounded-lg border px-2.5 py-1 font-mono text-sm tabular-nums transition-colors ${
                                        isOpen
                                            ? 'border-brand bg-brand/10 text-brand dark:border-brand dark:bg-brand/20 dark:text-brand'
                                            : 'border-slate-200 bg-slate-50 text-slate-700 hover:border-brand hover:text-brand dark:border-slate-700 dark:bg-slate-800 dark:text-slate-200 dark:hover:border-brand dark:hover:text-brand'
                                    }`}
                                >
                                    {year}
                                    <i
                                        className={`fas ${isOpen ? 'fa-chevron-up' : 'fa-download'} ml-1.5 text-xs`}
                                        aria-hidden="true"
                                    />
                                </button>
                            );
                        })}
                    </div>
                    <p className="mt-2 text-xs text-gray-500 dark:text-gray-400">
                        Kliknutím na ročník zobrazíš závierky, ktoré sa dajú stiahnuť.
                    </p>
                    {openYear !== null && (
                        <DocumentList key={openYear} ico={company.ico} year={openYear}/>
                    )}
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
                Prílohy závierok — správa audítora, výročná správa, samotné PDF — sa
                stahujú priamo odtiaľto, z registra účtovných závierok.
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
 * The documents of one year, fetched when its chip is opened.
 *
 * Every branch below exists because collapsing it would make the section claim
 * something it does not know:
 *
 * - A failed request is not an empty year. `unreachable` says the register
 *   could not be read; a 404 from the backend (a year we hold nothing for) is
 *   `no_statement`, which is a fact about *us*.
 * - A year that lists nothing is not the same as a year that could not be
 *   listed, and both differ from a year with no filing at all. Three sentences,
 *   three states, none of them "0".
 * - A size of `null` prints nothing rather than "0 B". The generated PDF carries
 *   no size in the register's metadata, and "0 B" would be a measurement of a
 *   document that has one.
 */
const DocumentList: React.FC<{ico: string; year: number}> = ({ico, year}) => {
    const [listing, setListing] = useState<DocumentListing | null>(null);
    const [failed, setFailed] = useState(false);

    React.useEffect(() => {
        let cancelled = false;
        setListing(null);
        setFailed(false);
        api.getFinancialDocuments(ico, year)
            .then((result) => {
                if (!cancelled) setListing(result);
            })
            .catch(() => {
                if (!cancelled) setFailed(true);
            });
        return () => {
            cancelled = true;
        };
    }, [ico, year]);

    if (failed) {
        return (
            <Notice tone="amber">
                Závierky pre rok {year} sa nepodarilo načítať. Register účtovných
                závierok je možno nedostupný — skús to prosím o chvíľu.
            </Notice>
        );
    }

    if (listing === null) {
        return (
            <p className="mt-3 text-sm text-gray-500 dark:text-gray-400">
                <i className="fas fa-spinner fa-spin mr-2"/>
                Načítavam závierky za rok {year}…
            </p>
        );
    }

    if (listing.state === 'unreachable') {
        return (
            <Notice tone="amber">
                Register účtovných závierok je momentálne nedostupný, takže nevieme,
                či sú pre rok {year} nejaké dokumenty. Nie je to tvrdenie o firme.
            </Notice>
        );
    }

    if (listing.state === 'no_statement') {
        return (
            <Notice tone="slate">
                Pre rok {year} nemáme v našich záznamoch uloženú závierku, takže
                nie je odkiaľ ju vziať. Ostatné ročníky vyššie môžu fungovať.
            </Notice>
        );
    }

    if (listing.documents.length === 0) {
        return (
            <Notice tone="slate">
                Register pre rok {year} neeviduje žiadny dokument, ktorý by sa dal
                stiahnuť. Stáva sa to pri ročníkoch, ktoré nemajú priložené PDF.
            </Notice>
        );
    }

    return (
        <ul className="mt-3 space-y-2">
            {listing.documents.map((document) => (
                <li key={document.id}>
                    <DocumentRow document={document}/>
                </li>
            ))}
        </ul>
    );
};

const DocumentRow: React.FC<{document: RuzDocument}> = ({document}) => {
    const isStatement = document.kind === 'vykaz';
    const meta = [
        formatSize(document.size),
        document.pages ? `${document.pages} str.` : null,
    ].filter(Boolean);

    return (
        <a
            href={document.url}
            // `download` so a click saves rather than navigating; the backend
            // also sends Content-Disposition, which is what actually names the
            // file -- a Slovak name cannot be trusted to survive the attribute.
            download
            className="flex items-start gap-3 rounded-lg border border-slate-200 bg-white px-3 py-2 transition-colors hover:border-brand hover:bg-brand/5 dark:border-slate-700 dark:bg-slate-800 dark:hover:border-brand dark:hover:bg-brand/10"
        >
            <i
                className={`fas ${
                    isStatement ? 'fa-file-invoice' : 'fa-file-pdf'
                } mt-0.5 text-brand`}
                aria-hidden="true"
            />
            <span className="min-w-0 flex-1">
                <span className="block truncate text-sm font-medium text-slate-800 dark:text-slate-100">
                    {document.name}
                </span>
                <span className="mt-0.5 block text-xs text-gray-500 dark:text-gray-400">
                    {isStatement ? 'Účtovný výkaz (PDF)' : 'Príloha'}
                    {meta.length > 0 && <> · {meta.join(' · ')}</>}
                </span>
            </span>
            <i className="fas fa-download mt-1 text-xs text-gray-400" aria-hidden="true"/>
        </a>
    );
};

const Notice: React.FC<{tone: 'amber' | 'slate'; children: React.ReactNode}> = ({
    tone,
    children,
}) => (
    <p
        className={`mt-3 rounded-lg px-4 py-3 text-sm ${
            tone === 'amber'
                ? 'bg-amber-50 text-amber-800 dark:bg-amber-900/20 dark:text-amber-300'
                : 'bg-slate-50 text-gray-600 dark:bg-slate-800/50 dark:text-gray-300'
        }`}
    >
        {children}
    </p>
);

/**
 * A document size, or nothing at all when the register did not give one.
 *
 * `null` is deliberately not `0`: the generated PDF of a výkaz carries no size
 * in the register's metadata, and printing "0 B" would report a measurement of a
 * document that plainly has one.
 */
function formatSize(bytes: number | null): string | null {
    if (bytes === null || bytes === undefined) return null;
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} kB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

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
