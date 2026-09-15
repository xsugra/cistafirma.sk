import React from 'react';
import type { Debt } from '../../types';
import { InfoCard } from '../InfoCard';
import { formatDate } from './helpers';

/**
 * The two sources a "no debts" answer has to have read to mean anything.
 *
 * `Sociálna poisťovňa` and `VšZP` are one source here because the register
 * carries one check date for the pair (`Dátum a čas kontroly VSZP/SP`), and the
 * two columns are written by the same pass.
 */
const INSURANCE = 'Sociálna poisťovňa a VšZP';
const TAX = 'Finančná správa';

interface CompanyDebtsProps {
    debts: Debt[];
    /** When we last read the insurance register for this company, or null. */
    insuranceCheckedOn: string | null;
    /** When we last read Finančná správa for this company, or null. */
    taxCheckedOn: string | null;
    /**
     * Sociálna poisťovňa lists the company without publishing a sum for it.
     * See the `Company` type for the register's two populations.
     */
    socialListedWithoutAmount: boolean | null;
}

/**
 * The sources nobody has read for this company, named.
 *
 * Hoisted out of `EmptyState` because two branches now ask the same question --
 * the unread panel below, and the sentence under a SP listing that has to say
 * whether the *money* question was answered at all. Two copies of this is how
 * the two would come to disagree about which source is missing.
 */
function unreadSources(
    insuranceCheckedOn: string | null,
    taxCheckedOn: string | null
): string[] {
    const unread: string[] = [];
    if (!insuranceCheckedOn) unread.push(INSURANCE);
    if (!taxCheckedOn) unread.push(TAX);
    return unread;
}

/**
 * What we owe the reader when we have found no debts.
 *
 * The empty state used to be unconditional: no debt rows, green tick, "Neboli
 * nájdené žiadne aktuálne dlhy." But a debt row is only built for an amount
 * above zero, so an empty list meant two opposite things — *we looked and there
 * is nothing* and *we have never looked* — and both were printed as the first.
 *
 * Measured 2026-09-12 over all 445 626 rows: the insurance pass has reached
 * 35 471 of them (8,0 %) and Finančná správa 250 349 (56,2 %), and of the
 * 411 186 companies shown that tick, 402 781 (98,0 %) rest on at least one
 * source nobody has read. Only 8 405 earned it. A green all-clear we have not
 * verified is the one direction a risk tool must never round in, so the state is
 * now derived from the two dates rather than assumed.
 */
function EmptyState({
    insuranceCheckedOn,
    taxCheckedOn,
    socialListedWithoutAmount,
}: Pick<
    CompanyDebtsProps,
    'insuranceCheckedOn' | 'taxCheckedOn' | 'socialListedWithoutAmount'
>) {
    // The listing is a *finding*, so it is answered before either of the two
    // branches below. It can never be the green tick -- the register does have
    // something recorded against this company -- and it is not a gap either, so
    // neither of the other two sentences may be printed over it.
    //
    // It is reached whenever the register said so, which implies the insurance
    // side *was* read: the flag is only ever written from a result that settled
    // the question. So this branch does not need `insuranceCheckedOn` to be set
    // to be true; it needs it to be absent to be a contradiction, and the
    // listing is still the honest thing to show in that case.
    if (socialListedWithoutAmount) {
        const unread = unreadSources(insuranceCheckedOn, taxCheckedOn);
        return (
            <div className="py-4 px-4 text-amber-800 dark:text-amber-300 bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-700/50 rounded-lg">
                <p>
                    <i className="fas fa-circle-exclamation mr-2"></i>
                    <strong>
                        Sociálna poisťovňa uvádza túto spoločnosť vo svojom zozname dlžníkov bez
                        zverejnenej sumy.
                    </strong>
                </p>
                <p className="mt-2 text-sm">
                    Nejde o peňažný nedoplatok — register k tejto firme nezverejnil žiadnu sumu.
                    Dôvodom je nesplnená vykazovacia povinnosť: nepredložený výkaz poistného a
                    príspevkov alebo neoznámené príjmy a výdavky.
                </p>
                <p className="mt-2 text-sm">
                    {unread.length === 0 ? (
                        <>
                            Peňažné nedoplatky voči VšZP, Sociálnej poisťovni ani Finančnej
                            správe sme nezistili.
                        </>
                    ) : (
                        <>
                            Či dlží aj <strong>peňažné</strong> nedoplatky, zatiaľ nevieme —{' '}
                            {unread.length === 2
                                ? `ani u ${INSURANCE}, ani na ${TAX} sme túto firmu ešte nekontrolovali`
                                : `u ${unread[0]} sme pre túto firmu ešte nekontrolovali`}
                            .
                        </>
                    )}
                </p>
            </div>
        );
    }

    // Tested directly rather than through a list length, so TypeScript narrows
    // both to non-null in the branch that needs them.
    if (insuranceCheckedOn && taxCheckedOn) {
        // The 8 405. Both sources were read, so this is a finding and not an
        // absence, and it may say so plainly -- with the two dates, so a reader
        // can see how current the answer is.
        return (
            <div className="text-center py-4 text-green-600 dark:text-green-400 bg-green-50 dark:bg-green-900/20 border border-green-200 dark:border-green-500/30 rounded-lg">
                <i className="fas fa-check-circle mr-2"></i> Neboli nájdené žiadne aktuálne dlhy.
                <p className="mt-2 text-xs text-green-700/80 dark:text-green-400/80">
                    Overené u {INSURANCE} k {formatDate(insuranceCheckedOn)} a na {TAX} k{' '}
                    {formatDate(taxCheckedOn)}.
                </p>
            </div>
        );
    }

    const unread: string[] = [];
    if (!insuranceCheckedOn) unread.push(INSURANCE);
    if (!taxCheckedOn) unread.push(TAX);

    const read = [insuranceCheckedOn ? INSURANCE : null, taxCheckedOn ? TAX : null]
        .filter(Boolean)
        .join(' a ');

    return (
        <div className="py-4 px-4 text-amber-800 dark:text-amber-300 bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-700/50 rounded-lg">
            <p>
                <i className="fas fa-circle-question mr-2"></i>
                {unread.length === 2 ? (
                    <>
                        Dlhy tejto firmy sme <strong>ešte nekontrolovali</strong> — ani u{' '}
                        {INSURANCE}, ani na {TAX}.
                    </>
                ) : (
                    <>
                        Dlhy sme preverili len čiastočne. U <strong>{unread[0]}</strong> sme pre
                        túto firmu <strong>ešte nekontrolovali</strong>
                        {read && <>, preverené teda máme len {read}</>}.
                    </>
                )}
            </p>
            <p className="mt-2 text-sm">
                To, že nič neevidujeme, tu neznamená, že firma nič nedlží — znamená to, že sme sa
                ešte nepozreli. Kontrola prebieha priebežne a doplní sa.
            </p>
        </div>
    );
}

