import {mockCompanyData} from './mockData';
import {ENABLE_MOCK_DATA} from './constants';
import {apiRequest} from './lib/apiClient';
import type {
  Company,
  HistoryEntry,
  NotificationEvent,
  NotificationPreferences,
  OrsrProfile,
  PeerList,
  PeerScope,
  User,
  WatchlistEntry,
} from './types';

interface RawUser {
  id: string;
  email: string;
  username: string;
  first_name?: string;
  last_name?: string;
  subscription_plan?: string;
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
}

interface LoginResult {
  token: string;
  user: User;
}

function mapUserResponse(data: RawUser): User {
  return {
    id: data.id,
    email: data.email,
    username: data.username,
    firstName: data.first_name || '',
    lastName: data.last_name || '',
    plan: (data.subscription_plan as User['plan']) || 'free',
    apiCallsUsed: data.api_calls_used || 0,
    apiCallsLimit: data.api_calls_limit || 10,
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

function mapCompanyResponse(data: any): Company {
  const toAmount = (value: any): number => {
    const n = Number(value);
    return Number.isFinite(n) ? n : 0;
  };

  const debtVszp = toAmount(data.debt_vszp);
  const debtSocPoist = toAmount(data.debt_soc_poist);
  const debtTax = toAmount(data.tax_debt);

  const debts = [
    ...(debtVszp > 0 ? [{ id: 'vszp', source: 'VšZP' as const, amountEur: debtVszp, dateOfRecord: data.last_insurance_debt }] : []),
    ...(debtSocPoist > 0 ? [{ id: 'sp', source: 'Sociálna poisťovňa' as const, amountEur: debtSocPoist, dateOfRecord: data.last_insurance_debt }] : []),
    ...(debtTax > 0 ? [{ id: 'fs', source: 'Finančná správa' as const, amountEur: debtTax, dateOfRecord: data.fs_update_date }] : []),
  ];

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
          assetsInventory: toFiledAmount(item.assetsInventory),
          assetsReceivablesLong: toFiledAmount(item.assetsReceivablesLong),
          assetsReceivablesShort: toFiledAmount(item.assetsReceivablesShort),
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
    lastUpdatedFromSource: data.datum_poslednej_upravy || new Date().toISOString(),
    debts,
    vatStatus: {
      icDph: data.ic_dph,
      isVatPayer: data.vat_payer,
      taxReliabilityIndex: data.tax_reliability || 'Spoľahlivý',
      reasonForDeregistration: data.vat_deleted_reason,
      lastCheckedAt: data.fs_update_date,
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
      return new Promise((resolve) =>
        setTimeout(
          () =>
            resolve({
              scope,
              // Both halves of the pair move together: a label with no subject
              // would be a narrowing that names nothing, which is the one
              // combination the real backend never sends.
              subject: scope === 'trzby' ? null : scope === 'kraj' ? 'SK010' : '62',
              subject_label:
                scope === 'trzby' ? null
                  : scope === 'kraj' ? 'Bratislavský kraj'
                    : '62 — Počítačové programovanie',
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

  login: async (identifier: string, password: string): Promise<LoginResult> => {
    if (ENABLE_MOCK_DATA) {
      return new Promise((resolve) => {
        setTimeout(() => {
          localStorage.setItem('token', 'mock-jwt-token-12345');
          resolve({
            token: 'mock-jwt-token-12345',
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

    return { token: accessToken, user: mapUserResponse(rawUserProfile) };
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

  // ── Notifications ──

  getNotifications: async (): Promise<NotificationEvent[]> => {
    return apiRequest<NotificationEvent[]>('/notifications/events/');
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
