import React, { useState } from 'react';
import type { Company } from '../types';
import {
    DEFAULT_SECTION_ID,
    getSection,
    type CompanySectionId,
    type ReadySectionId,
} from '../companySections';
import { SectionNav } from './company/SectionNav';
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

            {/* The same section list the company page draws, in its `strip`
                layout -- one component, so the two views cannot disagree about
                which sections exist or what we can fill.

                This view used to wrap the twenty entries into a grid instead,
                to keep all of them visible at once: a sideways strip showed the
                first five and gave no sign of fifteen more. That reasoning was
                sound and the fix is still a strip, because the product owner
                asked for one mechanism across both views and the company page's
                is the one that already works. The scrollbar is the affordance
                the grid was buying -- `pb-1` keeps it visible rather than hiding
                it behind `no-scrollbar`, so the row still says it continues. */}
            <div className="mb-6">
                <SectionNav layout="strip" activeId={activeTab} onSelect={setActiveTab} />
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
