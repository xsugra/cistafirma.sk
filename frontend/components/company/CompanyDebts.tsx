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
}: Pick<CompanyDebtsProps, 'insuranceCheckedOn' | 'taxCheckedOn'>) {
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
                </div>
            ) : (
                <EmptyState
                    insuranceCheckedOn={insuranceCheckedOn}
                    taxCheckedOn={taxCheckedOn}
                />
            )}
        </InfoCard>
    );
};
