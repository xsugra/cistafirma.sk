import React, { useCallback, useEffect, useState } from 'react';
import { adminApi } from '../api';
import type { AuditLogEntry } from '../types';

const METHOD_COLORS: Record<string, string> = {
  POST: 'bg-emerald-100 dark:bg-emerald-900/30 text-emerald-700 dark:text-emerald-400',
  PUT: 'bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-400',
  PATCH: 'bg-amber-100 dark:bg-amber-900/30 text-amber-700 dark:text-amber-400',
  DELETE: 'bg-red-100 dark:bg-red-900/30 text-red-700 dark:text-red-400',
};

export function AuditLog() {
  const [entries, setEntries] = useState<AuditLogEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [actionFilter, setActionFilter] = useState('');
  const [expanded, setExpanded] = useState<number | null>(null);

  const fetchData = useCallback(() => {
    setLoading(true);
    const params: Record<string, string> = {};
    if (actionFilter) params.action = actionFilter;
    adminApi.listAuditLog(params)
      .then(res => setEntries(Array.isArray(res) ? res : res.results || []))
      .catch(e => setError(e.message))
      .finally(() => setLoading(false));
  }, [actionFilter]);

  useEffect(() => { fetchData(); }, [fetchData]);

  return (
    <div className="space-y-4">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <h1 className="text-2xl font-bold text-slate-900 dark:text-white">Audit Log</h1>
        <div className="flex gap-2">
          <div className="relative">
            <i className="fas fa-filter absolute left-3 top-1/2 -translate-y-1/2 text-slate-400 text-sm" />
            <input
              type="text"
              placeholder="Filtrovať akcie..."
              value={actionFilter}
              onChange={e => setActionFilter(e.target.value)}
              className="pl-9 pr-4 py-2 rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 text-sm text-slate-900 dark:text-white placeholder-slate-400 w-48 focus:outline-none focus:ring-2 focus:ring-blue-500/40"
            />
          </div>
          <button
            onClick={fetchData}
            className="px-3 py-2 bg-slate-100 dark:bg-slate-700 hover:bg-slate-200 dark:hover:bg-slate-600 text-slate-700 dark:text-slate-300 rounded-lg text-sm transition-colors"
          >
            <i className="fas fa-sync-alt" />
          </button>
        </div>
      </div>

      {error && (
        <div className="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg px-4 py-3 text-sm text-red-700 dark:text-red-300">
          <i className="fas fa-exclamation-circle mr-2" />{error}
        </div>
      )}

      <div className="bg-white dark:bg-slate-800/60 rounded-xl border border-slate-200 dark:border-slate-700/50 overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800/80">
                <Th>Čas</Th>
                <Th>Metóda</Th>
                <Th>Akcia</Th>
                <Th>Používateľ</Th>
                <Th>Path</Th>
                <Th>Status</Th>
                <Th>IP</Th>
                <Th></Th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr><td colSpan={8} className="text-center py-12 text-slate-400"><i className="fas fa-spinner fa-spin mr-2" />Načítavam...</td></tr>
              ) : entries.length === 0 ? (
                <tr><td colSpan={8} className="text-center py-12 text-slate-400">Žiadne záznamy</td></tr>
              ) : (
                entries.map(e => (
                  <React.Fragment key={e.id}>
                    <tr className="border-b border-slate-100 dark:border-slate-700/50 hover:bg-slate-50 dark:hover:bg-slate-800/40 transition-colors">
                      <td className="px-4 py-3 text-xs text-slate-500 dark:text-slate-400 whitespace-nowrap">{new Date(e.created_at).toLocaleString('sk')}</td>
                      <td className="px-4 py-3">
                        <span className={`inline-flex px-2 py-0.5 rounded text-xs font-mono font-bold ${METHOD_COLORS[e.method] || 'bg-slate-100 dark:bg-slate-700 text-slate-600'}`}>{e.method}</span>
                      </td>
                      <td className="px-4 py-3 font-medium text-slate-900 dark:text-white text-xs">{e.action}</td>
                      <td className="px-4 py-3 text-slate-600 dark:text-slate-400 text-xs">{e.actor_email || '—'}</td>
                      <td className="px-4 py-3 text-xs font-mono text-slate-500 dark:text-slate-400 max-w-[200px] truncate">{e.path}</td>
                      <td className="px-4 py-3">
                        {e.status_code && (
                          <span className={`text-xs font-mono font-bold ${
                            e.status_code < 300 ? 'text-emerald-600' :
                            e.status_code < 400 ? 'text-blue-600' :
                            e.status_code < 500 ? 'text-amber-600' : 'text-red-600'
                          }`}>{e.status_code}</span>
                        )}
                      </td>
                      <td className="px-4 py-3 text-xs text-slate-400 font-mono">{e.ip_address || '—'}</td>
                      <td className="px-4 py-3">
                        {e.payload && Object.keys(e.payload).length > 0 && (
                          <button
                            onClick={() => setExpanded(expanded === e.id ? null : e.id)}
                            className="text-slate-400 hover:text-blue-600 transition-colors"
                          >
                            <i className={`fas ${expanded === e.id ? 'fa-chevron-up' : 'fa-chevron-down'} text-xs`} />
                          </button>
                        )}
                      </td>
                    </tr>
                    {expanded === e.id && e.payload && (
                      <tr className="bg-slate-50 dark:bg-slate-900/50">
                        <td colSpan={8} className="px-6 py-3">
                          <pre className="text-xs font-mono text-slate-600 dark:text-slate-400 overflow-auto max-h-40 whitespace-pre-wrap">
                            {JSON.stringify(e.payload, null, 2)}
                          </pre>
                        </td>
                      </tr>
                    )}
                  </React.Fragment>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

function Th({ children }: { children?: React.ReactNode }) {
  return <th className="px-4 py-3 text-left text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wider">{children}</th>;
}
