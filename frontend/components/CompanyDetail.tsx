import React, { useState } from 'react';
import type { Company } from '../types';
import { CompanyHeader } from './company/CompanyHeader';
import { CompanySummaryStrip } from './company/CompanySummaryStrip';
import { useCompanyProfile } from './company/useCompanyProfile';
import { OverviewSection } from './company/sections/OverviewSection';
import { FinancialAnalysisSection } from './company/sections/FinancialAnalysisSection';
import { PeopleOrgansSection } from './company/sections/PeopleOrgansSection';
import { RegisterSection } from './company/sections/RegisterSection';
import { ConnectionsSection } from './company/sections/ConnectionsSection';

/**
 * The tabbed presentation of a company, used where the detail is shown inline
 * inside another page (Profile, and Monitoring's search result).
 *
 * The bodies are not defined here — they live in `company/sections/` and are
 * shared with the standalone company page (`pages/Company.tsx`), which presents
 * the same content next to a navigation rail instead of above tabs. Only the
 * chrome differs; a section rendered in one place cannot drift from the other.
 */
const TABS = [
    { id: 'overview', label: 'Prehľad', icon: 'fa-chart-pie' },
    { id: 'financials', label: 'Finančná analýza', icon: 'fa-calculator' },
    { id: 'people', label: 'Osoby', icon: 'fa-users' },
    { id: 'registers', label: 'Registre', icon: 'fa-briefcase' },
    { id: 'connections', label: 'Prepojenia', icon: 'fa-project-diagram' },
] as const;

type TabId = typeof TABS[number]['id'];

interface CompanyDetailProps {
    company: Company;
}

export const CompanyDetail: React.FC<CompanyDetailProps> = ({ company }) => {
    const [activeTab, setActiveTab] = useState<TabId>('overview');
    const { profile } = useCompanyProfile(company);

    return (
        <div className="space-y-6 animate-fade-in mt-10">
            <CompanyHeader company={company} profile={profile} />

            <CompanySummaryStrip company={company} />

            {/* Tab Navigation */}
            <div className="tab-nav">
                {TABS.map(tab => (
                    <button
                        key={tab.id}
                        onClick={() => setActiveTab(tab.id)}
                        className={`tab-btn ${activeTab === tab.id ? 'active' : ''}`}
                    >
                        <i className={`fas ${tab.icon}`}></i>
                        {tab.label}
                    </button>
                ))}
            </div>

            {/* Tab Content */}
            {activeTab === 'overview' && <OverviewSection company={company} />}
            {activeTab === 'financials' && <FinancialAnalysisSection company={company} />}
            {activeTab === 'people' && <PeopleOrgansSection company={company} />}
            {activeTab === 'registers' && <RegisterSection company={company} />}
            {activeTab === 'connections' && <ConnectionsSection ico={company.ico} />}
        </div>
    );
};
