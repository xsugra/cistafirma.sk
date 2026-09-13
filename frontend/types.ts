
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
  /**
   * DIČ — the tax identification number, which is not the IČO.
   *
   * Measured 2026-09-12: 395 373 of 445 626 rows carry one, so this is an
   * ordinary field of a company record and not a bonus. It travelled in the
   * payload from the beginning and no line of this application named it.
   */
  dic: string | null;
  name: string;
  legalForm: string;
  status: 'Aktívna' | 'V likvidácii' | 'V konkurze' | 'Vymazaná';
  registrationDate: string;
  address: Address;
  /**
   * Where the seat is, as far as the address register can say. `null` for the
   * 1,92 % of companies whose PSČ the register does not list, and for the three
   * with no PSČ at all -- there the card is omitted rather than drawn as a
   * guess. Search results carry no seat location, so they are `null` too.
   */
  seatLocation: SeatLocation | null;
  lastUpdatedFromSource: string;
  /**
   * Whether we have ever asked each source about this company, and when.
   *
   * `Debt[]` cannot answer this on its own, and the difference is the whole
   * point. A debt row is only ever built for an amount above zero, so an empty
   * `debts` array meant two opposite things at once: "we checked and this firm
   * owes nothing" and "we have never checked". The section rendered both as a
   * green tick reading *Neboli nájdené žiadne aktuálne dlhy* — measured
   * 2026-09-12, 402 802 of the 411 186 companies that got that tick rest on at
   * least one source nobody has read, and only 8 384 earned it by reading both.
   * The insurance pass alone reaches 35 431 of 445 626 rows (8,0 %).
   *
   * `null` is "never", and it is not a date. These describe *our* coverage, not
   * the company: an old date is a stale answer, an absent one is no answer.
   */
  insuranceCheckedOn: string | null;
  /** The Finančná správa side of the same question. Same date as
   * `vatStatus.lastCheckedAt` — one expression in the mapper fills both, so the
   * two cannot drift apart. */
  taxCheckedOn: string | null;
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
    /**
     * How many účtovné závierky RUZ itself lists for this company.
     *
     * The denominator for `financials`. The page shows the years *we* read;
     * this says how many there are to read, which is the only way to tell a
     * company that files nothing from one the sync has not reached yet.
     *
     * `null` when the response did not carry it -- which is not the same fact
     * as a company RUZ holds nothing for, and the section renders the two
     * differently.
     */
    ruzStatements: number | null;
    /** The same count for výročné správy, which we do not read at all. */
    ruzAnnualReports: number | null;
}

export interface Address {
  street: string;
  city: string;
  zipCode: string;
  country: string;
}

/**
 * The registered seat as an area, not a point.
 *
 * We join our `psc` against the MV SR address register, which gives a centroid
 * per PSČ. That centroid sits a median **1 980 m** from its own address points
 * (p90 4 118 m, worst legitimate 8 709 m), so `radiusM` is the honest half of
 * this contract: the circle that covers 90 % of that PSČ's address points. A
 * consumer given only `lat`/`lon` would draw a marker claiming the accuracy of
 * a building entrance.
 *
 * `null` on `Company` means "we cannot place this seat" -- no PSČ, or a PSČ the
 * register does not list (1,92 % of our rows are post-office PSČ with no
 * address point at all). It does **not** mean the company has no seat.
 */
export interface SeatLocation {
  lat: number;
  lon: number;
  /** Metres. Between 270 m and 8 717 m across our 1 410 areas. */
  radiusM: number;
  psc: string;
  precision: 'postal_code';
}

export interface Debt {
  id: string;
  source: 'Sociálna poisťovňa' | 'VšZP' | 'Dôvera' | 'Union' | 'Finančná správa';
  amountEur: number;
  dateOfRecord: string;
}

