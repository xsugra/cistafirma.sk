import React from 'react';
import type { Company } from '../../../types';
import { CompanyBusiness } from '../CompanyBusiness';
import { useCompanyProfile } from '../useCompanyProfile';

interface RegisterSectionProps {
    company: Company;
}

export const RegisterSection: React.FC<RegisterSectionProps> = ({ company }) => {
    const { orsrProfile, structured, profile } = useCompanyProfile(company);

    return (
        <div className="space-y-6">
            <CompanyBusiness orsrProfile={orsrProfile} structured={structured} profile={profile} />
        </div>
    );
};
