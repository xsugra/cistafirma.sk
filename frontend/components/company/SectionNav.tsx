import React from 'react';
import { NavLink } from 'react-router-dom';
import { companyPath } from '../../constants';
import {
    COMPANY_SECTIONS,
    SECTION_GROUPS,
    STATUS_DOT,
    STATUS_LABEL,
    type CompanySectionId,
    type SectionGroup,
} from '../../companySections';

/**
 * The registry's own element type, not the widened `CompanySection`: the array
 * is `as const`, so this keeps `id` the literal union a caller can hand back
 * through `onSelect`. Annotating the loops with `CompanySection` typechecks the
 * read and breaks the write -- `section.id` becomes `string` and no longer
 * satisfies a `CompanySectionId` callback.
 */
type Section = (typeof COMPANY_SECTIONS)[number];

interface SectionNavProps {
    /** Link mode: where a section lives, so the list can be a set of routes. */
    ico?: string;
    /** Button mode: the section currently shown, when the list drives state. */
    activeId?: CompanySectionId;
    onSelect?: (id: CompanySectionId) => void;
}

// One set of classes for both modes. This list used to be drawn twice -- by the
// company page and, on the profile's inline detail, as the same entries wrapped
// into a grid -- and the two had drifted: the grid drew no status dot, so what
// we cannot fill was invisible exactly where the list was longest.
//
// `Profile.tsx` has a `.tab-nav` bar of its own, for the five *profile* tabs
// (Prehľad, Sledované, História, …). That is a different list, not a third copy
// of this one, and it keeps its own classes; only the company sections come from
// here.
const ITEM =
    'flex flex-shrink-0 items-center gap-2.5 rounded-lg px-3 py-2 text-sm whitespace-nowrap transition-colors';
const ACTIVE = 'bg-blue-50 dark:bg-blue-900/20 text-blue-700 dark:text-blue-300 font-medium';
const IDLE = 'text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-slate-800';

// A horizontal strip on a narrow screen, a column at `lg`, where it sits in the
// one-of-four sidebar both callers draw. `lg:overflow-visible` is the whole of
// the desktop behaviour: a column needs no scrolling, and a container that does
// not scroll draws no scrollbar. This used to be the company page's alone --
// the profile's inline detail carried a second, always-horizontal variant, so
// the same list showed a scrollbar on a desktop in one place and none in the
// other. There is now one behaviour and one constant.
const NAV = 'flex gap-1 overflow-x-auto pb-1 lg:flex-col lg:gap-0.5 lg:overflow-visible lg:pb-0';

/**
 * The company section list. One component, because it is drawn in two places
 * and a section that exists in one of them and not the other is either a dead
 * link or a page nobody can reach -- which is the defect this list was already
 * cured of once, when the profile's inline view carried a hand-written list of
 * eight ids that existed nowhere in the registry.
 *
 * Every section carries a coloured dot, so what we cannot fill is visible from
 * the list rather than only after the click. Hovering gives the reason. The
 * group headings are drawn at `lg` only, where the list is a column and they
 * have a column to head; in the horizontal strip of a narrow screen they would
 * break the row into labelled segments with no room for them.
 */
export const SectionNav: React.FC<SectionNavProps> = ({ico, activeId, onSelect}) => {
    return (
        <nav aria-label="Sekcie firmy" className={NAV}>
            {SECTION_GROUPS.map((group: SectionGroup) => {
                const items = COMPANY_SECTIONS.filter((s: Section) => s.group === group);
                if (!items.length) return null;
                return (
                    <React.Fragment key={group}>
                        <p className="hidden lg:block px-3 pt-4 pb-1 text-xs font-semibold uppercase tracking-wider text-gray-400 dark:text-gray-500 first:pt-1">
                            {group}
                        </p>
                        {items.map((section: Section) => {
                            const title = `${section.label} — ${STATUS_LABEL[section.status]}`;
                            const body = (
                                <>
                                    <i className={`fas ${section.icon} w-4 text-center opacity-80`} />
                                    <span className="flex-1">{section.label}</span>
                                    <span
                                        className={`h-1.5 w-1.5 flex-shrink-0 rounded-full ${STATUS_DOT[section.status]}`}
                                        aria-hidden="true"
                                    />
                                </>
                            );

                            if (ico) {
                                return (
                                    <NavLink
                                        key={section.id}
                                        to={companyPath(ico, section.id)}
                                        title={title}
                                        className={({ isActive }) =>
                                            `${ITEM} ${isActive ? ACTIVE : IDLE}`
                                        }
                                    >
                                        {body}
                                    </NavLink>
                                );
                            }

                            return (
                                <button
                                    key={section.id}
                                    type="button"
                                    onClick={() => onSelect?.(section.id)}
                                    title={title}
                                    // `aria-current`, not the `active` class: the
                                    // class is styling and a restyle must not be
                                    // able to silently break the one assertion
                                    // that says which section is open.
                                    aria-current={activeId === section.id ? 'true' : undefined}
                                    className={`${ITEM} ${activeId === section.id ? ACTIVE : IDLE}`}
                                >
                                    {body}
                                </button>
                            );
                        })}
                    </React.Fragment>
                );
            })}
        </nav>
    );
};
