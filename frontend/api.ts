import {mockCompanyData} from './mockData';
import {ENABLE_MOCK_DATA} from './constants';
import {apiRequest} from './lib/apiClient';
import type {
  Company,
  DocumentListing,
  HistoryEntry,
  NotificationEvent,
  NotificationPreferences,
  OrsrPersonHit,
  OrsrPersonSearchResponse,
  OrsrProfile,
  PeerList,
  PeerScope,
  PersonCoverage,
  PersonDetail,
  PersonMember,
  PersonRelation,
  PersonSearchResponse,
  PersonSummary,
  User,
  WatchlistEntry,
} from './types';

/**
 * The plan as the profile endpoint actually publishes it: a nested object, not
 * a slug. `UserDetailSerializer` nests `SubscriptionPlanSerializer`, so
 * `subscription_plan` arrives as `{id, name, slug, max_watched_companies,
 * price_eur}` or as null for an account with no plan.
 */
interface RawSubscriptionPlan {
  id: string;
  name: string;
  slug: User['plan'];
  max_watched_companies: number;
  price_eur: string;
}

interface RawUser {
  id: string;
  email: string;
  username: string;
  first_name?: string;
  last_name?: string;
  subscription_plan?: RawSubscriptionPlan | null;
  /** Declared because the API might send them; it does not, today. See `mapUserResponse`. */
  api_calls_used?: number;
  api_calls_limit?: number;
  is_staff?: boolean;
  is_superuser?: boolean;
}

interface UserPayload {
  email?: string;
  username?: string;
  password?: string;
  firstName?: string;
  lastName?: string;
}

interface LandingStats {
  companiesIndexed: number;
  dailyChecks: number;
  riskyCompaniesDetected: number;
}

interface SearchResult {
  results: Company[];
}

interface TokenResponse {
  access?: string;
  token?: string;
  /**
   * Carried, not dropped. It used to be read past: `access` was taken and the
   * refresh token thrown away, which left an expired access token with nothing
   * to recover from and signed the reader out 30 minutes after every sign-in.
   */
  refresh?: string;
}

interface LoginResult {
  token: string;
  refresh: string | null;
  user: User;
}

/**
 * Exported for its own spec, and for the same reason the function is worth
 * testing at all: it is the boundary where the API's shape and this app's types
 * meet, and the one place where a wrong reading of that shape is invisible to
 * the compiler.
 */
export function mapUserResponse(data: RawUser): User {
  return {
    id: data.id,
    email: data.email,
    username: data.username,
    firstName: data.first_name || '',
    lastName: data.last_name || '',
    // `.slug`, because `subscription_plan` is an object. This line used to read
    // `(data.subscription_plan as User['plan'])`, and the cast is what let it
    // compile: at runtime the field held the whole plan, so `plan` was an object
    // and the profile page rendered it as a React child. It survived only
    // because the one account in the database has no plan, and null falls
    // through to 'free'.
    plan: data.subscription_plan?.slug ?? 'free',
    // No invented fallback. The profile endpoint publishes neither field, so
    // `|| 0` and `|| 10` printed "0 / 10" under a heading that claims to measure
    // a quota -- a number and a progress bar for something nothing counts.
    // Absent is mapped as absent and the page decides what to say about it.
    apiCallsUsed: data.api_calls_used ?? null,
    apiCallsLimit: data.api_calls_limit ?? null,
    isStaff: Boolean(data.is_staff),
    isSuperuser: Boolean(data.is_superuser),
  };
}

function mapUserPayload(data: UserPayload): Record<string, string> {
  const payload: Record<string, string> = {};
  if (data.email !== undefined) payload.email = data.email;
  if (data.username !== undefined) payload.username = data.username;
  if (data.password !== undefined) payload.password = data.password;
  if (data.firstName !== undefined) payload.first_name = data.firstName;
  if (data.lastName !== undefined) payload.last_name = data.lastName;
  return payload;
}

