import React from 'react';
import { NavLink } from 'react-router-dom';
import { companyPath } from '../../constants';
import {
    COMPANY_SECTIONS,
    SECTION_GROUPS,
    STATUS_DOT,
    STATUS_LABEL,
    type CompanySection,
    type SectionGroup,
} from '../../companySections';

interface CompanyNavProps {
    ico: string;
}

/**
 * The company page's navigation rail.
 *
 * A column on desktop and a horizontal strip on mobile — one DOM, because two
 * would be two places for a section to be added and one of them to be missed.
 * The group headings are the only part that is desktop-only.
 *
 * Every section carries a coloured dot, so what we cannot fill is visible from
 * the rail rather than only after the click. Hovering gives the reason.
 */
export const CompanyNav: React.FC<CompanyNavProps> = ({ ico }) => (
    <nav
        aria-label="Sekcie firmy"
        className="flex gap-1 overflow-x-auto pb-1 lg:flex-col lg:gap-0.5 lg:overflow-visible lg:pb-0"
    >
        {SECTION_GROUPS.map((group: SectionGroup) => {
            const items = COMPANY_SECTIONS.filter((s: CompanySection) => s.group === group);
            if (!items.length) return null;
            return (
                <React.Fragment key={group}>
                    <p className="hidden lg:block px-3 pt-4 pb-1 text-xs font-semibold uppercase tracking-wider text-gray-400 dark:text-gray-500 first:pt-1">
                        {group}
                    </p>
                    {items.map((section: CompanySection) => (
                        <NavLink
                            key={section.id}
                            to={companyPath(ico, section.id)}
                            title={`${section.label} — ${STATUS_LABEL[section.status]}`}
                            className={({ isActive }) =>
                                `flex items-center gap-2.5 rounded-lg px-3 py-2 text-sm whitespace-nowrap transition-colors ${
                                    isActive
                                        ? 'bg-blue-50 dark:bg-blue-900/20 text-blue-700 dark:text-blue-300 font-medium'
                                        : 'text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-slate-800'
                                }`
                            }
                        >
                            <i className={`fas ${section.icon} w-4 text-center opacity-80`} />
                            <span className="flex-1">{section.label}</span>
                            <span
                                className={`h-1.5 w-1.5 flex-shrink-0 rounded-full ${STATUS_DOT[section.status]}`}
                                aria-hidden="true"
                            />
                        </NavLink>
                    ))}
                </React.Fragment>
            );
        })}
    </nav>
);
