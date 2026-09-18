import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { formatNumber } from '../../utils/format';
import { adminApi } from '../api';
import type {
  AdminCompany,
  CompanyPreset,
  CompanyReport,
  FilterBuilderCondition,
  FilterBuilderGroup,
  FilterBuilderNode,
  FilterLogic,
  SavedCompanyFilter,
} from '../types';

const FIELD_DEFS = [
  { value: 'q', label: 'Hľadať', kind: 'text', operators: ['contains'] as const },
  { value: 'mesto', label: 'Mesto', kind: 'text', operators: ['contains', 'equals'] as const },
  { value: 'psc', label: 'PSČ', kind: 'text', operators: ['contains', 'equals'] as const },
  { value: 'sk_nace', label: 'SK NACE', kind: 'text', operators: ['contains', 'equals'] as const },
  { value: 'pravna_forma', label: 'Právna forma', kind: 'select', options: ['112', '121', '101', '111', '205'], operators: ['equals'] as const },
  { value: 'kraj', label: 'Kraj', kind: 'text', operators: ['equals', 'contains'] as const },
  { value: 'okres', label: 'Okres', kind: 'text', operators: ['equals', 'contains'] as const },
  { value: 'sidlo', label: 'Sídlo', kind: 'text', operators: ['contains', 'equals'] as const },
  { value: 'active', label: 'Aktívnosť', kind: 'select', options: ['1', '0'], operators: ['equals'] as const },
  { value: 'has_orsr', label: 'ORSR profil', kind: 'select', options: ['1', '0'], operators: ['equals'] as const },
  { value: 'has_financials', label: 'Financie', kind: 'select', options: ['1', '0'], operators: ['equals'] as const },
  { value: 'debt_state', label: 'Dlhy', kind: 'select', options: ['no_debt', 'has_debt'], operators: ['equals'] as const },
  // The facet reads `profit`, which is the operating result -- a bare "Zisk"
  // over it named a figure the filter does not read (the same mislabelling the
  // column header and the company page carried). There is no after-tax facet
  // because `profit_after_tax` is only populated for rows re-read since the two
  // were split, so it would answer "Bez údajov" for almost every company.
  { value: 'profit_state', label: 'VH z hosp. činnosti', kind: 'select', options: ['profit', 'loss', 'break_even', 'unknown'], operators: ['equals'] as const },
  { value: 'revenue_state', label: 'Tržby', kind: 'select', options: ['revenue', 'no_revenue'], operators: ['equals'] as const },
  { value: 'vat_payer', label: 'Platiteľ DPH', kind: 'select', options: ['1', '0'], operators: ['equals'] as const },
  { value: 'tax_reliability', label: 'Daňová spoľahlivosť', kind: 'select', options: ['vysoko spoľahlivý', 'spoľahlivý', 'nespoľahlivý'], operators: ['equals'] as const },
  // The 23 codes of ŠÚ SR číselník 0073/KATP97, which is what the column
  // actually holds (`00`-`38`). The options used to read
  // `['mikro','small','medium','large']` -- words that appear in no row of the
  // table, so the filter could only ever return nothing while looking like it
  // had worked. `00` is in the list on purpose: the company page refuses to
  // *rank* the 206 240 firms whose size the register does not record, because a
  // ranking would present "unknown" as a category, but an operator asking for
  // exactly those firms is asking a question worth answering.
  {
    value: 'velkost_organizacie', label: 'Veľkosť firmy', kind: 'select',
    options: ['00', '01', '02', '03', '04', '05', '06', '07', '11', '12',
      '21', '22', '23', '24', '25', '31', '32', '33', '34', '35', '36', '37', '38'],
    operators: ['equals'] as const,
  },
  { value: 'sync_state', label: 'Sync stav', kind: 'select', options: ['healthy', 'failing', 'blocked'], operators: ['equals'] as const },
  { value: 'lead_score', label: 'Lead score', kind: 'number', operators: ['gte', 'lte', 'gt', 'lt'] as const },
  { value: 'confidence_min', label: 'Confidence min', kind: 'number', operators: ['gte', 'lte', 'gt', 'lt'] as const },
  { value: 'financial_year', label: 'Rok financií', kind: 'number', operators: ['equals', 'gte', 'lte'] as const },
] as const;

/** The API names conditions by key; the builder shows them by label. */
const FIELD_LABELS: Record<string, string> = Object.fromEntries(
  FIELD_DEFS.map(field => [field.value, field.label]),
);

type QueryParams = Record<string, string>;
const COMPANY_PAGE_SIZE = 50;

type UrlState = {
  preset: string;
  savedFilter: string;
  builder: FilterBuilderGroup;
};