function mapOrsrProfileResponse(profile: any): OrsrProfile | undefined {
  if (!profile) return undefined;
  return {
    oddiel: profile.oddiel || '',
    oddiel_type: profile.oddiel_type || '',
    vlozka_cislo: profile.vlozka_cislo || '',
    obchodne_meno: profile.obchodne_meno || '',
    sidlo: profile.sidlo || '',
    den_zapisu: profile.den_zapisu || null,
    pravna_forma: profile.pravna_forma || '',
    konanie: profile.konanie || '',
    prokura: profile.prokura || [],
    spolocnici: profile.spolocnici || [],
    statutarny_organ: profile.statutarny_organ || [],
    vklady_spolocnikov: profile.vklady_spolocnikov || [],
    vyska_zakladneho_imania: profile.vyska_zakladneho_imania || '',
    predmet_podnikania: profile.predmet_podnikania || [],
    raw_sections: profile.raw_sections || {},
    orsr_aktualizacia_dat: profile.orsr_aktualizacia_dat || null,
    orsr_datum_vypisu: profile.orsr_datum_vypisu || null,
    fetch_ok: Boolean(profile.fetch_ok),
    last_error: profile.last_error || '',
    predstavenstvo: profile.predstavenstvo || [],
    kontrolna_komisia: profile.kontrolna_komisia || [],
    zakladny_clensky_vklad: profile.zakladny_clensky_vklad || '',
    zapisovane_zakladne_imanie: profile.zapisovane_zakladne_imanie || '',
    dalske_pravne_skutocnosti: profile.dalske_pravne_skutocnosti || '',
    structured: profile.structured,
  };
}

// Financial figures keep their absence. `toAmount` below collapses a missing
// value to 0, which is correct for a debt -- a company with no recorded debt
// owes nothing -- and wrong for a filed statement, where a missing line means
// the statement did not carry it. The backend sends `null` for those, and it
// has to survive to the render, or an unread revenue shows as "0 €".
//
// It carries the RUZ statement counts too, for the same reason in a different
// place: a count is either something the response told us or something it did
// not, and a missing count that becomes 0 reads as "this company files
// nothing".
const toFiledAmount = (value: any): number | null => {
  if (value === null || value === undefined || value === '') return null;
  const n = Number(value);
  return Number.isFinite(n) ? n : null;
};

function mapPeerListResponse(data: any): PeerList {
  return {
    scope: data.scope,
    subject: data.subject ?? null,
    subject_label: data.subject_label ?? null,
    // Whitelisted rather than passed through: the frontend switches on this
    // value to choose a sentence, and an unrecognised one from a newer
    // backend should read as the common case rather than render nothing.
    reason: data.reason === 'no_region' || data.reason === 'no_nace' ? data.reason : null,
    ranked_by: data.ranked_by === 'similarity' ? 'similarity' : 'revenue',
    total_ranked: Number(data.total_ranked) || 0,
    total_in_scope: Number(data.total_in_scope) || 0,
    results: Array.isArray(data.results)
      ? data.results.map((item: any) => ({
          ico: item.ico,
          name: item.name || '',
          city: item.city || '',
          nace_code: item.nace_code || '',
          nace_name: item.nace_name ?? null,
          year: Number(item.year),
          revenue: toFiledAmount(item.revenue),
          profit: toFiledAmount(item.profit),
        }))
      : [],
  };
}

/**
 * The coverage counts, or `null` when the response did not carry them.
 *
 * `Number(undefined)` is NaN, which a `Number.isFinite` guard already rejects --
 * but `Number(null)` is `0`, and `0 z 0 firiem` is a flat statement about our
 * coverage that no response made. So absence is checked before conversion
 * rather than after it, and `null` travels to the screen, which says it cannot
 * quantify instead of saying zero.
 */
function mapCoverage(data: any): PersonCoverage | null {
  if (data?.companies_with_persons == null || data?.companies_total == null) return null;
  const withPersons = Number(data.companies_with_persons);
  const total = Number(data.companies_total);
  if (!Number.isFinite(withPersons) || !Number.isFinite(total)) return null;
  return { companies_with_persons: withPersons, companies_total: total };
}

/**
 * One relation: a company, a role, and whether the function still runs.
 *
 * **`is_active` keeps its third value.** `Boolean(data.is_active)` -- and any
 * `!!` or `|| false` beside it -- turns `null` into `false`, which is the one
 * thing this feature exists to prevent: it would print "skončila" about a
 * company whose history nobody has read. The comparison is written out three
 * ways so that an unrecognised value falls to `null` (we do not know) rather
 * than to a claim.
 *
 * The company arrives flat (`ico`, `name`, ...) from the backend's
 * `_relation_payload`. A nested `company: {ico, nazov_UJ}` was described for
 * this contract at one point and is read here too: choosing the wrong one would
 * render every person as being in no company at all, which is the same false
 * claim as above and harder to notice.
 */
export function mapPersonRelation(data: any): PersonRelation {
  const company = data?.company ?? null;
  return {
    ico: company?.ico ?? data?.ico ?? '',
    name: company?.nazov_UJ ?? data?.name ?? '',
    role: data?.role ?? '',
    // Empty and not the enum code: an unrecognised code is not a label, and a
    // row with no role reads as a missing field rather than as a role called
    // "konatel".
    role_display: data?.role_display ?? '',
    is_active: data?.is_active === true ? true : data?.is_active === false ? false : null,
    vznik_funkcie: data?.vznik_funkcie ?? null,
    zanik_funkcie: data?.zanik_funkcie ?? null,
    // Floored at 1, like `records` below and for the same reason: the field is
    // read as "how many filings this row stands for", and 0 or a missing field
    // must not render as "this row stands for nothing".
    intervals: Math.max(1, Number(data?.intervals) || 1),
  };
}

