import { useMemo } from 'react';
import type { Company, OrsrPerson, OrsrStructured } from '../../types';
import { getLegalFormProfile, type LegalFormProfile } from '../../utils/legalFormProfile';
import { normalizePeople } from './helpers';

/**
 * Everything `Company` derives from its ORSR payload, derived once.
 *
 * This used to live inline in `CompanyDetail`, which was fine while that was
 * the only place rendering a company. It no longer is: the company page
 * (`pages/Company.tsx`) renders the same bodies section by section next to a
 * navigation rail, and two copies of this derivation would drift the moment a
 * legal form changed shape -- the kind of divergence nobody notices until a
 * s.r.o. starts showing a predstavenstvo.
 *
 * The rules themselves are unchanged, including the deliberate fallbacks: a
 * structured `statutarny_organ` that is present but empty falls back to the
 * flat `orsr_profile.statutarny_organ`, because RPO populates one and the
 * scraper the other. An empty array is *not* the same as an absent one here.
 */
export interface CompanyProfileView {
    orsrProfile: Company['orsr_profile'];
    structured: OrsrStructured;
    profile: LegalFormProfile;

    statutari: OrsrPerson[];
    spolocnici: OrsrPerson[];
    prokuristy: OrsrPerson[];
    predstavenstvo: OrsrPerson[];
    kontrolnaKomisia: OrsrPerson[];
    dozornaRada: OrsrPerson[];
    akcionari: OrsrPerson[];

    konanie: string;
    prokuraOpravnenie: string[];

    showPredstavenstvo: boolean;
    showStatutar: boolean;
    showSpolocnici: boolean;
    showAkcionari: boolean;
    showDozornaRada: boolean;
    showKontrolnaKomisia: boolean;
    showProkura: boolean;
    showKonanie: boolean;
}

export const useCompanyProfile = (company: Company): CompanyProfileView =>
    useMemo(() => {
        const orsrProfile = company.orsr_profile;
        const structured: OrsrStructured = orsrProfile?.structured || {};
        const profile = getLegalFormProfile((orsrProfile?.oddiel_type || '').toLowerCase());

        const statutari = normalizePeople(
            structured.statutarny_organ?.length ? structured.statutarny_organ : orsrProfile?.statutarny_organ,
        );
        const spolocnici = normalizePeople(
            structured.spolocnici?.length ? structured.spolocnici : orsrProfile?.spolocnici,
        );
        const prokuristy = normalizePeople(
            structured.prokura?.length ? structured.prokura : orsrProfile?.prokura,
        );
        const predstavenstvo = normalizePeople(
            structured.predstavenstvo?.length ? structured.predstavenstvo : orsrProfile?.predstavenstvo,
        );
        const kontrolnaKomisia = normalizePeople(
            structured.kontrolna_komisia?.length ? structured.kontrolna_komisia : orsrProfile?.kontrolna_komisia,
        );
        const dozornaRada = normalizePeople(structured.dozorna_rada || []);
        const akcionari = normalizePeople(structured.akcionari || []);

        const konanie =
            orsrProfile?.konanie_menom_spolocnosti || structured.konanie || orsrProfile?.konanie || '';
        const prokuraOpravnenie = (structured.prokura_oprávnenie as string[] | undefined) || [];

        return {
            orsrProfile,
            structured,
            profile,

            statutari,
            spolocnici,
            prokuristy,
            predstavenstvo,
            kontrolnaKomisia,
            dozornaRada,
            akcionari,

            konanie,
            prokuraOpravnenie,

            showPredstavenstvo: Boolean(profile.predstavenstvo),
            showStatutar: Boolean(profile.statutar) && (statutari.length > 0 || !profile.predstavenstvo),
            showSpolocnici: Boolean(profile.spolocnici) && (spolocnici.length > 0 || !profile.akcionari),
            showAkcionari: Boolean(profile.akcionari),
            showDozornaRada: Boolean(profile.dozornaRada) && dozornaRada.length > 0,
            showKontrolnaKomisia: Boolean(profile.kontrolnaKomisia),
            showProkura: Boolean(profile.prokura) && (prokuristy.length > 0 || prokuraOpravnenie.length > 0),
            showKonanie: Boolean(profile.konanie) && Boolean(konanie),
        };
    }, [company]);
