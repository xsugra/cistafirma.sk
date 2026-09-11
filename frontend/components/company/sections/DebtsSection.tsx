import React from 'react';
import type { Company } from '../../../types';
import { CompanyDebts } from '../CompanyDebts';

interface DebtsSectionProps {
    company: Company;
}

/**
 * A section whose body is the same component the overview already shows.
 *
 * That is deliberate: the overview puts the debts next to everything else as a
 * headline, and this section is where a reader goes when the headline is the
 * thing they came for. Both render one component, so the two cannot disagree —
 * which is the failure mode a second implementation would guarantee.
 */
export const DebtsSection: React.FC<DebtsSectionProps> = ({ company }) => (
    <div className="space-y-6">
        <CompanyDebts debts={company.debts} />
    </div>
);