function mapPersonSummary(data: any): PersonSummary {
  return {
    id: Number(data?.id),
    name: data?.name ?? '',
    // Empty strings, not `undefined`: these are rendered directly, and the
    // difference between "absent" and "the string undefined" is a line that
    // reads `IČO: undefined`.
    title: data?.title ?? '',
    person_ico: data?.person_ico ?? '',
    // One is the honest floor, not zero: a summary came from at least one row,
    // and `Number(undefined) || 1` also covers an older response that predates
    // the field -- which described a person we hold one row for.
    records: Number(data?.records) || 1,
    companies: Array.isArray(data?.companies) ? data.companies.map(mapPersonRelation) : [],
  };
}

function mapPersonMember(data: any): PersonMember {
  return {
    id: Number(data?.id),
    name: data?.name ?? '',
    address: data?.address ?? '',
    // `null`, not `''`: a row whose section of the register stated no date is
    // not a row that stated an empty one, and the note prints nothing rather
    // than a placeholder -- there is no honest placeholder for "not stated"
    // next to a real date it has to be compared against.
    birth_date: data?.birth_date ?? null,
  };
}

/** Exported for its own spec, like the two mappers above and for the same reason. */
export function mapPersonSearchResponse(data: any): PersonSearchResponse {
  return {
    query: data?.query ?? '',
    role: data?.role ?? '',
    results: Array.isArray(data?.results) ? data.results.map(mapPersonSummary) : [],
    total_matches: Number(data?.total_matches) || 0,
    // `typeof === 'number'`, not `Number(x) || 0`: `Number(null)` is `0`, so a
    // conversion-first mapper would turn "we did not read far enough to count"
    // into "there are no people" -- a claim the response did not make, and the
    // exact opposite of the one it did.
    total_people: typeof data?.total_people === 'number' ? data.total_people : null,
    truncated: Boolean(data?.truncated),
    detail: data?.detail ?? null,
    coverage: mapCoverage(data?.coverage),
  };
}

export function mapPersonDetail(data: any): PersonDetail {
  return {
    id: Number(data?.id),
    name: data?.name ?? '',
    title: data?.title ?? '',
    person_ico: data?.person_ico ?? '',
    records: Number(data?.records) || 1,
    members: Array.isArray(data?.members) ? data.members.map(mapPersonMember) : [],
    companies: Array.isArray(data?.companies) ? data.companies.map(mapPersonRelation) : [],
    coverage: mapCoverage(data?.coverage),
  };
}

export function mapOrsrPersonSearchResponse(data: any): OrsrPersonSearchResponse {
  return {
    query: data?.query ?? '',
    hits: Array.isArray(data?.hits)
      ? data.hits.map((hit: any): OrsrPersonHit => ({
          person_name: hit?.person_name ?? '',
          company_name: hit?.company_name ?? '',
          current_url: hit?.current_url ?? '',
          full_url: hit?.full_url ?? '',
        }))
      : [],
    total: Number(data?.total) || 0,
    truncated: Boolean(data?.truncated),
    source_url: data?.source_url ?? '',
    // Not defaulted away. An empty string means the register answered; a
    // non-empty one means it did not, and the group renders the two
    // differently.
    error: data?.error ?? '',
    note: data?.note ?? '',
    detail: data?.detail ?? null,
    cached: Boolean(data?.cached),
  };
}

/**
 * Exported for its own spec.
 *
 * This is where two shapes meet, and it has already produced three wrong
 * screens by defaulting a field the API did not send: `riskScore ?? 100`, and
 * in the VAT block `vat_payer || false` plus `tax_reliability || 'Spoľahlivý'`.
 * A mapper is the one place where "absent" can quietly become a positive
 * claim, so it is tested directly rather than through a page.
 */
