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
// The body map lives below both presentations of a company, not in this one --
// the inline tabbed view draws the same sections and used to keep its own list.
import { BODIES } from '../components/company/sectionBodies';

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
