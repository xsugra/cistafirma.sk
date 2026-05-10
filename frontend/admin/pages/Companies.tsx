import React, { useCallback, useEffect, useState } from 'react';
import { adminApi } from '../api';
import type { AdminCompany } from '../types';

export function Companies() {
  const [companies, setCompanies] = useState<AdminCompany[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [search, setSearch] = useState('');
  const [activeFilter, setActiveFilter] = useState<string>('');

  const fetchData = useCallback(() => {
    setLoading(true);
    const params: Record<string, string> = {};
    if (search) params.q = search;
    if (activeFilter) params.active = activeFilter;
    adminApi.listCompanies(params)
      .then(res => setCompanies(Array.isArray(res) ? res : res.results || []))
      .catch(e => setError(e.message))
      .finally(() => setLoading(false));
  }, [search, activeFilter]);

  useEffect(() => { fetchData(); }, [fetchData]);

  return (
    <div className="space-y-4">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <h1 className="text-2xl font-bold text-slate-900 dark:text-white">Firmy</h1>
        <div className="flex gap-2">
          <div className="relative">
            <i className="fas fa-search absolute left-3 top-1/2 -translate-y-1/2 text-slate-400 text-sm" />
            <input
              type="text"
              placeholder="Hľadať ICO alebo názov..."
              value={search}
              onChange={e => setSearch(e.target.value)}
              className="pl-9 pr-4 py-2 rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 text-sm text-slate-900 dark:text-white placeholder-slate-400 w-64 focus:outline-none focus:ring-2 focus:ring-blue-500/40"
            />
          </div>
          <select
            value={activeFilter}
            onChange={e => setActiveFilter(e.target.value)}
            className="px-3 py-2 rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 text-sm text-slate-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-blue-500/40"
          >
            <option value="">Všetky</option>
            <option value="1">Aktívne</option>
            <option value="0">Zrušené</option>
          </select>
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
                <Th>Posl. kontrola dlhov</Th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr><td colSpan={6} className="text-center py-12 text-slate-400"><i className="fas fa-spinner fa-spin mr-2" />Načítavam...</td></tr>
              ) : companies.length === 0 ? (
                <tr><td colSpan={6} className="text-center py-12 text-slate-400">Žiadne výsledky</td></tr>
              ) : (
                companies.map(c => (
                  <tr key={c.id} className="border-b border-slate-100 dark:border-slate-700/50 hover:bg-slate-50 dark:hover:bg-slate-800/40 transition-colors">
                    <td className="px-4 py-3 font-mono text-xs text-blue-600 dark:text-blue-400">{c.ico}</td>
                    <td className="px-4 py-3 font-medium text-slate-900 dark:text-white max-w-xs truncate">{c.nazov_UJ}</td>
                    <td className="px-4 py-3 text-slate-600 dark:text-slate-400">{c.pravna_forma || '—'}</td>
                    <td className="px-4 py-3 text-slate-600 dark:text-slate-400">{c.datum_zalozenia ? new Date(c.datum_zalozenia).toLocaleDateString('sk') : '—'}</td>
                    <td className="px-4 py-3">
                      {c.datum_zrusenia ? (
                        <Badge color="red">Zrušená</Badge>
                      ) : (
                        <Badge color="green">Aktívna</Badge>
                      )}
                    </td>
                    <td className="px-4 py-3 text-slate-600 dark:text-slate-400 text-xs">{c.last_insurance_debt ? new Date(c.last_insurance_debt).toLocaleDateString('sk') : '—'}</td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
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

function ErrorBanner({ msg }: { msg: string }) {
  return (
    <div className="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg px-4 py-3 text-sm text-red-700 dark:text-red-300">
      <i className="fas fa-exclamation-circle mr-2" />{msg}
    </div>
  );
}
