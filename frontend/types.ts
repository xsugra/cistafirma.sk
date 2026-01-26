
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
    role: 'Konateľ' | 'Spoločník' | 'Prokurista';
}

export interface Connection {
    companyName: string;
    ico: string;
    role: string;
    status: 'Aktívna' | 'V likvidácii' | 'V konkurze';
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
