
export interface Company {
  id: string;
  ico: string;
  name: string;
  legalForm: string;
  status: 'Aktívna' | 'V likvidácii' | 'V konkurze' | 'Vymazaná';
  registrationDate: string;
  address: Address;
  lastUpdatedFromSource: string;
  debts: Debt[];
  vatStatus: VatStatus;
  riskScore: RiskScore;
  financials: Financials[];
  executives: Executive[];
  connections: Connection[];
  orsr_profile?: OrsrProfile;
}

export interface Address {
  street: string;
  city: string;
  zipCode: string;
  country: string;
}

export interface Debt {
  id: string;
  source: 'Sociálna poisťovňa' | 'VšZP' | 'Dôvera' | 'Union' | 'Finančná správa';
  amountEur: number;
  dateOfRecord: string;
}

export interface VatStatus {
  icDph: string | null;
  isVatPayer: boolean;
  taxReliabilityIndex: 'Vysoko spoľahlivý' | 'Spoľahlivý' | 'Nespoľahlivý';
  reasonForDeregistration: string | null;
  lastCheckedAt: string;
}

export interface RiskScore {
  score: number; // 0-100
  summary: string;
  calculationDate: string;
}

export interface Financials {
  year: number;
  revenue: number;
  profit: number;
}

export interface Executive {
    name: string;
    role: string;
}

export interface Connection {
    companyName: string;
    ico: string;
    role: string;
    status: 'Aktívna' | 'V likvidácii' | 'V konkurze' | 'Vymazaná';
}

export interface OrsrPerson {
    name: string;
    title?: string;
    role?: string;
    address?: string;
    address_lines?: string[];
    vznik_funkcie?: string;
    ine_id?: string;
    person_ico?: string;
    od?: string;
    notes?: string[];
}

export interface OrsrContribution {
    name: string;
    vklad?: string;
    splatene?: string;
    typ?: string;
    currency?: string;
    od?: string;
    summary?: string;
}

export interface OrsrCapital {
    imanie?: string;
    rozsah_splatenia?: string;
    currency?: string;
    raw?: string;
    od?: string;
}

export interface OrsrPredmet {
    text: string;
    od?: string;
}

export interface OrsrStructured {
    statutarny_organ?: OrsrPerson[];
    statutarny_organ_typ?: string;
    spolocnici?: OrsrPerson[];
    vklady_spolocnikov?: OrsrContribution[];
    prokura?: OrsrPerson[];
    prokura_oprávnenie?: string[];
    predstavenstvo?: OrsrPerson[];
    kontrolna_komisia?: OrsrPerson[];
    dozorna_rada?: OrsrPerson[];
    akcionari?: OrsrPerson[];
    predmet_podnikania?: OrsrPredmet[];
    dalsie_pravne_skutocnosti?: OrsrPredmet[];
    akcie?: OrsrPredmet[];
    vyska_zakladneho_imania?: OrsrCapital;
    konanie?: string;
}

export interface OrsrProfile {
    oddiel: string;
    oddiel_type?: string;
    vlozka_cislo: string;
    obchodne_meno: string;
    sidlo: string;
    den_zapisu: string;
    pravna_forma: string;
    konanie?: string;
    konanie_menom_spolocnosti?: string;
    prokura: string[];
    spolocnici: string[];
    statutarny_organ: string[];
    vklady_spolocnikov: string[];
    vyska_zakladneho_imania: string;
    predmet_podnikania: string[];
    raw_sections?: Record<string, string[]>;
    orsr_aktualizacia_dat: string;
    orsr_datum_vypisu: string;
    fetch_ok: boolean;
    last_error: string;

    // Družstvá / špeciálne typy ORSR
    predstavenstvo?: string[];
    kontrolna_komisia?: string[];
    zakladny_clensky_vklad?: string;
    zapisovane_zakladne_imanie?: string;
    dalske_pravne_skutocnosti?: string;

    // Strukturované dáta z nového parsera
    structured?: OrsrStructured;
}

// --- USER & PROFILE TYPES ---

export interface User {
    id: string;
    email: string;
    username: string;
    firstName: string;
    lastName: string;
    plan: 'free' | 'plus' | 'pro' | 'business';
    apiCallsUsed: number;
    apiCallsLimit: number;
    isStaff: boolean;
    isSuperuser: boolean;
}

export interface WatchlistEntry {
    id: string;
    ico: string;
    name: string;
    addedAt: string;
    status: 'Aktívna' | 'V likvidácii' | 'V konkurze' | 'Vymazaná';
    riskScore: number;
}

export interface HistoryEntry {
    id: string;
    ico: string;
    name: string;
    searchedAt: string;
}
