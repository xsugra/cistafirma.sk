import React, { useState } from 'react';
import type { OrsrProfile, OrsrStructured } from '../../types';
import { InfoCard } from '../InfoCard';
import type { LegalFormProfile } from '../../utils/legalFormProfile';

interface CompanyBusinessProps {
    orsrProfile?: OrsrProfile;
    structured: OrsrStructured;
    profile: LegalFormProfile;
}

export const CompanyBusiness: React.FC<CompanyBusinessProps> = ({ orsrProfile, structured, profile }) => {
    const [showAll, setShowAll] = useState(false);

    const predmety = structured.predmet_podnikania?.length
        ? structured.predmet_podnikania.map(p => p.text)
        : (orsrProfile?.predmet_podnikania || []);
    const predmetyVisible = predmety.slice(0, 3);
    const predmetyHidden = predmety.slice(3);

    return (
        <>
            <InfoCard title="Predmety Podnikania" icon="fa-briefcase">
                {predmety.length > 0 ? (
                    <div className="space-y-2">
                        {predmetyVisible.map((predmet, index) => (
                            <div key={index} className="flex items-start space-x-2 p-2">
                                <i className="fas fa-check text-green-600 dark:text-green-400 mt-1 text-sm"></i>
                                <p className="text-sm text-gray-700 dark:text-gray-300">{predmet}</p>
                            </div>
                        ))}
                        {predmetyHidden.length > 0 && !showAll && (
                            <button
                                onClick={() => setShowAll(true)}
                                className="w-full mt-3 py-2 text-sm text-blue-600 dark:text-blue-400 hover:bg-gray-100 dark:hover:bg-gray-800 rounded-lg font-medium transition"
                            >
                                <i className="fas fa-plus mr-1"></i> Zobraziť všetky ({predmety.length})
                            </button>
                        )}
                        {showAll && (
                            <>
                                {predmetyHidden.map((predmet, index) => (
                                    <div key={index} className="flex items-start space-x-2 p-2">
                                        <i className="fas fa-check text-green-600 dark:text-green-400 mt-1 text-sm"></i>
                                        <p className="text-sm text-gray-700 dark:text-gray-300">{predmet}</p>
                                    </div>
                                ))}
                                <button
                                    onClick={() => setShowAll(false)}
                                    className="w-full mt-3 py-2 text-sm text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-800 rounded-lg font-medium transition"
                                >
                                    <i className="fas fa-minus mr-1"></i> Skryť
                                </button>
                            </>
                        )}
                    </div>
                ) : (
                    <div className="text-center py-4 text-gray-500 dark:text-gray-400">
                        <i className="fas fa-info-circle mr-2"></i> Žiadne predmety podnikania
                    </div>
                )}
            </InfoCard>

            {profile.dalsiePravneSkutocnosti && orsrProfile?.dalske_pravne_skutocnosti && (
                <InfoCard title="Ďalšie právne skutočnosti" icon="fa-scroll">
                    <p className="text-sm text-gray-700 dark:text-gray-300 whitespace-pre-line leading-relaxed">
                        {orsrProfile.dalske_pravne_skutocnosti}
                    </p>
                </InfoCard>
            )}
        </>
    );
};
