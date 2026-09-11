import React from 'react';
import { InfoCard } from '../InfoCard';
import { STATUS_CHIP, STATUS_LABEL, type CompanySection, type SectionStatus } from '../../companySections';

interface SectionNoticeProps {
    section: CompanySection;
}

/** An icon per status, so the shape of the notice matches its meaning. */
const STATUS_ICON: Record<SectionStatus, string> = {
    ready: 'fa-check-circle',
    partial: 'fa-circle-half-stroke',
    unreliable: 'fa-triangle-exclamation',
    planned: 'fa-hourglass-half',
    paid: 'fa-lock',
};

const STATUS_TEXT: Record<SectionStatus, string> = {
    ready: 'text-green-600 dark:text-green-400',
    partial: 'text-amber-600 dark:text-amber-400',
    unreliable: 'text-red-600 dark:text-red-400',
    planned: 'text-slate-500 dark:text-slate-400',
    paid: 'text-purple-600 dark:text-purple-400',
};

/**
 * What a section shows when it has no body: the reason, in one sentence, stated
 * rather than implied.
 *
 * This is the whole point of the honest rail. An empty panel leaves the reader
 * to guess whether the firm has no data or we have no feature; both guesses are
 * wrong half the time, and the second one is our fault. A sentence costs
 * nothing and is never wrong.
 */
export const SectionNotice: React.FC<SectionNoticeProps> = ({ section }) => (
    <InfoCard title={section.label} icon={section.icon}>
        <div className="flex flex-col items-center gap-3 py-6 text-center">
            <i className={`fas ${STATUS_ICON[section.status]} text-3xl ${STATUS_TEXT[section.status]}`} />
            <span className={`inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-medium ${STATUS_CHIP[section.status]}`}>
                {STATUS_LABEL[section.status]}
            </span>
            <p className="max-w-xl text-sm leading-relaxed text-gray-600 dark:text-gray-300">
                {section.note}
            </p>
        </div>
    </InfoCard>
);
