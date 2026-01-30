// API Call types
export interface ApiCall {
  id: string;
  timestamp: string;
  service: 'safetyamp' | 'samsara' | 'msgraph' | 'viewpoint';
  method: string;
  endpoint: string;
  status_code: number;
  duration_ms: number;
  error_message?: string;
  correlation_id?: string;
  request_summary?: string;
  response_summary?: string;
}

export interface ApiCallsResponse {
  calls: ApiCall[];
  total: number;
  filters: {
    limit: number;
    service: string | null;
    method: string | null;
    errors_only: boolean;
  };
  error?: string;
}

// Sync Metrics types
export interface SyncMetrics {
  total_syncs: number;
  successful_syncs: number;
  failed_syncs: number;
  total_records_processed: number;
  success_rate: number;
  by_operation: Record<string, {
    total: number;
    successful: number;
    failed: number;
    records_processed: number;
  }>;
  time_series?: SyncMetricPoint[];
}

export interface SyncMetricPoint {
  timestamp: string;
  updates: number;
  errors: number;
  skips: number;
  details?: {
    updates: string[];
    errors: string[];
    skips: string[];
  };
}

// Error Suggestion types
export type ErrorSeverity = 'high' | 'medium' | 'low';
export type ErrorCategory = 'duplicate_field' | 'missing_field' | 'rate_limit' | 'validation' | 'connectivity';

export interface ErrorSuggestion {
  id: string;
  severity: ErrorSeverity;
  category: ErrorCategory;
  title: string;
  description: string;
  affected_records: string[];
  recommended_action: string;
  first_seen: string;
  occurrence_count: number;
  field?: string;
}

export interface ErrorSuggestionsResponse {
  suggestions: ErrorSuggestion[];
  total: number;
  hours: number;
  error?: string;
}

// Vista Records types
export type TimeRange = '1d' | '7d' | '30d' | '6mo';

export interface VistaRecordsResponse {
  time_range: TimeRange;
  total_records: number;
  by_entity_type: Record<string, number>;
  data_points: VistaDataPoint[];
  error?: string;
}

export interface VistaDataPoint {
  timestamp: string;
  count: number;
  entity_type?: string;
}

// Sync History types
export interface SyncSession {
  session_id: string;
  start_time: string;
  end_time?: string;
  duration_seconds: number;
  sync_type: string;
  status: 'success' | 'partial' | 'failed';
  records_processed: number;
  updates: number;
  errors: number;
  skips: number;
}

export interface SyncHistoryResponse {
  sessions: SyncSession[];
  total: number;
  error?: string;
}

// Entity Counts types
export interface EntityCounts {
  employees: number;
  jobs: number;
  departments: number;
  vehicles: number;
  titles?: number;
}

// Cache Stats types
export interface CacheStats {
  redis_connected: boolean;
  cache_ttl_hours: number;
  caches: Record<string, {
    size?: number;
    size_bytes?: number;
    ttl_remaining?: number;
    ttl_seconds?: number;
    last_updated?: string;
    key_type?: string;
  }>;
}

// Live Status types
export interface LiveStatus {
  sync_in_progress: boolean;
  last_sync_time: string | null;
  next_sync_time?: string | null;
  current_operation: string | null;
  progress?: {
    current: number;
    total: number;
    entity_type: string;
  };
}

// Failed Records types
export interface FailedRecordStats {
  total: number;
  by_entity_type: Record<string, number>;
  by_reason: Record<string, number>;
}

export interface FailedRecordsResponse {
  stats: FailedRecordStats;
  error?: string;
}

// Dependency Health types
export type HealthStatus = 'healthy' | 'degraded' | 'unhealthy' | 'unknown';

export interface DependencyHealth {
  database: {
    status: HealthStatus;
    latency_ms?: number;
    error?: string;
  };
  services: Record<string, {
    status: HealthStatus;
    latency_ms?: number;
    last_check?: string;
    error?: string;
  }>;
}

// Duration Trends types
export interface DurationTrend {
  timestamp: string;
  sync_type: string;
  duration_seconds: number;
  records_processed: number;
}

export interface DurationTrendsResponse {
  trends: DurationTrend[];
  hours: number;
  error?: string;
}

// API Stats types
export interface ApiStats {
  total_calls: number;
  by_service: Record<string, {
    total: number;
    errors: number;
    avg_duration_ms: number;
  }>;
  error_count: number;
  success_rate: number;
  avg_duration_ms: number;
}

// Failed Record (detailed) types - Feature 1
export interface FailedRecord {
  entity_id: string;
  entity_type: string;
  failure_reason: string;
  first_failed_at: string;
  last_failed_at: string;
  attempt_count: number;
  http_status: number;
  last_error_message: string;
  failed_fields: Record<string, {
    value_hash: string;
    error: string;
    value?: string;
  }>;
  retry_requested?: boolean;
  retry_requested_at?: string;
}

export interface FailedRecordsListResponse {
  records: FailedRecord[];
  total: number;
  limit: number;
  offset: number;
  error?: string;
}

// Sync Diff types - Feature 3
export interface SyncDiff {
  entity_type: string;
  entity_id: string;
  source_data: Record<string, unknown> | null;
  target_data: Record<string, unknown> | null;
  diff: {
    status: 'in_sync' | 'different' | 'source_missing' | 'target_missing' | 'both_missing';
    changed_fields: Array<{
      field: string;
      source_value: unknown;
      target_value: unknown;
    }>;
    total_fields?: number;
  };
  has_differences: boolean;
  error?: string;
}

// Notification types - Feature 5
export interface Notification {
  id: string;
  timestamp: string;
  type: string;
  status: 'sent' | 'failed' | 'pending';
  recipient?: string;
  subject?: string;
  error_count?: number;
  delivery_status?: string;
  error?: string;
}

export interface NotificationsResponse {
  notifications: Notification[];
  total: number;
  error?: string;
}

// Configuration Status types - Feature 6
export interface ConfigStatus {
  valid: boolean;
  validation?: {
    is_valid: boolean;
    missing?: string[];
    present?: string[];
  };
  azure?: {
    azure_key_vault_enabled: boolean;
    key_vault_name?: string;
  };
  settings?: Record<string, string>;
  error?: string;
}

// Audit Log types - Feature 9
export interface AuditLogEntry {
  id: string;
  timestamp: string;
  action: string;
  resource: string;
  user: string;
  details: Record<string, unknown>;
  ip_address?: string;
}

export interface AuditLogResponse {
  entries: AuditLogEntry[];
  total: number;
  error?: string;
}

// Theme types - Feature 10
export type Theme = 'light' | 'dark' | 'system';

// Sync Pause types - Feature 11
export interface SyncPauseState {
  paused: boolean;
  paused_by: string | null;
  paused_at: number | null;
}

export interface SyncPauseResponse {
  paused: boolean;
  message: string;
}
