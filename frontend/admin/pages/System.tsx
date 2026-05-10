import React, { useEffect, useState } from 'react';
import { adminApi } from '../api';

export function System() {
  const [health, setHealth] = useState<Record<string, any> | null>(null);
  const [info, setInfo] = useState<Record<string, any> | null>(null);
  const [queues, setQueues] = useState<Record<string, number | null> | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const fetchAll = () => {
    setLoading(true);
    Promise.all([
      adminApi.systemHealth(),
      adminApi.systemInfo(),
      adminApi.queueDepths().catch(() => ({ queues: {} })),
    ])
      .then(([h, i, q]) => { setHealth(h); setInfo(i); setQueues(q.queues); })
      .catch(e => setError(e.message))
      .finally(() => setLoading(false));
  };

  useEffect(() => { fetchAll(); }, []);

  if (loading) return (
    <div className="flex items-center justify-center h-64">
      <div className="w-8 h-8 border-4 border-blue-600 border-t-transparent rounded-full animate-spin" />
    </div>
  );

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-slate-900 dark:text-white">Systém</h1>
        <button
          onClick={fetchAll}
          className="px-3 py-2 bg-slate-100 dark:bg-slate-700 hover:bg-slate-200 dark:hover:bg-slate-600 text-slate-700 dark:text-slate-300 rounded-lg text-sm transition-colors"
        >
          <i className="fas fa-sync-alt mr-2" />Refresh
        </button>
      </div>

      {error && (
        <div className="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg px-4 py-3 text-sm text-red-700 dark:text-red-300">
          <i className="fas fa-exclamation-circle mr-2" />{error}
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Health */}
        {health && (
          <Card title="Zdravie služieb" icon="fa-heartbeat">
            <div className="space-y-3">
              <HealthRow label="Databáza (PostgreSQL)" status={health.db} />
              <HealthRow label="Redis" status={health.redis} />
              <div className="flex items-center justify-between text-sm">
                <span className="text-slate-600 dark:text-slate-400">Celery Workers</span>
                <span className={`font-semibold ${health.celery_workers > 0 ? 'text-emerald-600 dark:text-emerald-400' : 'text-red-600 dark:text-red-400'}`}>
                  {health.celery_workers}
                </span>
              </div>
            </div>
          </Card>
        )}

        {/* Info */}
        {info && (
          <Card title="Informácie o systéme" icon="fa-info-circle">
            <div className="space-y-2">
              <InfoRow label="Django" value={info.django_version} />
              <InfoRow label="Python" value={info.python_version?.split(' ')[0]} />
              <InfoRow label="Prostredie" value={info.environment} />
              <InfoRow label="Commit" value={info.deployed_commit?.slice(0, 8) || 'unknown'} mono />
            </div>
          </Card>
        )}

        {/* Queues */}
        {queues && Object.keys(queues).length > 0 && (
          <Card title="Celery Fronty" icon="fa-layer-group" wide>
            <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
              {Object.entries(queues).sort(([a], [b]) => a.localeCompare(b)).map(([name, count]) => (
                <div key={name} className="bg-slate-50 dark:bg-slate-800/80 rounded-lg p-3 border border-slate-100 dark:border-slate-700/50">
                  <p className="text-xs font-mono text-slate-500 dark:text-slate-400 mb-1">{name}</p>
                  <p className={`text-2xl font-bold ${
                    count === null ? 'text-slate-300' :
                    count > 100 ? 'text-amber-600 dark:text-amber-400' :
                    count > 0 ? 'text-blue-600 dark:text-blue-400' :
                    'text-slate-400'
                  }`}>
                    {count ?? '—'}
                  </p>
                  <p className="text-[10px] text-slate-400 mt-0.5">pending msgs</p>
                </div>
              ))}
            </div>
          </Card>
        )}
      </div>
    </div>
  );
}

function Card({ title, icon, children, wide }: { title: string; icon: string; children: React.ReactNode; wide?: boolean }) {
  return (
    <div className={`bg-white dark:bg-slate-800/60 rounded-xl border border-slate-200 dark:border-slate-700/50 p-5 ${wide ? 'lg:col-span-2' : ''}`}>
      <h2 className="text-sm font-semibold text-slate-900 dark:text-white mb-4">
        <i className={`fas ${icon} mr-2 text-blue-600`} />{title}
      </h2>
      {children}
    </div>
  );
}

function HealthRow({ label, status }: { label: string; status: string }) {
  const ok = status === 'ok';
  return (
    <div className="flex items-center justify-between text-sm">
      <span className="text-slate-600 dark:text-slate-400 flex items-center gap-2">
        <span className={`w-2.5 h-2.5 rounded-full ${ok ? 'bg-emerald-500' : 'bg-red-500'}`} />
        {label}
      </span>
      <span className={`font-semibold ${ok ? 'text-emerald-600 dark:text-emerald-400' : 'text-red-600 dark:text-red-400'}`}>
        {status}
      </span>
    </div>
  );
}

function InfoRow({ label, value, mono }: { label: string; value: string; mono?: boolean }) {
  return (
    <div className="flex items-center justify-between text-sm">
      <span className="text-slate-600 dark:text-slate-400">{label}</span>
      <span className={`font-medium text-slate-900 dark:text-white ${mono ? 'font-mono text-xs' : ''}`}>{value}</span>
    </div>
  );
}
