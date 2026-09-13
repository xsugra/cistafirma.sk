import React from 'react';
import {
    ROLE_STATE_CHIP,
    ROLE_STATE_LINE,
    ROLE_STATE_SENTENCE,
    ROLE_STATE_WORD,
    roleStateOf,
} from './roleState';

interface RoleStateBadgeProps {
    isActive: boolean | null;
}

/**
 * „áno" / „nie" / „nevieme", with the stroke the graph draws that state with.
 *
 * The word carries the answer and the line carries it too, so the badge is
 * legible without colour, and identical to the graph's legend for a reader who
 * has seen both.
 */
export const RoleStateBadge: React.FC<RoleStateBadgeProps> = ({ isActive }) => {
    const state = roleStateOf(isActive);
    return (
        <span
            className={`inline-flex shrink-0 items-center gap-1.5 rounded-full border px-2 py-0.5 text-xs font-semibold ${ROLE_STATE_CHIP[state]}`}
            title={ROLE_STATE_SENTENCE[state]}
        >
            <span className={`h-0.5 w-3.5 ${ROLE_STATE_LINE[state]}`} aria-hidden="true" />
            {ROLE_STATE_WORD[state]}
        </span>
    );
};
