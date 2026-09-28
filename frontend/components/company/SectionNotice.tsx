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

/**
 * The same status, said above a body rather than instead of one.
 *
 * A `partial` section has both things to say at once: the part of the data it
 * does have, and the reason the rest is missing. `SectionNotice` can only say
 * the second, and dropping the first to make room for it is not honesty — it is
 * losing the answer to keep the caveat. So the caveat moves up here, where it
 * still precedes the first indicator, and the body keeps the section below it.
 *
 * Laid out as a line rather than as a centred block: this one has a page under
 * it, and a centred empty-state above content reads as a page that failed.
 */
export const SectionStatusBanner: React.FC<SectionNoticeProps> = ({ section }) => (
    <div className="flex items-start gap-3 rounded-xl border border-gray-200 bg-white px-4 py-3 dark:border-slate-700 dark:bg-slate-900">
        <i className={`fas ${STATUS_ICON[section.status]} mt-0.5 ${STATUS_TEXT[section.status]}`} />
        <div className="min-w-0">
            <span className={`inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-medium ${STATUS_CHIP[section.status]}`}>
                {STATUS_LABEL[section.status]}
            </span>
            <p className="mt-2 text-sm leading-relaxed text-gray-600 dark:text-gray-300">
                {section.note}
            </p>
        </div>
    </div>
);
