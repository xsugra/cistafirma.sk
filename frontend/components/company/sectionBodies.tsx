import React from 'react';
import type { Company as CompanyType, PeerScope } from '../../types';
import type { BodySectionId } from '../../companySections';
import { OverviewSection } from './sections/OverviewSection';
import { RiskScoreSection } from './sections/RiskScoreSection';
import { FinancialAnalysisSection } from './sections/FinancialAnalysisSection';
import { BalanceSheetSection } from './sections/BalanceSheetSection';
import { ProfitLossSection } from './sections/ProfitLossSection';
import { PeopleOrgansSection } from './sections/PeopleOrgansSection';
import { RegisterSection } from './sections/RegisterSection';
import { ConnectionsSection } from './sections/ConnectionsSection';
import { ReportSection } from './sections/ReportSection';
import { DebtsSection } from './sections/DebtsSection';
import { PeerListSection } from './sections/PeerListSection';
import { ZaverkySection } from './sections/ZaverkySection';
import { UdalostiSection } from './sections/UdalostiSection';
import { RedFlagsSection } from './sections/RedFlagsSection';

/**
 * The section bodies, and the only map from a section id to what it draws.
 *
 * This lived in `pages/Company.tsx` while that page was the only consumer. It is
 * not any more: the inline tabbed view (`components/CompanyDetail.tsx`) renders
 * the same registry into tabs, and its own hand-written list had already drifted
 * — five ids of its own invention, twelve sections unreachable. A body map owned
 * by one of the two presentations is a body map the other can fall behind, so it
 * moved here, below both of them.
 *
 * What a section *looks like* is not here either -- that is `SectionPanel`,
 * which asks this map for a body and falls back to `SectionNotice` when there
 * is none. Keeping the two apart is what lets this file stay a plain map: it
 * answers one question ("what draws this id?") and neither view has to know
 * how a missing answer is dressed.
 */

/**
 * The five Databáza sections are one component asked five different questions,
 * so the section id and the scope it names are built together rather than
 * written twice and left to agree by hand.
 */
const peer = (scope: PeerScope): React.FC<{ company: CompanyType }> =>
    ({ company }) => <PeerListSection ico={company.ico} scope={scope} />;

/**
 * Every section the registry gives a body to, and nothing else.
 *
 * Typing this as a `Record` over the body ids means the two cannot drift: mark a
 * section `ready` or `partial` without writing its body and the typecheck fails
 * here, rather than the page quietly rendering a heading over nothing.
 */
export const BODIES: Record<BodySectionId, React.FC<{ company: CompanyType }>> = {
    prehlad: OverviewSection,
    skore: RiskScoreSection,
    register: RegisterSection,
    report: ReportSection,
    ukazovatele: FinancialAnalysisSection,
    suvaha: BalanceSheetSection,
    vykaz: ProfitLossSection,
    dlhy: DebtsSection,
    osoby: PeopleOrgansSection,
    prepojenia: ({ company }) => <ConnectionsSection ico={company.ico} />,
    zaverky: ZaverkySection,
    udalosti: ({ company }) => <UdalostiSection ico={company.ico} />,
    podobne: peer('podobne'),
    'databaza-kraj': peer('kraj'),
    'databaza-odvetvie': peer('odvetvie'),
    'databaza-trzby': peer('trzby'),
    'databaza-zamestnanci': peer('zamestnanci'),
    'rizikove-indikatory': RedFlagsSection,
};

/**
 * The body for a section id, or `undefined` when the registry gives it none.
 *
 * Both views ask this question — the standalone page and the inline tabbed one —
 * and both used to answer it themselves, as `section.status === 'ready' ? BODIES[…]
 * : undefined` with a cast to make the lookup typecheck. The question belongs to
 * whoever owns the map: adding a status that can carry a body would otherwise
 * mean remembering to change it in two `? :` expressions, and the failure mode
 * of forgetting is silent — the section renders a notice over a body that exists.
 */
export const bodyFor = (
    id: string,
): React.FC<{ company: CompanyType }> | undefined =>
    id in BODIES ? BODIES[id as BodySectionId] : undefined;