export function mapCompanyResponse(data: any): Company {
  const toAmount = (value: any): number => {
    const n = Number(value);
    return Number.isFinite(n) ? n : 0;
  };

  const debtVszp = toAmount(data.debt_vszp);
  const debtSocPoist = toAmount(data.debt_soc_poist);
  const debtTax = toAmount(data.tax_debt);

  // The one expression that reads the FS check date. `vatStatus.lastCheckedAt`
  // and `taxCheckedOn` are the same fact under two names -- the VAT block asks
  // "when did we last read the tax office", the debts section asks "did we ever"
  // -- and spelling `data.fs_update_date` twice is how those two would come to
  // disagree.
  const taxCheckedOn = data.fs_update_date ?? null;

  const debts = [
    ...(debtVszp > 0 ? [{ id: 'vszp', source: 'VšZP' as const, amountEur: debtVszp, dateOfRecord: data.last_insurance_debt }] : []),
    ...(debtSocPoist > 0 ? [{ id: 'sp', source: 'Sociálna poisťovňa' as const, amountEur: debtSocPoist, dateOfRecord: data.last_insurance_debt }] : []),
    ...(debtTax > 0 ? [{ id: 'fs', source: 'Finančná správa' as const, amountEur: debtTax, dateOfRecord: data.fs_update_date }] : []),
  ];

  // The register's second population, and the reason `debts` cannot carry it:
  // a `LISTED_NO_AMOUNT` company has `debt_soc_poist` NULL, so it builds no row
  // and its arrears read as zero. Read with `=== true` and not a truthy test:
  // the column is nullable, `null` means we never read the register, and a
  // default here would be the fourth wrong screen this mapper produced.
  const socialListedWithoutAmount =
    data.social_listed_without_amount === true ? true
      : data.social_listed_without_amount === false ? false
        : null;

  const totalDebt = debtVszp + debtSocPoist + debtTax;
  const hasDebt = totalDebt > 0;

  const financials = Array.isArray(data.financials)
    ? data.financials
        .map((item: any) => ({
          year: Number(item.year),
          revenue: toFiledAmount(item.revenue),
          profit: toFiledAmount(item.profit),
          profitAfterTax: toFiledAmount(item.profitAfterTax),
          totalRevenue: toFiledAmount(item.totalRevenue),
          costs: toFiledAmount(item.costs),
          addedValue: toFiledAmount(item.addedValue),
          incomeTax: toFiledAmount(item.incomeTax),
          incomeTaxPaid: toFiledAmount(item.incomeTaxPaid),
          assetsTotal: toFiledAmount(item.assetsTotal),
          assetsIntangible: toFiledAmount(item.assetsIntangible),
          assetsTangible: toFiledAmount(item.assetsTangible),
          assetsFinancial: toFiledAmount(item.assetsFinancial),
          assetsCurrent: toFiledAmount(item.assetsCurrent),
          assetsInventory: toFiledAmount(item.assetsInventory),
          assetsReceivablesLong: toFiledAmount(item.assetsReceivablesLong),
          assetsReceivablesShort: toFiledAmount(item.assetsReceivablesShort),
          assetsFinancialShort: toFiledAmount(item.assetsFinancialShort),
          assetsFinancialAccounts: toFiledAmount(item.assetsFinancialAccounts),
          assetsAccruals: toFiledAmount(item.assetsAccruals),
          equity: toFiledAmount(item.equity),
          equityBasic: toFiledAmount(item.equityBasic),
          equityCapitalFunds: toFiledAmount(item.equityCapitalFunds),
          equityProfitFunds: toFiledAmount(item.equityProfitFunds),
          equityRetained: toFiledAmount(item.equityRetained),
          liabilitiesTotal: toFiledAmount(item.liabilitiesTotal),
          liabilitiesReserves: toFiledAmount(item.liabilitiesReserves),
          liabilitiesLong: toFiledAmount(item.liabilitiesLong),
          liabilitiesShort: toFiledAmount(item.liabilitiesShort),
          liabilitiesAccruals: toFiledAmount(item.liabilitiesAccruals),
          debtRatio: item.debtRatio ?? null,
          grossMargin: item.grossMargin ?? null,
        }))
        .filter((item: any) => Number.isFinite(item.year))
        .sort((a: any, b: any) => a.year - b.year)
    : [];

  const executives = Array.isArray(data.executives)
    ? data.executives.map((item: any) => ({
        name: item.name || 'Neznáma osoba',
        role: item.role || 'Štatutár',
      }))
    : [];

  const connections = Array.isArray(data.connections)
    ? data.connections.map((item: any, index: number) => ({
        companyName: item.companyName || `Prepojenie ${index + 1}`,
        ico: item.ico || '',
        role: item.role || 'Prepojenie',
        status: item.status || 'Aktívna',
      }))
    : [];

  // The risk score comes from the API. It used to be built here, and this
  // copy is the one that made the phone and the desktop disagree with the
  // watchlist about the same company: the backend's watchlist entry read the
  // three debts and nothing else, so a company in the Altman bankruptcy zone
  // with no debt was 100/100 in the list and 80/100 on its own page. One
  // ladder, on the server, published by `CompanyDetailSerializer`.
  //
  // `score` stays `null` when the API did not send one. The `?? 100` that was
  // here meant a response missing the field rendered as a perfect 100/100 on
  // every company -- "nothing here to look at" -- with nothing logged.
  // `calculationDate` went with it: it was `new Date()`, a timestamp of when
  // the browser mapped the response, and no screen ever read it.
  const riskScore = {
    score: typeof data.riskScore?.score === 'number' ? data.riskScore.score : null,
    summary: data.riskScore?.summary ?? '',
    breakdown: data.riskScore?.breakdown ?? null,
  };

  return {
    id: data.id,
    ico: data.ico,
    // The tax number, sent from the beginning and named nowhere until now.
    dic: data.dic ?? null,
    name: data.nazov_UJ,
    legalForm: data.legal_form || 'Neznáma forma',
    status: data.datum_zrusenia ? 'Vymazaná' : 'Aktívna',
    registrationDate: data.datum_zalozenia,
    address: {
      street: data.ulica || '',
      city: data.mesto || '',
      zipCode: data.psc || '',
      country: 'Slovenská republika',
    },
    // Absent on search results, which is why this is `?? null` and not a
    // required field of the response. The backend sends `null` rather than a
    // fallback coordinate, and the two must stay distinguishable: a missing
    // field would silently become "no map" for a company we could place.
    seatLocation: data.seatLocation ?? null,
    lastUpdatedFromSource: data.datum_poslednej_upravy || new Date().toISOString(),
    // When we last read each debt source, or `null` for never. Read once here
    // and given to both consumers rather than letting the strip and the debts
    // section each reach for `data.fs_update_date` and drift apart.
    insuranceCheckedOn: data.last_insurance_debt ?? null,
    taxCheckedOn: taxCheckedOn,
    socialListedWithoutAmount,
    debts,
    vatStatus: {
      icDph: data.ic_dph,
      // No `|| false`. The column is nullable, 302 713 rows hold nothing, and
      // the fallback turned every one of them into "Neplatiteľ DPH" -- a
      // negative claim about a company the tax office simply did not mention.
      isVatPayer: data.vat_payer ?? null,
      // No `|| 'Spoľahlivý'` either. That fallback printed half the register as
      // *reliable* on no evidence, which is the reassuring direction of the
      // same mistake and the worse one in a risk tool.
      taxReliabilityIndex: data.tax_reliability ?? null,
      registeredOn: data.datum_reg_dph ?? null,
      // Was dropped on the floor. It is also the only field that tells a
      // company struck off the register from one that was never on it, since
      // most deregistrations carry no `Platiteľ DPH` value at all.
      deregisteredOn: data.vat_deleted_date ?? null,
      reasonForDeregistration: data.vat_deleted_reason,
      lastCheckedAt: taxCheckedOn,
    },
    riskScore,
    financials,
    // The backend names why the statement sections are empty; without it every
    // one of the four reasons renders as the same "nie sú k dispozícii". The
    // fallback is `not_fetched`, which is the only honest default: it is what a
    // missing field means, and it is the reason that promises a later attempt.
    financialsState: data.financialsState || 'not_fetched',
    executives,
    connections,
    orsr_profile: mapOrsrProfileResponse(data.orsr_profile),
    analysis: data.analysis || undefined,
    benchmark: data.benchmark || undefined,
    usesIfrs: data.uses_ifrs || false,
    ruzPortalUrl: data.ruz_portal_url || null,
    // Kept absent when absent, like every other figure here. `Number(x) || 0`
    // would turn a response that did not carry the field into a positive claim
    // that RUZ holds no statements for this company -- the same mistake the
    // risk score made when it defaulted to 100.
    ruzStatements: toFiledAmount(data.ruz_statements),
    ruzAnnualReports: toFiledAmount(data.ruz_annual_reports),
  };
}

