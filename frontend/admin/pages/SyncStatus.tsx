import React, { useCallback, useEffect, useState } from 'react';
import { adminApi } from '../api';
import type { CompanySyncStatus } from '../types';

const SOURCE_LABELS: Record<string, string> = {
  ruz: 'RUZ základné údaje',
  orsr: 'ORSR profil',
  financials: 'Finančné výkazy',
  vszp: 'VšZP dlhy',
  social: 'Sociálna poisťovňa',
  fs: 'Finančná správa',
};

const PAGE_SIZE = 50;

function StateBadge({ row }: { row: CompanySyncStatus }) {
  if (row.is_blocked) {
    return (
      <span
        className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium bg-red-50 dark:bg-red-900/30 text-red-700 dark:text-red-400"
        title={row.blocked_reason || undefined}
      >
        <i className="fas fa-ban text-[10px]" />
        Blokované
      </span>
    );
  }
  if (row.consecutive_failures > 0) {
    return (
      <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium bg-amber-50 dark:bg-amber-900/30 text-amber-700 dark:text-amber-400">
        <i className="fas fa-exclamation-triangle text-[10px]" />
        {row.consecutive_failures}× zlyhanie
      </span>
    );
  }
  return (
    <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium bg-emerald-50 dark:bg-emerald-900/30 text-emerald-700 dark:text-emerald-400">
      <i className="fas fa-check text-[10px]" />
      V poriadku
    </span>
  );
}

/**
 * The reason a company is where it is.
 *
 * `last_error` is written only when an attempt failed; `last_detail` is written
 * on every attempt, including the ones that succeeded by not recording
 * anything. A company whose statements were read and none of them recordable is
 * an *answered* attempt, so it shows a green badge and is exactly the row an
 * operator is looking for — which is why both are printed here and neither is
 * summarised away.
 */
function ReasonCell({ row }: { row: CompanySyncStatus }) {
  const error = row.last_error?.trim();
  const detail = row.last_detail?.trim();
  if (!error && !detail) return <span className="text-slate-400 dark:text-slate-500">—</span>;
  return (
    <div className="space-y-0.5">
      {error && (
        <p className="text-xs text-red-600 dark:text-red-400 line-clamp-2" title={error}>
          {error}
        </p>
      )}
      {detail && (
        <p className="text-xs text-slate-500 dark:text-slate-400 line-clamp-2" title={detail}>
          {detail}
        </p>
      )}
    </div>
  );
}

function formatDateTime(value: string | null): string {
  if (!value) return '—';
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return '—';
  return d.toLocaleString('sk-SK', { dateStyle: 'short', timeStyle: 'short' });
}

