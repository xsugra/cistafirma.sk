import React from 'react';
import type { Company, RiskScoreBreakdown, RiskScorePart } from '../../../types';
import { InfoCard } from '../../InfoCard';
import { RiskDonut } from '../../RiskDonut';

interface RiskScoreSectionProps {
    company: Company;
}

/**
 * One deduction, in points, as the reader would say it.
 *
 * The backend sends the delta as an exact number, because it is the same
 * number the score is built from and rounding it here would make the parts
 * disagree with the total. Only the printing is rounded, and only to one
 * decimal -- which is the most the debt slope (one point per 5 000 €) can
 * ever produce.
 */
function formatDelta(delta: number): string {
    const rounded = Math.round(delta * 10) / 10;
    return String(rounded).replace('.', ',');
}

/**
 * "bod" after 1, "body" after 2-4, "bodov" after 5 and up.
 *
 * A decimal takes the genitive singular in Slovak ("70,5 bodu"), so anything
 * that is not a whole number skips the ladder entirely. Getting this wrong is
 * the kind of thing a reader notices immediately in their own language and
 * that no test written in English would catch.
 */
function pointsLabel(points: number): string {
    if (!Number.isInteger(points)) return `${formatDelta(points)} bodu`;
    if (points === 1) return '1 bod';
    if (points >= 2 && points <= 4) return `${points} body`;
    return `${points} bodov`;
}

/**
 * The score's own line for one factor.
 *
 * The three states are deliberately three, not two. A factor that cost
 * nothing is not the same as a factor we could not read: the first says the
 * model looked and found nothing to charge for, the second says we have no
 * závierka for this company and the model never saw it. Rendering the second
 * as a zero would claim a look that did not happen.
 */
const PartRow: React.FC<{ part: RiskScorePart }> = ({ part }) => {
    const unread = part.delta === null;
    const free = part.delta === 0;

    return (
        <tr>
            <td className="px-3 py-2 text-gray-900 dark:text-white">{part.label}</td>
            <td className="px-3 py-2 text-gray-600 dark:text-gray-300">{part.detail}</td>
            <td className="px-3 py-2 text-right font-mono tabular-nums">
                {unread && (
                    <span
                        className="text-gray-400 dark:text-gray-500"
                        title="Tento faktor sa nedal vyhodnotiť — chýba závierka."
                    >
                        nevyhodnotené
                    </span>
                )}
                {free && <span className="text-gray-400 dark:text-gray-500">bez vplyvu</span>}
                {!unread && !free && (
                    <span className="font-medium text-red-600 dark:text-red-400">
                        {formatDelta(part.delta as number)}
                    </span>
                )}
            </td>
        </tr>
    );
};

/**
 * The risk score, and the reasons it is what it is.
 *
 * The number and its one-sentence summary already sit in the strip above every
 * section, so this page does not repeat them as a headline -- it answers the
 * question the strip cannot: *why this number*. A reader who is about to act
 * on "68/100" is entitled to see which facts produced it, and which of them we
 * simply do not have.
 *
 * Every figure here comes from the server (`breakdown` on the risk score).
 * Nothing is recomputed in the browser, which is the whole point of the module
 * the backend keeps this ladder in: this page used to be a third copy.
 */
