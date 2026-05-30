import React from 'react';
import type { Company } from '../../types';
import { InfoCard } from '../InfoCard';
import { RiskDonut } from '../RiskDonut';
import { DetailItem } from './DetailItem';

interface CompanySidebarProps {
    company: Company;
}

export const CompanySidebar: React.FC<CompanySidebarProps> = ({ company }) => (
    <div className="lg:col-span-1 space-y-8">
        <InfoCard title="Risk Skóre" icon="fa-tachometer-alt">
            <RiskDonut score={company.riskScore.score} />
            <p className="text-center text-gray-600 dark:text-gray-300 mt-4 leading-relaxed">{company.riskScore.summary}</p>
        </InfoCard>
        <InfoCard title="Status DPH" icon="fa-percent">
            <div className="space-y-4">
                <DetailItem label="Platiteľ DPH" value={company.vatStatus.isVatPayer ? 'Áno' : 'Nie'} icon="fa-check-circle" />
                {company.vatStatus.icDph &&
                    <DetailItem label="IČ DPH" value={company.vatStatus.icDph} icon="fa-hashtag" />}
                <DetailItem label="Index daňovej spoľahlivosti" value={<span
                    className={`font-bold ${company.vatStatus.taxReliabilityIndex === 'Nespoľahlivý' ? 'text-red-500 dark:text-red-400' : 'text-green-600 dark:text-green-400'}`}>{company.vatStatus.taxReliabilityIndex}</span>}
                    icon="fa-thumbs-up" />
            </div>
        </InfoCard>
    </div>
);
