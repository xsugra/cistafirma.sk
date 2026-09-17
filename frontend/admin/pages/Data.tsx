import React, { useEffect, useState } from 'react';
import { adminApi } from '../api';
import type { DashboardOverview } from '../types';

export function Data() {
  const [overview, setOverview] = useState<DashboardOverview | null>(null);
  const [loading, setLoading] = useState(true);
  const [syncing, setSyncing] = useState<'idle' | 'firmy' | 'szco'>('idle');
  const [syncMessage, setSyncMessage] = useState('');
  const [tab, setTab] = useState<'firmy' | 'szco'>('firmy');

  useEffect(() => {
    adminApi.dashboardOverview()
      .then(data => setOverview(data))
      .catch(e => console.error('Failed to load overview:', e))
      .finally(() => setLoading(false));
  }, []);

  const triggerSync = async (entityType: 'company' | 'szco') => {
    try {
      setSyncing(entityType === 'company' ? 'firmy' : 'szco');
      setSyncMessage(`Spúšťam FULL RUZ SYNC pre ${entityType === 'company' ? 'Firmy' : 'SZCO'}...`);

      const job_type = entityType === 'company' ? 'ruz_full_firmy' : 'ruz_full_szco';
      const job = await adminApi.triggerSyncJob({
        job_type,
        notes: `Manual FULL RUZ SYNC for ${entityType === 'company' ? 'Firmy' : 'SZCO'} from admin panel`,
      });

      setSyncMessage(`✓ Synchronizácia pre ${entityType === 'company' ? 'Firmy' : 'SZCO'} bola spustená (ID: ${job.id})`);
    } catch (error: any) {
      setSyncMessage(`✗ Chyba: ${error.message}`);
    } finally {
      setSyncing('idle');
    }
  };

  if (loading) {
    return <div className="flex items-center justify-center p-8"><i className="fas fa-spinner fa-spin mr-2" />Načítavam...</div>;
  }

  const firmy_count = overview?.companies?.firmy_count || 0;
  const szco_count = overview?.companies?.szco_count || 0;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-3xl font-bold text-slate-900 dark:text-white">Data Management</h1>
        <p className="text-sm text-slate-500 dark:text-slate-400">Spravujte synchronizáciu Firiem a SZCO</p>
      </div>

      {/* Tabs */}
      <div className="flex gap-4 border-b border-slate-200 dark:border-slate-700">
        <button
          onClick={() => setTab('firmy')}
          className={`px-4 py-3 font-medium border-b-2 transition-colors ${
            tab === 'firmy'
              ? 'border-blue-500 text-blue-600 dark:text-blue-400'
              : 'border-transparent text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white'
          }`}
        >
          <i className="fas fa-building mr-2" />Firmy ({firmy_count.toLocaleString('sk')})
        </button>
        <button
          onClick={() => setTab('szco')}
          className={`px-4 py-3 font-medium border-b-2 transition-colors ${
            tab === 'szco'
              ? 'border-blue-500 text-blue-600 dark:text-blue-400'
              : 'border-transparent text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white'
          }`}
        >
          <i className="fas fa-user-tie mr-2" />SZCO ({szco_count.toLocaleString('sk')})
        </button>
      </div>

      {/* Firmy Tab */}
      {tab === 'firmy' && (
        <div className="space-y-4">
          <div className="bg-white dark:bg-slate-800/60 rounded-xl border border-slate-200 dark:border-slate-700/50 p-6">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
              <div>
                <p className="text-sm text-slate-500 dark:text-slate-400 uppercase tracking-wide mb-1">Počet Firiem</p>
                <p className="text-3xl font-bold text-slate-900 dark:text-white">{firmy_count.toLocaleString('sk')}</p>
              </div>
              <div>
                <p className="text-sm text-slate-500 dark:text-slate-400 uppercase tracking-wide mb-1">Podiel</p>
                <p className="text-3xl font-bold text-slate-900 dark:text-white">
                  {overview?.companies?.total ? ((firmy_count / overview.companies.total) * 100).toFixed(1) : 0}%
                </p>
              </div>
            </div>

            <div className="space-y-3">
              <h3 className="text-sm font-semibold text-slate-900 dark:text-white">Synchronizácia</h3>
              <p className="text-xs text-slate-600 dark:text-slate-400">
                Spustite FULL RUZ SYNC iba pre právnické osoby (s.r.o., a.s., atď.) bez self-employed osôb.
              </p>
              <button
                onClick={() => triggerSync('company')}
                disabled={syncing !== 'idle'}
                className="w-full px-4 py-3 rounded-lg bg-emerald-600 text-white font-medium hover:bg-emerald-700 disabled:opacity-60 transition-colors flex items-center justify-center gap-2"
              >
                {syncing === 'firmy' ? (
                  <>
                    <i className="fas fa-spinner fa-spin" />
                    Synchronizujem...
                  </>
                ) : (
                  <>
                    <i className="fas fa-sync" />
                    FULL RUZ SYNC - Firmy
                  </>
                )}
              </button>

              {syncMessage && (
                <div className={`p-3 rounded-lg text-sm ${
                  syncMessage.startsWith('✓')
                    ? 'bg-emerald-50 dark:bg-emerald-900/20 text-emerald-700 dark:text-emerald-400'
                    : 'bg-red-50 dark:bg-red-900/20 text-red-700 dark:text-red-400'
                }`}>
                  {syncMessage}
                </div>
              )}
            </div>
          </div>

          <div className="bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800/50 rounded-xl p-4">
            <div className="flex gap-3">
              <i className="fas fa-info-circle text-blue-600 dark:text-blue-400 mt-0.5" />
              <div className="text-sm text-blue-700 dark:text-blue-300">
                <strong>Firmy</strong> sú právnické osoby s právnymi formami: s.r.o., a.s., v.o.s., k.s., nadácie, družstvá a podobne (kódy 111-995).
              </div>
            </div>
          </div>
        </div>
      )}

      {/* SZCO Tab */}
      {tab === 'szco' && (
        <div className="space-y-4">
          <div className="bg-white dark:bg-slate-800/60 rounded-xl border border-slate-200 dark:border-slate-700/50 p-6">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
              <div>
                <p className="text-sm text-slate-500 dark:text-slate-400 uppercase tracking-wide mb-1">Počet SZCO</p>
                <p className="text-3xl font-bold text-slate-900 dark:text-white">{szco_count.toLocaleString('sk')}</p>
              </div>
              <div>
                <p className="text-sm text-slate-500 dark:text-slate-400 uppercase tracking-wide mb-1">Podiel</p>
                <p className="text-3xl font-bold text-slate-900 dark:text-white">
                  {overview?.companies?.total ? ((szco_count / overview.companies.total) * 100).toFixed(1) : 0}%
                </p>
              </div>
            </div>

            <div className="space-y-3">
              <h3 className="text-sm font-semibold text-slate-900 dark:text-white">Synchronizácia</h3>
              <p className="text-xs text-slate-600 dark:text-slate-400">
                Spustite FULL RUZ SYNC iba pre self-employed osoby bez právnických osôb.
              </p>
              <button
                onClick={() => triggerSync('szco')}
                disabled={syncing !== 'idle'}
                className="w-full px-4 py-3 rounded-lg bg-purple-600 text-white font-medium hover:bg-purple-700 disabled:opacity-60 transition-colors flex items-center justify-center gap-2"
              >
                {syncing === 'szco' ? (
                  <>
                    <i className="fas fa-spinner fa-spin" />
                    Synchronizujem...
                  </>
                ) : (
                  <>
                    <i className="fas fa-sync" />
                    FULL RUZ SYNC - SZCO
                  </>
                )}
              </button>

              {syncMessage && (
                <div className={`p-3 rounded-lg text-sm ${
                  syncMessage.startsWith('✓')
                    ? 'bg-emerald-50 dark:bg-emerald-900/20 text-emerald-700 dark:text-emerald-400'
                    : 'bg-red-50 dark:bg-red-900/20 text-red-700 dark:text-red-400'
                }`}>
                  {syncMessage}
                </div>
              )}
            </div>
          </div>

          <div className="bg-purple-50 dark:bg-purple-900/20 border border-purple-200 dark:border-purple-800/50 rounded-xl p-4">
            <div className="flex gap-3">
              <i className="fas fa-info-circle text-purple-600 dark:text-purple-400 mt-0.5" />
              <div className="text-sm text-purple-700 dark:text-purple-300">
                <strong>SZCO</strong> (Samozaměstnaní/Self-employed) sú fyzické osoby s podnikateľskou činnosťou (kódy 100-110): FO-podnikateľ, FO-slobodné povolania, SHR atď.
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Legend */}
      <div className="bg-slate-50 dark:bg-slate-800/30 rounded-xl border border-slate-200 dark:border-slate-700/50 p-4">
        <h3 className="text-sm font-semibold text-slate-900 dark:text-white mb-3">ℹ️ Pomôcka</h3>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs text-slate-600 dark:text-slate-400">
          <div>
            <p className="font-medium text-slate-900 dark:text-white mb-1">FULL RUZ SYNC</p>
            <p>Stiahne všetky údaje z RUZ registru pre danú kategóriu a aktualizuje databázu.</p>
          </div>
          <div>
            <p className="font-medium text-slate-900 dark:text-white mb-1">Nezávislé spúšťanie</p>
            <p>Každú kategóriu možno synchronizovať oddelene bez vplyvu na druhú kategóriu.</p>
          </div>
        </div>
      </div>
    </div>
  );
}