export const RiskScoreSection: React.FC<RiskScoreSectionProps> = ({ company }) => {
    const { score, summary, breakdown } = company.riskScore;

    // `!breakdown` and not `breakdown === null`: the API sends null, but a
    // response mapped before this field existed has no key at all, and
    // `undefined.parts` would take the page down rather than show the notice.
    if (score === null || !breakdown) {
        return (
            <InfoCard title="Rizikové skóre" icon="fa-tachometer-alt">
                <p className="text-gray-700 dark:text-gray-300 leading-relaxed">
                    Skóre sa pre túto firmu nepodarilo načítať, preto tu nie je čo rozobrať.
                    Skús stránku obnoviť; ak to pretrváva, údaj o firme sa nedoplnil celý.
                </p>
            </InfoCard>
        );
    }

    const charged = breakdown.parts.filter((p) => p.delta !== null && p.delta !== 0);
    const unread = breakdown.parts.filter((p) => p.delta === null);
    const deduction = breakdown.parts.reduce((sum, p) => sum + (p.delta ?? 0), 0);

    return (
        <div className="space-y-6">
            <InfoCard title="Rizikové skóre" icon="fa-tachometer-alt">
                <div className="flex flex-col gap-6 sm:flex-row sm:items-center">
                    <div className="h-20 w-20 flex-shrink-0">
                        <RiskDonut score={score} size="sm" />
                    </div>
                    <div className="min-w-0">
                        <p className="text-3xl font-bold text-gray-900 dark:text-white">
                            {score}
                            <span className="text-base font-normal text-gray-400"> / 100</span>
                        </p>
                        <p className="mt-1 text-gray-700 dark:text-gray-300">{summary}</p>
                    </div>
                </div>

                <p className="mt-6 text-sm leading-relaxed text-gray-600 dark:text-gray-400">
                    Skóre je <strong>ukazovateľ pozornosti</strong>, nie pravdepodobnosť
                    bankrotu ani účtovná veličina. 100 znamená „nie je tu nič, čo by si
                    mal riešiť“, 5 znamená „pozri sa na to teraz“. Je to naše vlastné
                    skóre z verejných dát, nie cudzí model — Altmanov a Tafflerov model
                    sú počítané zvlášť a sú zverejnené v sekcii Finančné ukazovatele.
                </p>
            </InfoCard>

            <InfoCard title="Z čoho skóre vzniká" icon="fa-list-ol">
                <p className="mb-4 text-sm text-gray-600 dark:text-gray-400">
                    Skóre začína na {breakdown.start} a za každý zistený faktor sa odpočítava.
                </p>

                <div className="overflow-x-auto">
                    <table className="w-full text-sm">
                        <thead>
                            <tr className="border-b border-gray-200 dark:border-slate-700">
                                <th className="px-3 py-2 text-left text-xs font-medium uppercase text-gray-500 dark:text-gray-400">
                                    Faktor
                                </th>
                                <th className="px-3 py-2 text-left text-xs font-medium uppercase text-gray-500 dark:text-gray-400">
                                    Čo sme našli
                                </th>
                                <th className="px-3 py-2 text-right text-xs font-medium uppercase text-gray-500 dark:text-gray-400">
                                    Vplyv
                                </th>
                            </tr>
                        </thead>
                        <tbody className="divide-y divide-gray-50 dark:divide-slate-800/50">
                            {breakdown.parts.map((part) => (
                                <PartRow key={part.key} part={part} />
                            ))}
                        </tbody>
                    </table>
                </div>

                {breakdown.clamped ? (
                    /* The floor always binds at the bottom of the scale, and when
                       it does the arithmetic genuinely does not reach the score.
                       Saying so is the difference between an explained cap and a
                       table that does not add up. */
                    <p className="mt-4 rounded-lg bg-amber-50 px-4 py-3 text-sm text-amber-800 dark:bg-amber-900/20 dark:text-amber-300">
                        <i className="fas fa-circle-info mr-2" />
                        Súčet odpočtov je vyšší, než koľko bodov skóre má, preto sa zastavilo
                        na spodnej hranici {breakdown.floor}. Znamená to, že firma nazbierala
                        viac problémov, než vie táto stupnica rozlíšiť — poradie medzi
                        takýmito firmami už ďalej nehovorí nič.
                    </p>
                ) : (
                    <p className="mt-4 text-xs text-gray-400 dark:text-gray-500">
                        {charged.length === 0
                            ? 'Nebol zistený žiadny faktor, ktorý by skóre znížil.'
                            : `Spolu odpočítané: ${pointsLabel(-deduction)}.`}
                    </p>
                )}

                {unread.length > 0 && (
                    <p className="mt-3 text-xs text-gray-400 dark:text-gray-500">
                        {unread.length === breakdown.parts.length
                            ? 'Ani jeden faktor sa nedal vyhodnotiť — pre túto firmu nemáme uloženú závierku.'
                            : `${unread.length} z ${breakdown.parts.length} faktorov sa nedalo vyhodnotiť, preto je skóre miernejšie, než by bolo s úplnými dátami.`}
                    </p>
                )}
            </InfoCard>
        </div>
    );
};
