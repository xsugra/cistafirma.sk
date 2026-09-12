import React from 'react';
import type { Company, FinancialsState } from '../../../types';
import { InfoCard } from '../../InfoCard';

/**
 * Why a statement section has nothing to draw, in the reader's words.
 *
 * Every one of these used to be the same sentence — "finančné údaje nie sú k
 * dispozícii" — which is one answer for four different facts. A reader cannot
 * tell from it whether waiting helps (we have not asked RUZ yet), whether
 * asking again is pointless (RUZ answered, and there is nothing), or whether
 * the company is a dead end for a different reason entirely (it accounts under
 * IFRS, so its statements exist only as PDFs). The backend now names the state
 * and this table turns it into a sentence.
 *
 * IFRS is checked first and deliberately: it is a fact about the company, not
 * about our import, and it is the one case here where the figures genuinely do
 * exist somewhere — behind a PDF, which is why the caller offers the link.
 */
const STATE_NOTE: Record<FinancialsState, string> = {
    ready: 'Závierku máme, ale nepodarilo sa z nej vykresliť túto tabuľku.',
    not_fetched:
        'Závierku tejto firmy sme z RUZ ešte nečítali. Naskenujeme ju pri najbližšom prechode registrom — poradie je dané rotáciou, nie dôležitosťou firmy.',
    nothing_recorded:
        'RUZ k tejto firme nevrátil závierku, z ktorej by sa dal prečítať aspoň jeden údaj. Skúsili sme to a tento pokus je uzavretý.',
    failed:
        'Závierku sme sa pokúsili načítať, ale pokus zlyhal. Skúsime to znova pri najbližšom prechode registrom.',
    blocked:
        'Načítavanie závierok pre túto firmu je pozastavené. Dôvod je vidieť v administrácii v sekcii Stav synchronizácie.',
};

const IFRS_NOTE =
    'Táto spoločnosť účtuje podľa medzinárodných štandardov (IFRS). RUZ vydáva jej výkazy len ako PDF, takže ich nevieme načítať po riadkoch.';

interface EmptyFinancialsNoticeProps {
    company: Company;
    title: string;
    icon: string;
}

export const EmptyFinancialsNotice: React.FC<EmptyFinancialsNoticeProps> = ({
    company,
    title,
    icon,
}) => {
    const ifrs = company.usesIfrs;
    const note = ifrs
        ? IFRS_NOTE
        : STATE_NOTE[company.financialsState] ?? STATE_NOTE.not_fetched;

    return (
        <InfoCard title={title} icon={icon}>
            <div className="py-2 text-center text-gray-500 dark:text-gray-400">
                <i className={`fas ${ifrs ? 'fa-file-pdf' : 'fa-info-circle'} mr-2`}></i>
                <span className="align-middle">{note}</span>
            </div>
            {ifrs && company.ruzPortalUrl && (
                <div className="mt-3 text-center">
                    <a
                        href={company.ruzPortalUrl}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="inline-flex items-center gap-2 rounded-lg bg-blue-600 px-4 py-2 text-sm text-white transition-colors hover:bg-blue-700"
                    >
                        <i className="fas fa-external-link-alt"></i>
                        Zobraziť na RUZ portáli
                    </a>
                </div>
            )}
        </InfoCard>
    );
};
