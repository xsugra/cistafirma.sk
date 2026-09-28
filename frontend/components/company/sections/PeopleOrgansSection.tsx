import React, {useState} from 'react';
import type {Company} from '../../../types';
import {CompanyPeopleHistory} from '../CompanyPeopleHistory';
import {PeopleSection} from '../PersonCard';
import {useCompanyProfile} from '../useCompanyProfile';

interface PeopleOrgansSectionProps {
    company: Company;
}

type PeopleView = 'aktualne' | 'historia';

const VIEWS: {id: PeopleView; label: string; icon: string}[] = [
    {id: 'aktualne', label: 'Aktuálne', icon: 'fa-user-check'},
    {id: 'historia', label: 'História', icon: 'fa-clock-rotate-left'},
];

/**
 * The statutory bodies of the legal form, and the record of who held them.
 *
 * The cards are the register's extract, which is the bodies as they stand
 * today. The stored relations hold everyone who ever held an office there, and
 * until now no screen read them -- so this section gets a second view rather
 * than a second section, because the two are the same question asked at two
 * dates, not two subjects.
 *
 * The toggle is always offered, including for a company with no officers today:
 * "nobody holds an office now" and "nobody ever did" are different claims, and
 * a company whose only officer has left is exactly the case this view exists
 * for. Only the fetch can tell them apart.
 */
export const PeopleOrgansSection: React.FC<PeopleOrgansSectionProps> = ({ company }) => {
    const [view, setView] = useState<PeopleView>('aktualne');
    const {
        profile,
        structured,
        statutari,
        spolocnici,
        prokuristy,
        predstavenstvo,
        kontrolnaKomisia,
        dozornaRada,
        akcionari,
        prokuraOpravnenie,
        showPredstavenstvo,
        showStatutar,
        showSpolocnici,
        showAkcionari,
        showDozornaRada,
        showKontrolnaKomisia,
        showProkura,
    } = useCompanyProfile(company);

    return (
        <div className="space-y-6">
            <div
                className="inline-flex rounded-lg border border-slate-200 bg-slate-50 p-0.5 dark:border-slate-700 dark:bg-slate-800"
                role="group"
                aria-label="Zobrazenie osôb"
            >
                {VIEWS.map((item) => (
                    <button
                        key={item.id}
                        type="button"
                        onClick={() => setView(item.id)}
                        aria-pressed={view === item.id}
                        className={`min-h-9 rounded-md px-3 py-1.5 text-sm transition-colors ${
                            view === item.id
                                ? 'bg-white font-medium text-gray-900 shadow-sm dark:bg-slate-700 dark:text-white'
                                : 'text-gray-600 hover:text-gray-900 dark:text-gray-300 dark:hover:text-white'
                        }`}
                    >
                        <i className={`fas ${item.icon} mr-1.5`} aria-hidden="true"></i>
                        {item.label}
                    </button>
                ))}
            </div>

            {view === 'aktualne' ? (
                <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                    {showPredstavenstvo && (
                        <PeopleSection
                            title={profile.predstavenstvo!.title}
                            icon={profile.predstavenstvo!.icon}
                            people={predstavenstvo.length ? predstavenstvo : statutari}
                            accent="blue"
                            personIcon="fa-user-tie"
                            subtitle={profile.predstavenstvo!.subtitle}
                            emptyLabel={profile.predstavenstvo!.emptyLabel || 'Žiadni členovia'}
                        />
                    )}

                    {showStatutar && (
                        <PeopleSection
                            title={profile.statutar!.title}
                            icon={profile.statutar!.icon}
                            people={statutari}
                            accent="blue"
                            personIcon="fa-badge-check"
                            subtitle={profile.statutar!.subtitle}
                            emptyLabel={profile.statutar!.emptyLabel || 'Žiadny štatutárny orgán'}
                        />
                    )}

                    {showSpolocnici && (
                        <PeopleSection
                            title={profile.spolocnici!.title}
                            icon={profile.spolocnici!.icon}
                            people={spolocnici}
                            accent="purple"
                            personIcon="fa-user-tie"
                            subtitle={profile.spolocnici!.subtitle}
                            emptyLabel={profile.spolocnici!.emptyLabel || 'Žiadni spoločníci'}
                        />
                    )}

                    {showAkcionari && (
                        <PeopleSection
                            title={profile.akcionari!.title}
                            icon={profile.akcionari!.icon}
                            people={akcionari}
                            accent="rose"
                            personIcon="fa-building"
                            subtitle={profile.akcionari!.subtitle}
                            emptyLabel={profile.akcionari!.emptyLabel || 'Jediný akcionár sa nezverejňuje'}
                        />
                    )}

                    {showDozornaRada && (
                        <PeopleSection
                            title={profile.dozornaRada!.title}
                            icon={profile.dozornaRada!.icon}
                            people={dozornaRada}
                            accent="sky"
                            personIcon="fa-user-shield"
                            subtitle={profile.dozornaRada!.subtitle}
                            emptyLabel={profile.dozornaRada!.emptyLabel || 'Žiadni členovia'}
                        />
                    )}

                    {showKontrolnaKomisia && (
                        <PeopleSection
                            title={profile.kontrolnaKomisia!.title}
                            icon={profile.kontrolnaKomisia!.icon}
                            people={kontrolnaKomisia}
                            accent="green"
                            personIcon="fa-user-shield"
                            subtitle={profile.kontrolnaKomisia!.subtitle}
                            emptyLabel={profile.kontrolnaKomisia!.emptyLabel || 'Žiadni členovia'}
                        />
                    )}

                    {showProkura && (
                        <PeopleSection
                            title={profile.prokura!.title}
                            icon={profile.prokura!.icon}
                            people={prokuristy}
                            accent="amber"
                            personIcon="fa-pen-fancy"
                            emptyLabel={profile.prokura!.emptyLabel || 'Žiadna prokúra'}
                            subtitle={prokuraOpravnenie.length > 0 ? prokuraOpravnenie.join(' ') : profile.prokura!.subtitle}
                        />
                    )}
                </div>
            ) : (
                <CompanyPeopleHistory ico={company.ico} />
            )}
        </div>
    );
};
