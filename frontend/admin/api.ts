import type {
  AdminCompany,
  CompanyPreset,
  CompanyReport,
  AdminUser,
  AuditLogEntry,
  CompanySyncStatus,
  DashboardOverview,
  DashboardSync,
  DashboardSystem,
  SavedCompanyFilter,
  ScheduledTask,
  SyncJob,
} from './types';
import { apiRequest } from '../lib/apiClient';

const API_BASE = '/api/admin';

function adminRequest<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
  console.log('[adminApi] Fetching:', endpoint);
  return apiRequest<T>(endpoint, options, API_BASE);
}

async function adminDownload(endpoint: string, params?: Record<string, string | number | boolean | undefined | null>): Promise<Blob> {
  const token = localStorage.getItem('token');
  const filtered = Object.fromEntries(
    Object.entries(params || {}).filter(([, value]) => value !== undefined && value !== null && value !== ''),
  ) as Record<string, string>;
  const qs = Object.keys(filtered).length ? `?${new URLSearchParams(filtered).toString()}` : '';
  const response = await fetch(`${API_BASE}${endpoint}${qs}`, {
    headers: {
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
  });
  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || `HTTP Error: ${response.status}`);
  }
  return response.blob();
}

export const adminApi = {
  // Dashboard
  dashboardOverview: () => adminRequest<DashboardOverview>('/metrics/overview/'),
  dashboardSync: () => adminRequest<DashboardSync>('/metrics/sync/'),
  dashboardSystem: () => adminRequest<DashboardSystem>('/metrics/system/'),

  // Companies
  listCompanies: (
    params?: Record<string, string | number | boolean | undefined | null>,
    options: RequestInit = {},
  ) => {
    const filtered = Object.fromEntries(
      Object.entries(params || {}).filter(([, value]) => value !== undefined && value !== null && value !== ''),
    ) as Record<string, string>;
    const qs = Object.keys(filtered).length ? '?' + new URLSearchParams(filtered).toString() : '';
    return adminRequest<{ results: AdminCompany[]; count: number }>(`/companies/${qs}`, options);
  },
  companyReport: (
    params?: Record<string, string | number | boolean | undefined | null>,
    options: RequestInit = {},
  ) => {
    const filtered = Object.fromEntries(
      Object.entries(params || {}).filter(([, value]) => value !== undefined && value !== null && value !== ''),
    ) as Record<string, string>;
    if (filtered.mode === undefined && filtered.light === undefined) {
      filtered.light = '1';
    }
    const qs = Object.keys(filtered).length ? '?' + new URLSearchParams(filtered).toString() : '';
    return adminRequest<CompanyReport>(`/companies/report/${qs}`, options);
  },
  downloadCompanyReport: (format: 'csv' | 'xlsx', params?: Record<string, string | number | boolean | undefined | null>) =>
    adminDownload('/companies/report/', { ...(params || {}), export: format }),
  companyPresets: () => adminRequest<CompanyPreset[]>('/companies/presets/'),
  listCompanyFilters: () => adminRequest<{ results: SavedCompanyFilter[]; count: number }>('/company-filters/'),
  saveCompanyFilter: (data: Pick<SavedCompanyFilter, 'name' | 'description' | 'filters' | 'is_favorite'>) =>
    adminRequest<SavedCompanyFilter>('/company-filters/', {
      method: 'POST',
      body: JSON.stringify(data),
    }),
  updateCompanyFilter: (id: number, data: Partial<SavedCompanyFilter>) =>
    adminRequest<SavedCompanyFilter>(`/company-filters/${id}/`, {
      method: 'PATCH',
      body: JSON.stringify(data),
    }),
  deleteCompanyFilter: (id: number) =>
    adminRequest<void>(`/company-filters/${id}/`, { method: 'DELETE' }),

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
