import React from 'react';
import type { PersonMember } from '../../types';
import { formatDate } from '../company/helpers';

interface PersonRecordsNoteProps {
    members: PersonMember[];
    className?: string;
}

/**
 * The stored rows this person's card was gathered from.
 *
 * The register writes the same officer under two sections of one document --
 * once in the predstavenstvo, once among the spoločníci -- and the two sections
 * do not carry the same lines, so the extractor stores two rows with two
 * different fingerprints. They are shown here as one person, and this says
 * which rows went into that.
 *
 * It is not decoration. The grouping is a judgement made by matching a name and
 * a postcode, and the reader who knows the two rows are a father and a son is
 * the only one who can correct it -- which they cannot do about rows they are
 * not shown. A merge would have hidden this; grouping is what lets it be
 * checked.
 *
 * Where the register states a date of birth it is shown on the row it belongs
 * to, because that is the one piece of evidence here that can contradict the
 * grouping rather than merely agree with it.
 *
 * Renders nothing for the ordinary case of one row, because a note on every
 * person page would be noise and this one has to be read when it appears.
 */
export const PersonRecordsNote: React.FC<PersonRecordsNoteProps> = ({ members, className = '' }) => {
    if (members.length < 2) return null;

    return (
        <div className={`rounded-xl border border-slate-200 bg-slate-50 p-4 text-xs text-slate-700 dark:border-slate-700 dark:bg-slate-800/40 dark:text-slate-300 ${className}`}>
            <p className="flex items-start gap-2">
                <i className="fas fa-layer-group mt-0.5 shrink-0" aria-hidden="true"></i>
                <span>
                    Register uvádza túto osobu v jednom dokumente na viacerých miestach
                    a my sme každé uložili ako samostatný záznam. Zobrazujeme ich spolu
                    ako jedného človeka — tu sú tak, ako ich máme.
                </span>
            </p>
            <ul className="mt-3 space-y-1.5 border-t border-slate-200 pt-3 dark:border-slate-700">
                {members.map((member) => (
                    <li key={member.id} className="flex flex-wrap items-baseline gap-x-2">
                        <span className="font-mono text-[10px] text-slate-400 dark:text-slate-500">
                            #{member.id}
                        </span>
                        <span className="font-medium text-slate-900 dark:text-slate-100">
                            {member.name}
                        </span>
                        {member.birth_date && (
                            <span className="text-slate-500 dark:text-slate-400">
                                nar. {formatDate(member.birth_date)}
                            </span>
                        )}
                        <span className="text-slate-500 dark:text-slate-400">
                            {member.address || 'bez adresy'}
                        </span>
                    </li>
                ))}
            </ul>
        </div>
    );
};
