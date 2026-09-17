import React, { useCallback, useEffect, useState } from 'react';
import { adminApi } from '../api';
import type { SyncJob } from '../types';

const JOB_TYPE_LABELS: Record<string, string> = {
  ruz_full: 'RUZ Full Sync',
  ruz_incremental: 'RUZ Incremental',
  ruz_repair: 'RUZ Repair',
  orsr_batch: 'ORSR Batch',
  financials_batch: 'Financie Batch',
  insurance_batch: 'Poistenie Batch',
  fs_update: 'Finančná správa',
};

const STATUS_STYLES: Record<string, { bg: string; text: string; icon: string }> = {
  queued: { bg: 'bg-slate-100 dark:bg-slate-700/50', text: 'text-slate-600 dark:text-slate-300', icon: 'fa-clock' },
  running: { bg: 'bg-blue-50 dark:bg-blue-900/30', text: 'text-blue-700 dark:text-blue-400', icon: 'fa-spinner fa-spin' },
  completed: { bg: 'bg-emerald-50 dark:bg-emerald-900/30', text: 'text-emerald-700 dark:text-emerald-400', icon: 'fa-check' },
  failed: { bg: 'bg-red-50 dark:bg-red-900/30', text: 'text-red-700 dark:text-red-400', icon: 'fa-times' },
  paused: { bg: 'bg-amber-50 dark:bg-amber-900/30', text: 'text-amber-700 dark:text-amber-400', icon: 'fa-pause' },
  cancelled: { bg: 'bg-slate-100 dark:bg-slate-700/50', text: 'text-slate-500 dark:text-slate-400', icon: 'fa-ban' },
};

