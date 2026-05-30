import React from 'react';
import type { Debt } from '../../types';
import { InfoCard } from '../InfoCard';

interface CompanyDebtsProps {
    debts: Debt[];
}

export const CompanyDebts: React.FC<CompanyDebtsProps> = ({ debts }) => {
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
                                    dátumu: {new Date(debt.dateOfRecord).toLocaleDateString('sk-SK')}</p>
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
                <div className="text-center py-4 text-green-600 dark:text-green-400 bg-green-50 dark:bg-green-900/20 border border-green-200 dark:border-green-500/30 rounded-lg">
                    <i className="fas fa-check-circle mr-2"></i> Neboli nájdené žiadne aktuálne dlhy.
                </div>
            )}
        </InfoCard>
    );
};
