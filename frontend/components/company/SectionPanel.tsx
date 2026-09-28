import React from 'react';
import type { Company } from '../../types';
import type { CompanySection } from '../../companySections';
import { SectionNotice, SectionStatusBanner } from './SectionNotice';
import { bodyFor } from './sectionBodies';

interface SectionPanelProps {
    company: Company;
    section: CompanySection;
}

/**
 * One section of a company page: its body when the registry gives it one, and
 * always the status the registry assigns it.
 *
 * This is the third thing both presentations have to agree on -- the rail has
 * `SectionNav`, the list has `COMPANY_SECTIONS`, and what a *section* looks
 * like was, until now, a `? :` expression written out in each view. One of them
 * would eventually have been changed alone.
 *
 * A section with no body says why instead of drawing one. A section *with* a
 * body gets that same sentence above it when its status is not `ready`, because
 * for a `partial` section both halves are true at once: we have part of the
 * data, and we have a reason the rest is missing. Hiding the indicators behind
 * the caveat would trade the answer for the disclaimer.
 */
export const SectionPanel: React.FC<SectionPanelProps> = ({ company, section }) => {
    const Body = bodyFor(section.id);

    if (!Body) {
        return <SectionNotice section={section} />;
    }

    return (
        <div className="space-y-4">
            {section.status !== 'ready' && <SectionStatusBanner section={section} />}
            <Body company={company} />
        </div>
    );
};
