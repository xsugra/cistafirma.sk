import React from 'react';
import { Link } from 'react-router-dom';
import type { PersonSummary } from '../../types';
import { personPath } from '../../constants';
import { RoleStateBadge } from './RoleStateBadge';

interface PersonResultRowProps {
    person: PersonSummary;
    /** Run as the row is followed -- closing a dropdown, say. */
    onClick?: () => void;
    className?: string;
}

/**
 * One person, as a search result.
 *
 * The row is shared by the search box's dropdown and by the results page, which
 * is the whole reason it exists as a component: two renderings of "a person we
 * found" would drift, and the one that drifted would be the one showing a name
 * with no state or no company beside it -- a row that reads as a claim about a
 * person with nothing under it to say where the claim came from.
 *
 * What it deliberately does not carry is the coverage sentence. That belongs
 * once per list and not once per row (see `PersonCoverageNote`), so the list
 * that renders these owns it.
 *
 * The first company is printed and the rest are counted, not listed: this is a
 * row in a list of people, and a person with forty companies would push every
 * other person off the screen. The count is `companies.length - 1` and the
 * wording is the same one the dropdown used before this component existed.
 */
export const PersonResultRow: React.FC<PersonResultRowProps> = ({
    person,
    onClick,
    className = '',
}) => {
    const first = person.companies[0];
    const rest = person.companies.length - 1;

    return (
        <Link
            to={personPath(person.id)}
            onClick={onClick}
            className={`flex items-center justify-between gap-4 transition-colors hover:bg-blue-50 dark:hover:bg-blue-900/20 group ${className}`}
        >
            <div className="flex-grow min-w-0">
                <p className="font-bold text-gray-900 dark:text-white truncate group-hover:text-blue-600 dark:group-hover:text-blue-400">
                    {person.name}
                </p>
                {first && (
                    <p className="text-xs text-gray-500 dark:text-gray-400 truncate">
                        {first.role_display ? `${first.role_display} · ` : ''}
                        {first.name}
                        {rest > 0 ? ` a ďalšie ${rest}` : ''}
                    </p>
                )}
            </div>
            {first && <RoleStateBadge isActive={first.is_active} />}
        </Link>
    );
};