/**
 * Debts, and — when there are none — whether that is an answer or a gap.
 *
 * `debts` alone cannot tell the two apart, which is why the two check dates
 * travel with it. See `EmptyState` for what that cost before they did.
 */
export const CompanyDebts: React.FC<CompanyDebtsProps> = ({
    debts,
    insuranceCheckedOn,
    taxCheckedOn,
    socialListedWithoutAmount,
}) => {
    const totalDebt = debts.reduce((sum, debt) => sum + debt.amountEur, 0);

    return (
        <InfoCard title="Dlhy a Nedoplatky" icon="fa-exclamation-triangle">
            {debts.length > 0 ? (
                <div className="space-y-4">
                    {debts.map(debt => (
                        <div key={debt.id}
                             className="flex justify-between items-center p-3 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-500/30 rounded-lg">
                            <div>
                                <p className="font-semibold text-red-700 dark:text-red-300">{debt.source}</p>
                                <p className="text-sm text-gray-600 dark:text-gray-400">K
                                    dátumu: {formatDate(debt.dateOfRecord)}</p>
                            </div>
                            <p className="text-lg font-bold text-red-600 dark:text-red-300">{debt.amountEur.toLocaleString('sk-SK', {
                                style: 'currency',
                                currency: 'EUR'
                            })}</p>
                        </div>
                    ))}
                    <div className="flex justify-between items-center p-4 bg-red-100 dark:bg-red-900/50 rounded-lg mt-4">
                        <p className="font-bold text-gray-900 dark:text-white text-lg">Celkový dlh</p>
                        <p className="text-xl font-bold text-red-600 dark:text-white">{totalDebt.toLocaleString('sk-SK', {
                            style: 'currency',
                            currency: 'EUR'
                        })}</p>
                    </div>
                    {/* The total above is money, and the SP listing is not, so it
                        is not folded into it -- but it must not vanish either
                        just because the company also owes someone else. The
                        reader looking hardest at debts is the one this matters
                        to most. */}
                    {socialListedWithoutAmount && (
                        <p className="text-sm text-amber-800 dark:text-amber-300 bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-700/50 rounded-lg p-3">
                            <i className="fas fa-circle-exclamation mr-2"></i>
                            Sociálna poisťovňa navyše uvádza túto spoločnosť vo svojom zozname
                            dlžníkov <strong>bez zverejnenej sumy</strong> — dôvodom je nesplnená
                            vykazovacia povinnosť. Táto položka nie je zahrnutá v celkovej sume,
                            pretože register k nej žiadnu sumu neuvádza.
                        </p>
                    )}
                </div>
            ) : (
                <EmptyState
                    insuranceCheckedOn={insuranceCheckedOn}
                    taxCheckedOn={taxCheckedOn}
                    socialListedWithoutAmount={socialListedWithoutAmount}
                />
            )}
        </InfoCard>
    );
};
