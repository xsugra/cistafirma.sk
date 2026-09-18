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
  // Tailwind's `md`. Kept as a number rather than read from the theme because
  // this is the one place the layout asks JavaScript instead of CSS.
  const MD = 768;

  /**
   * Collapsed on a narrow screen, open on a wide one.
   *
   * `w-60` is 240 px and `flex-shrink-0`, so on a 393 px phone the content was
   * left 153 px -- 105 px after `p-6` -- with nothing to say the sidebar could
   * be collapsed. The toggle existed; the default was the problem. Read once,
   * on mount, rather than watched: re-opening itself when the viewport grows
   * back would overrule a choice the reader just made by hand.
   */
  const [sidebarOpen, setSidebarOpen] = useState(() => window.innerWidth >= MD);

  const groups = NAV_ITEMS.reduce<Record<string, NavItem[]>>((acc, item) => {
    (acc[item.group] = acc[item.group] || []).push(item);
    return acc;
  }, {});

  return (
    // `h-dvh`, not `h-screen`: `100vh` on iOS Safari is the *large* viewport,
    // measured as if the address bar were already hidden, so the bottom of a
    // `h-screen overflow-hidden` shell sits under browser chrome that is still
    // there. `dvh` tracks what is actually visible.
    <div className="flex h-dvh bg-slate-50 dark:bg-slate-950 overflow-hidden relative z-10">
      {/* Sidebar. Below `md` it leaves the flow and overlays the content
          instead of squeezing it: `w-60` inside a 393 px flex row left the page
          105 px wide, and no amount of making the content shrink fixes a width
          that was never there. The shadow is what says the panel is above the
          page rather than beside it.

          Collapsed on a narrow screen it is *gone*, not a 64 px icon rail --
          and the display utility is conditional to say so. A rail was measured
          covering x 0..64 of a 393 px page whose content also starts at 0, so
          the first 40 px of every line sat behind it; beside the content it was
          a fair trade, over it, it is not. Writing that as `max-md:hidden`
          beside an unconditional `flex` does not work: both are display
          utilities and `flex` was emitted last, so the `hidden` lost and the
          rail stayed painted over the text. `hidden md:flex` pits a variant
          against the plain utility instead, which is the ordering that holds. */}
      <aside className={`${sidebarOpen ? 'w-60 flex' : 'w-16 hidden md:flex'} flex-shrink-0 bg-white dark:bg-slate-900 border-r border-slate-200 dark:border-slate-800 flex-col transition-all duration-200 max-md:absolute max-md:inset-y-0 max-md:left-0 max-md:z-30 max-md:shadow-2xl`}>
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
                    // Collapses behind the reader on a narrow screen, where the
                    // sidebar is an overlay: without this the panel stayed over
                    // the page it had just navigated to, so every nav tap cost a
                    // second one on the toggle to see the result. Read at click
                    // time rather than from state, because what matters is the
                    // width now -- the page may not have been rendered on this
                    // screen at all. On a wide screen the sidebar is not an
                    // overlay and stays put, which is the point of it.
                    onClick={() => {
                      onNavigate(item.id);
                      if (window.innerWidth < MD) setSidebarOpen(false);
                    }}
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
          {/* Named, and sized. The icon says nothing to a screen reader, and
              below `md` this is no longer a convenience -- it is the only way
              to reach the navigation at all, so it is the one control here that
              cannot be an unlabelled 16 px glyph. `min-h-11 min-w-11` is
              Apple's 44 px minimum tap target; `-ml-2` keeps the icon on the
              `px-6` gutter it sat on before the padding arrived. */}
          <button
            onClick={() => setSidebarOpen(!sidebarOpen)}
            aria-label={sidebarOpen ? 'Zbaliť menu' : 'Rozbaliť menu'}
            aria-expanded={sidebarOpen}
            className="-ml-2 min-h-11 min-w-11 flex items-center justify-center text-slate-400 hover:text-slate-600 dark:hover:text-slate-300 transition-colors"
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
