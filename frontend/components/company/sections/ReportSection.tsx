import React, { useState } from 'react';
import type { Company } from '../../../types';
import { InfoCard } from '../../InfoCard';
import { exportCompanyPDF } from '../../../utils/pdfExport';

interface ReportSectionProps {
    company: Company;
}

/**
 * The same export the header button offers, given the room to say what it is.
 *
 * The button in the header is a shortcut for someone already looking at the
 * firm; this is the answer to "where do I get the report", which is a different
 * question and deserves a sentence.
 */
export const ReportSection: React.FC<ReportSectionProps> = ({ company }) => {
    const [isExporting, setIsExporting] = useState(false);
    const [failed, setFailed] = useState(false);

    const handleExport = async () => {
        setIsExporting(true);
        setFailed(false);
        try {
            await exportCompanyPDF(company);
        } catch (e) {
            console.error('PDF export failed', e);
            setFailed(true);
        } finally {
            setIsExporting(false);
        }
    };

    return (
        <InfoCard title="Finančný report" icon="fa-file-pdf">
            <p className="text-gray-700 dark:text-gray-300 leading-relaxed">
                Report zhrnie základné údaje o firme, jej hospodárske výsledky a zistené dlhy
                do jedného dokumentu, ktorý sa dá uložiť alebo poslať ďalej.
            </p>
            <div className="mt-4 flex items-center gap-3">
                <button
                    onClick={handleExport}
                    disabled={isExporting}
                    className="btn btn-primary disabled:opacity-60"
                >
                    <i className={`fas ${isExporting ? 'fa-spinner animate-spin' : 'fa-download'}`}></i>
                    {' '}{isExporting ? 'Pripravujem…' : 'Stiahnuť PDF'}
                </button>
                {failed && (
                    <span className="text-sm text-red-600 dark:text-red-400">
                        <i className="fas fa-exclamation-circle mr-1"></i>
                        Report sa nepodarilo vytvoriť. Skús to znova.
                    </span>
                )}
            </div>
        </InfoCard>
    );
};