export const api = {
  getLandingStats: async (): Promise<LandingStats> => {
    if (ENABLE_MOCK_DATA) {
      return new Promise((resolve) =>
        setTimeout(() => resolve({ companiesIndexed: 1250000, dailyChecks: 45000, riskyCompaniesDetected: 120 }), 500),
      );
    }
    return apiRequest<LandingStats>('/stats/landing/');
  },

  searchCompanies: async (query: string, options: RequestInit = {}): Promise<SearchResult> => {
    if (ENABLE_MOCK_DATA) {
      return new Promise((resolve) =>
        setTimeout(() => resolve({ results: [mockCompanyData] }), 500),
      );
    }
    return apiRequest<SearchResult>(`/companies/search/?q=${encodeURIComponent(query)}`, options);
  },

  getCompany: async (ico: string): Promise<Company> => {
    if (ENABLE_MOCK_DATA) {
      return new Promise((resolve, reject) => {
        setTimeout(() => {
          if (ico === '50059959') {
            resolve(mockCompanyData);
          } else if (ico === '12345678') {
            resolve({
              ...mockCompanyData,
              ico: '12345678',
              name: 'Stará Firma, a.s.',
              status: 'V likvidácii',
              riskScore: {
                score: 90,
                summary: 'Vysoké riziko.',
                breakdown: {
                  start: 100,
                  floor: 5,
                  clamped: false,
                  parts: [
                    { key: 'debt', label: 'Evidované nedoplatky', delta: -10, detail: 'žiadne' },
                    { key: 'zone', label: 'Altman Z-score', delta: 0, detail: 'bezpečná zóna' },
                    { key: 'roa', label: 'Rentabilita aktív', delta: 0, detail: '2,0 %' },
                  ],
                },
              },
            });
          } else if (ico.length !== 8) {
            reject(new Error('IČO musí mať 8 číslic.'));
          } else {
            resolve({
              ...mockCompanyData,
              ico,
              name: `Mock Firma ${ico}`,
              status: 'Aktívna',
              riskScore: {
                score: Math.floor(Math.random() * 100),
                summary: 'Automaticky generovaný mock.',
                // A generated mock has no factors behind it, so it carries no
                // breakdown rather than an invented one -- the section then
                // shows its "could not load" notice, which is what this data is.
                breakdown: null,
              },
            });
          }
        }, 600);
      });
    }
    const data = await apiRequest<any>(`/companies/${ico}/`);
    return mapCompanyResponse(data);
  },

  /**
   * Companies ranked next to this one. Four sections read this.
   *
   * The scope travels as a query parameter and is not defaulted here: each
   * value answers a different question, and a client-side default would hide
   * a caller that forgot to name one behind the wrong ranking.
   */
  getPeers: async (ico: string, scope: PeerScope): Promise<PeerList> => {
    if (ENABLE_MOCK_DATA) {
      // One entry per scope rather than a chain of ternaries: the two halves
      // have to come from the *same* scope, and a fallthrough would label a
      // size band with a NACE code, which reads as a band called "62".
      const mockSubject: Record<PeerScope, [string | null, string | null]> = {
        podobne: ['62', '62 — Počítačové programovanie'],
        kraj: ['SK010', 'Bratislavský kraj'],
        odvetvie: ['62', '62 — Počítačové programovanie'],
        trzby: [null, null],
        zamestnanci: ['04', '04 — 3-4 zamestnanci'],
      };
      return new Promise((resolve) =>
        setTimeout(
          () =>
            resolve({
              scope,
              // Both halves of the pair move together: a label with no subject
              // would be a narrowing that names nothing, which is the one
              // combination the real backend never sends.
              subject: mockSubject[scope][0],
              subject_label: mockSubject[scope][1],
              reason: null,
              ranked_by: scope === 'podobne' ? 'similarity' : 'revenue',
              total_ranked: 3,
              total_in_scope: 1250,
              results: [1, 2, 3].map((n) => ({
                ico: `5005995${n}`,
                name: `Mock Firma ${n}, s. r. o.`,
                city: 'Bratislava',
                nace_code: '62010',
                nace_name: 'Počítačové programovanie',
                year: 2023,
                revenue: 1_000_000 * n,
                profit: 50_000 * n,
              })),
            }),
          500,
        ),
      );
    }
    const data = await apiRequest<any>(`/companies/${ico}/peers/?scope=${encodeURIComponent(scope)}`);
    return mapPeerListResponse(data);
  },

  /**
   * The závierky downloadable for one company-year.
   *
   * The backend answers `503` with `state: 'unreachable'` when the register
   * cannot be read, so this rejects rather than resolving to an empty list --
   * and the rejection is caught by the caller, which says so. Resolving to
   * `documents: []` here would be the same substitution the state exists to
   * prevent, moved one layer up where it is harder to see.
   */
  getFinancialDocuments: async (ico: string, year: number): Promise<DocumentListing> => {
    if (ENABLE_MOCK_DATA) {
      return new Promise((resolve) =>
        setTimeout(
          () =>
            resolve({
              year,
              state: 'listed',
              documents: [
                {
                  id: `vykaz-${year}001`,
                  kind: 'vykaz',
                  name: `Účtovný výkaz ${year}`,
                  mimeType: 'application/pdf',
                  size: null,
                  pages: null,
                  url: `/api/companies/${ico}/financials/${year}/documents/vykaz-${year}001/`,
                },
                {
                  id: `priloha-${year}002`,
                  kind: 'priloha',
                  name: 'Príloha k účtovnej závierke MÚJ.PDF',
                  mimeType: 'application/pdf',
                  size: 852398,
                  pages: 4,
                  url: `/api/companies/${ico}/financials/${year}/documents/priloha-${year}002/`,
                },
              ],
            }),
          400,
        ),
      );
    }
    const data = await apiRequest<any>(`/companies/${ico}/financials/${year}/documents/`);
    return {
      year: Number(data?.year ?? year),
      // `?? 'unreachable'` and not `?? 'listed'`: a response that did not carry
      // a state is one we cannot read, and defaulting to `listed` would render
      // an empty list as "this company filed nothing".
      state: (data?.state ?? 'unreachable') as DocumentListing['state'],
      documents: Array.isArray(data?.documents) ? data.documents : [],
    };
  },

  login: async (identifier: string, password: string): Promise<LoginResult> => {
    if (ENABLE_MOCK_DATA) {
      return new Promise((resolve) => {
        setTimeout(() => {
          // No storage write here: `AuthContext.login` owns that, so the mock
          // session lands in the same place a real one does and the "remember"
          // box behaves the same either way.
          resolve({
            token: 'mock-jwt-token-12345',
            // A mock sign-in has no backend to refresh against.
            refresh: null,
            user: {
              id: 'u1',
              email: 'jozef@example.com',
              username: 'jmrkvicka',
              firstName: 'Jozef',
              lastName: 'Mrkvička',
              plan: 'plus',
              apiCallsUsed: 34,
              apiCallsLimit: 50,
              isStaff: false,
              isSuperuser: false,
            },
          });
        }, 1000);
      });
    }

    const tokenResponse = await apiRequest<TokenResponse>('/auth/token/', {
      method: 'POST',
      body: JSON.stringify({ email: identifier, password }),
    });

    const accessToken = tokenResponse.access || tokenResponse.token;
    if (!accessToken) {
      throw new Error('Server nevrátil prístupový token. Skontrolujte odpoveď backendu.');
    }

    const rawUserProfile = await apiRequest<RawUser>('/auth/profile/', {
      headers: { Authorization: `Bearer ${accessToken}` },
    });

    return {
      token: accessToken,
      refresh: tokenResponse.refresh ?? null,
      user: mapUserResponse(rawUserProfile),
    };
  },

  register: async (userData: UserPayload): Promise<{ success: boolean }> => {
    if (ENABLE_MOCK_DATA) {
      return new Promise((resolve) => setTimeout(() => resolve({ success: true }), 1500));
    }
    const payload = mapUserPayload(userData);
    return apiRequest<{ success: boolean }>('/auth/register/', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  },

  getProfile: async (): Promise<User> => {
    if (ENABLE_MOCK_DATA) {
      return new Promise((resolve) =>
        setTimeout(
          () =>
            resolve({
              id: 'u1',
              firstName: 'Jozef',
              lastName: 'Mrkvička',
              username: 'jmrkvicka',
              email: 'jozef@example.com',
              plan: 'plus',
              apiCallsUsed: 34,
              apiCallsLimit: 50,
              isStaff: false,
              isSuperuser: false,
            }),
          600,
        ),
      );
    }
    const rawData = await apiRequest<RawUser>('/auth/profile/');
    return mapUserResponse(rawData);
  },

  updateProfile: async (data: UserPayload): Promise<User> => {
    if (ENABLE_MOCK_DATA) {
      return new Promise((resolve) =>
        setTimeout(() => resolve(data as unknown as User), 1000),
      );
    }
    const payload = mapUserPayload(data);
    const rawData = await apiRequest<RawUser>('/auth/profile/', {
      method: 'PATCH',
      body: JSON.stringify(payload),
    });
    return mapUserResponse(rawData);
  },

  changePassword: async (oldPassword: string, newPassword: string): Promise<{ success: boolean }> => {
    if (ENABLE_MOCK_DATA) {
      return new Promise((resolve) => setTimeout(() => resolve({ success: true }), 1000));
    }
    return apiRequest<{ success: boolean }>('/auth/change-password/', {
      method: 'POST',
      body: JSON.stringify({ old_password: oldPassword, new_password: newPassword }),
    });
  },

  getWatchlist: async (): Promise<WatchlistEntry[]> => {
    if (ENABLE_MOCK_DATA) {
      return new Promise((resolve) =>
        setTimeout(
          () =>
            resolve([
              { id: 'w1', ico: '50059959', name: 'Quantum Solutions s. r. o.', status: 'Aktívna', riskScore: 68, addedAt: '2024-01-15' },
              { id: 'w2', ico: '12345678', name: 'Stará Firma, a.s.', status: 'V likvidácii', riskScore: 90, addedAt: '2023-11-20' },
              { id: 'w3', ico: '87654321', name: 'Tech Startup s.r.o.', status: 'Aktívna', riskScore: 12, addedAt: '2024-02-01' },
            ]),
          800,
        ),
      );
    }
    return apiRequest<WatchlistEntry[]>('/watchlist/');
  },

  addToWatchlist: async (ico: string): Promise<{ success: boolean }> => {
    if (ENABLE_MOCK_DATA) {
      return new Promise((resolve) => setTimeout(() => resolve({ success: true }), 600));
    }
    return apiRequest<{ success: boolean }>('/watchlist/', {
      method: 'POST',
      body: JSON.stringify({ ico }),
    });
  },

  removeFromWatchlist: async (id: string): Promise<{ success: boolean }> => {
    if (ENABLE_MOCK_DATA) {
      return new Promise((resolve) => setTimeout(() => resolve({ success: true }), 600));
    }
    return apiRequest<{ success: boolean }>(`/watchlist/${id}/`, { method: 'DELETE' });
  },

  getHistory: async (): Promise<HistoryEntry[]> => {
    if (ENABLE_MOCK_DATA) {
      return new Promise((resolve) =>
        setTimeout(
          () =>
            resolve([
              { id: 'h1', ico: '50059959', name: 'Quantum Solutions s. r. o.', searchedAt: '2024-02-10T14:30:00' },
              { id: 'h2', ico: '33322211', name: 'Stavebniny XY', searchedAt: '2024-02-09T09:15:00' },
              { id: 'h3', ico: '11111111', name: 'Neznáma firma', searchedAt: '2024-02-08T18:45:00' },
            ]),
          800,
        ),
      );
    }
    return apiRequest<HistoryEntry[]>('/history/');
  },

  // ── Persons ──

  /**
   * Our own person graph, searched by name.
   *
   * Ours, and therefore partial: we hold relations for a fraction of the
   * register, which is why every response carries `coverage` and why the screen
   * that renders the results is required to print it. An empty list without it
   * reads as "this person is in no company", which is a different and false
   * claim.
   *
   * `options` exists for the same reason `searchCompanies` has it: the search
   * box aborts the previous request as the reader keeps typing, and a request
   * that cannot be aborted keeps a third keystroke's answer on screen.
   */
  searchPersons: async (
    query: string,
    role?: string,
    options: RequestInit = {},
  ): Promise<PersonSearchResponse> => {
    const params = new URLSearchParams({ q: query });
    if (role) params.set('role', role);
    const data = await apiRequest<any>(`/persons/?${params.toString()}`, options);
    return mapPersonSearchResponse(data);
  },

  getPerson: async (id: number | string): Promise<PersonDetail> => {
    const data = await apiRequest<any>(`/persons/${id}/`);
    return mapPersonDetail(data);
  },

  /**
   * The live ORSR register, asked by name.
   *
   * Deliberately not part of any autocomplete: this is somebody else's server,
   * rate-limited to 60 requests an hour per caller and cached for 15 minutes,
   * and it must be reached only from a button the reader pressed. Nothing that
   * reacts to typing may call this, ever -- see `OrsrRegisterGroup`, which is
   * the only caller, and `SearchBar`, which must not become the second one.
   */
  searchOrsrPersons: async (query: string): Promise<OrsrPersonSearchResponse> => {
    const data = await apiRequest<any>(`/persons/orsr/?q=${encodeURIComponent(query)}`);
    return mapOrsrPersonSearchResponse(data);
  },

  // ── Notifications ──

  getNotifications: async (): Promise<NotificationEvent[]> => {
    return apiRequest<NotificationEvent[]>('/notifications/events/');
  },

  /**
   * The notifications *this account* was sent about one company.
   *
   * The company is a filter on the signed-in user's own mailbox, not a
   * property of the company: the same URL answers differently for two people,
   * and read without an account it is a 401 rather than an empty list. The
   * section that calls this is behind `useAuth` for exactly that reason.
   */
  getCompanyEvents: async (ico: string): Promise<NotificationEvent[]> => {
    return apiRequest<NotificationEvent[]>(
      `/notifications/events/?ico=${encodeURIComponent(ico)}`
    );
  },

  getNotificationPreferences: async (): Promise<NotificationPreferences> => {
    return apiRequest<NotificationPreferences>('/notifications/preferences/');
  },

  updateNotificationPreferences: async (data: Partial<NotificationPreferences>): Promise<NotificationPreferences> => {
    return apiRequest<NotificationPreferences>('/notifications/preferences/update_preferences/', {
      method: 'PATCH',
      body: JSON.stringify(data),
    });
  },
};
