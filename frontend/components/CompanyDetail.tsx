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

            {/* The company page's layout, not a variant of it: the list in a
                sticky one-of-four sidebar at `lg`, the section's body beside it.
                Both views draw the same registry through the same component, so
                they cannot disagree about which sections exist or what we can
                fill.

                This used to be a sideways strip at every width, which on a
                desktop meant five sections and a scrollbar standing in for the
                other fifteen -- while the company page drew the identical list
                as a column with no scrollbar at all. The product owner asked
                for the two to work the same, and the shape below is what "the
                same" means: there is no scrollbar to read because there is
                nothing to scroll. On a narrow screen the list is still the
                horizontal strip both views use.

                Button mode, not `ico`: this view drives its own state rather
                than routing to a section URL. */}
            <div className="grid grid-cols-1 gap-6 lg:grid-cols-4">
                <div className="lg:col-span-1">
                    <div className="lg:sticky lg:top-6 rounded-xl border border-gray-200 bg-white p-2 dark:border-slate-700 dark:bg-slate-900">
                        <SectionNav activeId={activeTab} onSelect={setActiveTab} />
                    </div>
                </div>

                <div className="lg:col-span-3">
                    {/* Tab Content. The key is the tab, so a switch unmounts what
                        was there: several bodies hold request state for the
                        company they were handed, and a reused instance would
                        draw the previous tab's rows under this tab's heading. */}
                    {Body
                        ? <Body key={activeTab} company={company} />
                        : section && <SectionNotice key={activeTab} section={section} />}
                </div>
            </div>
        </div>
    );
};