/**
 * The bands Finančná správa publishes for the tax-reliability index, spelled
 * the way it spells them.
 *
 * Measured 2026-09-12 over all 445 626 rows of `"Companies and SZCO"`:
 * `vysoko spoľahlivý` 92 320, `spoľahlivý` 84 543, `menej spoľahlivý` 50 620,
 * and no index at all for 218 143.
 *
 * This type used to read `'Vysoko spoľahlivý' | 'Spoľahlivý' | 'Nespoľahlivý'`
 * — capitalised, and matching none of the three values the register actually
 * holds. So `isUnreliable = (index === 'Nespoľahlivý')`, the branch that was
 * supposed to flag the worst band, could never fire: a company the tax office
 * rates `menej spoľahlivý` was drawn in the same calm colour as one it rates
 * `vysoko spoľahlivý`, and the warning was code that ran and did nothing.
 */
export type TaxReliability = 'vysoko spoľahlivý' | 'spoľahlivý' | 'menej spoľahlivý';

export interface VatStatus {
  icDph: string | null;
  /**
   * `null` is not `false`. The column is nullable and 302 713 of 445 626 rows
   * hold no value, because Finančná správa publishes none for them — and this
   * field used to be declared `boolean`, so every one of those rendered as
   * "Neplatiteľ DPH", a claim no source ever made.
   */
  isVatPayer: boolean | null;
  /**
   * The index as the register spells it, or `null` when it published none.
   *
   * Typed `string` and not the `TaxReliability` union on purpose: the union is
   * what we have *measured*, and a value outside it must render as itself
   * rather than be forced into a band we cannot justify. `vatReliability()`
   * is the only reader, and it has an explicit branch for a value it does not
   * recognise.
   */
  taxReliabilityIndex: string | null;
  /** When the company entered the VAT register. 142 913 rows carry one. */
  registeredOn: string | null;
  /**
   * When it was struck off, and the one field that decides the state.
   *
   * 32 050 rows carry a date, and 27 857 of those carry no `Platiteľ DPH`
   * value at all — so deriving "is it still a payer" from the flag alone
   * misreads most deregistrations. The date is the fact; the flag is a hint.
   */
  deregisteredOn: string | null;
  /** Why, in the register's own words — `Rok porušenia: 2018` for 32 023 rows. */
  reasonForDeregistration: string | null;
  lastCheckedAt: string;
}

/** One factor the risk score looked at, and what it cost. */
export interface RiskScorePart {
  key: string;
  label: string;
  /** Points taken off the score, or `null` when the factor was not assessed.
   *  A factor at 0 and a factor we could not read are different facts. */
  delta: number | null;
  /** What was read, in words: the debt amount, the zone, the ROA. */
  detail: string;
}

export interface RiskScoreBreakdown {
  /** What the score starts from before any deduction — 100. */
  start: number;
  /** The score never falls below this. */
  floor: number;
  /** True when the floor is what set the number, so the parts deliberately do
   *  not add up to it — the section says so rather than leaving the reader to
   *  find an inconsistency. */
  clamped: boolean;
  parts: RiskScorePart[];
}

