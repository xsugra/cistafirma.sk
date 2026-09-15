import type {Company} from './types';

export const mockCompanyData: Company = {
  id: 'a1b2c3d4-e5f6-7890-1234-567890abcdef',
  ico: '50059959',
  dic: '2120159999',
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
  // The real imported area for PSČ 821 09, read out of `PostalCodeArea` rather
  // than invented -- a mock with made-up coordinates would place the demo pin
  // somewhere the register does not, which is the one thing this card must not
  // do. 1 047 address points, 737 m, Bratislava-Ružinov.
  seatLocation: {
    lat: 48.14748,
    lon: 17.14051,
    radiusM: 737,
    psc: '82109',
    precision: 'postal_code',
  },
  lastUpdatedFromSource: new Date().toISOString(),
  insuranceCheckedOn: '2026-09-10T00:00:00Z',
  taxCheckedOn: '2026-09-12T00:00:00Z',
  // The register's two SP populations are complementary in the rows measured on
  // 2026-09-15 (43 of 50 carried a sum, 5 carried a dash and missing periods),
  // and this fixture is one of the first: it owes money, so it is not listed
  // for a reporting breach.
  socialListedWithoutAmount: false,
  debts: [
    { id: 'd1', source: 'Sociálna poisťovňa', amountEur: 1250.75, dateOfRecord: '2024-07-15' },
    { id: 'd2', source: 'Finančná správa', amountEur: 840.00, dateOfRecord: '2024-07-10' },
  ],
  vatStatus: {
    icDph: 'SK2120159999',
    isVatPayer: true,
    // Spelled the way the register spells it — lowercase, and one of the three
    // values it actually holds. The fixture used to say 'Spoľahlivý', a
    // capitalised form that appears in no row of `"Companies and SZCO"`.
    taxReliabilityIndex: 'spoľahlivý',
    registeredOn: '2010-03-01',
    deregisteredOn: null,
    reasonForDeregistration: null,
    lastCheckedAt: new Date().toISOString(),
  },
  riskScore: {
    score: 68,
    summary: 'Spoločnosť vykazuje mierne riziko z dôvodu existujúcich nedoplatkov. Finančné výsledky sú stabilné.',
    breakdown: {
      start: 100,
      floor: 5,
      clamped: false,
      parts: [
        { key: 'debt', label: 'Evidované nedoplatky', delta: -32, detail: '10 000 €' },
        { key: 'zone', label: 'Altman Z-score', delta: 0, detail: 'bezpečná zóna' },
        { key: 'roa', label: 'Rentabilita aktív', delta: 0, detail: '5,2 %' },
      ],
    },
  },
  financials: [
    { year: 2021, revenue: 1250000, profit: 85000, profitAfterTax: 67000, totalRevenue: 1300000, costs: 1165000, incomeTax: 18000, incomeTaxPaid: 18000, assetsTotal: 2100000, assetsIntangible: 50000, assetsTangible: 800000, assetsFinancial: 100000, assetsInventory: 200000, assetsReceivablesLong: 50000, assetsReceivablesShort: 600000, assetsFinancialAccounts: 250000, assetsAccruals: 50000, equity: 900000, equityBasic: 200000, equityCapitalFunds: 0, equityProfitFunds: 100000, equityRetained: 515000, liabilitiesTotal: 1150000, liabilitiesReserves: 50000, liabilitiesLong: 400000, liabilitiesShort: 700000, liabilitiesAccruals: 50000, debtRatio: 57.14, grossMargin: 10.8 },
    { year: 2022, revenue: 1420000, profit: 110000, profitAfterTax: 87000, totalRevenue: 1480000, costs: 1310000, incomeTax: 23000, incomeTaxPaid: 23000, assetsTotal: 2300000, assetsIntangible: 45000, assetsTangible: 850000, assetsFinancial: 120000, assetsInventory: 220000, assetsReceivablesLong: 40000, assetsReceivablesShort: 650000, assetsFinancialAccounts: 320000, assetsAccruals: 55000, equity: 1010000, equityBasic: 200000, equityCapitalFunds: 0, equityProfitFunds: 120000, equityRetained: 580000, liabilitiesTotal: 1230000, liabilitiesReserves: 60000, liabilitiesLong: 380000, liabilitiesShort: 790000, liabilitiesAccruals: 60000, debtRatio: 56.09, grossMargin: 11.27 },
    { year: 2023, revenue: 1380000, profit: 95000, profitAfterTax: 75000, totalRevenue: 1440000, costs: 1285000, incomeTax: 20000, incomeTaxPaid: 20000, assetsTotal: 2250000, assetsIntangible: 40000, assetsTangible: 820000, assetsFinancial: 130000, assetsInventory: 210000, assetsReceivablesLong: 35000, assetsReceivablesShort: 630000, assetsFinancialAccounts: 330000, assetsAccruals: 55000, equity: 1050000, equityBasic: 200000, equityCapitalFunds: 0, equityProfitFunds: 130000, equityRetained: 625000, liabilitiesTotal: 1140000, liabilitiesReserves: 55000, liabilitiesLong: 350000, liabilitiesShort: 735000, liabilitiesAccruals: 60000, debtRatio: 53.33, grossMargin: 11.23 },
  ],
  // This fixture files three complete years, so the sections have something to
  // draw. `ready` is the state the backend reports for a company with rows.
  financialsState: 'ready',
  // One more than we read, which is the ordinary case in the live register and
  // exercises the notice that says so. The counts are RUZ's, the years above are
  // ours, and nothing joins the two lists -- which is the whole point of the
  // Účtovné závierky section.
  ruzStatements: 4,
  ruzAnnualReports: 1,
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
   },
    usesIfrs: false,
    ruzPortalUrl: null,
};
