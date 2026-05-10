/**
 * ORSR legal-form profiles: každý typ oddielu má iné povinné sekcie.
 * oddiel_type vychádza z URL ORSR (Sro, Sa, Dr, Po, Sr, Pš, Pšn, Firm) znormalizovaný na lowercase.
 *
 * Referencia: https://www.orsr.sk/
 *  - Sro  = spoločnosť s ručením obmedzeným (s.r.o.)
 *  - Sa   = akciová spoločnosť (a.s.) + jednoduchá spol. na akcie (j.s.a.)
 *  - Dr   = družstvo
 *  - Po   = iná právnická osoba (v.o.s., k.s., európske zoskupenie, ...)
 *  - Sr   = samostatne hospodáriaci roľník / staré zápisy FO
 *  - Pš   = podnik zahraničnej osoby
 *  - Pšn  = podnik zahraničnej osoby (organizačná zložka)
 *  - Firm = fyzická osoba – podnikateľ (staré zápisy)
 */

export type PeopleSectionConfig = {
    title: string;
    icon: string;
    subtitle?: string;
    emptyLabel?: string;
};

export type LegalFormProfile = {
    label: string;
    statutar?: PeopleSectionConfig;          // konatelia / štatutárny orgán
    predstavenstvo?: PeopleSectionConfig;    // a.s., družstvo
    dozornaRada?: PeopleSectionConfig;       // a.s., niekedy s.r.o.
    kontrolnaKomisia?: PeopleSectionConfig;  // družstvo
    spolocnici?: PeopleSectionConfig;        // s.r.o., v.o.s., k.s.
    akcionari?: PeopleSectionConfig;         // a.s.
    prokura?: PeopleSectionConfig;           // kto môže
    konanie?: boolean;                       // "Konanie menom spoločnosti"
    imanie?: boolean;                        // základné imanie
    akcie?: boolean;                         // opis akcií
    zapisovaneImanie?: boolean;              // družstvo
    clenskyVklad?: boolean;                  // družstvo
    vkladySpolocnikov?: boolean;             // s.r.o., v.o.s., k.s.
    dalsiePravneSkutocnosti?: boolean;
};

const DEFAULT_PROFILE: LegalFormProfile = {
    label: 'Podnikateľský subjekt',
    statutar: { title: 'Štatutárny orgán', icon: 'fa-gavel' },
    spolocnici: { title: 'Spoločníci', icon: 'fa-handshake' },
    prokura: { title: 'Prokúra', icon: 'fa-file-signature' },
    konanie: true,
    imanie: true,
    vkladySpolocnikov: true,
    dalsiePravneSkutocnosti: true,
};

const PROFILES: Record<string, LegalFormProfile> = {
    sro: {
        label: 'Spoločnosť s ručením obmedzeným',
        statutar: {
            title: 'Štatutárny orgán (konatelia)',
            icon: 'fa-gavel',
            emptyLabel: 'Žiadny konateľ',
        },
        spolocnici: {
            title: 'Spoločníci',
            icon: 'fa-handshake',
            emptyLabel: 'Žiadni spoločníci',
        },
        prokura: { title: 'Prokúra', icon: 'fa-file-signature' },
        konanie: true,
        imanie: true,
        vkladySpolocnikov: true,
        dalsiePravneSkutocnosti: true,
    },
    sa: {
        label: 'Akciová spoločnosť',
        predstavenstvo: {
            title: 'Predstavenstvo',
            icon: 'fa-users',
            subtitle: 'Štatutárny orgán akciovej spoločnosti',
            emptyLabel: 'Žiadni členovia predstavenstva',
        },
        dozornaRada: {
            title: 'Dozorná rada',
            icon: 'fa-shield-alt',
            emptyLabel: 'Žiadni členovia dozornej rady',
        },
        akcionari: {
            title: 'Akcionári',
            icon: 'fa-chart-pie',
            emptyLabel: 'Jediný akcionár sa nezverejňuje',
        },
        prokura: { title: 'Prokúra', icon: 'fa-file-signature' },
        konanie: true,
        imanie: true,
        akcie: true,
        dalsiePravneSkutocnosti: true,
    },
    dr: {
        label: 'Družstvo',
        predstavenstvo: {
            title: 'Predstavenstvo',
            icon: 'fa-users',
            subtitle: 'Štatutárny orgán družstva',
            emptyLabel: 'Žiadni členovia predstavenstva',
        },
        kontrolnaKomisia: {
            title: 'Kontrolná komisia',
            icon: 'fa-user-check',
            emptyLabel: 'Žiadni členovia kontrolnej komisie',
        },
        prokura: { title: 'Prokúra', icon: 'fa-file-signature' },
        konanie: true,
        imanie: true,
        zapisovaneImanie: true,
        clenskyVklad: true,
        dalsiePravneSkutocnosti: true,
    },
    po: {
        label: 'Osobná obchodná spoločnosť (v.o.s. / k.s.)',
        statutar: {
            title: 'Štatutárny orgán',
            icon: 'fa-gavel',
            subtitle: 'Komplementári vystupujú ako štatutári',
            emptyLabel: 'Žiadny štatutár',
        },
        spolocnici: {
            title: 'Spoločníci',
            icon: 'fa-handshake',
            subtitle: 'Komplementári / komanditisti',
            emptyLabel: 'Žiadni spoločníci',
        },
        prokura: { title: 'Prokúra', icon: 'fa-file-signature' },
        konanie: true,
        imanie: true,
        vkladySpolocnikov: true,
        dalsiePravneSkutocnosti: true,
    },
    sr: {
        label: 'Samostatne hospodáriaci subjekt (Sr)',
    },
    pš: {
        label: 'Podnik zahraničnej osoby',
        statutar: {
            title: 'Vedúci podniku',
            icon: 'fa-user-tie',
            subtitle: 'Osoba oprávnená konať za zahraničný podnik v SR',
            emptyLabel: 'Nezverejnený vedúci podniku',
        },
        prokura: { title: 'Prokúra', icon: 'fa-file-signature' },
        konanie: true,
        dalsiePravneSkutocnosti: true,
    },
    pšn: {
        label: 'Organizačná zložka podniku zahraničnej osoby',
        statutar: {
            title: 'Vedúci organizačnej zložky',
            icon: 'fa-user-tie',
            subtitle: 'Osoba oprávnená konať za organizačnú zložku v SR',
            emptyLabel: 'Nezverejnený vedúci org. zložky',
        },
        prokura: { title: 'Prokúra', icon: 'fa-file-signature' },
        konanie: true,
        dalsiePravneSkutocnosti: true,
    },
    firm: {
        label: 'Fyzická osoba – podnikateľ',
        statutar: {
            title: 'Podnikateľ',
            icon: 'fa-user',
            emptyLabel: 'Nezverejnený podnikateľ',
        },
        dalsiePravneSkutocnosti: true,
    },
};

export const getLegalFormProfile = (oddielType?: string | null): LegalFormProfile => {
    const key = (oddielType || '').toLowerCase().trim();
    if (!key) return DEFAULT_PROFILE;
    return PROFILES[key] || DEFAULT_PROFILE;
};
