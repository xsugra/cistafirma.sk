import React from 'react';
import type { Company } from '../../../types';
import { PeopleSection } from '../PersonCard';
import { useCompanyProfile } from '../useCompanyProfile';

interface PeopleOrgansSectionProps {
    company: Company;
}

/**
 * The statutory bodies, each rendered only where the legal form actually has
 * one -- which is what `profile` (from `utils/legalFormProfile`) decides, not
 * whether the data happens to be present. A družstvo with no dozorná rada in
 * the register should not show an empty dozorná rada card.
 */
export const PeopleOrgansSection: React.FC<PeopleOrgansSectionProps> = ({ company }) => {
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
                    subtitle={
                        profile.statutar!.subtitle ||
                        (structured.statutarny_organ_typ ? `Typ: ${structured.statutarny_organ_typ}` : undefined)
                    }
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
    );
};