export function CompaniesBuilderPage() {
  const [companies, setCompanies] = useState<AdminCompany[]>([]);
  const [companyCount, setCompanyCount] = useState(0);
  const [page, setPage] = useState(1);
  const [report, setReport] = useState<CompanyReport | null>(null);
  const [presets, setPresets] = useState<CompanyPreset[]>([]);
  const [savedFilters, setSavedFilters] = useState<SavedCompanyFilter[]>([]);
  const [loading, setLoading] = useState(true);
  const [reportLoading, setReportLoading] = useState(false);
  const [error, setError] = useState('');
  const initialState = useMemo(() => parseUrlState(), []);
  const [builder, setBuilder] = useState<FilterBuilderGroup>(() => initialState.builder);
  const [selectedPreset, setSelectedPreset] = useState(() => initialState.preset);
  const [selectedSavedFilter, setSelectedSavedFilter] = useState(() => initialState.savedFilter);
  const [savedName, setSavedName] = useState('');
  const [savedDescription, setSavedDescription] = useState('');
  const [saving, setSaving] = useState(false);
  const listRequestRef = useRef<{ id: number; controller: AbortController } | null>(null);
  const reportRequestRef = useRef<{ id: number; controller: AbortController } | null>(null);
  const requestIdRef = useRef(0);
  /**
   * Which condition emptied the result. The API only sends this when nothing
   * matched, so an empty array here means "no explanation available" -- either
   * the report has not arrived yet or a page past the end was requested.
   */
  const zeroDiagnosis = report?.zero_diagnosis ?? [];

  const queryParams = useMemo(() => {
    const params: QueryParams = {};
    const normalized = normalizeGroup(builder);
    if (normalized) params.filter_builder = JSON.stringify(normalized);
    if (selectedPreset) params.preset = selectedPreset;
    if (selectedSavedFilter) params.saved_filter = selectedSavedFilter;
    params.page = String(page);
    return params;
  }, [builder, page, selectedPreset, selectedSavedFilter]);
  const queryKey = useMemo(() => JSON.stringify(queryParams), [queryParams]);
  const currentQueryKeyRef = useRef(queryKey);
  currentQueryKeyRef.current = queryKey;

  const loadPresets = useCallback(() => adminApi.companyPresets().then(setPresets), []);
  const loadSavedFilters = useCallback(() => adminApi.listCompanyFilters().then(res => setSavedFilters(res.results || [])), []);

  const loadCompanies = useCallback(async () => {
    listRequestRef.current?.controller.abort();
    const request = {
      id: ++requestIdRef.current,
      controller: new AbortController(),
    };
    const requestQueryKey = queryKey;
    listRequestRef.current = request;
    setLoading(true);
    setError('');
    try {
      console.log('[CompaniesBuilderPage] Loading companies with params:', queryParams);
      const companiesRes = await adminApi.listCompanies(queryParams, { signal: request.controller.signal });
      if (
        request.controller.signal.aborted ||
        listRequestRef.current?.id !== request.id ||
        currentQueryKeyRef.current !== requestQueryKey
      ) {
        return;
      }
      console.log('[CompaniesBuilderPage] Companies loaded:', companiesRes);
      setCompanies(Array.isArray(companiesRes) ? companiesRes : companiesRes.results || []);
      setCompanyCount(Array.isArray(companiesRes) ? 0 : companiesRes.count || 0);
    } catch (e: any) {
      if (request.controller.signal.aborted || e?.name === 'AbortError') return;
      if (
        listRequestRef.current?.id !== request.id ||
        currentQueryKeyRef.current !== requestQueryKey
      ) {
        return;
      }
      console.error('[CompaniesBuilderPage] Error loading data:', e);
      console.error('[CompaniesBuilderPage] Error stack:', e.stack);
      const errorMsg = e.message || 'Chyba pri načítaní dát z databázy';
      setCompanies([]);
      setCompanyCount(0);
      setError(errorMsg);
    } finally {
      if (listRequestRef.current?.id === request.id) {
        setLoading(false);
      }
    }
  }, [queryKey, queryParams]);

  const refreshReport = useCallback(async () => {
    reportRequestRef.current?.controller.abort();
    const request = {
      id: ++requestIdRef.current,
      controller: new AbortController(),
    };
    const requestQueryKey = queryKey;
    reportRequestRef.current = request;
    setReportLoading(true);
    setError('');
    try {
      console.log('[CompaniesBuilderPage] Loading report with mode=light...');
      const reportRes = await adminApi.companyReport(
        { ...queryParams, mode: 'light' },
        { signal: request.controller.signal },
      );
      if (
        request.controller.signal.aborted ||
        reportRequestRef.current?.id !== request.id ||
        currentQueryKeyRef.current !== requestQueryKey
      ) {
        return;
      }
      console.log('[CompaniesBuilderPage] Report loaded:', reportRes);
      setReport(reportRes);
    } catch (e: any) {
      if (request.controller.signal.aborted || e?.name === 'AbortError') return;
      setError(e.message || 'Chyba pri načítaní súhrnu');
    } finally {
      if (reportRequestRef.current?.id === request.id) {
        setReportLoading(false);
      }
    }
  }, [queryKey, queryParams]);

  useEffect(() => {
    loadPresets();
    loadSavedFilters();
  }, [loadPresets, loadSavedFilters]);

  useEffect(() => {
    reportRequestRef.current?.controller.abort();
    reportRequestRef.current = null;
    setReport(null);
    setReportLoading(false);
    const timeout = window.setTimeout(() => {
      loadCompanies();
    }, 250);

    return () => {
      window.clearTimeout(timeout);
      const activeRequest = listRequestRef.current;
      activeRequest?.controller.abort();
      if (activeRequest) listRequestRef.current = null;
    };
  }, [loadCompanies]);

  useEffect(() => () => {
    reportRequestRef.current?.controller.abort();
    reportRequestRef.current = null;
  }, []);

  useEffect(() => {
    const next = new URL(window.location.href);
    const normalized = normalizeGroup(builder);
    if (normalized) next.searchParams.set('filter_builder', JSON.stringify(normalized));
    else next.searchParams.delete('filter_builder');
    if (selectedPreset) next.searchParams.set('preset', selectedPreset); else next.searchParams.delete('preset');
    if (selectedSavedFilter) next.searchParams.set('saved_filter', selectedSavedFilter); else next.searchParams.delete('saved_filter');
    window.history.replaceState({}, '', `${next.pathname}${next.search}${next.hash}`);
  }, [builder, selectedPreset, selectedSavedFilter]);

  const applyPreset = (preset: CompanyPreset) => {
    setSelectedPreset(preset.key);
    setSelectedSavedFilter('');
    setPage(1);
    setBuilder(filtersToBuilder(preset.filters));
  };

  const applySavedFilter = (filter: SavedCompanyFilter) => {
    setSelectedSavedFilter(String(filter.id));
    setSelectedPreset('');
    setPage(1);
    setBuilder(filtersToBuilder(filter.filters));
  };

  const saveBuilder = async () => {
    if (!savedName.trim()) {
      setError('Zadaj názov uloženého filtra.');
      return;
    }
    setSaving(true);
    try {
      await adminApi.saveCompanyFilter({
        name: savedName.trim(),
        description: savedDescription.trim(),
        filters: normalizeGroup(builder) ? { filter_builder: JSON.stringify(normalizeGroup(builder)), preset: selectedPreset, saved_filter: selectedSavedFilter } : {},
        is_favorite: false,
      });
      setSavedName('');
      setSavedDescription('');
      loadSavedFilters();
    } catch (e: any) {
      setError(e.message);
    } finally {
      setSaving(false);
    }
  };

  const exportCurrent = async (format: 'csv' | 'xlsx') => {
    try {
      const blob = await adminApi.downloadCompanyReport(format, queryParams);
      downloadBlob(blob, `companies-builder.${format}`);
    } catch (e: any) {
      setError(e.message);
    }
  };

  const exportPreset = async (preset: CompanyPreset, format: 'csv' | 'xlsx') => {
    try {
      const blob = await adminApi.downloadCompanyReport(format, { preset: preset.key });
      downloadBlob(blob, `${slugify(preset.name)}.${format}`);
    } catch (e: any) {
      setError(e.message);
    }
  };

  const resetAll = () => {
    setBuilder(emptyGroup());
    setSelectedPreset('');
    setSelectedSavedFilter('');
    setPage(1);
  };
  const updateBuilder = (next: FilterBuilderGroup) => {
    setPage(1);
    setBuilder(next);
  };
  const totalPages = Math.max(1, Math.ceil(companyCount / COMPANY_PAGE_SIZE));

  return (
    <div className="space-y-5">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 dark:text-white">Firmy</h1>
          <p className="text-sm text-slate-500 dark:text-slate-400">AND/OR builder s URL synchronizáciou, presety a exportom.</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <button className="px-3 py-2 rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 text-sm" onClick={loadCompanies}>Obnoviť</button>
          <button className="px-3 py-2 rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 text-sm disabled:opacity-60" onClick={refreshReport} disabled={reportLoading}>
            {reportLoading ? 'Načítavam súhrn…' : 'Obnoviť súhrn'}
          </button>
          <button className="px-3 py-2 rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 text-sm" onClick={resetAll}>Reset</button>
          <button className="px-3 py-2 rounded-lg bg-emerald-600 text-white text-sm" onClick={() => exportCurrent('csv')}>Export CSV</button>
          <button className="px-3 py-2 rounded-lg bg-blue-600 text-white text-sm" onClick={() => exportCurrent('xlsx')}>Export XLSX</button>
        </div>
      </div>

      {report && (
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
          <StatCard label="Výsledky" value={formatInt(report.count)} />
          <StatCard label="Aktívne" value={formatInt(report.active_count)} />
          <StatCard label="Bez dlhov" value={formatInt(report.debt_free_count)} />
          <StatCard label="Priem. score" value={formatDecimal(report.avg_lead_score)} />
        </div>
      )}
      {reportLoading && <p className="text-xs text-slate-500 dark:text-slate-400">Načítavam súhrn…</p>}

      <div className="grid gap-4 lg:grid-cols-2">
        <div className="bg-white dark:bg-slate-800/60 rounded-xl border border-slate-200 dark:border-slate-700/50 p-4 space-y-3">
          <h2 className="text-sm font-semibold text-slate-900 dark:text-white">Presety</h2>
          <div className="flex flex-wrap gap-3">
            {presets.map(preset => (
              <PresetCard
                key={preset.key}
                preset={preset}
                active={preset.key === selectedPreset}
                onApply={() => applyPreset(preset)}
                onExportCsv={() => exportPreset(preset, 'csv')}
                onExportXlsx={() => exportPreset(preset, 'xlsx')}
              />
            ))}
          </div>
        </div>

        <div className="bg-white dark:bg-slate-800/60 rounded-xl border border-slate-200 dark:border-slate-700/50 p-4 space-y-3">
          <h2 className="text-sm font-semibold text-slate-900 dark:text-white">Uložené filtre</h2>
          <div className="max-h-72 overflow-y-auto space-y-2 pr-1">
            {savedFilters.map(filter => (
              <div key={filter.id} className="rounded-lg border border-slate-200 dark:border-slate-700 p-3 flex items-start justify-between gap-2">
                <div>
                  <div className="font-medium text-slate-900 dark:text-white">{filter.name}</div>
                  <div className="text-xs text-slate-500 dark:text-slate-400">{filter.description || 'Bez popisu'}</div>
                </div>
                <div className="flex gap-1">
                  <button className="text-xs px-2 py-1 rounded-md border border-slate-200 dark:border-slate-700" onClick={() => applySavedFilter(filter)}>Použiť</button>
                  <button className="text-xs px-2 py-1 rounded-md border border-slate-200 dark:border-slate-700" onClick={() => adminApi.updateCompanyFilter(filter.id, { is_favorite: !filter.is_favorite }).then(loadSavedFilters)}>{filter.is_favorite ? '★' : '☆'}</button>
                  <button className="text-xs px-2 py-1 rounded-md border border-slate-200 dark:border-slate-700 text-red-600 dark:text-red-300" onClick={() => adminApi.deleteCompanyFilter(filter.id).then(loadSavedFilters)}>×</button>
                </div>
              </div>
            ))}
          </div>
          <Input label="Názov" value={savedName} onChange={setSavedName} placeholder="Napr. IT Trnava bez dlhov" />
          <Input label="Popis" value={savedDescription} onChange={setSavedDescription} placeholder="Krátky popis" />
          <button className="px-3 py-2 rounded-lg bg-blue-600 text-white text-sm" disabled={saving} onClick={saveBuilder}>{saving ? 'Ukladám...' : 'Uložiť builder'}</button>
        </div>
      </div>

      <section className="bg-white dark:bg-slate-800/60 rounded-xl border border-slate-200 dark:border-slate-700/50 p-4 space-y-3">
        <div className="flex flex-wrap gap-2 justify-between items-center">
          <div>
            <h2 className="text-sm font-semibold text-slate-900 dark:text-white">Builder</h2>
            <p className="text-xs text-slate-500 dark:text-slate-400">Vnorené AND/OR skupiny sa prenášajú cez `filter_builder` v URL.</p>
          </div>
          <div className="flex flex-wrap gap-2">
            <button className="px-3 py-2 rounded-lg border border-slate-200 dark:border-slate-700 text-sm" onClick={() => updateBuilder(addGroup(builder, 'and'))}>+ AND skupina</button>
            <button className="px-3 py-2 rounded-lg border border-slate-200 dark:border-slate-700 text-sm" onClick={() => updateBuilder(addGroup(builder, 'or'))}>+ OR skupina</button>
            <button className="px-3 py-2 rounded-lg border border-slate-200 dark:border-slate-700 text-sm" onClick={() => updateBuilder(addCondition(builder, defaultCondition('mesto')))}>+ Podmienka</button>
          </div>
        </div>
        <GroupEditor group={builder} onChange={updateBuilder} isRoot />
      </section>

      {report?.top_companies?.length ? (
        <section className="bg-white dark:bg-slate-800/60 rounded-xl border border-slate-200 dark:border-slate-700/50 p-4">
          <h2 className="text-sm font-semibold text-slate-900 dark:text-white mb-3">Top výsledky</h2>
          <div className="flex flex-wrap gap-2">
            {report.top_companies.slice(0, 10).map(company => (
              <span key={company.id} className="px-3 py-2 rounded-full bg-slate-100 dark:bg-slate-700/60 text-xs text-slate-700 dark:text-slate-200">
                  {company.nazov_UJ} · {formatMaybeInt(company.lead_score)}
              </span>
            ))}
          </div>
        </section>
      ) : null}

      <section className="bg-white dark:bg-slate-800/60 rounded-xl border border-slate-200 dark:border-slate-700/50 overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800/80">
                <Th>ICO</Th>
                <Th>Názov</Th>
                <Th>Sídlo</Th>
                <Th>NACE</Th>
                <Th>Stav</Th>
                <Th>Dlhy</Th>
                <Th>Tržby</Th>
                {/* The column reads `latest_profit`, which is the operating
                    result -- a bare "Zisk" named a figure that used to be
                    whichever of the two profit rows the parser picked. */}
                <Th>VH z hosp. činnosti</Th>
                <Th>Score</Th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr><td colSpan={9} className="text-center py-12 text-slate-400">Načítavam...</td></tr>
              ) : companies.length === 0 ? (
                <tr>
                  <td colSpan={9} className="px-4 py-12 text-center">
                    <p className="text-slate-400">Žiadne výsledky</p>
                    {zeroDiagnosis.length > 0 ? (
                      <div className="mx-auto mt-4 max-w-2xl rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-left dark:border-amber-900/50 dark:bg-amber-900/20">
                        <p className="text-sm text-amber-900 dark:text-amber-300">
                          Filtru nezodpovedá ani jedna firma. Podmienky sú zoradené
                          podľa toho, koľko firiem by zostalo bez nich:
                        </p>
                        <ul className="mt-2 space-y-1 text-sm text-amber-800 dark:text-amber-400">
                          {zeroDiagnosis.map(entry => (
                            <li key={entry.condition}>
                              {FIELD_LABELS[entry.condition] ?? entry.condition} ={' '}
                              <span className="font-mono">{entry.value}</span> — bez tejto
                              podmienky {formatMaybeInt(entry.count_without)} firiem
                            </li>
                          ))}
                        </ul>
                        <p className="mt-3 text-xs text-amber-700 dark:text-amber-500">
                          Ak je aj najvyššie číslo malé, je to skôr údaj, ktorý ešte
                          nemáme naimportovaný, než chyba filtra.
                        </p>
                      </div>
                    ) : null}
                  </td>
                </tr>
              ) : companies.map(company => (
                <tr key={company.id} className="border-b border-slate-100 dark:border-slate-700/50">
                  <td className="px-4 py-3 font-mono text-xs text-blue-600 dark:text-blue-400">{company.ico}</td>
                  <td className="px-4 py-3 font-medium text-slate-900 dark:text-white max-w-xs truncate">
                    {company.nazov_UJ}
                    {/* Two data-quality signals the row used to hide. A blocked
                        source has stopped retrying; consecutive failures mean the
                        figures beside it are older than they look. Both are
                        reasons not to trust the row at a glance, so they sit on
                        the name rather than in a column nobody scans. */}
                    {company.is_blocked ? (
                      <i
                        className="fas fa-ban ml-1.5 text-[10px] text-red-500"
                        title="Synchronizácia zdroja je pozastavená — údaje môžu byť neaktuálne"
                      />
                    ) : company.sync_failures > 0 ? (
                      <i
                        className="fas fa-exclamation-triangle ml-1.5 text-[10px] text-amber-500"
                        title={`${company.sync_failures} neúspešných synchronizácií za sebou`}
                      />
                    ) : null}
                  </td>
                  <td className="px-4 py-3 text-slate-600 dark:text-slate-400">{locationLabel(company.psc, company.mesto)}</td>
                  <td className="px-4 py-3 text-slate-600 dark:text-slate-400">{company.sk_NACE || '—'}</td>
                  <td className="px-4 py-3 text-slate-600 dark:text-slate-400">{company.datum_zrusenia ? 'Zrušená' : 'Aktívna'}</td>
                  <td className="px-4 py-3 text-slate-600 dark:text-slate-400">{debtLabel(company.debt_state, company.tax_debt, company.debt_vszp, company.debt_soc_poist)}</td>
                  {/* The year travels with the figure: a filing lags, and "12 345 €"
                      from 2019 is a different proposition from the same number
                      from 2025. */}
                  <td className="px-4 py-3 text-right font-mono text-xs text-slate-700 dark:text-slate-300 whitespace-nowrap">
                    {money(company.latest_revenue)}
                    {company.latest_financial_year != null && (
                      <span className="ml-1 text-[10px] text-slate-400 dark:text-slate-500">{company.latest_financial_year}</span>
                    )}
                  </td>
                  <td className={`px-4 py-3 text-right font-mono text-xs whitespace-nowrap ${
                    company.latest_profit === null
                      ? 'text-slate-400 dark:text-slate-500'
                      : Number(company.latest_profit) < 0
                        ? 'text-red-600 dark:text-red-400'
                        : 'text-emerald-600 dark:text-emerald-400'
                  }`}>
                    {money(company.latest_profit)}
                  </td>
                  <td className="px-4 py-3 text-slate-600 dark:text-slate-400">{formatMaybeInt(company.lead_score)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      {companyCount > 0 && (
        <nav className="flex flex-col gap-3 rounded-xl border border-slate-200 bg-white px-4 py-3 text-sm dark:border-slate-700 dark:bg-slate-800/60 sm:flex-row sm:items-center sm:justify-between" aria-label="Stránkovanie firiem">
          <span className="text-slate-600 dark:text-slate-300">
            Strana {page} z {totalPages} · {formatInt(companyCount)} výsledkov
          </span>
          <div className="flex gap-2">
            <button
              type="button"
              className="rounded-lg border border-slate-200 px-3 py-2 disabled:cursor-not-allowed disabled:opacity-50 dark:border-slate-700"
              disabled={loading || page === 1}
              onClick={() => setPage(current => Math.max(1, current - 1))}
            >
              Predchádzajúca
            </button>
            <button
              type="button"
              className="rounded-lg border border-slate-200 px-3 py-2 disabled:cursor-not-allowed disabled:opacity-50 dark:border-slate-700"
              disabled={loading || page >= totalPages}
              onClick={() => setPage(current => Math.min(totalPages, current + 1))}
            >
              Nasledujúca
            </button>
          </div>
        </nav>
      )}

      {error && <ErrorBanner msg={error} />}
    </div>
  );
}

function GroupEditor({ group, onChange, isRoot = false }: { group: FilterBuilderGroup; onChange: (group: FilterBuilderGroup) => void; isRoot?: boolean }) {
  return (
    <div className={`rounded-xl border p-3 space-y-3 ${isRoot ? 'border-blue-200 bg-blue-50/30 dark:border-blue-900/60 dark:bg-blue-900/10' : 'border-slate-200 bg-slate-50 dark:border-slate-700 dark:bg-slate-800/40'}`}>
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <span className="text-xs font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400">Skupina</span>
          <select className="px-2 py-1 rounded-md border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 text-base sm:text-xs" value={group.logic} onChange={e => onChange({ ...group, logic: e.target.value as FilterLogic })}>
            <option value="and">AND</option>
            <option value="or">OR</option>
          </select>
        </div>
        {!isRoot && <button className="text-xs px-2 py-1 rounded-md border border-red-300 text-red-600 dark:border-red-800 dark:text-red-300" onClick={() => onChange(emptyGroup())}>Odstrániť</button>}
      </div>
      <div className="space-y-3">
        {group.children.length === 0 ? <div className="text-xs italic text-slate-500">Zatiaľ bez podmienok.</div> : group.children.map(child => (
          child.type === 'condition' ? (
            <ConditionEditor key={child.id} node={child} onChange={next => onChange(updateChild(group, next))} onDelete={() => onChange(removeChild(group, child.id))} />
          ) : (
            <div key={child.id} className="pl-3 border-l-2 border-slate-200 dark:border-slate-700"><GroupEditor group={child} onChange={next => onChange(updateChild(group, next))} /></div>
          )
        ))}
      </div>
      <div className="flex flex-wrap gap-2">
        <button className="text-xs px-2 py-1 rounded-md border border-slate-300 dark:border-slate-600" onClick={() => onChange(addCondition(group, defaultCondition('mesto')))}>+ Podmienka</button>
        <button className="text-xs px-2 py-1 rounded-md border border-slate-300 dark:border-slate-600" onClick={() => onChange(addGroup(group, 'and'))}>+ AND skupina</button>
        <button className="text-xs px-2 py-1 rounded-md border border-slate-300 dark:border-slate-600" onClick={() => onChange(addGroup(group, 'or'))}>+ OR skupina</button>
      </div>
    </div>
  );
}

function ConditionEditor({ node, onChange, onDelete }: { node: FilterBuilderCondition; onChange: (node: FilterBuilderCondition) => void; onDelete: () => void }) {
  const meta = fieldMeta(node.field);
  return (
    <div className="grid grid-cols-1 gap-2 rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 p-3 md:grid-cols-12">
      <div className="md:col-span-3">
        <Label text="Pole" />
        <select className="w-full rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 px-3 py-2 text-base sm:text-sm" value={node.field} onChange={e => onChange(defaultCondition(e.target.value, node.value))}>
          {FIELD_DEFS.map(f => <option key={f.value} value={f.value}>{f.label}</option>)}
        </select>
      </div>
      <div className="md:col-span-2">
        <Label text="Operátor" />
        <select className="w-full rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 px-3 py-2 text-base sm:text-sm" value={node.operator} onChange={e => onChange({ ...node, operator: e.target.value })}>
          {operatorsForField(node.field).map(op => <option key={op.value} value={op.value}>{op.label}</option>)}
        </select>
      </div>
      <div className="md:col-span-6">
        <Label text="Hodnota" />
        {meta.kind === 'select' ? (
          <select className="w-full rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 px-3 py-2 text-base sm:text-sm" value={node.value} onChange={e => onChange({ ...node, value: e.target.value })}>
            <option value="">Vyber</option>
            {meta.options.map(opt => <option key={opt} value={opt}>{selectLabel(node.field, opt)}</option>)}
          </select>
        ) : meta.kind === 'number' ? (
          <input className="w-full rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 px-3 py-2 text-base sm:text-sm" type="number" value={node.value} onChange={e => onChange({ ...node, value: e.target.value })} />
        ) : (
          <input className="w-full rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 px-3 py-2 text-base sm:text-sm" type="text" value={node.value} onChange={e => onChange({ ...node, value: e.target.value })} placeholder={meta.label} />
        )}
      </div>
      <div className="md:col-span-1 flex md:justify-end">
        <button className="px-3 py-2 rounded-lg border border-red-300 text-red-600 text-sm dark:border-red-800 dark:text-red-300" onClick={onDelete}>×</button>
      </div>
    </div>
  );
}

function PresetCard({ preset, active, onApply, onExportCsv, onExportXlsx }: { preset: CompanyPreset; active: boolean; onApply: () => void; onExportCsv: () => void; onExportXlsx: () => void }) {
  return (
    <div className={`min-w-[240px] flex-1 rounded-xl border p-3 space-y-2 ${active ? 'border-blue-400 bg-blue-50 dark:bg-blue-900/20 dark:border-blue-900/60' : 'border-slate-200 bg-slate-50 dark:border-slate-700 dark:bg-slate-800/40'}`}>
      <div className="flex items-start justify-between gap-2">
        <div>
          <div className="font-semibold text-slate-900 dark:text-white">{preset.name}</div>
          <div className="text-xs text-slate-500 dark:text-slate-400">{preset.description}</div>
        </div>
        {active && <span className="rounded-full bg-blue-600 px-2 py-0.5 text-xs text-white">Aktívny</span>}
      </div>
      <div className="flex flex-wrap gap-2">
        <button className="px-2 py-1 text-xs rounded-md border border-slate-300 dark:border-slate-600" onClick={onApply}>Použiť</button>
        <button className="px-2 py-1 text-xs rounded-md bg-emerald-600 text-white" onClick={onExportCsv}>CSV</button>
        <button className="px-2 py-1 text-xs rounded-md bg-blue-600 text-white" onClick={onExportXlsx}>XLSX</button>
      </div>
    </div>
  );
}

function StatCard({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="bg-white dark:bg-slate-800/60 rounded-xl border border-slate-200 dark:border-slate-700/50 p-4">
      <p className="text-xs uppercase tracking-wider text-slate-500 dark:text-slate-400">{label}</p>
      <p className="mt-1 text-2xl font-bold text-slate-900 dark:text-white">{value}</p>
    </div>
  );
}

function Input({ label, value, onChange, placeholder }: { label: string; value: string; onChange: (value: string) => void; placeholder?: string }) {
  return (
    <label className="space-y-1 block">
      <span className="block text-xs font-medium text-slate-500 dark:text-slate-400">{label}</span>
      <input className="w-full rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 px-3 py-2 text-base sm:text-sm" value={value} onChange={e => onChange(e.target.value)} placeholder={placeholder} />
    </label>
  );
}

function Label({ text }: { text: string }) {
  return <span className="mb-1 block text-xs font-medium text-slate-500 dark:text-slate-400">{text}</span>;
}

function ErrorBanner({ msg }: { msg: string }) {
  return <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700 dark:border-red-800 dark:bg-red-900/20 dark:text-red-300">{msg}</div>;
}

function Th({ children }: { children: React.ReactNode }) {
  return <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400">{children}</th>;
}

function emptyGroup(): FilterBuilderGroup {
  return { id: uid(), type: 'group', logic: 'and', children: [] };
}

function defaultCondition(field: string, value = ''): FilterBuilderCondition {
  return { id: uid(), type: 'condition', field, operator: defaultOperator(field), value };
}

function defaultOperator(field: string) {
  return operatorsForField(field)[0]?.value || 'contains';
}

function operatorsForField(field: string) {
  const meta = fieldMeta(field);
  return meta.operators.map(op => ({ value: op, label: operatorLabel(op) }));
}

function fieldMeta(field: string) {
  return FIELD_DEFS.find(f => f.value === field) || FIELD_DEFS[0];
}

function selectLabel(field: string, value: string) {
  const map: Record<string, Record<string, string>> = {
    active: { '1': 'Aktívne', '0': 'Zrušené' },
    has_orsr: { '1': 'Áno', '0': 'Nie' },
    has_financials: { '1': 'Áno', '0': 'Nie' },
    debt_state: { no_debt: 'Bez dlhov', has_debt: 'S dlhmi' },
    profit_state: { profit: 'V zisku', loss: 'V strate', break_even: 'Na nule', unknown: 'Bez údajov' },
    revenue_state: { revenue: 'Má tržby', no_revenue: 'Nemá tržby' },
    vat_payer: { '1': 'Áno', '0': 'Nie' },
    sync_state: { healthy: 'Zdravý', failing: 'Chybný', blocked: 'Blokovaný' },
    pravna_forma: { '112': 's. r. o.', '121': 'a. s.', '101': 'FO-podnikateľ', '111': 'v. o. s.', '205': 'družstvo' },
    // The register's own band wording, with the code in front of it. The code
    // is what the filter writes, and the číselník's edges are uneven -- `07` is
    // 20-24 employees and `11` is 25-49 -- so a bare code is not decodable from
    // the sequence. The authority for these strings is
    // `backend/companies/services/velkost.py`; this is the admin panel's copy.
    velkost_organizacie: {
      '00': '00 — nezistený',
      '01': '01 — 0 zamestnancov',
      '02': '02 — 1 zamestnanec',
      '03': '03 — 2 zamestnanci',
      '04': '04 — 3-4 zamestnanci',
      '05': '05 — 5-9 zamestnancov',
      '06': '06 — 10-19 zamestnancov',
      '07': '07 — 20-24 zamestnancov',
      '11': '11 — 25-49 zamestnancov',
      '12': '12 — 50-99 zamestnancov',
      '21': '21 — 100-149 zamestnancov',
      '22': '22 — 150-199 zamestnancov',
      '23': '23 — 200-249 zamestnancov',
      '24': '24 — 250-499 zamestnancov',
      '25': '25 — 500-999 zamestnancov',
      '31': '31 — 1000-1999 zamestnancov',
      '32': '32 — 2000-2999 zamestnancov',
      '33': '33 — 3000-3999 zamestnancov',
      '34': '34 — 4000-4999 zamestnancov',
      '35': '35 — 5000-9999 zamestnancov',
      '36': '36 — 10000-19999 zamestnancov',
      '37': '37 — 20000-29999 zamestnancov',
      '38': '38 — 30000+ zamestnancov',
    },
  };
  return map[field]?.[value] || value;
}

function operatorLabel(op: string) {
  return ({ contains: 'obsahuje', equals: '=', gte: '≥', lte: '≤', gt: '>', lt: '<' } as Record<string, string>)[op] || op;
}

function normalizeGroup(group: FilterBuilderGroup | any): FilterBuilderGroup | null {
  if (!group || group.type !== 'group') return null;
  const children = (group.children || [])
    .map((child: any) => normalizeNode(child))
    .filter(Boolean) as FilterBuilderNode[];
  if (children.length === 0) return null;
  return { id: String(group.id || uid()), type: 'group', logic: group.logic === 'or' ? 'or' : 'and', children };
}

function normalizeNode(node: any): FilterBuilderNode | null {
  if (!node) return null;
  if (node.type === 'condition') {
    const value = String(node.value || '').trim();
    if (!value) return null;
    return { id: String(node.id || uid()), type: 'condition', field: String(node.field || 'q'), operator: String(node.operator || defaultOperator(String(node.field || 'q'))), value };
  }
  if (node.type === 'group') return normalizeGroup(node);
  return null;
}

function filtersToBuilder(filters: Record<string, any>): FilterBuilderGroup {
  if (filters.filter_builder) return parseBuilder(String(filters.filter_builder));
  const entries = Object.entries(filters).filter(([k, v]) => !['preset', 'saved_filter'].includes(k) && k !== 'filter_builder' && v !== undefined && v !== null && v !== '');
  return {
    id: uid(),
    type: 'group',
    logic: 'and',
    children: entries.map(([field, value]) => defaultCondition(field, String(value))),
  };
}

function parseUrlState(): UrlState {
  const params = new URLSearchParams(window.location.search);
  return {
    preset: params.get('preset') || '',
    savedFilter: params.get('saved_filter') || '',
    builder: params.get('filter_builder') ? parseBuilder(params.get('filter_builder') || '') : emptyGroup(),
  };
}

function parseBuilder(raw: string): FilterBuilderGroup {
  try {
    const parsed = JSON.parse(raw);
    const normalized = normalizeGroup(parsed);
    if (normalized) return normalized;
  } catch {
    // ignore
  }
  return emptyGroup();
}

function uid() {
  return typeof crypto !== 'undefined' && 'randomUUID' in crypto ? crypto.randomUUID() : `id_${Math.random().toString(36).slice(2, 10)}`;
}

function slugify(value: string) {
  return value.toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g, '').replace(/[^a-z0-9]+/g, '-').replace(/(^-|-$)+/g, '');
}

function downloadBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

function addCondition(group: FilterBuilderGroup, condition: FilterBuilderCondition): FilterBuilderGroup {
  return { ...group, children: [...group.children, condition] };
}

function addGroup(group: FilterBuilderGroup, logic: FilterLogic): FilterBuilderGroup {
  return { ...group, children: [...group.children, { id: uid(), type: 'group', logic, children: [] }] };
}

function updateChild(group: FilterBuilderGroup, child: FilterBuilderNode): FilterBuilderGroup {
  return { ...group, children: group.children.map(node => node.id === child.id ? child : node) };
}

function removeChild(group: FilterBuilderGroup, id: string): FilterBuilderGroup {
  return { ...group, children: group.children.filter(node => node.id !== id) };
}

function locationLabel(psc: string | null, mesto: string | null) {
  return [psc, mesto].filter(Boolean).join(' • ') || '—';
}

function debtLabel(state: 'debt_free' | 'has_debt', taxDebt: string | null, debtVszp: string | null, debtSocPoist: string | null) {
  if (state === 'debt_free') return 'Bez dlhov';
  const parts = [taxDebt, debtVszp, debtSocPoist].filter(v => v && Number(v) > 0).length;
  return `Dlhy (${parts})`;
}

function money(value: string | number | null | undefined) {
  // `Number(null)` is 0, so an unguarded `money` prints "0 €" for a company
  // that filed no such line -- the same collapse `toAmountOrNull` exists to
  // prevent elsewhere. An absent figure is a dash.
  if (value === null || value === undefined || value === '') return '—';
  const n = Number(value);
  return Number.isNaN(n) ? String(value) : `${formatNumber(n)} €`;
}

function formatInt(value: number | string | null | undefined) {
  const n = Number(value);
  return Number.isNaN(n) ? '0' : formatNumber(n);
}

function formatMaybeInt(value: number | string | null | undefined) {
  if (value === null || value === undefined || value === '') return '—';
  return formatInt(value);
}

function formatDecimal(value: number | string | null | undefined) {
  const n = Number(value);
  if (Number.isNaN(n)) return '0,0';
  return new Intl.NumberFormat('sk-SK', {
    minimumFractionDigits: 1,
    maximumFractionDigits: 1,
  }).format(n);
}