export function SyncStatus() {
  const [rows, setRows] = useState<CompanySyncStatus[]>([]);
  const [count, setCount] = useState(0);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [source, setSource] = useState('');
  const [onlyErrors, setOnlyErrors] = useState(false);
  const [onlyBlocked, setOnlyBlocked] = useState(false);
  const [onlyWithDetail, setOnlyWithDetail] = useState(false);

  const fetchRows = useCallback(() => {
    setLoading(true);
    const params: Record<string, string> = { page: String(page), page_size: String(PAGE_SIZE) };
    if (source) params.source = source;
    if (onlyErrors) params.has_errors = '1';
    if (onlyBlocked) params.blocked = '1';
    if (onlyWithDetail) params.has_detail = '1';
    adminApi
      .listSyncStatuses(params)
      .then(res => {
        setRows(Array.isArray(res) ? res : res.results || []);
        setCount(Array.isArray(res) ? res.length : res.count || 0);
        setError('');
      })
      .catch(e => setError(e.message))
      .finally(() => setLoading(false));
  }, [page, source, onlyErrors, onlyBlocked, onlyWithDetail]);

  useEffect(() => {
    fetchRows();
  }, [fetchRows]);

  // Any filter change has to start from the first page: page 7 of an unfiltered
  // list is not page 7 of the filtered one.
  const changeFilter = (apply: () => void) => {
    setPage(1);
    apply();
  };

  const pages = Math.max(1, Math.ceil(count / PAGE_SIZE));

  return (
    <div className="space-y-4">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 dark:text-white">Stav synchronizácie</h1>
          <p className="text-sm text-slate-500 dark:text-slate-400 mt-0.5">
            Prečo je firma tam, kde je — vrátane pokusov, ktoré prebehli a nič nezapísali.
          </p>
        </div>
        <button
          onClick={fetchRows}
          className="self-start px-3 py-2 bg-slate-100 dark:bg-slate-700 hover:bg-slate-200 dark:hover:bg-slate-600 text-slate-700 dark:text-slate-300 rounded-lg text-sm transition-colors"
          title="Obnoviť"
        >
          <i className="fas fa-sync-alt" />
        </button>
      </div>

      <div className="flex flex-wrap items-center gap-3">
        <select
          value={source}
          onChange={e => changeFilter(() => setSource(e.target.value))}
          className="px-3 py-2 rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 text-sm text-slate-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-blue-500/40"
        >
          <option value="">Všetky zdroje</option>
          {Object.entries(SOURCE_LABELS).map(([value, label]) => (
            <option key={value} value={value}>{label}</option>
          ))}
        </select>

        <Toggle
          checked={onlyErrors}
          onChange={v => changeFilter(() => setOnlyErrors(v))}
          label="Len so zlyhaniami"
        />
        <Toggle
          checked={onlyBlocked}
          onChange={v => changeFilter(() => setOnlyBlocked(v))}
          label="Len blokované"
        />
        <Toggle
          checked={onlyWithDetail}
          onChange={v => changeFilter(() => setOnlyWithDetail(v))}
          label="Len s dôvodom"
        />
      </div>

      {error && (
        <div className="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg px-4 py-3 text-sm text-red-700 dark:text-red-300">
          <i className="fas fa-exclamation-circle mr-2" />
          {error}
        </div>
      )}

      <div className="bg-white dark:bg-slate-800/60 rounded-xl border border-slate-200 dark:border-slate-700/50 overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800/80">
                <Th>Firma</Th>
                <Th>Zdroj</Th>
                <Th>Stav</Th>
                <Th>Naposledy</Th>
                <Th>Dôvod</Th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr>
                  <td colSpan={5} className="text-center py-12 text-slate-400">
                    <i className="fas fa-spinner fa-spin mr-2" />
                    Načítavam...
                  </td>
                </tr>
              ) : rows.length === 0 ? (
                <tr>
                  <td colSpan={5} className="text-center py-12 text-slate-400">
                    Pre tento filter nemá žiadna firma záznam
                  </td>
                </tr>
              ) : (
                rows.map(row => (
                  <tr
                    key={row.id}
                    className="border-b border-slate-100 dark:border-slate-700/50 hover:bg-slate-50 dark:hover:bg-slate-800/40 transition-colors align-top"
                  >
                    <td className="px-4 py-3">
                      <p className="font-medium text-slate-900 dark:text-white">{row.company_name}</p>
                      <p className="font-mono text-xs text-slate-500 dark:text-slate-400">{row.company_ico}</p>
                    </td>
                    <td className="px-4 py-3 text-xs text-slate-600 dark:text-slate-400">
                      {SOURCE_LABELS[row.source] || row.source}
                    </td>
                    <td className="px-4 py-3">
                      <StateBadge row={row} />
                    </td>
                    <td className="px-4 py-3 text-xs text-slate-500 dark:text-slate-400 whitespace-nowrap">
                      {formatDateTime(row.last_attempted_at)}
                      {row.next_retry_at && (
                        <span className="block text-slate-400 dark:text-slate-500">
                          ďalší pokus {formatDateTime(row.next_retry_at)}
                        </span>
                      )}
                    </td>
                    <td className="px-4 py-3 max-w-md">
                      <ReasonCell row={row} />
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      <div className="flex items-center justify-between text-sm text-slate-500 dark:text-slate-400">
        <span>
          {count === 0
            ? 'Nič na zobrazenie'
            : `${(page - 1) * PAGE_SIZE + 1}–${Math.min(page * PAGE_SIZE, count)} z ${count.toLocaleString('sk-SK')} záznamov`}
        </span>
        <div className="flex items-center gap-2">
          <button
            onClick={() => setPage(p => Math.max(1, p - 1))}
            disabled={page <= 1 || loading}
            className="px-3 py-1.5 rounded-lg border border-slate-200 dark:border-slate-700 hover:bg-slate-100 dark:hover:bg-slate-700 disabled:opacity-40 disabled:hover:bg-transparent transition-colors"
          >
            <i className="fas fa-chevron-left text-xs" />
          </button>
          <span className="tabular-nums">
            {page} / {pages}
          </span>
          <button
            onClick={() => setPage(p => Math.min(pages, p + 1))}
            disabled={page >= pages || loading}
            className="px-3 py-1.5 rounded-lg border border-slate-200 dark:border-slate-700 hover:bg-slate-100 dark:hover:bg-slate-700 disabled:opacity-40 disabled:hover:bg-transparent transition-colors"
          >
            <i className="fas fa-chevron-right text-xs" />
          </button>
        </div>
      </div>
    </div>
  );
}

function Toggle({
  checked,
  onChange,
  label,
}: {
  checked: boolean;
  onChange: (value: boolean) => void;
  label: string;
}) {
  return (
    <label
      className={`inline-flex items-center gap-2 px-3 py-2 rounded-lg border text-sm cursor-pointer transition-colors ${
        checked
          ? 'border-blue-300 dark:border-blue-700 bg-blue-50 dark:bg-blue-900/20 text-blue-700 dark:text-blue-400'
          : 'border-slate-200 dark:border-slate-700 text-slate-600 dark:text-slate-400 hover:bg-slate-50 dark:hover:bg-slate-800'
      }`}
    >
      <input
        type="checkbox"
        checked={checked}
        onChange={e => onChange(e.target.checked)}
        className="accent-blue-600"
      />
      {label}
    </label>
  );
}

function Th({ children }: { children: React.ReactNode }) {
  return (
    <th className="px-4 py-3 text-left text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wider">
      {children}
    </th>
  );
}
