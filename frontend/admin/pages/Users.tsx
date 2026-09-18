import React, { useCallback, useEffect, useState } from 'react';
import { adminApi } from '../api';
import type { AdminUser } from '../types';

export function Users() {
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [search, setSearch] = useState('');
  const [staffFilter, setStaffFilter] = useState('');
  const [toggling, setToggling] = useState<number | null>(null);

  const fetchData = useCallback(() => {
    setLoading(true);
    const params: Record<string, string> = {};
    if (search) params.q = search;
    if (staffFilter) params.is_staff = staffFilter;
    adminApi.listUsers(params)
      .then(res => setUsers(Array.isArray(res) ? res : res.results || []))
      .catch(e => setError(e.message))
      .finally(() => setLoading(false));
  }, [search, staffFilter]);

  useEffect(() => { fetchData(); }, [fetchData]);

  const toggleActive = async (user: AdminUser) => {
    setToggling(user.id);
    try {
      await adminApi.updateUser(user.id, { is_active: !user.is_active });
      setUsers(prev => prev.map(u => u.id === user.id ? { ...u, is_active: !u.is_active } : u));
    } catch (e: any) {
      setError(e.message);
    } finally {
      setToggling(null);
    }
  };

  return (
    <div className="space-y-4">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <h1 className="text-2xl font-bold text-slate-900 dark:text-white">Používatelia</h1>
        <div className="flex gap-2">
          <div className="relative">
            <i className="fas fa-search absolute left-3 top-1/2 -translate-y-1/2 text-slate-400 text-sm" />
            <input
              type="text"
              placeholder="Email alebo meno..."
              value={search}
              onChange={e => setSearch(e.target.value)}
              className="pl-9 pr-4 py-2 rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 text-base sm:text-sm text-slate-900 dark:text-white placeholder-slate-400 w-56 focus:outline-none focus:ring-2 focus:ring-blue-500/40"
            />
          </div>
          <select
            value={staffFilter}
            onChange={e => setStaffFilter(e.target.value)}
            className="px-3 py-2 rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 text-base sm:text-sm text-slate-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-blue-500/40"
          >
            <option value="">Všetci</option>
            <option value="1">Staff</option>
            <option value="0">Bežní</option>
          </select>
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
                <Th>Email</Th>
                <Th>Meno</Th>
                <Th>Plán</Th>
                <Th>Rola</Th>
                <Th>Stav</Th>
                <Th>Posl. prihlásenie</Th>
                <Th>Registrovaný</Th>
                <Th>Akcia</Th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr><td colSpan={8} className="text-center py-12 text-slate-400"><i className="fas fa-spinner fa-spin mr-2" />Načítavam...</td></tr>
              ) : users.length === 0 ? (
                <tr><td colSpan={8} className="text-center py-12 text-slate-400">Žiadni používatelia</td></tr>
              ) : (
                users.map(u => (
                  <tr key={u.id} className="border-b border-slate-100 dark:border-slate-700/50 hover:bg-slate-50 dark:hover:bg-slate-800/40 transition-colors">
                    <td className="px-4 py-3 text-slate-900 dark:text-white font-medium">{u.email}</td>
                    <td className="px-4 py-3 text-slate-600 dark:text-slate-400">{[u.first_name, u.last_name].filter(Boolean).join(' ') || '—'}</td>
                    <td className="px-4 py-3">
                      <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-blue-50 dark:bg-blue-900/30 text-blue-700 dark:text-blue-400">
                        {u.subscription_plan_name || 'Free'}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-xs">
                      {u.is_superuser ? (
                        <span className="text-blue-600 dark:text-blue-400 font-semibold">Superuser</span>
                      ) : u.is_staff ? (
                        <span className="text-amber-600 dark:text-amber-400 font-semibold">Staff</span>
                      ) : (
                        <span className="text-slate-500">User</span>
                      )}
                    </td>
                    <td className="px-4 py-3">
                      {u.is_active ? (
                        <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-emerald-50 dark:bg-emerald-900/30 text-emerald-700 dark:text-emerald-400">Aktívny</span>
                      ) : (
                        <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-red-50 dark:bg-red-900/30 text-red-700 dark:text-red-400">Neaktívny</span>
                      )}
                    </td>
                    <td className="px-4 py-3 text-slate-500 dark:text-slate-400 text-xs">{u.last_login ? new Date(u.last_login).toLocaleString('sk') : 'nikdy'}</td>
                    <td className="px-4 py-3 text-slate-500 dark:text-slate-400 text-xs">{new Date(u.created_at).toLocaleDateString('sk')}</td>
                    <td className="px-4 py-3">
                      <button
                        onClick={() => toggleActive(u)}
                        disabled={toggling === u.id}
                        className={`text-xs px-3 py-1.5 rounded-lg font-medium transition-colors ${
                          u.is_active
                            ? 'bg-red-50 dark:bg-red-900/20 text-red-600 dark:text-red-400 hover:bg-red-100 dark:hover:bg-red-900/40'
                            : 'bg-emerald-50 dark:bg-emerald-900/20 text-emerald-600 dark:text-emerald-400 hover:bg-emerald-100 dark:hover:bg-emerald-900/40'
                        } disabled:opacity-50`}
                      >
                        {toggling === u.id ? <i className="fas fa-spinner fa-spin" /> : u.is_active ? 'Deaktivovať' : 'Aktivovať'}
                      </button>
                    </td>
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
