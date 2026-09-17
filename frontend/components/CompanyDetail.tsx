import React, { useState } from 'react';
import type { Company } from '../types';
import {
    COMPANY_SECTIONS,
    DEFAULT_SECTION_ID,
    getSection,
    type CompanySectionId,
    type ReadySectionId,
} from '../companySections';
import { CompanyHeader } from './company/CompanyHeader';
import { CompanySummaryStrip } from './company/CompanySummaryStrip';
import { SectionNotice } from './company/SectionNotice';
import { useCompanyProfile } from './company/useCompanyProfile';
import { BODIES } from './company/sectionBodies';

interface CompanyDetailProps {
    company: Company;
}

/**
 * The tabbed presentation of a company, used where the detail is shown inline
 * inside another page (Profile).
 *
 * Both the bodies and the list come from the registry — the bodies through
 * `company/sectionBodies.tsx`, shared with the standalone company page, and the
 * list straight out of `COMPANY_SECTIONS`. This view has no vocabulary of its
 * own, and it used to: a hand-written `TABS` array of eight entries, five of
 * them ids that exist nowhere in the registry (`overview`, `financials`,
 * `people`, `registers`, `connections`), which left twelve of the twenty
 * sections unreachable from the view most readers actually use. Sharing the
 * bodies was not enough — the list is the half that decides what can be found.
 *
 * A section without a body keeps its tab and says why. Dropping it would make
 * this a list that has everything, which is the one thing it must not be.
 */
export const CompanyDetail: React.FC<CompanyDetailProps> = ({ company }) => {
    const [activeTab, setActiveTab] = useState<CompanySectionId>(DEFAULT_SECTION_ID);
    const { profile } = useCompanyProfile(company);

    const section = getSection(activeTab);
    const Body = section && section.status === 'ready'
        ? BODIES[section.id as ReadySectionId]
        : undefined;

    return (
        <div className="space-y-6 animate-fade-in mt-10">
            <CompanyHeader company={company} profile={profile} />

            <CompanySummaryStrip company={company} />

            {/* Tab Navigation. Twenty entries do not fit on one line, and they
                wrap rather than scroll sideways. The scroll was the first
                attempt and it undid the fix above: a reader saw the first five
                tabs and had no reason to suspect fifteen more, which is the
                same unreachability this view was just cured of, only quieter.
                Wrapping shows all twenty at once, so the price is a taller bar
                instead of hidden sections. */}
            <div className="tab-nav flex-wrap pb-1 mb-6">
                {COMPANY_SECTIONS.map((entry) => (
                    <button
                        key={entry.id}
                        onClick={() => setActiveTab(entry.id)}
                        className={`tab-btn whitespace-nowrap flex-shrink-0 ${activeTab === entry.id ? 'active' : ''}`}
                    >
                        <i className={`fas ${entry.icon}`}></i>
                        {entry.label}
                    </button>
                ))}
            </div>

            {/* Tab Content. The key is the tab, so a switch unmounts what was
                there: several bodies hold request state for the company they
                were handed, and a reused instance would draw the previous tab's
                rows under this tab's heading. */}
            {Body
                ? <Body key={activeTab} company={company} />
                : section && <SectionNotice key={activeTab} section={section} />}
        </div>
    );
};
