import React, { useEffect, useState } from 'react';
import { Link, Navigate, useParams } from 'react-router-dom';
import { api } from '../api';
import type { Company as CompanyType } from '../types';
import { ROUTES, companyPath } from '../constants';
import { DEFAULT_SECTION_ID, getSection, type ReadySectionId } from '../companySections';
import { LoadingSpinner } from '../components/LoadingSpinner';
import { CompanyHeader } from '../components/company/CompanyHeader';
import { CompanySummaryStrip } from '../components/company/CompanySummaryStrip';
import { CompanyNav } from '../components/company/CompanyNav';
import { SectionNotice } from '../components/company/SectionNotice';
import { useCompanyProfile } from '../components/company/useCompanyProfile';
import { OverviewSection } from '../components/company/sections/OverviewSection';
import { RiskScoreSection } from '../components/company/sections/RiskScoreSection';
import { FinancialAnalysisSection } from '../components/company/sections/FinancialAnalysisSection';
import { BalanceSheetSection } from '../components/company/sections/BalanceSheetSection';
import { ProfitLossSection } from '../components/company/sections/ProfitLossSection';
import { PeopleOrgansSection } from '../components/company/sections/PeopleOrgansSection';
import { RegisterSection } from '../components/company/sections/RegisterSection';
import { ConnectionsSection } from '../components/company/sections/ConnectionsSection';
import { ReportSection } from '../components/company/sections/ReportSection';
import { DebtsSection } from '../components/company/sections/DebtsSection';
import { PeerListSection } from '../components/company/sections/PeerListSection';
import { ZaverkySection } from '../components/company/sections/ZaverkySection';
import { UdalostiSection } from '../components/company/sections/UdalostiSection';
import type { PeerScope } from '../types';

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
const BODIES: Record<ReadySectionId, React.FC<{ company: CompanyType }>> = {
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

/**
 * The standalone company page: one section at a time, chosen from a rail.
 *
 * A separate route from the inline tabbed detail (`CompanyDetail`) on purpose.
 * The inline one is an answer inside a page the reader is already on; this one
 * is a destination that can be linked to, bookmarked and shared, which is what
 * the URL-per-section shape buys. Both draw the same section bodies, so the two
 * presentations cannot disagree about what a firm's finances are.
 */
export const Company: React.FC = () => {
    const { ico = '', sekcia } = useParams<{ ico: string; sekcia?: string }>();
    const [company, setCompany] = useState<CompanyType | null>(null);
    const [isLoading, setIsLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        let cancelled = false;
        setIsLoading(true);
        setError(null);
        setCompany(null);

        api.getCompany(ico)
            .then((data) => { if (!cancelled) setCompany(data); })
            .catch((err: unknown) => {
                if (cancelled) return;
                setError(err instanceof Error && err.message
                    ? err.message
                    : 'Nepodarilo sa načítať údaje o firme.');
            })
            .finally(() => { if (!cancelled) setIsLoading(false); });

        return () => { cancelled = true; };
    }, [ico]);

    // One canonical URL per view, so the rail always has something to mark as
    // active. Without this `/firma/123` renders the overview with no section
    // highlighted, which reads as a broken menu rather than a default.
    if (!sekcia) {
        return <Navigate to={companyPath(ico, DEFAULT_SECTION_ID)} replace />;
    }

    const section = getSection(sekcia);

    return (
        <div className="mx-auto w-full max-w-7xl animate-fade-in py-8">
            {isLoading && <LoadingSpinner />}

            {error && !isLoading && (
                <div className="mx-auto max-w-2xl rounded-xl border border-red-200 bg-white p-8 text-center shadow-lg dark:border-red-900/50 dark:bg-slate-900">
                    <i className="fas fa-exclamation-triangle mb-4 text-3xl text-red-500"></i>
                    <p className="font-medium text-red-600 dark:text-red-400">{error}</p>
                    <Link to={ROUTES.MONITORING} className="btn btn-primary mt-6 inline-flex">
                        <i className="fas fa-search"></i> Späť na vyhľadávanie
                    </Link>
                </div>
            )}

            {!isLoading && !error && !section && (
                <div className="mx-auto max-w-2xl rounded-xl border border-gray-200 bg-white p-8 text-center shadow-lg dark:border-slate-700 dark:bg-slate-900">
                    <i className="fas fa-compass mb-4 text-3xl text-gray-400"></i>
                    <p className="font-medium text-gray-700 dark:text-gray-200">
                        Sekcia „{sekcia}“ neexistuje.
                    </p>
                    <Link to={companyPath(ico)} className="btn btn-primary mt-6 inline-flex">
                        <i className="fas fa-arrow-left"></i> Späť na prehľad
                    </Link>
                </div>
            )}

            {!isLoading && !error && company && section && (
                <CompanyBody company={company} section={section} />
            )}
        </div>
    );
};

const CompanyBody: React.FC<{
    company: CompanyType;
    section: NonNullable<ReturnType<typeof getSection>>;
}> = ({ company, section }) => {
    const { profile } = useCompanyProfile(company);
    const Body = section.status === 'ready'
        ? BODIES[section.id as ReadySectionId]
        : undefined;

    return (
        <div className="space-y-6">
            <CompanyHeader company={company} profile={profile} />
            <CompanySummaryStrip company={company} />

            <div className="grid grid-cols-1 gap-6 lg:grid-cols-4">
                <div className="lg:col-span-1">
                    <div className="lg:sticky lg:top-6 rounded-xl border border-gray-200 bg-white p-2 dark:border-slate-700 dark:bg-slate-900">
                        <CompanyNav ico={company.ico} />
                    </div>
                </div>
                <div className="lg:col-span-3">
                    {Body ? <Body company={company} /> : <SectionNotice section={section} />}
                </div>
            </div>
        </div>
    );
};
