import type {
  AdminCompany,
  AdminUser,
  AuditLogEntry,
  CompanySyncStatus,
  DashboardOverview,
  DashboardSync,
  DashboardSystem,
  ScheduledTask,
  SyncJob,
} from './types';
import { apiRequest } from '../lib/apiClient';

const API_BASE = '/api/admin';

function adminRequest<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
  return apiRequest<T>(endpoint, options, API_BASE);
}

export const adminApi = {
  // Dashboard
  dashboardOverview: () => adminRequest<DashboardOverview>('/metrics/overview/'),
  dashboardSync: () => adminRequest<DashboardSync>('/metrics/sync/'),
  dashboardSystem: () => adminRequest<DashboardSystem>('/metrics/system/'),

  // Companies
  listCompanies: (params?: Record<string, string>) => {
    const qs = params ? '?' + new URLSearchParams(params).toString() : '';
    return adminRequest<{ results: AdminCompany[]; count: number }>(`/companies/${qs}`);
  },

  // Users
  listUsers: (params?: Record<string, string>) => {
    const qs = params ? '?' + new URLSearchParams(params).toString() : '';
    return adminRequest<{ results: AdminUser[]; count: number }>(`/users/${qs}`);
  },
  updateUser: (id: number, data: Partial<AdminUser>) =>
    adminRequest<AdminUser>(`/users/${id}/`, {
      method: 'PATCH',
      body: JSON.stringify(data),
    }),

  // Sync Jobs
  listSyncJobs: (params?: Record<string, string>) => {
    const qs = params ? '?' + new URLSearchParams(params).toString() : '';
    return adminRequest<{ results: SyncJob[]; count: number }>(`/sync/jobs/${qs}`);
  },
  triggerSyncJob: (data: { job_type: string; parameters?: Record<string, any>; notes?: string }) =>
    adminRequest<SyncJob>('/sync/jobs/', { method: 'POST', body: JSON.stringify(data) }),
  pauseSyncJob: (id: number, reason?: string) =>
    adminRequest<SyncJob>(`/sync/jobs/${id}/pause/`, {
      method: 'POST',
      body: JSON.stringify({ reason: reason || '' }),
    }),
  resumeSyncJob: (id: number) =>
    adminRequest<SyncJob>(`/sync/jobs/${id}/resume/`, { method: 'POST' }),
  cancelSyncJob: (id: number, reason?: string) =>
    adminRequest<SyncJob>(`/sync/jobs/${id}/cancel/`, {
      method: 'POST',
      body: JSON.stringify({ reason: reason || '' }),
    }),
  retrySyncJob: (id: number) =>
    adminRequest<SyncJob>(`/sync/jobs/${id}/retry-failed/`, { method: 'POST' }),

  // Company Sync Status
  listSyncStatuses: (params?: Record<string, string>) => {
    const qs = params ? '?' + new URLSearchParams(params).toString() : '';
    return adminRequest<{ results: CompanySyncStatus[]; count: number }>(`/sync/companies/${qs}`);
  },

  // Queue Depths
  queueDepths: () => adminRequest<{ queues: Record<string, number | null> }>('/sync/queues/'),

  // Scheduled Tasks
  listScheduledTasks: () =>
    adminRequest<{ results: ScheduledTask[] }>('/sync/scheduled/'),
  toggleScheduledTask: (id: number) =>
    adminRequest<{ id: number; enabled: boolean }>(`/sync/scheduled/${id}/toggle/`, {
      method: 'POST',
    }),

  // Audit Log
  listAuditLog: (params?: Record<string, string>) => {
    const qs = params ? '?' + new URLSearchParams(params).toString() : '';
    return adminRequest<{ results: AuditLogEntry[]; count: number }>(`/audit/${qs}`);
  },

  // System
  systemHealth: () => adminRequest<Record<string, any>>('/system/health/'),
  systemInfo: () => adminRequest<Record<string, any>>('/system/info/'),
};
