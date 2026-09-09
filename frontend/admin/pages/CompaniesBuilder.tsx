import React, { useCallback, useEffect, useMemo, useState } from 'react';
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

type QueryParams = Record<string, string>;

type URLState = {
  builder: FilterBuilderGroup;
  presetKey: string;
  savedFilterId: string;
  hasBuilder: boolean;
};

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
  { value: 'profit_state', label: 'Zisk / strata', kind: 'select', options: ['profit', 'loss', 'break_even', 'unknown'], operators: ['equals'] as const },
  { value: 'revenue_state', label: 'Tržby', kind: 'select', options: ['revenue', 'no_revenue'], operators: ['equals'] as const },
  { value: 'vat_payer', label: 'Platiteľ DPH', kind: 'select', options: ['1', '0'], operators: ['equals'] as const },
  { value: 'tax_reliability', label: 'Daňová spoľahlivosť', kind: 'select', options: ['vysoko spoľahlivý', 'spoľahlivý', 'nespoľahlivý'], operators: ['equals'] as const },
  { value: 'velkost_organizacie', label: 'Veľkosť firmy', kind: 'select', options: ['mikro', 'small', 'medium', 'large'], operators: ['equals'] as const },
  { value: 'sync_state', label: 'Sync stav', kind: 'select', options: ['healthy', 'failing', 'blocked'], operators: ['equals'] as const },
  { value: 'lead_score', label: 'Lead score', kind: 'number', operators: ['gte', 'lte', 'gt', 'lt'] as const },
  { value: 'confidence_min', label: 'Confidence min', kind: 'number', operators: ['gte', 'lte', 'gt', 'lt'] as const },
  { value: 'financial_year', label: 'Rok financií', kind: 'number', operators: ['equals', 'gte', 'lte'] as const },
] as const;

const DEFAULT_URL_STATE: URLState = {
  builder: { id: uid(), type: 'group', logic: 'and', children: [] },
  presetKey: '',
  savedFilterId: '',
  hasBuilder: false,
};

