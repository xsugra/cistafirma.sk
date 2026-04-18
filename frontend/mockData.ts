
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
    { year: 2021, revenue: 1250000, profit: 85000 },
    { year: 2022, revenue: 1420000, profit: 110000 },
    { year: 2023, revenue: 1380000, profit: 95000 },
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
