import React, { useEffect, useState } from 'react';
import { adminApi } from '../api';
import type { DashboardOverview, DashboardSync, DashboardSystem } from '../types';

function KpiCard({ label, value, sub, icon, color }: {
  label: string; value: string | number; sub?: string; icon: string; color: string;
}) {
  return (
    <div className="bg-white dark:bg-slate-800/60 rounded-xl border border-slate-200 dark:border-slate-700/50 p-5 flex items-start gap-4">
      <div className={`w-11 h-11 rounded-lg flex items-center justify-center text-white ${color}`}>
        <i className={`fas ${icon} text-lg`} />
      </div>
      <div className="min-w-0">
        <p className="text-sm text-slate-500 dark:text-slate-400">{label}</p>
        <p className="text-2xl font-bold text-slate-900 dark:text-white mt-0.5">{value}</p>
        {sub && <p className="text-xs text-slate-400 dark:text-slate-500 mt-0.5">{sub}</p>}
      </div>
    </div>
  );
}

function HealthDot({ status }: { status: string }) {
  const ok = status === 'ok';
  return (
    <span className={`inline-block w-2.5 h-2.5 rounded-full mr-2 ${ok ? 'bg-emerald-500' : 'bg-red-500'}`} />
  );
}

function ThroughputChart({ succeeded, failed }: { succeeded: number[]; failed: number[] }) {
  const max = Math.max(...succeeded, ...failed, 1);
  return (
    <div className="mt-4">
      <div className="flex items-end gap-[3px] h-32">
        {succeeded.map((s, i) => {
          const f = failed[i] || 0;
          const sH = (s / max) * 100;
          const fH = (f / max) * 100;
          return (
            <div key={i} className="flex-1 flex flex-col justify-end items-center gap-0" title={`${24 - i}h ago: ${s} ok, ${f} fail`}>
              <div className="w-full bg-emerald-500/80 rounded-t-sm" style={{ height: `${sH}%`, minHeight: s > 0 ? 2 : 0 }} />
              {f > 0 && <div className="w-full bg-red-400/80" style={{ height: `${fH}%`, minHeight: 2 }} />}
            </div>
          );
        })}
      </div>
      <div className="flex justify-between mt-1 text-[10px] text-slate-400">
        <span>-24h</span>
        <span>-12h</span>
        <span>teraz</span>
      </div>
    </div>
  );
}

