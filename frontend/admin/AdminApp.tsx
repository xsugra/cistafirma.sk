import React, { useState } from 'react';
import { AdminLayout } from './AdminLayout';
import { Dashboard } from './pages/Dashboard';
import { Data } from './pages/Data';
import { CompaniesBuilderPage } from './pages/CompaniesBuilderPage';
import { Users } from './pages/Users';
import { SyncJobs } from './pages/SyncJobs';
import { SyncStatus } from './pages/SyncStatus';
import { ScheduledTasks } from './pages/ScheduledTasks';
import { AuditLog } from './pages/AuditLog';
import { System } from './pages/System';
import type { AdminPage } from './types';

interface Props {
  onExit: () => void;
  userName?: string;
}

export function AdminApp({ onExit, userName }: Props) {
  const [page, setPage] = useState<AdminPage>('dashboard');

  const renderPage = () => {
    switch (page) {
      case 'dashboard': return <Dashboard />;
      case 'data': return <Data />;
      case 'companies': return <CompaniesBuilderPage />;
      case 'users': return <Users />;
      case 'sync-jobs': return <SyncJobs />;
      case 'sync-status': return <SyncStatus />;
      case 'scheduled-tasks': return <ScheduledTasks />;
      case 'audit-log': return <AuditLog />;
      case 'system': return <System />;
      default: return <Dashboard />;
    }
  };

  return (
    <AdminLayout
      activePage={page}
      onNavigate={setPage}
      onExit={onExit}
      userName={userName}
    >
      {renderPage()}
    </AdminLayout>
  );
}
