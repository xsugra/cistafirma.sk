import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { formatNumber } from '../../utils/format';
import { adminApi } from '../api';
import type { AdminCompany, CompanyPreset, CompanyReport, SavedCompanyFilter } from '../types';

type FilterRecord = Record<string, string>;

const EMPTY_FILTERS = {
  search: '',
  activeFilter: '',
  cityFilter: '',
  pscFilter: '',
  naceFilter: '',
  legalFormFilter: '',
  krajFilter: '',
  sizeFilter: '',
  debtFilter: '',
  profitFilter: '',
  financialsFilter: '',
  orsrFilter: '',
  vatFilter: '',
  taxReliabilityFilter: '',
  leadScoreMin: '',
  leadScoreMax: '',
  syncFilter: '',
  confidenceMin: '',
  financialYear: '',
};

export function Companies() {
  const [companies, setCompanies] = useState<AdminCompany[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [report, setReport] = useState<CompanyReport | null>(null);
  const [savedFilters, setSavedFilters] = useState<SavedCompanyFilter[]>([]);
  const [savedFilterName, setSavedFilterName] = useState('');
  const [savedFilterDescription, setSavedFilterDescription] = useState('');
  const [selectedPresetKey, setSelectedPresetKey] = useState('');
  const [selectedSavedFilterId, setSelectedSavedFilterId] = useState('');
  const [savingFilter, setSavingFilter] = useState(false);
  const [search, setSearch] = useState(EMPTY_FILTERS.search);
  const [activeFilter, setActiveFilter] = useState(EMPTY_FILTERS.activeFilter);
  const [cityFilter, setCityFilter] = useState(EMPTY_FILTERS.cityFilter);
  const [pscFilter, setPscFilter] = useState(EMPTY_FILTERS.pscFilter);
  const [naceFilter, setNaceFilter] = useState(EMPTY_FILTERS.naceFilter);
  const [legalFormFilter, setLegalFormFilter] = useState(EMPTY_FILTERS.legalFormFilter);
  const [krajFilter, setKrajFilter] = useState(EMPTY_FILTERS.krajFilter);
  const [sizeFilter, setSizeFilter] = useState(EMPTY_FILTERS.sizeFilter);
  const [debtFilter, setDebtFilter] = useState(EMPTY_FILTERS.debtFilter);
  const [profitFilter, setProfitFilter] = useState(EMPTY_FILTERS.profitFilter);
  const [financialsFilter, setFinancialsFilter] = useState(EMPTY_FILTERS.financialsFilter);
  const [orsrFilter, setOrsrFilter] = useState(EMPTY_FILTERS.orsrFilter);
  const [vatFilter, setVatFilter] = useState(EMPTY_FILTERS.vatFilter);
  const [taxReliabilityFilter, setTaxReliabilityFilter] = useState(EMPTY_FILTERS.taxReliabilityFilter);
  const [leadScoreMin, setLeadScoreMin] = useState(EMPTY_FILTERS.leadScoreMin);
  const [leadScoreMax, setLeadScoreMax] = useState(EMPTY_FILTERS.leadScoreMax);
  const [syncFilter, setSyncFilter] = useState(EMPTY_FILTERS.syncFilter);
  const [confidenceMin, setConfidenceMin] = useState(EMPTY_FILTERS.confidenceMin);
  const [financialYear, setFinancialYear] = useState(EMPTY_FILTERS.financialYear);

  const params = useMemo(() => compactParams({
    q: search,
    active: activeFilter,
    mesto: cityFilter,
    psc: pscFilter,
    sk_nace: naceFilter,
    pravna_forma: legalFormFilter,
    kraj: krajFilter,
    velkost_organizacie: sizeFilter,
    debt_state: debtFilter,
    profit_state: profitFilter,
    has_financials: financialsFilter,
    has_orsr: orsrFilter,
    vat_payer: vatFilter,
    tax_reliability: taxReliabilityFilter,
    lead_score_min: leadScoreMin,
    lead_score_max: leadScoreMax,
    sync_state: syncFilter,
    confidence_min: confidenceMin,
    financial_year: financialYear,
  }), [
    search,
    activeFilter,
    cityFilter,
    pscFilter,
    naceFilter,
    legalFormFilter,
    krajFilter,
    sizeFilter,
    debtFilter,
    profitFilter,
    financialsFilter,
    orsrFilter,
    vatFilter,
    taxReliabilityFilter,
    leadScoreMin,
    leadScoreMax,
    syncFilter,
    confidenceMin,
    financialYear,
  ]);

  const loadSavedFilters = useCallback(() => {
    adminApi.listCompanyFilters()
      .then(res => setSavedFilters(res.results || []))
      .catch(e => setError(e.message));
  }, []);

  const fetchData = useCallback(() => {
    setLoading(true);
    setError('');

    adminApi.listCompanies(params)
      .then(companiesRes => {
        setCompanies(Array.isArray(companiesRes) ? companiesRes : companiesRes.results || []);
      })
      .catch(e => setError(e.message))
      .finally(() => setLoading(false));

    adminApi.companyReport(params)
      .then(reportRes => setReport(reportRes))
      .catch(e => {
        // Keep list responsive even if report summary fails or is delayed.
        setError(prev => prev || e.message);
      });
  }, [params]);

  useEffect(() => {
    fetchData();
    loadSavedFilters();
  }, [fetchData, loadSavedFilters]);

  const resetFilters = () => {
    setSearch('');
    setActiveFilter('');
    setCityFilter('');
    setPscFilter('');
    setNaceFilter('');
    setLegalFormFilter('');
    setKrajFilter('');
    setSizeFilter('');
    setDebtFilter('');
    setProfitFilter('');
    setFinancialsFilter('');
    setOrsrFilter('');
    setVatFilter('');
    setTaxReliabilityFilter('');
    setLeadScoreMin('');
    setLeadScoreMax('');
    setSyncFilter('');
    setConfidenceMin('');
    setFinancialYear('');
    setSelectedPresetKey('');
    setSelectedSavedFilterId('');
  };

  const applyFilterRecord = (filters: FilterRecord) => {
    setSearch(filters.q || '');
    setActiveFilter(filters.active || '');
    setCityFilter(filters.mesto || '');
    setPscFilter(filters.psc || '');
    setNaceFilter(filters.sk_nace || '');
    setLegalFormFilter(filters.pravna_forma || '');
    setKrajFilter(filters.kraj || '');
    setSizeFilter(filters.velkost_organizacie || '');
    setDebtFilter(filters.debt_state || '');
    setProfitFilter(filters.profit_state || '');
    setFinancialsFilter(filters.has_financials || '');
    setOrsrFilter(filters.has_orsr || '');
    setVatFilter(filters.vat_payer || '');
    setTaxReliabilityFilter(filters.tax_reliability || '');
    setLeadScoreMin(filters.lead_score_min || '');
    setLeadScoreMax(filters.lead_score_max || '');
    setSyncFilter(filters.sync_state || '');
    setConfidenceMin(filters.confidence_min || '');
    setFinancialYear(filters.financial_year || '');
  };

  const applyPreset = () => {
    const preset = report?.presets?.find(p => p.key === selectedPresetKey);
    if (!preset) return;
    applyFilterRecord(preset.filters);
  };

  const applySavedFilter = () => {
    const saved = savedFilters.find(f => String(f.id) === selectedSavedFilterId);
    if (!saved) return;
    applyFilterRecord(saved.filters);
  };

  const saveCurrentFilter = async () => {
    if (!savedFilterName.trim()) {
      setError('Zadaj názov uloženého filtra.');
      return;
    }
    setSavingFilter(true);
    try {
      await adminApi.saveCompanyFilter({
        name: savedFilterName.trim(),
        description: savedFilterDescription.trim(),
        filters: params,
        is_favorite: false,
      });
      setSavedFilterName('');
      setSavedFilterDescription('');
      loadSavedFilters();
    } catch (e: any) {
      setError(e.message);
    } finally {
      setSavingFilter(false);
    }
  };

  const toggleFavorite = async (item: SavedCompanyFilter) => {
    try {
      await adminApi.updateCompanyFilter(item.id, { is_favorite: !item.is_favorite });
      loadSavedFilters();
    } catch (e: any) {
      setError(e.message);
    }
  };

  const deleteSavedFilter = async (id: number) => {
    try {
      await adminApi.deleteCompanyFilter(id);
      loadSavedFilters();
    } catch (e: any) {
      setError(e.message);
    }
  };

  const downloadReport = async (format: 'csv' | 'xlsx') => {
    try {
      const blob = await adminApi.downloadCompanyReport(format, params);
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `companies-report.${format}`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
    } catch (e: any) {
      setError(e.message);
    }
  };

  const presets = report?.presets || [];

  return (
    <div className="space-y-4">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <h1 className="text-2xl font-bold text-slate-900 dark:text-white">Firmy</h1>
        <div className="flex flex-wrap gap-2">
          <button onClick={() => fetchData()} className="px-3 py-2 rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 text-sm text-slate-700 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-slate-700 transition-colors">
            Obnoviť
          </button>
          <button onClick={resetFilters} className="px-3 py-2 rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 text-sm text-slate-700 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-slate-700 transition-colors">
            Reset filtrov
          </button>
          <button onClick={() => downloadReport('csv')} className="px-3 py-2 rounded-lg bg-emerald-600 text-white text-sm hover:bg-emerald-700 transition-colors">
            Export CSV
          </button>
          <button onClick={() => downloadReport('xlsx')} className="px-3 py-2 rounded-lg bg-blue-600 text-white text-sm hover:bg-blue-700 transition-colors">
            Export XLSX
          </button>
        </div>
      </div>

      {report && (
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
          <SummaryCard label="Výsledky" value={report.count} />
          <SummaryCard label="Aktívne" value={report.active_count} />
          <SummaryCard label="Bez dlhov" value={report.debt_free_count} />
          <SummaryCard label="Priem. score" value={report.avg_lead_score.toFixed(1)} />
        </div>
      )}

      {report && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-3">
          <SummaryCard label="Súčet tržieb" value={formatMoney(report.revenue_sum)} />
          <SummaryCard label="Súčet zisku" value={formatMoney(report.profit_sum)} />
          <SummaryCard label="Súčet daňových dlhov" value={formatMoney(report.tax_debt_sum)} />
        </div>
      )}

      <div className="bg-white dark:bg-slate-800/60 rounded-xl border border-slate-200 dark:border-slate-700/50 p-4 space-y-4">
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-3">
          <label className="space-y-1 block">
            <span className="block text-xs font-medium text-slate-500 dark:text-slate-400">Preset filtre</span>
            <select value={selectedPresetKey} onChange={e => setSelectedPresetKey(e.target.value)} className="w-full px-3 py-2 rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 text-sm text-slate-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-blue-500/40">
              <option value="">Vyber preset</option>
              {presets.map(preset => <option key={preset.key} value={preset.key}>{preset.name}</option>)}
            </select>
            <p className="text-xs text-slate-500 dark:text-slate-400">{presets.find(p => p.key === selectedPresetKey)?.description || 'Preset filtruje kombináciu naraz.'}</p>
            <button onClick={applyPreset} className="mt-2 px-3 py-2 rounded-lg bg-slate-900 dark:bg-slate-100 text-white dark:text-slate-900 text-sm">Použiť preset</button>
          </label>

          <label className="space-y-1 block">
            <span className="block text-xs font-medium text-slate-500 dark:text-slate-400">Uložené filtre</span>
            <select value={selectedSavedFilterId} onChange={e => setSelectedSavedFilterId(e.target.value)} className="w-full px-3 py-2 rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 text-sm text-slate-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-blue-500/40">
              <option value="">Vyber uložený filter</option>
              {savedFilters.map(filter => <option key={filter.id} value={filter.id}>{filter.name}</option>)}
            </select>
            <p className="text-xs text-slate-500 dark:text-slate-400">{savedFilters.find(f => String(f.id) === selectedSavedFilterId)?.description || 'Tvoje uložené filtre.'}</p>
            <button onClick={applySavedFilter} className="mt-2 px-3 py-2 rounded-lg bg-slate-900 dark:bg-slate-100 text-white dark:text-slate-900 text-sm">Použiť uložený filter</button>
          </label>

          <div className="space-y-2">
            <FilterInput label="Názov uloženého filtra" value={savedFilterName} onChange={setSavedFilterName} placeholder="Napr. Trnava IT bez dlhov" />
            <FilterInput label="Popis (voliteľné)" value={savedFilterDescription} onChange={setSavedFilterDescription} placeholder="Krátky popis filtra" />
            <button onClick={saveCurrentFilter} disabled={savingFilter} className="px-3 py-2 rounded-lg bg-blue-600 text-white text-sm hover:bg-blue-700 disabled:opacity-60">
              {savingFilter ? 'Ukladám...' : 'Uložiť aktuálny filter'}
            </button>
          </div>
        </div>

        {savedFilters.length > 0 && (
          <div className="space-y-2">
            <p className="text-xs font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400">Moje uložené filtre</p>
            <div className="flex flex-wrap gap-2">
              {savedFilters.map(filter => (
                <div key={filter.id} className={`flex items-center gap-2 px-3 py-2 rounded-full border ${filter.is_favorite ? 'border-amber-400 bg-amber-50 dark:bg-amber-900/20' : 'border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800'}`}>
                  <span className="text-sm text-slate-700 dark:text-slate-200">{filter.name}</span>
                  <button onClick={() => toggleFavorite(filter)} className="text-xs text-amber-700 dark:text-amber-400">★</button>
                  <button onClick={() => deleteSavedFilter(filter.id)} className="text-xs text-red-600 dark:text-red-400">×</button>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      <div className="bg-white dark:bg-slate-800/60 rounded-xl border border-slate-200 dark:border-slate-700/50 p-4 space-y-3">
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-3">
          <FilterInput label="Hľadať" value={search} onChange={setSearch} placeholder="ICO, názov, DIČ, adresa..." />
          <FilterSelect label="Aktívnosť" value={activeFilter} onChange={setActiveFilter} options={[
            ['', 'Všetky'], ['1', 'Aktívne'], ['0', 'Zrušené'],
          ]} />
          <FilterInput label="Mesto" value={cityFilter} onChange={setCityFilter} placeholder="napr. Trnava" />
          <FilterInput label="PSČ" value={pscFilter} onChange={setPscFilter} placeholder="napr. 917" />
          <FilterInput label="SK NACE" value={naceFilter} onChange={setNaceFilter} placeholder="napr. 62.01" />
          <FilterSelect label="Právna forma" value={legalFormFilter} onChange={setLegalFormFilter} options={[
            ['', 'Všetky'], ['112', 's. r. o.'], ['121', 'a. s.'], ['101', 'FO-podnikateľ'], ['111', 'v. o. s.'],
          ]} />
          <FilterInput label="Kraj" value={krajFilter} onChange={setKrajFilter} placeholder="kód alebo názov" />
          <FilterSelect label="Veľkosť firmy" value={sizeFilter} onChange={setSizeFilter} options={[
            ['', 'Všetky'], ['mikro', 'Mikro'], ['small', 'Malá'], ['medium', 'Stredná'], ['large', 'Veľká'],
          ]} />
          <FilterSelect label="Dlhy" value={debtFilter} onChange={setDebtFilter} options={[
            ['', 'Všetky'], ['debt_free', 'Bez dlhov'], ['has_debt', 'S dlhmi'],
          ]} />
          <FilterSelect label="Zisk / strata" value={profitFilter} onChange={setProfitFilter} options={[
            ['', 'Všetky'], ['profit', 'V zisku'], ['loss', 'V strate'], ['break_even', 'Na nule'], ['unknown', 'Bez údajov'],
          ]} />
          <FilterSelect label="Finančné výsledky" value={financialsFilter} onChange={setFinancialsFilter} options={[
            ['', 'Všetky'], ['1', 'Má financie'], ['0', 'Nemá financie'],
          ]} />
          <FilterSelect label="ORSR profil" value={orsrFilter} onChange={setOrsrFilter} options={[
            ['', 'Všetky'], ['1', 'Má ORSR'], ['0', 'Nemá ORSR'],
          ]} />
          <FilterSelect label="Platiteľ DPH" value={vatFilter} onChange={setVatFilter} options={[
            ['', 'Všetky'], ['1', 'Áno'], ['0', 'Nie'],
          ]} />
          <FilterSelect label="Daňová spoľahlivosť" value={taxReliabilityFilter} onChange={setTaxReliabilityFilter} options={[
            ['', 'Všetky'], ['vysoko spoľahlivý', 'Vysoko spoľahlivý'], ['spoľahlivý', 'Spoľahlivý'], ['nespoľahlivý', 'Nespoľahlivý'],
          ]} />
          <FilterInput label="Lead score min" value={leadScoreMin} onChange={setLeadScoreMin} placeholder="0-100" type="number" />
          <FilterInput label="Lead score max" value={leadScoreMax} onChange={setLeadScoreMax} placeholder="0-100" type="number" />
          <FilterSelect label="Sync stav" value={syncFilter} onChange={setSyncFilter} options={[
            ['', 'Všetky'], ['healthy', 'Zdravý'], ['failing', 'Chybový'], ['blocked', 'Blokovaný'],
          ]} />
          <FilterInput label="Confidence min" value={confidenceMin} onChange={setConfidenceMin} placeholder="0-100" type="number" />
          <FilterInput label="Rok financií" value={financialYear} onChange={setFinancialYear} placeholder="napr. 2024" type="number" />
        </div>
        <div className="text-xs text-slate-500 dark:text-slate-400">
          Filtre sa kombinujú naraz — napr. <span className="font-medium">Trnava + 62.01 + bez dlhov + aktívne + len firmy so ziskom</span>.
        </div>
      </div>

      {error && <ErrorBanner msg={error} />}

      <div className="bg-white dark:bg-slate-800/60 rounded-xl border border-slate-200 dark:border-slate-700/50 overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800/80">
                <Th>ICO</Th>
                <Th>Názov</Th>
                <Th>Právna forma</Th>
                <Th>Založená</Th>
                <Th>Stav</Th>
                <Th>PSČ / mesto</Th>
                <Th>NACE</Th>
                <Th>Dlhy</Th>
                <Th>Zisk</Th>
                <Th>Score</Th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr><td colSpan={10} className="text-center py-12 text-slate-400"><i className="fas fa-spinner fa-spin mr-2" />Načítavam...</td></tr>
              ) : companies.length === 0 ? (
                <tr><td colSpan={10} className="text-center py-12 text-slate-400">Žiadne výsledky</td></tr>
              ) : (
                companies.map(c => (
                  <tr key={c.id} className="border-b border-slate-100 dark:border-slate-700/50 hover:bg-slate-50 dark:hover:bg-slate-800/40 transition-colors">
                    <td className="px-4 py-3 font-mono text-xs text-blue-600 dark:text-blue-400">{c.ico}</td>
                    <td className="px-4 py-3 font-medium text-slate-900 dark:text-white max-w-xs truncate">{c.nazov_UJ}</td>
                    <td className="px-4 py-3 text-slate-600 dark:text-slate-400">{c.pravna_forma || '—'}</td>
                    <td className="px-4 py-3 text-slate-600 dark:text-slate-400">{c.datum_zalozenia ? new Date(c.datum_zalozenia).toLocaleDateString('sk') : '—'}</td>
                    <td className="px-4 py-3">{c.datum_zrusenia ? <Badge color="red">Zrušená</Badge> : <Badge color="green">Aktívna</Badge>}</td>
                    <td className="px-4 py-3 text-slate-600 dark:text-slate-400 text-xs">{formatLocation(c.psc, c.mesto)}</td>
                    <td className="px-4 py-3 text-slate-600 dark:text-slate-400 text-xs">{c.sk_NACE || '—'}</td>
                    <td className="px-4 py-3 text-slate-600 dark:text-slate-400 text-xs">{formatDebtState(c.debt_state, c.tax_debt, c.debt_vszp, c.debt_soc_poist)}</td>
                    <td className="px-4 py-3 text-slate-600 dark:text-slate-400 text-xs">{formatProfit(c.latest_profit)}</td>
                    <td className="px-4 py-3 text-slate-600 dark:text-slate-400 text-xs">{c.lead_score ?? '—'}</td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {report?.top_companies?.length ? (
        <div className="bg-white dark:bg-slate-800/60 rounded-xl border border-slate-200 dark:border-slate-700/50 p-4">
          <h2 className="text-sm font-semibold text-slate-900 dark:text-white mb-3">Top výsledky</h2>
          <div className="flex flex-wrap gap-2">
            {report.top_companies.slice(0, 5).map(company => (
              <span key={company.id} className="px-3 py-2 rounded-full bg-slate-100 dark:bg-slate-700/60 text-xs text-slate-700 dark:text-slate-200">
                {company.nazov_UJ} · {company.lead_score ?? '—'}
              </span>
            ))}
          </div>
        </div>
      ) : null}
    </div>
  );
}

function SummaryCard({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="bg-white dark:bg-slate-800/60 rounded-xl border border-slate-200 dark:border-slate-700/50 p-4">
      <p className="text-xs text-slate-500 dark:text-slate-400 uppercase tracking-wider">{label}</p>
      <p className="text-2xl font-bold text-slate-900 dark:text-white mt-1">{value}</p>
    </div>
  );
}

function Th({ children }: { children: React.ReactNode }) {
  return <th className="px-4 py-3 text-left text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wider">{children}</th>;
}

function Badge({ children, color }: { children: React.ReactNode; color: 'green' | 'red' | 'amber' | 'blue' | 'gray' }) {
  const colors = {
    green: 'bg-emerald-50 dark:bg-emerald-900/30 text-emerald-700 dark:text-emerald-400',
    red: 'bg-red-50 dark:bg-red-900/30 text-red-700 dark:text-red-400',
    amber: 'bg-amber-50 dark:bg-amber-900/30 text-amber-700 dark:text-amber-400',
    blue: 'bg-blue-50 dark:bg-blue-900/30 text-blue-700 dark:text-blue-400',
    gray: 'bg-slate-100 dark:bg-slate-700/50 text-slate-600 dark:text-slate-400',
  };
  return <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium ${colors[color]}`}>{children}</span>;
}

function FilterInput({
  label,
  value,
  onChange,
  placeholder,
  type = 'text',
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  type?: string;
}) {
  return (
    <label className="space-y-1 block">
      <span className="block text-xs font-medium text-slate-500 dark:text-slate-400">{label}</span>
      <input
        type={type}
        value={value}
        onChange={e => onChange(e.target.value)}
        placeholder={placeholder}
        className="w-full px-3 py-2 rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 text-sm text-slate-900 dark:text-white placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-blue-500/40"
      />
    </label>
  );
}

function FilterSelect({
  label,
  value,
  onChange,
  options,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  options: Array<[string, string]>;
}) {
  return (
    <label className="space-y-1 block">
      <span className="block text-xs font-medium text-slate-500 dark:text-slate-400">{label}</span>
      <select
        value={value}
        onChange={e => onChange(e.target.value)}
        className="w-full px-3 py-2 rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 text-sm text-slate-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-blue-500/40"
      >
        {options.map(([optValue, optLabel]) => (
          <option key={optValue || 'all'} value={optValue}>{optLabel}</option>
        ))}
      </select>
    </label>
  );
}

function compactParams(params: Record<string, string>): Record<string, string> {
  return Object.fromEntries(Object.entries(params).filter(([, value]) => value !== ''));
}

function formatLocation(psc: string | null, mesto: string | null) {
  return [psc, mesto].filter(Boolean).join(' • ') || '—';
}

function formatDebtState(
  debtState: 'debt_free' | 'has_debt',
  taxDebt: string | null,
  debtVszp: string | null,
  debtSocPoist: string | null,
) {
  if (debtState === 'debt_free') return 'Bez dlhov';
  const parts = [taxDebt, debtVszp, debtSocPoist].filter(v => v && Number(v) > 0).length;
  return `Dlhy (${parts})`;
}

function formatProfit(value: string | null) {
  if (value === null || value === undefined) return '—';
  const n = Number(value);
  if (Number.isNaN(n)) return value;
  if (n > 0) return `Zisk ${formatNumber(n)}`;
  if (n < 0) return `Strata ${formatNumber(Math.abs(n))}`;
  return 'Na nule';
}

function formatMoney(value: string | number) {
  const n = Number(value);
  if (Number.isNaN(n)) return String(value);
  return `${formatNumber(n)} €`;
}

function ErrorBanner({ msg }: { msg: string }) {
  return (
    <div className="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg px-4 py-3 text-sm text-red-700 dark:text-red-300">
      <i className="fas fa-exclamation-circle mr-2" />{msg}
    </div>
  );
}