function StatusBadge({ status }: { status: string }) {
  const s = STATUS_STYLES[status] || STATUS_STYLES.queued;
  return (
    <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium ${s.bg} ${s.text}`}>
      <i className={`fas ${s.icon} text-[10px]`} />
      {status}
    </span>
  );
}

function ProgressBar({ pct }: { pct: number }) {
  return (
    <div className="flex items-center gap-2">
      <div className="flex-1 h-1.5 bg-slate-100 dark:bg-slate-700 rounded-full overflow-hidden">
        <div
          className="h-full bg-blue-600 rounded-full transition-all"
          style={{ width: `${Math.min(pct, 100)}%` }}
        />
      </div>
      <span className="text-xs text-slate-500 dark:text-slate-400 w-10 text-right">{pct.toFixed(0)}%</span>
    </div>
  );
}

export function SyncJobs() {
  const [jobs, setJobs] = useState<SyncJob[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [showTrigger, setShowTrigger] = useState(false);
  const [actionLoading, setActionLoading] = useState<number | null>(null);

  const fetchJobs = useCallback(() => {
    setLoading(true);
    const params: Record<string, string> = {};
    if (statusFilter) params.status = statusFilter;
    adminApi.listSyncJobs(params)
      .then(res => setJobs(Array.isArray(res) ? res : res.results || []))
      .catch(e => setError(e.message))
      .finally(() => setLoading(false));
  }, [statusFilter]);

  useEffect(() => { fetchJobs(); }, [fetchJobs]);

  const doAction = async (id: number, action: 'pause' | 'resume' | 'cancel' | 'retry') => {
    setActionLoading(id);
    try {
      if (action === 'pause') await adminApi.pauseSyncJob(id);
      else if (action === 'resume') await adminApi.resumeSyncJob(id);
      else if (action === 'cancel') await adminApi.cancelSyncJob(id);
      else if (action === 'retry') await adminApi.retrySyncJob(id);
      fetchJobs();
    } catch (e: any) {
      setError(e.message);
    } finally {
      setActionLoading(null);
    }
  };

  return (
    <div className="space-y-4">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <h1 className="text-2xl font-bold text-slate-900 dark:text-white">Sync Joby</h1>
        <div className="flex gap-2">
          <select
            value={statusFilter}
            onChange={e => setStatusFilter(e.target.value)}
            className="px-3 py-2 rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 text-sm text-slate-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-blue-500/40"
          >
            <option value="">Všetky stavy</option>
            <option value="queued">Queued</option>
            <option value="running">Running</option>
            <option value="completed">Completed</option>
            <option value="failed">Failed</option>
            <option value="paused">Paused</option>
            <option value="cancelled">Cancelled</option>
          </select>
          <button
            onClick={() => setShowTrigger(!showTrigger)}
            className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-sm font-medium transition-colors"
          >
            <i className="fas fa-play mr-2" />Nový job
          </button>
          <button
            onClick={fetchJobs}
            className="px-3 py-2 bg-slate-100 dark:bg-slate-700 hover:bg-slate-200 dark:hover:bg-slate-600 text-slate-700 dark:text-slate-300 rounded-lg text-sm transition-colors"
          >
            <i className="fas fa-sync-alt" />
          </button>
        </div>
      </div>

      {showTrigger && <TriggerPanel onClose={() => setShowTrigger(false)} onTriggered={fetchJobs} />}

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
                <Th>ID</Th>
                <Th>Typ</Th>
                <Th>Stav</Th>
                <Th>Progres</Th>
                <Th>Items</Th>
                <Th>Spustil</Th>
                <Th>Čas</Th>
                <Th>Akcie</Th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr><td colSpan={8} className="text-center py-12 text-slate-400"><i className="fas fa-spinner fa-spin mr-2" />Načítavam...</td></tr>
              ) : jobs.length === 0 ? (
                <tr><td colSpan={8} className="text-center py-12 text-slate-400">Žiadne joby</td></tr>
              ) : (
                jobs.map(job => (
                  <React.Fragment key={job.id}>
                  <tr className="border-b border-slate-100 dark:border-slate-700/50 hover:bg-slate-50 dark:hover:bg-slate-800/40 transition-colors">
                    <td className="px-4 py-3 font-mono text-xs text-slate-500">#{job.id}</td>
                    <td className="px-4 py-3 font-medium text-slate-900 dark:text-white">{JOB_TYPE_LABELS[job.job_type] || job.job_type}</td>
                    <td className="px-4 py-3"><StatusBadge status={job.status} /></td>
                    <td className="px-4 py-3 min-w-[120px]">
                      <ProgressBar pct={job.progress_percentage} />
                    </td>
                    <td className="px-4 py-3 text-xs text-slate-600 dark:text-slate-400">
                      <span className="text-emerald-600">{job.succeeded_items}</span>
                      {job.failed_items > 0 && <> / <span className="text-red-500">{job.failed_items}</span></>}
                      {job.total_items && <span className="text-slate-400"> of {job.total_items}</span>}
                    </td>
                    <td className="px-4 py-3 text-xs text-slate-500 dark:text-slate-400">{job.triggered_by_email || job.triggered_via}</td>
                    <td className="px-4 py-3 text-xs text-slate-500 dark:text-slate-400">
                      {job.duration_seconds != null ? formatDuration(job.duration_seconds) : '—'}
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex gap-1">
                        {(job.status === 'running') && (
                          <ActionBtn icon="fa-pause" title="Pause" onClick={() => doAction(job.id, 'pause')} loading={actionLoading === job.id} />
                        )}
                        {(job.status === 'paused') && (
                          <ActionBtn icon="fa-play" title="Resume" onClick={() => doAction(job.id, 'resume')} loading={actionLoading === job.id} color="green" />
                        )}
                        {(job.status === 'running' || job.status === 'queued' || job.status === 'paused') && (
                          <ActionBtn icon="fa-stop" title="Cancel" onClick={() => doAction(job.id, 'cancel')} loading={actionLoading === job.id} color="red" />
                        )}
                        {(job.status === 'failed' && job.failed_items > 0) && (
                          <ActionBtn icon="fa-redo" title="Retry Failed" onClick={() => doAction(job.id, 'retry')} loading={actionLoading === job.id} color="amber" />
                        )}
                      </div>
                    </td>
                  </tr>
                  {(job.last_error || job.notes) && (
                    <tr className="border-b border-slate-100 dark:border-slate-700/50">
                      <td colSpan={8} className="px-4 pb-3 pt-0">
                        <div className="space-y-1.5">
                          {job.last_error && (
                            <div className="rounded-md bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 px-3 py-2">
                              <p className="text-[11px] font-semibold text-red-700 dark:text-red-300 uppercase tracking-wider">
                                <i className="fas fa-exclamation-triangle mr-1.5" />Chyba
                              </p>
                              {/* A traceback is long and its line breaks are part of
                                  the meaning, so it wraps and scrolls rather than
                                  being clipped. */}
                              <p className="mt-0.5 max-h-40 overflow-y-auto whitespace-pre-wrap break-words font-mono text-xs text-red-700 dark:text-red-300">
                                {job.last_error}
                              </p>
                            </div>
                          )}
                          {job.notes && (
                            <p className="text-xs text-slate-500 dark:text-slate-400">
                              <i className="fas fa-note-sticky mr-1.5" />{job.notes}
                            </p>
                          )}
                        </div>
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

function TriggerPanel({ onClose, onTriggered }: { onClose: () => void; onTriggered: () => void }) {
  const [jobType, setJobType] = useState('ruz_full');
  const [notes, setNotes] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');

  const submit = async () => {
    setSubmitting(true);
    setError('');
    try {
      await adminApi.triggerSyncJob({ job_type: jobType, notes });
      onTriggered();
      onClose();
    } catch (e: any) {
      setError(e.message);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="bg-white dark:bg-slate-800/80 rounded-xl border border-slate-200 dark:border-slate-700/50 p-5">
      <div className="flex items-center justify-between mb-4">
        <h3 className="font-semibold text-slate-900 dark:text-white">Spustiť nový sync job</h3>
        <button onClick={onClose} className="text-slate-400 hover:text-slate-600 dark:hover:text-slate-300"><i className="fas fa-times" /></button>
      </div>
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <div>
          <label className="block text-xs font-medium text-slate-500 dark:text-slate-400 mb-1">Typ jobu</label>
          <select
            value={jobType}
            onChange={e => setJobType(e.target.value)}
            className="w-full px-3 py-2 rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 text-sm text-slate-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-blue-500/40"
          >
            {Object.entries(JOB_TYPE_LABELS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
          </select>
        </div>
        <div>
          <label className="block text-xs font-medium text-slate-500 dark:text-slate-400 mb-1">Poznámka</label>
          <input
            value={notes}
            onChange={e => setNotes(e.target.value)}
            placeholder="Voliteľná poznámka..."
            className="w-full px-3 py-2 rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 text-sm text-slate-900 dark:text-white placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-blue-500/40"
          />
        </div>
        <div className="flex items-end">
          <button
            onClick={submit}
            disabled={submitting}
            className="w-full px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-sm font-medium transition-colors disabled:opacity-50"
          >
            {submitting ? <><i className="fas fa-spinner fa-spin mr-2" />Spúšťam...</> : <><i className="fas fa-rocket mr-2" />Spustiť</>}
          </button>
        </div>
      </div>
      {error && <p className="mt-3 text-sm text-red-600 dark:text-red-400"><i className="fas fa-exclamation-circle mr-1" />{error}</p>}
    </div>
  );
}

function ActionBtn({ icon, title, onClick, loading, color = 'blue' }: {
  icon: string; title: string; onClick: () => void; loading: boolean; color?: string;
}) {
  const colors: Record<string, string> = {
    blue: 'text-blue-600 hover:bg-blue-50 dark:hover:bg-blue-900/30',
    green: 'text-emerald-600 hover:bg-emerald-50 dark:hover:bg-emerald-900/30',
    red: 'text-red-600 hover:bg-red-50 dark:hover:bg-red-900/30',
    amber: 'text-amber-600 hover:bg-amber-50 dark:hover:bg-amber-900/30',
  };
  return (
    <button
      onClick={onClick}
      disabled={loading}
      title={title}
      className={`w-7 h-7 rounded-md flex items-center justify-center text-xs transition-colors ${colors[color]} disabled:opacity-50`}
    >
      <i className={`fas ${loading ? 'fa-spinner fa-spin' : icon}`} />
    </button>
  );
}

function Th({ children }: { children: React.ReactNode }) {
  return <th className="px-4 py-3 text-left text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wider">{children}</th>;
}

function formatDuration(seconds: number): string {
  if (seconds < 60) return `${Math.round(seconds)}s`;
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m ${Math.round(seconds % 60)}s`;
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  return `${h}h ${m}m`;
}
