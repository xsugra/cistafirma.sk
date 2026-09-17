import React from 'react';
import type { Company as CompanyType, PeerScope } from '../../types';
import type { ReadySectionId } from '../../companySections';
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
 * `SectionNotice` is deliberately *not* here. A body is what a `ready` section
 * draws; a section without one is a fact about the registry, and each view says
 * it in its own chrome.
 */

/**
 * The five Databáza sections are one component asked five different questions,
 * so the section id and the scope it names are built together rather than
 * written twice and left to agree by hand.
 */
const peer = (scope: PeerScope): React.FC<{ company: CompanyType }> =>
    ({ company }) => <PeerListSection ico={company.ico} scope={scope} />;

/**
 * Every section the registry calls `ready`, and nothing else.
 *
 * Typing this as a `Record` over the ready ids means the two cannot drift: mark
 * a section ready without writing its body and the typecheck fails here, rather
 * than the page quietly rendering a heading over nothing.
 */
export const BODIES: Record<ReadySectionId, React.FC<{ company: CompanyType }>> = {
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
};
