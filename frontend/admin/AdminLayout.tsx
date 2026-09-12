import React, { useState } from 'react';
import type { AdminPage } from './types';

interface NavItem {
  id: AdminPage;
  label: string;
  icon: string;
  group: string;
}

const NAV_ITEMS: NavItem[] = [
  { id: 'dashboard', label: 'Dashboard', icon: 'fa-th-large', group: 'Prehľad' },
  { id: 'data', label: 'Data (Firmy/SZCO)', icon: 'fa-database', group: 'Dáta' },
  { id: 'companies', label: 'Firmy - Detaily', icon: 'fa-building', group: 'Dáta' },
  { id: 'users', label: 'Používatelia', icon: 'fa-users', group: 'Dáta' },
  { id: 'sync-jobs', label: 'Sync Joby', icon: 'fa-sync-alt', group: 'Synchronizácia' },
  { id: 'sync-status', label: 'Stav synchronizácie', icon: 'fa-heartbeat', group: 'Synchronizácia' },
  { id: 'scheduled-tasks', label: 'Periodické úlohy', icon: 'fa-clock', group: 'Synchronizácia' },
  { id: 'audit-log', label: 'Audit Log', icon: 'fa-scroll', group: 'Systém' },
  { id: 'system', label: 'Systém', icon: 'fa-server', group: 'Systém' },
];

interface Props {
  activePage: AdminPage;
  onNavigate: (page: AdminPage) => void;
  onExit: () => void;
  children: React.ReactNode;
  userName?: string;
}

export function AdminLayout({ activePage, onNavigate, onExit, children, userName }: Props) {
  const [sidebarOpen, setSidebarOpen] = useState(true);

  const groups = NAV_ITEMS.reduce<Record<string, NavItem[]>>((acc, item) => {
    (acc[item.group] = acc[item.group] || []).push(item);
    return acc;
  }, {});

  return (
    <div className="flex h-screen bg-slate-50 dark:bg-slate-950 overflow-hidden relative z-10">
      {/* Sidebar */}
      <aside className={`${sidebarOpen ? 'w-60' : 'w-16'} flex-shrink-0 bg-white dark:bg-slate-900 border-r border-slate-200 dark:border-slate-800 flex flex-col transition-all duration-200`}>
        {/* Logo */}
        <div className="h-14 flex items-center px-4 border-b border-slate-200 dark:border-slate-800 gap-3">
          <div className="w-8 h-8 rounded-lg bg-blue-600 flex items-center justify-center text-white flex-shrink-0">
            <i className="fas fa-shield-alt text-sm" />
          </div>
          {sidebarOpen && (
            <div className="min-w-0">
              <p className="text-sm font-bold text-slate-900 dark:text-white truncate">CistaFirma</p>
              <p className="text-[10px] text-slate-400 -mt-0.5">Admin Panel</p>
            </div>
          )}
        </div>

        {/* Navigation */}
        <nav className="flex-1 overflow-y-auto py-3 px-2">
          {Object.entries(groups).map(([group, items]) => (
            <div key={group} className="mb-3">
              {sidebarOpen && (
                <p className="px-3 mb-1 text-[10px] font-semibold text-slate-400 dark:text-slate-500 uppercase tracking-wider">{group}</p>
              )}
              {items.map(item => {
                const active = activePage === item.id;
                return (
                  <button
                    key={item.id}
                    onClick={() => onNavigate(item.id)}
                    className={`w-full flex items-center gap-3 px-3 py-2 rounded-lg text-sm transition-colors mb-0.5 ${
                      active
                        ? 'bg-blue-50 dark:bg-blue-900/20 text-blue-700 dark:text-blue-400 font-medium'
                        : 'text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800/60 hover:text-slate-900 dark:hover:text-white'
                    }`}
                    title={!sidebarOpen ? item.label : undefined}
                  >
                    <i className={`fas ${item.icon} w-4 text-center text-xs ${active ? 'text-blue-600 dark:text-blue-400' : ''}`} />
                    {sidebarOpen && <span className="truncate">{item.label}</span>}
                  </button>
                );
              })}
            </div>
          ))}
        </nav>

        {/* Bottom */}
        <div className="border-t border-slate-200 dark:border-slate-800 p-2">
          <button
            onClick={onExit}
            className="w-full flex items-center gap-3 px-3 py-2 rounded-lg text-sm text-slate-500 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800/60 hover:text-slate-900 dark:hover:text-white transition-colors"
            title="Späť na web"
          >
            <i className="fas fa-arrow-left w-4 text-center text-xs" />
            {sidebarOpen && <span>Späť na web</span>}
          </button>
        </div>
      </aside>

      {/* Main content */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* Top bar */}
        <header className="h-14 flex items-center justify-between px-6 border-b border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 flex-shrink-0">
          <button
            onClick={() => setSidebarOpen(!sidebarOpen)}
            className="text-slate-400 hover:text-slate-600 dark:hover:text-slate-300 transition-colors"
          >
            <i className={`fas ${sidebarOpen ? 'fa-indent' : 'fa-outdent'}`} />
          </button>
          <div className="flex items-center gap-3">
            {userName && (
              <span className="text-sm text-slate-500 dark:text-slate-400">
                <i className="fas fa-user-shield mr-1.5 text-blue-600" />{userName}
              </span>
            )}
          </div>
        </header>

        {/* Page content */}
        <main className="flex-1 overflow-y-auto p-6">
          {children}
        </main>
      </div>
    </div>
  );
}