export function Dashboard() {
  const [overview, setOverview] = useState<DashboardOverview | null>(null);
  const [sync, setSync] = useState<DashboardSync | null>(null);
  const [system, setSystem] = useState<DashboardSystem | null>(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      adminApi.dashboardOverview(),
      adminApi.dashboardSync(),
      adminApi.dashboardSystem(),
    ])
      .then(([o, s, sys]) => { setOverview(o); setSync(s); setSystem(sys); })
      .catch(e => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <Loading />;
  if (error) return <ErrorMsg msg={error} />;
  if (!overview) return null;

  const c = overview.companies;
  const u = overview.users;
  const sn = overview.sync;

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-slate-900 dark:text-white">Dashboard</h1>

      {/* KPI cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <KpiCard label="Firmy celkom" value={c.total.toLocaleString('sk')} sub={`${c.active.toLocaleString('sk')} aktívnych`} icon="fa-building" color="bg-blue-600" />
        <KpiCard label="ORSR pokrytie" value={`${c.orsr_coverage_pct}%`} sub={`${c.with_orsr.toLocaleString('sk')} profilov`} icon="fa-landmark" color="bg-indigo-600" />
        <KpiCard label="Financie pokrytie" value={`${c.financials_coverage_pct}%`} sub={`${c.with_financials.toLocaleString('sk')} firiem`} icon="fa-chart-line" color="bg-emerald-600" />
        <KpiCard label="Používatelia" value={u.total} sub={`${u.active_7d} aktívnych za 7d`} icon="fa-users" color="bg-violet-600" />
      </div>

      {/* Sync row */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <div className="lg:col-span-2 bg-white dark:bg-slate-800/60 rounded-xl border border-slate-200 dark:border-slate-700/50 p-5">
          <h2 className="text-sm font-semibold text-slate-900 dark:text-white mb-1">Sync Throughput (24h)</h2>
          <div className="flex gap-4 text-xs text-slate-500 dark:text-slate-400 mb-2">
            <span><span className="inline-block w-2.5 h-2.5 rounded-sm bg-emerald-500 mr-1" />Úspešné</span>
            <span><span className="inline-block w-2.5 h-2.5 rounded-sm bg-red-400 mr-1" />Zlyhané</span>
          </div>
          {sync && <ThroughputChart succeeded={sync.throughput_24h.succeeded_per_hour} failed={sync.throughput_24h.failed_per_hour} />}
        </div>

        <div className="bg-white dark:bg-slate-800/60 rounded-xl border border-slate-200 dark:border-slate-700/50 p-5">
          <h2 className="text-sm font-semibold text-slate-900 dark:text-white mb-3">Sync Stav</h2>
          <div className="space-y-3">
            <StatRow label="Aktívne joby" value={sn.active_jobs} />
            <StatRow label="Dokončené (24h)" value={sn.completed_jobs_24h} color="text-emerald-600 dark:text-emerald-400" />
            <StatRow label="Zlyhané (24h)" value={sn.failed_jobs_24h} color={sn.failed_jobs_24h > 0 ? 'text-red-600 dark:text-red-400' : undefined} />
            <StatRow label="Blokované firmy" value={sn.blocked_companies} color={sn.blocked_companies > 0 ? 'text-amber-600 dark:text-amber-400' : undefined} />
          </div>
        </div>
      </div>

      {/* Source coverage + System health */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {sync && (
          <div className="bg-white dark:bg-slate-800/60 rounded-xl border border-slate-200 dark:border-slate-700/50 p-5">
            <h2 className="text-sm font-semibold text-slate-900 dark:text-white mb-3">Pokrytie podľa zdroja</h2>
            <div className="space-y-3">
              {sync.sources.map(s => (
                <div key={s.source}>
                  <div className="flex justify-between text-sm mb-1">
                    <span className="text-slate-700 dark:text-slate-300">{s.label}</span>
                    <span className="font-medium text-slate-900 dark:text-white">{s.coverage_pct}%</span>
                  </div>
                  <div className="h-2 bg-slate-100 dark:bg-slate-700 rounded-full overflow-hidden">
                    <div className="h-full bg-blue-600 rounded-full transition-all" style={{ width: `${Math.min(s.coverage_pct, 100)}%` }} />
                  </div>
                  {s.failing_count > 0 && (
                    <p className="text-xs text-amber-600 dark:text-amber-400 mt-0.5">{s.failing_count} zlyhávajúcich</p>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}

        {system && (
          <div className="bg-white dark:bg-slate-800/60 rounded-xl border border-slate-200 dark:border-slate-700/50 p-5">
            <h2 className="text-sm font-semibold text-slate-900 dark:text-white mb-3">Systém</h2>
            <div className="space-y-2 text-sm">
              <div className="flex items-center justify-between">
                <span className="text-slate-600 dark:text-slate-400"><HealthDot status={system.health.db} />Databáza</span>
                <span className="font-medium text-slate-900 dark:text-white">{system.health.db}</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-slate-600 dark:text-slate-400"><HealthDot status={system.health.redis} />Redis</span>
                <span className="font-medium text-slate-900 dark:text-white">{system.health.redis}</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-slate-600 dark:text-slate-400">Celery workers</span>
                <span className="font-medium text-slate-900 dark:text-white">{system.health.celery_workers}</span>
              </div>
              <hr className="border-slate-200 dark:border-slate-700" />
              <div className="flex items-center justify-between">
                <span className="text-slate-600 dark:text-slate-400">Audit udalostí (1h)</span>
                <span className="font-medium text-slate-900 dark:text-white">{system.audit_events_last_hour}</span>
              </div>
              {Object.keys(system.health.queues).length > 0 && (
                <>
                  <hr className="border-slate-200 dark:border-slate-700" />
                  <p className="text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wider">Fronty</p>
                  {Object.entries(system.health.queues).map(([q, count]) => (
                    <div key={q} className="flex items-center justify-between">
                      <span className="text-slate-600 dark:text-slate-400 font-mono text-xs">{q}</span>
                      <span className="font-medium text-slate-900 dark:text-white">{count ?? '—'}</span>
                    </div>
                  ))}
                </>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

function StatRow({ label, value, color }: { label: string; value: number | string; color?: string }) {
  return (
    <div className="flex justify-between text-sm">
      <span className="text-slate-600 dark:text-slate-400">{label}</span>
      <span className={`font-semibold ${color || 'text-slate-900 dark:text-white'}`}>{value}</span>
    </div>
  );
}

function Loading() {
  return (
    <div className="flex items-center justify-center h-64">
      <div className="w-8 h-8 border-4 border-blue-600 border-t-transparent rounded-full animate-spin" />
    </div>
  );
}

function ErrorMsg({ msg }: { msg: string }) {
  return (
    <div className="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-xl p-6 text-center">
      <i className="fas fa-exclamation-triangle text-red-500 text-2xl mb-2" />
      <p className="text-red-700 dark:text-red-300">{msg}</p>
    </div>
  );
}