export interface RiskScore {
  /** 0-100, or `null` when the API sent no score.
   *
   * This used to be `data.riskScore?.score ?? 100`, so a response that did not
   * carry the field — a rename on the server, a shape change — read as a
   * perfect 100/100 "nothing here to look at" on every company in the
   * registry, silently. Absent is not the same as safest. */
  score: number | null;
  summary: string;
  /** The reasons behind the number. `null` when the API sent none. */
  breakdown: RiskScoreBreakdown | null;
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
  assetsCurrent?: number | null;
  assetsInventory: number | null;
  assetsReceivablesLong: number | null;
  assetsReceivablesShort: number | null;
  assetsFinancialShort?: number | null;
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
  // may use to colour or describe it. Re-deriving it from `zScore` is what put
  // 1.23 and 2.90 in the wrong zone: two of the copies -- `api.ts` and the PDF
  // renderer -- wrote the mirror of the backend's `> 2.90` / `> 1.23`, and a
  // mirror is not the same ladder.
  zScoreZone: 'safe' | 'grey' | 'distress' | null;
  // The Taffler model (1977, modified form), scored on the same statement --
  // and, like the Z-score, its zone is decided by the backend.
  //
  // Two models, not the six the plan named. The other four each need a line
  // the registry's statement format can carry but this schema does not store:
  // IN05 needs nákladové úroky (interest expense), and the Kralicek quick test
  // plus both names for the Index bonity / Binkert model need cash flow. They
  // are omitted rather than approximated -- an approximated score is still a
  // number in the right range, which is the failure this codebase keeps
  // finding. See `financial_analysis.py` for the per-model record.
  tafflerScore: number | null;
  tafflerLabel: string | null;
  tafflerZone: 'safe' | 'grey' | 'distress' | null;
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

// --- PEERS ---

/**
 * The five questions a company page can ask about its neighbours.
 *
 * Closed on purpose: the backend rejects anything else with a 400 rather than
 * falling back to a default, because each value answers a different question
 * and a silent default would put one ranking under another one's heading.
 */
export type PeerScope = 'podobne' | 'kraj' | 'odvetvie' | 'trzby' | 'zamestnanci';

/** How a scope ordered its rows. `similarity` means closeness in *ratio*. */
export type PeerRanking = 'revenue' | 'similarity';

/**
 * Why a scope could not rank the subject at all.
 *
 * `no_region` and `no_nace` are the two the register can produce: a company
 * with no region, or no readable NACE code, has no boundary to be ranked
 * inside. A code and not a sentence -- the Slovak text is built here.
 *
 * `no_size` is the third, and it is different in kind: the register *does* have
 * a value for this company, and the value says it does not know the size
 * (`00` — "nezistený"). It is the common case rather than an edge one, 63,3 %
 * of active companies, so its panel reports how many others are in the same
 * position instead of treating the firm as an anomaly.
 */
export type PeerReason = 'no_region' | 'no_nace' | 'no_size' | null;

export interface PeerRow {
    ico: string;
    name: string;
    city: string;
    nace_code: string;
    nace_name: string | null;
    /** The year of *this* company's most recent statement, which is not the
     * same year for every row -- the section prints it for exactly that. */
    year: number;
    revenue: number | null;
    profit: number | null;
}

export interface PeerList {
    scope: PeerScope;
    /** The narrowing value (`SK010`, `62`), or null for the whole register. */
    subject: string | null;
    subject_label: string | null;
    reason: PeerReason;
    ranked_by: PeerRanking;
    /** How many companies could be ranked, i.e. have a filed revenue. */
    total_ranked: number;
    /** How many companies the question was asked about, filers or not. */
    total_in_scope: number;
    results: PeerRow[];
}

/**
 * What can be downloaded for one company-year, and how sure the answer is.
 *
 * Four outcomes, and only the first is a promise that a download will work:
 *
 * - `listed` with documents — there is something to download.
 * - `listed` with none — the register answered, and holds nothing for that year.
 * - `no_statement` — we have no filing tied to that year in our own records.
 *   A statement about *us*, not about the register.
 * - `unreachable` — the register could not be read, so we do not know. The
 *   endpoint answers 503 for this, and it must never be rendered as "no
 *   documents": that would be a claim about the company invented out of a
 *   network failure.
 */
export type DocumentListingState = 'listed' | 'no_statement' | 'unreachable';

export type RuzDocumentKind = 'vykaz' | 'priloha';

export interface RuzDocument {
    /** This app's own handle (`'priloha-8736666'`), not a register URL. */
    id: string;
    kind: RuzDocumentKind;
    name: string;
    mimeType: string | null;
    size: number | null;
    pages: number | null;
    /** Where to download it from *here*. Never a registeruz.sk address. */
    url: string;
}

export interface DocumentListing {
    year: number;
    state: DocumentListingState;
    documents: RuzDocument[];
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

// --- PERSONS ---

/**
 * One company, as seen from a person.
 *
 * `role` is the enum code and `role_display` the words -- the opposite way
 * round from the graph's edges, deliberately, so that a row can be filtered and
 * round-tripped by the code while still rendering a label. See
 * `_relation_payload` in `connections/views.py`.
 *
 * `is_active` is **three-valued** and that is the point of the whole feature:
 * `true` the register states the function is current, `false` it states it
 * ended, `null` we have never read that company's history, so we do not know.
 * `null` is not "no". It is typed as a union rather than a boolean so that a
 * mapper which collapses the third answer fails the typecheck instead of
 * printing a claim about a company nobody checked.
 */
export interface PersonRelation {
    ico: string;
    name: string;
    role: string;
    role_display: string;
    is_active: boolean | null;
    vznik_funkcie: string | null;
    zanik_funkcie: string | null;
}

/**
 * What our person graph covers, as a count.
 *
 * It travels with every response rather than living in the interface as a fixed
 * sentence, because it is a moving number -- the coverage grows with each ORSR
 * sync, and a hardcoded claim would drift into a lie the first time it stopped
 * being true. `null` when the response did not carry it, which is not the same
 * fact as a coverage of zero.
 */
export interface PersonCoverage {
    companies_with_persons: number;
    companies_total: number;
}

/** One person as a search result: who they are, and every company we hold. */
export interface PersonSummary {
    id: number;
    name: string;
    /** The academic title, as its own field. May be empty. */
    title: string;
    /** The person's own IČO (a self-employed person has one). May be empty. */
    person_ico: string;
    companies: PersonRelation[];
}

export interface PersonSearchResponse {
    query: string;
    role: string;
    results: PersonSummary[];
    total_matches: number;
    truncated: boolean;
    /**
     * Why there are no results, in Slovak, when the question itself could not
     * be asked -- a query shorter than two characters, say. It must be shown
     * instead of the empty list, which would read as "this person is in no
     * company" about a search nobody ran.
     */
    detail: string | null;
    /** `null` when the response carried no counts; see `PersonCoverage`. */
    coverage: PersonCoverage | null;
}

/** One person, plus every relation we hold for them. */
export interface PersonDetail {
    id: number;
    name: string;
    title: string;
    person_ico: string;
    companies: PersonRelation[];
    coverage: PersonCoverage | null;
}

/**
 * One row of the register's own answer.
 *
 * The register names the company, never the capacity -- it has no column for it
 * -- so a hit says "this name is recorded in this company" and nothing more.
 */
export interface OrsrPersonHit {
    person_name: string;
    company_name: string;
    /** The register's výpis, current records only. Empty when it gave no id. */
    current_url: string;
    /** The same výpis including the historical entries. Empty likewise. */
    full_url: string;
}

/**
 * What the live register answered, and how sure we are of it.
 *
 * `error` non-empty means the register could not be read -- which must never be
 * rendered as "no records": that is a claim about a person invented out of a
 * request that never completed. `note` is the register's own limitation, in
 * Slovak, and belongs next to the results it describes.
 */
export interface OrsrPersonSearchResponse {
    query: string;
    hits: OrsrPersonHit[];
    total: number;
    truncated: boolean;
    source_url: string;
    error: string;
    note: string;
    /** Set on the short-query case, where the question was never asked. */
    detail: string | null;
    /** True when this answer came from our cache and not from the register now. */
    cached: boolean;
}

// --- USER & PROFILE TYPES ---

export interface User {
    id: string;
    email: string;
    username: string;
    firstName: string;
    lastName: string;
    /**
     * The plan, as its slug. The API publishes the plan as a nested object
     * (`subscription_plan`), so this is `subscription_plan.slug` -- reading that
     * object as if it were already a string is how the profile page came to
     * render an object where a plan name belongs.
     */
    plan: 'free' | 'plus' | 'pro' | 'business';
    /**
     * How much of a monthly API quota this account has used, and what the quota
     * is. `null` means the response did not say -- and it never has: the profile
     * endpoint publishes neither field. They are nullable so that the page can
     * tell "no quota reported" from "a quota of zero", which is the same
     * distinction the risk score and the RUZ statement counts are built on.
     */
    apiCallsUsed: number | null;
    apiCallsLimit: number | null;
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