export function Companies() {
  const [companies, setCompanies] = useState<AdminCompany[]>([]);
  const [report, setReport] = useState<CompanyReport | null>(null);
  const [presets, setPresets] = useState<CompanyPreset[]>([]);
  const [savedFilters, setSavedFilters] = useState<SavedCompanyFilter[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [savingFilter, setSavingFilter] = useState(false);
  const [savedFilterName, setSavedFilterName] = useState('');
  const [savedFilterDescription, setSavedFilterDescription] = useState('');
  const [selectedPresetKey, setSelectedPresetKey] = useState(DEFAULT_URL_STATE.presetKey);
  const [selectedSavedFilterId, setSelectedSavedFilterId] = useState(DEFAULT_URL_STATE.savedFilterId);
  const [builder, setBuilder] = useState<FilterBuilderGroup>(DEFAULT_URL_STATE.builder);
  const [hasUrlBuilder, setHasUrlBuilder] = useState(DEFAULT_URL_STATE.hasBuilder);

  const queryParams = useMemo(() => {
    const params: QueryParams = {};
    const normalized = normalizeGroup(builder);
    if (normalized) {
      params.filter_builder = JSON.stringify(normalized);
    }
    if (selectedPresetKey && normalized) {
      params.preset = selectedPresetKey;
    }
    if (selectedSavedFilterId && normalized) {
      params.saved_filter = selectedSavedFilterId;
    }
    return params;
  }, [builder, selectedPresetKey, selectedSavedFilterId]);

  const loadData = useCallback(() => {
    setLoading(true);
    setError('');

    adminApi.listCompanies(queryParams)
      .then(companiesRes => {
        setCompanies(Array.isArray(companiesRes) ? companiesRes : companiesRes.results || []);
      })
      .catch((e: any) => setError(e.message))
      .finally(() => setLoading(false));

    adminApi.companyReport(queryParams)
      .then(reportRes => setReport(reportRes))
      .catch((e: any) => {
        // Keep list responsive even if report summary fails or is delayed.
        setError(prev => prev || e.message);
      });
  }, [queryParams]);

  const loadPresets = useCallback(() => {
    adminApi.companyPresets()
      .then(setPresets)
      .catch((e: any) => setError(e.message));
  }, []);

  const loadSavedFilters = useCallback(() => {
    adminApi.listCompanyFilters()
      .then(res => setSavedFilters(res.results || []))
      .catch((e: any) => setError(e.message));
  }, []);

  useEffect(() => {
    const state = parseUrlState();
    setBuilder(state.builder);
    setSelectedPresetKey(state.presetKey);
    setSelectedSavedFilterId(state.savedFilterId);
    setHasUrlBuilder(state.hasBuilder);
    loadPresets();
    loadSavedFilters();
  }, [loadPresets, loadSavedFilters]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  useEffect(() => {
    const url = new URL(window.location.href);
    const normalized = normalizeGroup(builder);
    if (normalized) {
      url.searchParams.set('filter_builder', JSON.stringify(normalized));
    } else {
      url.searchParams.delete('filter_builder');
    }
    if (selectedPresetKey) url.searchParams.set('preset', selectedPresetKey);
    else url.searchParams.delete('preset');
    if (selectedSavedFilterId) url.searchParams.set('saved_filter', selectedSavedFilterId);
    else url.searchParams.delete('saved_filter');
    window.history.replaceState({}, '', `${url.pathname}${url.search}${url.hash}`);
  }, [builder, selectedPresetKey, selectedSavedFilterId]);

  useEffect(() => {
    const onPopState = () => {
      const state = parseUrlState();
      setBuilder(state.builder);
      setSelectedPresetKey(state.presetKey);
      setSelectedSavedFilterId(state.savedFilterId);
      setHasUrlBuilder(state.hasBuilder);
    };
    window.addEventListener('popstate', onPopState);
    return () => window.removeEventListener('popstate', onPopState);
  }, []);

  useEffect(() => {
    if (hasUrlBuilder) return;
    if (selectedPresetKey && presets.length > 0) {
      const preset = presets.find(p => p.key === selectedPresetKey);
      if (preset) {
        setBuilder(filtersToBuilder(preset.filters));
      }
      return;
    }
    if (selectedSavedFilterId && savedFilters.length > 0) {
      const saved = savedFilters.find(f => String(f.id) === selectedSavedFilterId);
      if (saved) {
        setBuilder(filtersToBuilder(saved.filters));
      }
    }
  }, [hasUrlBuilder, selectedPresetKey, presets, selectedSavedFilterId, savedFilters]);

  const selectedPreset = presets.find(p => p.key === selectedPresetKey) || null;
  const selectedSavedFilter = savedFilters.find(f => String(f.id) === selectedSavedFilterId) || null;

  const updateBuilder = (next: FilterBuilderGroup) => {
    setSelectedPresetKey('');
    setSelectedSavedFilterId('');
    setHasUrlBuilder(true);
    setBuilder(next);
  };

  const applyPreset = (preset: CompanyPreset) => {
    setSelectedPresetKey(preset.key);
    setSelectedSavedFilterId('');
    setHasUrlBuilder(true);
    setBuilder(filtersToBuilder(preset.filters));
  };

  const applySavedFilter = (filter: SavedCompanyFilter) => {
    setSelectedPresetKey('');
    setSelectedSavedFilterId(String(filter.id));
    setHasUrlBuilder(true);
    setBuilder(filtersToBuilder(filter.filters));
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
        filters: normalizeGroup(builder) ? { ...queryParams, filter_builder: JSON.stringify(normalizeGroup(builder)) } : queryParams,
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

  const downloadCurrent = async (format: 'csv' | 'xlsx') => {
    try {
      const label = selectedPreset?.name || selectedSavedFilter?.name || 'companies-builder';
      const blob = await adminApi.downloadCompanyReport(format, queryParams);
      downloadBlob(blob, slugify(label) + `.${format}`);
    } catch (e: any) {
      setError(e.message);
    }
  };

  const exportPreset = async (preset: CompanyPreset, format: 'csv' | 'xlsx') => {
    try {
      const blob = await adminApi.downloadCompanyReport(format, { preset: preset.key });
      downloadBlob(blob, slugify(preset.name) + `.${format}`);
    } catch (e: any) {
      setError(e.message);
    }
  };

  const clearAll = () => {
    setBuilder({ id: uid(), type: 'group', logic: 'and', children: [] });
    setSelectedPresetKey('');
    setSelectedSavedFilterId('');
    setSavedFilterName('');
    setSavedFilterDescription('');
    setHasUrlBuilder(false);
  };

  return (
    <div className="space-y-5">
      <header className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 dark:text-white">Firmy</h1>
          <p className="text-sm text-slate-500 dark:text-slate-400">Kombinovaný filter builder s AND/OR skupinami, URL synchronizáciou a preset exportom.</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <button className="px-3 py-2 rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 text-sm" onClick={loadData}>Obnoviť</button>
          <button className="px-3 py-2 rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 text-sm" onClick={clearAll}>Reset builder</button>
          <button className="px-3 py-2 rounded-lg bg-emerald-600 text-white text-sm" onClick={() => downloadCurrent('csv')}>Export aktuálny CSV</button>
          <button className="px-3 py-2 rounded-lg bg-blue-600 text-white text-sm" onClick={() => downloadCurrent('xlsx')}>Export aktuálny XLSX</button>
        </div>
      </header>

      {report && (
        <section className="grid grid-cols-2 lg:grid-cols-4 gap-3">
          <SummaryCard label="Výsledky" value={report.count} />
          <SummaryCard label="Aktívne" value={report.active_count} />
          <SummaryCard label="Bez dlhov" value={report.debt_free_count} />
          <SummaryCard label="Priem. score" value={report.avg_lead_score.toFixed(1)} />
        </section>
      )}

      {report && (
        <section className="grid grid-cols-1 lg:grid-cols-3 gap-3">
          <SummaryCard label="Súčet tržieb" value={money(report.revenue_sum)} />
          <SummaryCard label="Súčet zisku" value={money(report.profit_sum)} />
          <SummaryCard label="Súčet daňových dlhov" value={money(report.tax_debt_sum)} />
        </section>
      )}

      <section className="bg-white dark:bg-slate-800/60 rounded-xl border border-slate-200 dark:border-slate-700/50 p-4 space-y-4">
        <div className="flex items-center justify-between gap-3">
          <div>
            <h2 className="text-sm font-semibold text-slate-900 dark:text-white">Presety</h2>
            <p className="text-xs text-slate-500 dark:text-slate-400">Každý preset má vlastné tlačidlo exportu CSV/XLSX.</p>
          </div>
          <button className="px-3 py-2 rounded-lg bg-slate-900 dark:bg-slate-100 text-white dark:text-slate-900 text-sm" onClick={() => setBuilder(filtersToBuilder(presets.find(p => p.key === selectedPresetKey)?.filters || {}))}>
            Použiť vybraný preset
          </button>
        </div>
        <div className="flex flex-wrap gap-3">
          {presets.map(preset => (
            <PresetCard
              key={preset.key}
              preset={preset}
              active={preset.key === selectedPresetKey}
              onApply={() => applyPreset(preset)}
              onExportCsv={() => exportPreset(preset, 'csv')}
              onExportXlsx={() => exportPreset(preset, 'xlsx')}
            />
          ))}
        </div>
      </section>

      <section className="grid gap-4 lg:grid-cols-2">
        <div className="bg-white dark:bg-slate-800/60 rounded-xl border border-slate-200 dark:border-slate-700/50 p-4 space-y-3">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-sm font-semibold text-slate-900 dark:text-white">Uložené filtre</h2>
              <p className="text-xs text-slate-500 dark:text-slate-400">Vaše osobné filtre pre neskoršie použitie.</p>
            </div>
          </div>
          <div className="grid gap-2 max-h-72 overflow-y-auto pr-1">
            {savedFilters.map(filter => (
              <div key={filter.id} className={`rounded-lg border p-3 ${String(filter.id) === selectedSavedFilterId ? 'border-blue-400 bg-blue-50 dark:bg-blue-900/20' : 'border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800/50'}`}>
                <div className="flex items-start justify-between gap-2">
                  <div>
                    <div className="font-medium text-slate-900 dark:text-white">{filter.name}</div>
                    <div className="text-xs text-slate-500 dark:text-slate-400">{filter.description || 'Bez popisu'}</div>
                  </div>
                  <div className="flex gap-1">
                    <button className="text-xs px-2 py-1 rounded-md border border-slate-200 dark:border-slate-700" onClick={() => applySavedFilter(filter)}>Použiť</button>
                    <button className="text-xs px-2 py-1 rounded-md border border-amber-300 text-amber-700 dark:text-amber-300" onClick={() => toggleFavorite(filter)}>{filter.is_favorite ? '★' : '☆'}</button>
                    <button className="text-xs px-2 py-1 rounded-md border border-red-300 text-red-600" onClick={() => deleteSavedFilter(filter.id)}>×</button>
                  </div>
                </div>
              </div>
            ))}
          </div>
          <div className="grid gap-2">
            <Input label="Názov uloženého filtra" value={savedFilterName} onChange={setSavedFilterName} placeholder="Napr. IT Trnava bez dlhov" />
            <Input label="Popis" value={savedFilterDescription} onChange={setSavedFilterDescription} placeholder="Krátky popis" />
            <button className="px-3 py-2 rounded-lg bg-blue-600 text-white text-sm" disabled={savingFilter} onClick={saveCurrentFilter}>{savingFilter ? 'Ukladám...' : 'Uložiť aktuálny builder'}</button>
          </div>
        </div>

        <div className="bg-white dark:bg-slate-800/60 rounded-xl border border-slate-200 dark:border-slate-700/50 p-4 space-y-3">
          <div className="flex items-center justify-between gap-2">
            <div>
              <h2 className="text-sm font-semibold text-slate-900 dark:text-white">Builder</h2>
              <p className="text-xs text-slate-500 dark:text-slate-400">AND/OR skupiny sa ukladajú aj do URL.</p>
            </div>
            <div className="flex gap-2">
              <button className="px-3 py-2 rounded-lg border border-slate-200 dark:border-slate-700 text-sm" onClick={() => updateBuilder(addGroup(builder, 'and'))}>+ Skupina AND</button>
              <button className="px-3 py-2 rounded-lg border border-slate-200 dark:border-slate-700 text-sm" onClick={() => updateBuilder(addGroup(builder, 'or'))}>+ Skupina OR</button>
              <button className="px-3 py-2 rounded-lg border border-slate-200 dark:border-slate-700 text-sm" onClick={() => updateBuilder(addCondition(builder, defaultCondition('mesto')))}>+ Podmienka</button>
            </div>
          </div>
          <GroupEditor
            group={builder}
            onChange={next => updateBuilder(next)}
            isRoot
          />
        </div>
      </section>

      <section className="bg-white dark:bg-slate-800/60 rounded-xl border border-slate-200 dark:border-slate-700/50 overflow-hidden">
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
              ) : companies.map(company => (
                <tr key={company.id} className="border-b border-slate-100 dark:border-slate-700/50 hover:bg-slate-50 dark:hover:bg-slate-800/40 transition-colors">
                  <td className="px-4 py-3 font-mono text-xs text-blue-600 dark:text-blue-400">{company.ico}</td>
                  <td className="px-4 py-3 font-medium text-slate-900 dark:text-white max-w-xs truncate">{company.nazov_UJ}</td>
                  <td className="px-4 py-3 text-slate-600 dark:text-slate-400">{company.pravna_forma || '—'}</td>
                  <td className="px-4 py-3 text-slate-600 dark:text-slate-400">{company.datum_zalozenia ? new Date(company.datum_zalozenia).toLocaleDateString('sk') : '—'}</td>
                  <td className="px-4 py-3">{company.datum_zrusenia ? <Badge color="red">Zrušená</Badge> : <Badge color="green">Aktívna</Badge>}</td>
                  <td className="px-4 py-3 text-slate-600 dark:text-slate-400 text-xs">{locationLabel(company.psc, company.mesto)}</td>
                  <td className="px-4 py-3 text-slate-600 dark:text-slate-400 text-xs">{company.sk_NACE || '—'}</td>
                  <td className="px-4 py-3 text-slate-600 dark:text-slate-400 text-xs">{debtLabel(company.debt_state, company.tax_debt, company.debt_vszp, company.debt_soc_poist)}</td>
                  <td className="px-4 py-3 text-slate-600 dark:text-slate-400 text-xs">{profitLabel(company.latest_profit)}</td>
                  <td className="px-4 py-3 text-slate-600 dark:text-slate-400 text-xs">{company.lead_score ?? '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      {report?.top_companies?.length ? (
        <section className="bg-white dark:bg-slate-800/60 rounded-xl border border-slate-200 dark:border-slate-700/50 p-4">
          <h2 className="text-sm font-semibold text-slate-900 dark:text-white mb-3">Top firmy podľa aktuálneho výberu</h2>
          <div className="flex flex-wrap gap-2">
            {report.top_companies.slice(0, 10).map(company => (
              <span key={company.id} className="px-3 py-2 rounded-full bg-slate-100 dark:bg-slate-700/60 text-xs text-slate-700 dark:text-slate-200">
                {company.nazov_UJ} · {company.lead_score ?? '—'}
              </span>
            ))}
          </div>
        </section>
      ) : null}

      {error && <ErrorBanner msg={error} />}
    </div>
  );
}

function GroupEditor({ group, onChange, isRoot = false }: {
  group: FilterBuilderGroup;
  onChange: (group: FilterBuilderGroup) => void;
  isRoot?: boolean;
}) {
  return (
    <div className={`rounded-xl border p-3 space-y-3 ${isRoot ? 'border-blue-200 dark:border-blue-900/60 bg-blue-50/30 dark:bg-blue-900/10' : 'border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800/40'}`}>
      <div className="flex flex-wrap items-center gap-2 justify-between">
        <div className="flex items-center gap-2">
          <span className="text-xs font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400">Skupina</span>
          <select className="px-2 py-1 rounded-md border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 text-xs" value={group.logic} onChange={e => onChange({ ...group, logic: e.target.value as FilterLogic })}>
            <option value="and">AND</option>
            <option value="or">OR</option>
          </select>
        </div>
        {!isRoot && (
          <button className="text-xs px-2 py-1 rounded-md border border-red-300 text-red-600" onClick={() => removeGroup(onChange)}>Odstrániť skupinu</button>
        )}
      </div>

      <div className="space-y-3">
        {group.children.length === 0 ? (
          <div className="text-xs text-slate-500 dark:text-slate-400 italic">Zatiaľ bez podmienok. Pridaj podmienku alebo podskupinu.</div>
        ) : group.children.map(child => child.type === 'condition' ? (
          <ConditionEditor
            key={child.id}
            node={child}
            onChange={next => onChange(updateChild(group, next))}
            onDelete={() => onChange(removeChild(group, child.id))}
          />
        ) : (
          <div key={child.id} className="pl-3 border-l-2 border-slate-200 dark:border-slate-700">
            <GroupEditor
              group={child}
              onChange={next => onChange(updateChild(group, next))}
            />
          </div>
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

function ConditionEditor({ node, onChange, onDelete }: {
  node: FilterBuilderCondition;
  onChange: (node: FilterBuilderCondition) => void;
  onDelete: () => void;
}) {
  const meta = fieldMeta(node.field);
  const operatorOptions = operatorsForField(node.field);
  return (
    <div className="grid grid-cols-1 md:grid-cols-12 gap-2 items-end rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 p-3">
      <div className="md:col-span-3">
        <Label text="Pole" />
        <select className="w-full px-3 py-2 rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 text-sm" value={node.field} onChange={e => onChange(defaultCondition(e.target.value))}>
          {FIELD_DEFS.map(field => <option key={field.value} value={field.value}>{field.label}</option>)}
        </select>
      </div>
      <div className="md:col-span-2">
        <Label text="Operátor" />
        <select className="w-full px-3 py-2 rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 text-sm" value={node.operator} onChange={e => onChange({ ...node, operator: e.target.value })}>
          {operatorOptions.map(opt => <option key={opt.value} value={opt.value}>{opt.label}</option>)}
        </select>
      </div>
      <div className="md:col-span-6">
        <Label text="Hodnota" />
        {meta.kind === 'select' ? (
          <select className="w-full px-3 py-2 rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 text-sm" value={node.value} onChange={e => onChange({ ...node, value: e.target.value })}>
            <option value="">Vyber</option>
            {meta.options.map(opt => <option key={opt} value={opt}>{selectLabel(node.field, opt)}</option>)}
          </select>
        ) : meta.kind === 'number' ? (
          <input type="number" className="w-full px-3 py-2 rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 text-sm" value={node.value} onChange={e => onChange({ ...node, value: e.target.value })} />
        ) : (
          <input type="text" className="w-full px-3 py-2 rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 text-sm" value={node.value} onChange={e => onChange({ ...node, value: e.target.value })} placeholder={meta.label} />
        )}
      </div>
      <div className="md:col-span-1 flex md:justify-end">
        <button className="px-3 py-2 rounded-lg border border-red-300 text-red-600 text-sm" onClick={onDelete}>×</button>
      </div>
    </div>
  );
}

function PresetCard({ preset, active, onApply, onExportCsv, onExportXlsx }: {
  preset: CompanyPreset;
  active: boolean;
  onApply: () => void;
  onExportCsv: () => void;
  onExportXlsx: () => void;
}) {
  return (
    <div className={`min-w-[240px] flex-1 rounded-xl border p-3 space-y-2 ${active ? 'border-blue-400 bg-blue-50 dark:bg-blue-900/20' : 'border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800/40'}`}>
      <div className="flex items-start justify-between gap-2">
        <div>
          <div className="font-semibold text-slate-900 dark:text-white">{preset.name}</div>
          <div className="text-xs text-slate-500 dark:text-slate-400">{preset.description}</div>
        </div>
        {active && <Badge color="blue">Aktívny</Badge>}
      </div>
      <div className="flex flex-wrap gap-2">
        <button className="text-xs px-2 py-1 rounded-md border border-slate-300 dark:border-slate-600" onClick={onApply}>Použiť</button>
        <button className="text-xs px-2 py-1 rounded-md bg-emerald-600 text-white" onClick={onExportCsv}>Export CSV</button>
        <button className="text-xs px-2 py-1 rounded-md bg-blue-600 text-white" onClick={onExportXlsx}>Export XLSX</button>
      </div>
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

function Input({ label, value, onChange, placeholder }: { label: string; value: string; onChange: (value: string) => void; placeholder?: string }) {
  return (
    <label className="space-y-1 block">
      <span className="block text-xs font-medium text-slate-500 dark:text-slate-400">{label}</span>
      <input className="w-full px-3 py-2 rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 text-sm" value={value} onChange={e => onChange(e.target.value)} placeholder={placeholder} />
    </label>
  );
}

function Label({ text }: { text: string }) {
  return <span className="block text-xs font-medium text-slate-500 dark:text-slate-400 mb-1">{text}</span>;
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

function ErrorBanner({ msg }: { msg: string }) {
  return <div className="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg px-4 py-3 text-sm text-red-700 dark:text-red-300"><i className="fas fa-exclamation-circle mr-2" />{msg}</div>;
}

function parseUrlState(): URLState {
  const params = new URLSearchParams(window.location.search);
  const presetKey = params.get('preset') || '';
  const savedFilterId = params.get('saved_filter') || '';
  const builderRaw = params.get('filter_builder');
  const builder = builderRaw ? parseBuilder(builderRaw) : { id: uid(), type: 'group', logic: 'and' as FilterLogic, children: [] };
  return { builder, presetKey, savedFilterId, hasBuilder: Boolean(builderRaw) };
}

function parseBuilder(raw: string): FilterBuilderGroup {
  try {
    const parsed = JSON.parse(raw);
    if (parsed && parsed.type === 'group') return normalizeGroup(parsed) || { id: uid(), type: 'group', logic: 'and', children: [] };
  } catch {
    // ignore
  }
  return { id: uid(), type: 'group', logic: 'and', children: [] };
}

function filtersToBuilder(filters: Record<string, any>): FilterBuilderGroup {
  if (filters.filter_builder) return parseBuilder(String(filters.filter_builder));
  const children: FilterBuilderNode[] = [];
  Object.entries(filters).forEach(([field, value]) => {
    if (value === undefined || value === null || value === '') return;
    if (field === 'preset' || field === 'saved_filter') return;
    if (field === 'filter_builder') return;
    children.push(defaultCondition(field, String(value)));
  });
  return { id: uid(), type: 'group', logic: 'and', children };
}

function normalizeGroup(group: FilterBuilderGroup | any): FilterBuilderGroup | null {
  if (!group || group.type !== 'group') return null;
  const children = (group.children || [])
    .map((child: any) => normalizeNode(child))
    .filter(Boolean) as FilterBuilderNode[];
  if (children.length === 0) return null;
  return {
    id: String(group.id || uid()),
    type: 'group',
    logic: (group.logic === 'or' ? 'or' : 'and') as FilterLogic,
    children,
  };
}

function normalizeNode(node: any): FilterBuilderNode | null {
  if (!node) return null;
  if (node.type === 'condition') {
    const value = String(node.value || '').trim();
    if (!value) return null;
    return {
      id: String(node.id || uid()),
      type: 'condition',
      field: String(node.field || 'q'),
      operator: String(node.operator || 'contains'),
      value,
    };
  }
  if (node.type === 'group') {
    return normalizeGroup(node);
  }
  return null;
}

function defaultCondition(field: string, value = ''): FilterBuilderCondition {
  return {
    id: uid(),
    type: 'condition',
    field,
    operator: defaultOperator(field),
    value,
  };
}

function defaultOperator(field: string) {
  return operatorsForField(field)[0]?.value || 'contains';
}

function operatorsForField(field: string) {
  const meta = fieldMeta(field);
  return meta.operators.map(op => ({ value: op, label: operatorLabel(op) }));
}

function fieldMeta(field: string) {
  return FIELD_DEFS.find(def => def.value === field) || FIELD_DEFS[0];
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
    sync_state: { healthy: 'Zdravý', failing: 'Chybový', blocked: 'Blokovaný' },
    pravna_forma: { '112': 's. r. o.', '121': 'a. s.', '101': 'FO-podnikateľ', '111': 'v. o. s.', '205': 'družstvo' },
    velkost_organizacie: { mikro: 'Mikro', small: 'Malá', medium: 'Stredná', large: 'Veľká' },
  };
  return map[field]?.[value] || value;
}

function operatorLabel(op: string) {
  return ({ contains: 'obsahuje', equals: '=', gte: '≥', lte: '≤', gt: '>', lt: '<' } as Record<string, string>)[op] || op;
}

function uid() {
  return typeof crypto !== 'undefined' && 'randomUUID' in crypto ? crypto.randomUUID() : `id_${Math.random().toString(36).slice(2, 10)}`;
}

function slugify(value: string) {
  return value
    .toLowerCase()
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/(^-|-$)+/g, '');
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

function money(value: string | number) {
  const n = Number(value);
  return Number.isNaN(n) ? String(value) : `${formatNumber(n)} €`;
}

function locationLabel(psc: string | null, mesto: string | null) {
  return [psc, mesto].filter(Boolean).join(' • ') || '—';
}

function debtLabel(state: 'debt_free' | 'has_debt', taxDebt: string | null, debtVszp: string | null, debtSocPoist: string | null) {
  if (state === 'debt_free') return 'Bez dlhov';
  const parts = [taxDebt, debtVszp, debtSocPoist].filter(v => v && Number(v) > 0).length;
  return `Dlhy (${parts})`;
}

function profitLabel(value: string | null) {
  if (value === null || value === undefined) return '—';
  const n = Number(value);
  if (Number.isNaN(n)) return value;
  if (n > 0) return `Zisk ${formatNumber(n)}`;
  if (n < 0) return `Strata ${formatNumber(Math.abs(n))}`;
  return 'Na nule';
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

function removeGroup(_onChange: (group: FilterBuilderGroup) => void) {
  return undefined as never;
}
*** End Patch
