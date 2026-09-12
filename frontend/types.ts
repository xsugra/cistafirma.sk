
/**
 * Why the financial sections have nothing to draw.
 *
 * A token, not a sentence -- the words live in `EmptyFinancialsNotice`, next to
 * the screens that show them. The backend derives it (`financialsState` on
 * `CompanyDetailSerializer`) because only it can see the sync status, and
 * collapses one distinction on purpose: "the registry says there are no
 * statements" and "there are statements and none was readable" both leave zero
 * rows, and telling them apart would mean publishing an operator's sentence.
 */
export type FinancialsState =
  | 'ready'
  | 'not_fetched'
  | 'nothing_recorded'
  | 'failed'
  | 'blocked';

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
  financialsState: FinancialsState;
  executives: Executive[];
  connections: Connection[];
  orsr_profile?: OrsrProfile;
  analysis?: FinancialAnalysis;
  benchmark?: CompanyBenchmark;
    usesIfrs: boolean;
    ruzPortalUrl: string | null;
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

/**
 * One year's figures, as filed.
 *
 * Every amount is `number | null`, and the distinction is load-bearing rather
 * than defensive: a statement may carry a balance sheet and no income
 * statement, so `revenue` and `profit` are legitimately absent. `null` means
 * "this line is not in the statement", which is not the same fact as `0` --
 * render it as `—`, never as `0 €`.
 */
export interface Financials {
  year: number;
  revenue: number | null;
  /** Výsledok hospodárenia z hospodárskej činnosti -- the operating result, pre-tax. */
  profit: number | null;
  /**
   * Zisk po zdanení. `null` until the year has been re-read since the two rows
   * were split apart; before that, `profit` held whichever of the two the
   * parser happened to pick, so the after-tax figure is simply not known.
   */
  profitAfterTax: number | null;
  totalRevenue: number | null;
  costs: number | null;
  addedValue?: number | null;
  incomeTax: number | null;
  incomeTaxPaid: number | null;
  assetsTotal: number | null;
  assetsIntangible: number | null;
  assetsTangible: number | null;
  assetsFinancial: number | null;
  assetsInventory: number | null;
  assetsReceivablesLong: number | null;
  assetsReceivablesShort: number | null;
  assetsFinancialAccounts: number | null;
  assetsAccruals: number | null;
  equity: number | null;
  equityBasic: number | null;
  equityCapitalFunds: number | null;
  equityProfitFunds: number | null;
  equityRetained: number | null;
  liabilitiesTotal: number | null;
  liabilitiesReserves: number | null;
  liabilitiesLong: number | null;
  liabilitiesShort: number | null;
  liabilitiesAccruals: number | null;
  debtRatio: number | null;
  grossMargin: number | null;
}

// --- FINANCIAL ANALYSIS ---

export interface RatioSet {
  roa: number | null;
  roe: number | null;
  ros: number | null;
  currentRatio: number | null;
  quickRatio: number | null;
  cashRatio: number | null;
  assetTurnover: number | null;
  receivablesCollection: number | null;
  debtToEquity: number | null;
  selfFinancingRatio: number | null;
}

export interface YearAnalysis {
  year: number;
  ratios: RatioSet;
  // `unknown` is a token, not a missing key: the backend answers it for a ratio
  // the statement did not support, so the screen can say "not judged" instead of
  // defaulting to a verdict.
  interpretation: Record<string, 'good' | 'warning' | 'bad' | 'unknown'>;
  zScore: number | null;
  zScoreLabel: string | null;
  // The Altman zone the backend put the score in, and the only thing a client
  // may use to colour or describe it. Deriving it here from `zScore` is what
  // put 1.23 and 2.90 in the wrong zone: the backend's ladder is `> 2.90` /
  // `> 1.23` and the mirror of it is not the same ladder.
  zScoreZone: 'safe' | 'grey' | 'distress' | null;
}

export interface FinancialAnalysis {
  latest: YearAnalysis;
  history: YearAnalysis[];
}

// --- BENCHMARKING ---

export interface BenchmarkMedians {
  revenue: number | null;
  profit: number | null;
  assetsTotal: number | null;
  equity: number | null;
  roa: number | null;
  roe: number | null;
  ros: number | null;
  debtRatio: number | null;
  grossMargin: number | null;
  currentRatio: number | null;
  selfFinancingRatio: number | null;
}

export interface CompanyBenchmark {
  section: string;
  sectionName: string | null;
  divisionName: string | null;
  naceCode: string;
  year: number;
  companyCount: number;
  medians: BenchmarkMedians;
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

// --- NOTIFICATIONS ---

export interface NotificationEvent {
    id: number;
    companyIco: string;
    companyName: string;
    eventType: 'debt_change' | 'status_change' | 'executive_change';
    eventTypeDisplay: string;
    title: string;
    details: Record<string, any>;
    sentEmail: boolean;
    createdAt: string;
}

export interface NotificationPreferences {
    emailEnabled: boolean;
    onDebtChange: boolean;
    onStatusChange: boolean;
    onExecutiveChange: boolean;
}
