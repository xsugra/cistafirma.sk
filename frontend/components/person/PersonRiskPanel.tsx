import React from 'react';
import type { PersonRiskIndicators } from '../../types';
import { FlagChip, FlagCounts, FlagOutcome } from '../riskFlagState';
import { formatNumber } from '../../utils/format';

interface PersonRiskPanelProps {
    /** Absent on a response mapped before the field existed, and on any
     *  response whose rules all vanished. Both render nothing: this panel is
     *  the whole page's fourth section, and an empty frame with a heading over
     *  it would read as "no indicators" rather than "we could not say". */
    indicators?: PersonRiskIndicators;
}

/**
 * What this person's company footprint adds up to -- and the sentence that
 * keeps it from being a verdict.
 *
 * The distinction this panel is built around: "konateľ v 14 firmách, z toho 5
 * zrušených" is an observation with dates attached, and the register supports
 * it. "Biely kôň" is a claim about a human being, and the register does not
 * support it -- not because our code is incomplete, but because the data that
 * would settle it (who actually controls the company, whether the person was
 * paid to lend their name) is not in any public register at all. The product
 * may write the first and must never write the second, so the second appears
 * once, in this introduction, as the thing below it is not.
 *
 * The person is also the reason the counts are computed over the *cluster* and
 * not over one row: a person is more than one `Person` row (§11.18), and
 * counting rows would make every number here wrong for exactly the people this
 * panel is about.
 */
export const PersonRiskPanel: React.FC<PersonRiskPanelProps> = ({ indicators }) => {
    const payload = indicators;

    if (!payload?.flags?.length) {
        return null;
    }

    const { flags, counts, coverage } = payload;

    const coverageRows: { label: string; value: string; missing: boolean }[] = [
        {
            label: 'Firmy v našich dátach',
            value: formatNumber(coverage.companies),
            missing: coverage.companies === 0,
        },
        {
            label: 'Z toho zrušených',
            value: formatNumber(coverage.companies_dissolved),
            missing: false,
        },
        {
            label: 'Funkcia, o ktorej vieme, či trvá',
            value: formatNumber(coverage.companies_active_known),
            missing: coverage.companies_active_known === 0,
        },
    ];

    return (
        <section className="overflow-hidden rounded-xl border border-gray-200 bg-white shadow-lg dark:border-slate-700 dark:bg-slate-900 dark:shadow-none">
            <div className="border-b border-gray-200 bg-gray-50/50 px-6 py-4 dark:border-slate-700 dark:bg-slate-900/50">
                <h2 className="flex items-center gap-3 text-lg font-bold text-gray-900 dark:text-white">
                    <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-brand/10">
                        <i className="fas fa-flag text-brand"></i>
                    </span>
                    Rizikové indikátory
                </h2>
            </div>

            <div className="space-y-4 p-6">
                <p className="text-sm leading-relaxed text-gray-600 dark:text-gray-400">
                    Toto je <strong>pozorovanie o firmách</strong>, ktoré sú s touto osobou
                    zapísané — koľko ich je, v akých odvetviach a koľko z nich register
                    zrušil. <strong>Nie je to tvrdenie o tejto osobe</strong> a nie je to
                    zistenie protiprávneho konania. „Biely kôň" sa z verejných registrov
                    preukázať nedá: kto firmu naozaj riadi a či si niekto meno prepožičal,
                    v žiadnom z nich nie je. To isté číslo preto vidí človek, ktorý
                    podniká v štrnástich firmách, aj ten, koho do nich niekto postavil —
                    a rozlíšiť ich vie len vyšetrovateľ, nie register. Indikátory sa
                    zámerne <strong>nesčítavajú</strong> do jedného čísla.
                </p>

                <FlagCounts counts={counts} total={flags.length} />

                <ul className="divide-y divide-gray-100 rounded-lg border border-gray-200 dark:divide-slate-800 dark:border-slate-700">
                    {flags.map((flag) => (
                        <li key={flag.code} className="flex flex-wrap items-baseline gap-x-3 gap-y-1 px-4 py-3">
                            <span className="font-medium text-gray-900 dark:text-white">
                                {flag.label}
                            </span>
                            <FlagChip flag={flag} />
                            <span className="w-full text-sm text-gray-600 sm:w-auto sm:flex-1 dark:text-gray-300">
                                <FlagOutcome flag={flag} />
                            </span>
                        </li>
                    ))}
                </ul>

                <dl className="grid grid-cols-1 gap-x-6 gap-y-2 pt-1 sm:grid-cols-3">
                    {coverageRows.map((row) => (
                        <div key={row.label}>
                            <dt className="text-xs text-gray-500 dark:text-gray-400">
                                {row.label}
                            </dt>
                            <dd
                                className={
                                    row.missing
                                        ? 'text-gray-400 dark:text-gray-500'
                                        : 'font-medium text-gray-900 dark:text-white'
                                }
                            >
                                {row.value}
                            </dd>
                        </div>
                    ))}
                </dl>

                {/* Our own gap, stated here and never as an indicator. When the
                    ORSR history for a company was never read, the relation's
                    state is unknown -- that is a hole in our scraping, and
                    putting it among the flags would dress it up as a fact about
                    a person. It still belongs on the page: it is why the third
                    count above is smaller than the first. */}
                {coverage.companies_function_state_unknown > 0 && (
                    <p className="flex items-start gap-2 text-xs text-gray-500 dark:text-gray-400">
                        <i className="fas fa-circle-info mt-0.5 shrink-0" aria-hidden="true"></i>
                        <span>
                            Pri {formatNumber(coverage.companies_function_state_unknown)} z{' '}
                            {formatNumber(coverage.companies)} firiem sme históriu funkcií ešte
                            nečítali, preto o trvaní funkcie nevieme. Je to medzera v našich
                            dátach, nie zistenie o osobe.
                        </span>
                    </p>
                )}
            </div>
        </section>
    );
};
