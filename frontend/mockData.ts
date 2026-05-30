
import type { Company } from './types';

export const mockCompanyData: Company = {
  id: 'a1b2c3d4-e5f6-7890-1234-567890abcdef',
  ico: '50059959',
  name: 'Quantum Solutions s. r. o.',
  legalForm: 'Spoločnosť s ručením obmedzeným',
  status: 'Aktívna',
  registrationDate: '2015-10-21',
  address: {
    street: 'Mlynské nivy 42',
    city: 'Bratislava',
    zipCode: '821 09',
    country: 'Slovenská republika',
  },
  lastUpdatedFromSource: new Date().toISOString(),
  debts: [
    { id: 'd1', source: 'Sociálna poisťovňa', amountEur: 1250.75, dateOfRecord: '2024-07-15' },
    { id: 'd2', source: 'Finančná správa', amountEur: 840.00, dateOfRecord: '2024-07-10' },
  ],
  vatStatus: {
    icDph: 'SK2120159999',
    isVatPayer: true,
    taxReliabilityIndex: 'Spoľahlivý',
    reasonForDeregistration: null,
    lastCheckedAt: new Date().toISOString(),
  },
  riskScore: {
    score: 68,
    summary: 'Spoločnosť vykazuje mierne riziko z dôvodu existujúcich nedoplatkov. Finančné výsledky sú stabilné.',
    calculationDate: new Date().toISOString(),
  },
  financials: [
    { year: 2021, revenue: 1250000, profit: 85000, totalRevenue: 1300000, costs: 1165000, incomeTax: 18000, incomeTaxPaid: 18000, assetsTotal: 2100000, assetsIntangible: 50000, assetsTangible: 800000, assetsFinancial: 100000, assetsInventory: 200000, assetsReceivablesLong: 50000, assetsReceivablesShort: 600000, assetsFinancialAccounts: 250000, assetsAccruals: 50000, equity: 900000, equityBasic: 200000, equityCapitalFunds: 0, equityProfitFunds: 100000, equityRetained: 515000, liabilitiesTotal: 1150000, liabilitiesReserves: 50000, liabilitiesLong: 400000, liabilitiesShort: 700000, liabilitiesAccruals: 50000, debtRatio: 57.14, grossMargin: 10.8 },
    { year: 2022, revenue: 1420000, profit: 110000, totalRevenue: 1480000, costs: 1310000, incomeTax: 23000, incomeTaxPaid: 23000, assetsTotal: 2300000, assetsIntangible: 45000, assetsTangible: 850000, assetsFinancial: 120000, assetsInventory: 220000, assetsReceivablesLong: 40000, assetsReceivablesShort: 650000, assetsFinancialAccounts: 320000, assetsAccruals: 55000, equity: 1010000, equityBasic: 200000, equityCapitalFunds: 0, equityProfitFunds: 120000, equityRetained: 580000, liabilitiesTotal: 1230000, liabilitiesReserves: 60000, liabilitiesLong: 380000, liabilitiesShort: 790000, liabilitiesAccruals: 60000, debtRatio: 56.09, grossMargin: 11.27 },
    { year: 2023, revenue: 1380000, profit: 95000, totalRevenue: 1440000, costs: 1285000, incomeTax: 20000, incomeTaxPaid: 20000, assetsTotal: 2250000, assetsIntangible: 40000, assetsTangible: 820000, assetsFinancial: 130000, assetsInventory: 210000, assetsReceivablesLong: 35000, assetsReceivablesShort: 630000, assetsFinancialAccounts: 330000, assetsAccruals: 55000, equity: 1050000, equityBasic: 200000, equityCapitalFunds: 0, equityProfitFunds: 130000, equityRetained: 625000, liabilitiesTotal: 1140000, liabilitiesReserves: 55000, liabilitiesLong: 350000, liabilitiesShort: 735000, liabilitiesAccruals: 60000, debtRatio: 53.33, grossMargin: 11.23 },
  ],
   executives: [
       { name: 'Ing. Ján Vážny', role: 'Konateľ' },
       { name: 'Mgr. Eva Múdra', role: 'Konateľ' },
       { name: 'Ján Vážny - 50%', role: 'Spoločník' },
       { name: 'Future Investments, s.r.o. - 50%', role: 'Spoločník' },
       { name: 'Ing. Peter Procházka', role: 'Prokurista' },
   ],
   connections: [
       { companyName: 'Cyber Systems, a.s.', ico: '12345678', role: 'Konateľ (Ing. Ján Vážny)', status: 'V konkurze'},
       { companyName: 'Old Ventures, s.r.o.', ico: '87654321', role: 'Spoločník (Future Investments, s.r.o.)', status: 'V likvidácii'},
       { companyName: 'Innovate Group, s.r.o.', ico: '11223344', role: 'Konateľ (Mgr. Eva Múdra)', status: 'Aktívna'}
   ],
   orsr_profile: {
     oddiel: 'Sr',
     vlozka_cislo: '123/S',
     obchodne_meno: 'Quantum Solutions s. r. o.',
     sidlo: 'Mlynské nivy 42, 821 09 Bratislava',
     den_zapisu: '2015-10-21',
     pravna_forma: 'Spoločnosť s ručením obmedzeným',
     prokura: ['Prokúra na podpis: Ing. Peter Procházka'],
     spolocnici: ['Ján Vážny - 50%', 'Future Investments, s.r.o. - 50%'],
     statutarny_organ: ['Ing. Ján Vážny', 'Mgr. Eva Múdra'],
     vklady_spolocnikov: ['Ján Vážny: 50 000 EUR', 'Future Investments, s.r.o.: 50 000 EUR'],
     vyska_zakladneho_imania: '100 000 EUR',
     predmet_podnikania: [
       'Poskytovanie služieb v oblasti IT',
       'Vývoj softvérových aplikácií',
       'Poradenstvo v oblasti informačných technológií',
       'Predaj a servisy počítačovej techniky',
       'Predaj počítačového softvéru',
     ],
     orsr_aktualizacia_dat: '2024-07-15',
     orsr_datum_vypisu: '2024-07-20',
     fetch_ok: true,
     last_error: '',
   }
};
