import { mockCompanyData } from './mockData';
import { ENABLE_MOCK_DATA } from './constants';
import { apiRequest } from './lib/apiClient';
import type {
  Company,
  User,
  WatchlistEntry,
  HistoryEntry,
  OrsrProfile,
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
          revenue: toAmount(item.revenue),
          profit: toAmount(item.profit),
          totalRevenue: toAmount(item.totalRevenue),
          costs: toAmount(item.costs),
          incomeTax: toAmount(item.incomeTax),
          incomeTaxPaid: toAmount(item.incomeTaxPaid),
          assetsTotal: toAmount(item.assetsTotal),
          assetsIntangible: toAmount(item.assetsIntangible),
          assetsTangible: toAmount(item.assetsTangible),
          assetsFinancial: toAmount(item.assetsFinancial),
          assetsInventory: toAmount(item.assetsInventory),
          assetsReceivablesLong: toAmount(item.assetsReceivablesLong),
          assetsReceivablesShort: toAmount(item.assetsReceivablesShort),
          assetsFinancialAccounts: toAmount(item.assetsFinancialAccounts),
          assetsAccruals: toAmount(item.assetsAccruals),
          equity: toAmount(item.equity),
          equityBasic: toAmount(item.equityBasic),
          equityCapitalFunds: toAmount(item.equityCapitalFunds),
          equityProfitFunds: toAmount(item.equityProfitFunds),
          equityRetained: toAmount(item.equityRetained),
          liabilitiesTotal: toAmount(item.liabilitiesTotal),
          liabilitiesReserves: toAmount(item.liabilitiesReserves),
          liabilitiesLong: toAmount(item.liabilitiesLong),
          liabilitiesShort: toAmount(item.liabilitiesShort),
          liabilitiesAccruals: toAmount(item.liabilitiesAccruals),
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

  const riskScore = hasDebt ? Math.max(5, 70 - Math.min(totalDebt / 5000, 50)) : 100;

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
    riskScore: {
      score: Math.round(riskScore),
      summary: hasDebt
        ? 'Spoločnosť vykazuje riziko z dôvodu existujúcich nedoplatkov.'
        : 'Spoločnosť vyzerá byť v dobrom finančnom zdraví.',
      calculationDate: new Date().toISOString(),
    },
    financials,
    executives,
    connections,
    orsr_profile: mapOrsrProfileResponse(data.orsr_profile),
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

  searchCompanies: async (query: string): Promise<SearchResult> => {
    if (ENABLE_MOCK_DATA) {
      return new Promise((resolve) =>
        setTimeout(() => resolve({ results: [mockCompanyData] }), 500),
      );
    }
    return apiRequest<SearchResult>(`/companies/search/?q=${encodeURIComponent(query)}`);
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
              riskScore: { score: 90, summary: 'Vysoké riziko.', calculationDate: new Date().toISOString() },
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
                calculationDate: new Date().toISOString(),
              },
            });
          }
        }, 600);
      });
    }
    const data = await apiRequest<any>(`/companies/${ico}/`);
    return mapCompanyResponse(data);
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
};
