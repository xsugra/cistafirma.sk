import React, { useEffect, useState } from 'react';
import { adminApi } from '../api';
import type { ScheduledTask } from '../types';

export function ScheduledTasks() {
  const [tasks, setTasks] = useState<ScheduledTask[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [toggling, setToggling] = useState<number | null>(null);

  const fetchTasks = () => {
    setLoading(true);
    adminApi.listScheduledTasks()
      .then(res => setTasks(res.results || []))
      .catch(e => setError(e.message))
      .finally(() => setLoading(false));
  };

  useEffect(() => { fetchTasks(); }, []);

  const toggle = async (id: number) => {
    setToggling(id);
    try {
      const res = await adminApi.toggleScheduledTask(id);
      setTasks(prev => prev.map(t => t.id === id ? { ...t, enabled: res.enabled } : t));
    } catch (e: any) {
      setError(e.message);
    } finally {
      setToggling(null);
    }
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-slate-900 dark:text-white">Periodické úlohy</h1>
        <button
          onClick={fetchTasks}
          className="px-3 py-2 bg-slate-100 dark:bg-slate-700 hover:bg-slate-200 dark:hover:bg-slate-600 text-slate-700 dark:text-slate-300 rounded-lg text-sm transition-colors"
        >
          <i className="fas fa-sync-alt" />
        </button>
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
                <Th>Názov</Th>
                <Th>Task</Th>
                <Th>Interval</Th>
                <Th>Queue</Th>
                <Th>Posledné spustenie</Th>
                <Th>Počet</Th>
                <Th>Stav</Th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr><td colSpan={7} className="text-center py-12 text-slate-400"><i className="fas fa-spinner fa-spin mr-2" />Načítavam...</td></tr>
              ) : tasks.length === 0 ? (
                <tr><td colSpan={7} className="text-center py-12 text-slate-400">Žiadne periodické úlohy</td></tr>
              ) : (
                tasks.map(t => (
                  <tr key={t.id} className="border-b border-slate-100 dark:border-slate-700/50 hover:bg-slate-50 dark:hover:bg-slate-800/40 transition-colors">
                    <td className="px-4 py-3 font-medium text-slate-900 dark:text-white">{t.name}</td>
                    <td className="px-4 py-3 text-xs font-mono text-slate-500 dark:text-slate-400 max-w-xs truncate">{t.task}</td>
                    <td className="px-4 py-3 text-slate-600 dark:text-slate-400 text-xs">{t.interval || t.crontab || '—'}</td>
                    <td className="px-4 py-3">
                      {t.queue ? (
                        <span className="inline-flex px-2 py-0.5 rounded text-xs font-mono bg-slate-100 dark:bg-slate-700 text-slate-600 dark:text-slate-400">{t.queue}</span>
                      ) : '—'}
                    </td>
                    <td className="px-4 py-3 text-slate-500 dark:text-slate-400 text-xs">{t.last_run_at ? new Date(t.last_run_at).toLocaleString('sk') : 'nikdy'}</td>
                    <td className="px-4 py-3 text-slate-600 dark:text-slate-400">{t.total_run_count}</td>
                    <td className="px-4 py-3">
                      <button
                        onClick={() => toggle(t.id)}
                        disabled={toggling === t.id}
                        className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${
                          t.enabled ? 'bg-blue-600' : 'bg-slate-300 dark:bg-slate-600'
                        } ${toggling === t.id ? 'opacity-50' : ''}`}
                      >
                        <span className={`inline-block h-4 w-4 rounded-full bg-white shadow transform transition-transform ${
                          t.enabled ? 'translate-x-6' : 'translate-x-1'
                        }`} />
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
