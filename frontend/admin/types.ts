export interface DashboardOverview {
  generated_at: string;
  companies: {
    total: number;
    active: number;
    with_orsr: number;
    with_financials: number;
    orsr_coverage_pct: number;
    financials_coverage_pct: number;
  };
  sync: {
    active_jobs: number;
    completed_jobs_24h: number;
    failed_jobs_24h: number;
    company_failures_24h: number;
    blocked_companies: number;
  };
  users: {
    total: number;
    active_7d: number;
    mrr_eur: number;
  };
}

export interface DashboardSync {
  sources: SyncSource[];
  throughput_24h: {
    succeeded_per_hour: number[];
    failed_per_hour: number[];
  };
}

export interface SyncSource {
  source: string;
  label: string;
  synced_count: number;
  coverage_pct: number;
  failing_count: number;
  avg_consecutive_failures: number;
}

export interface DashboardSystem {
  health: {
    db: string;
    redis: string;
    celery_workers: number;
    queues: Record<string, number | null>;
  };
  audit_events_last_hour: number;
}

export interface SyncJob {
  id: number;
  job_type: string;
  status: 'queued' | 'running' | 'completed' | 'failed' | 'paused' | 'cancelled';
  triggered_by: number | null;
  triggered_by_email: string | null;
  triggered_via: string;
  parameters: Record<string, any> | null;
  total_items: number | null;
  processed_items: number;
  succeeded_items: number;
  failed_items: number;
  skipped_items: number;
  progress_percentage: number;
  items_per_hour: number;
  duration_seconds: number | null;
  queued_at: string;
  started_at: string | null;
  completed_at: string | null;
  last_heartbeat: string | null;
  last_error: string | null;
  notes: string;
  celery_task_id: string;
}

export interface AdminCompany {
  id: number;
  ico: string;
  ruz_id: string | null;
  nazov_UJ: string;
  pravna_forma: string | null;
  sidlo: string | null;
  datum_zalozenia: string | null;
  datum_zrusenia: string | null;
  last_insurance_debt: string | null;
}

export interface AdminUser {
  id: number;
  email: string;
  username: string;
  first_name: string;
  last_name: string;
  subscription_plan: number | null;
  subscription_plan_name: string | null;
  is_active: boolean;
  is_staff: boolean;
  is_superuser: boolean;
  last_login: string | null;
  created_at: string;
}

export interface AuditLogEntry {
  id: number;
  actor: number | null;
  actor_email: string | null;
  action: string;
  target_type: string | null;
  target_id: string | null;
  payload: Record<string, any> | null;
  method: string;
  path: string;
  status_code: number | null;
  ip_address: string | null;
  user_agent: string | null;
  created_at: string;
}

export interface ScheduledTask {
  id: number;
  name: string;
  task: string;
  enabled: boolean;
  interval: string | null;
  crontab: string | null;
  queue: string | null;
  last_run_at: string | null;
  total_run_count: number;
  args: string;
  kwargs: string;
}

export interface CompanySyncStatus {
  id: number;
  company: number;
  company_ico: string;
  company_name: string;
  source: string;
  last_attempted_at: string | null;
  last_succeeded_at: string | null;
  last_error: string | null;
  last_error_type: string | null;
  consecutive_failures: number;
  next_retry_at: string | null;
  is_blocked: boolean;
  blocked_reason: string | null;
  updated_at: string;
}

export type AdminPage =
  | 'dashboard'
  | 'companies'
  | 'users'
  | 'sync-jobs'
  | 'sync-status'
  | 'scheduled-tasks'
  | 'audit-log'
  | 'system';
