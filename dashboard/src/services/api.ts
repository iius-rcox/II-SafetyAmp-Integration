import axios, { type AxiosInstance } from 'axios';
import type {
  ApiCallsResponse,
  SyncMetrics,
  ErrorSuggestionsResponse,
  VistaRecordsResponse,
  TimeRange,
  SyncHistoryResponse,
  EntityCounts,
  CacheStats,
  LiveStatus,
  FailedRecordsResponse,
  DependencyHealth,
  DurationTrendsResponse,
  ApiStats,
  FailedRecordsListResponse,
  SyncDiff,
  NotificationsResponse,
  ConfigStatus,
  AuditLogResponse,
} from '../types/dashboard';

// Create axios instance with base configuration
const createApiClient = (): AxiosInstance => {
  const client = axios.create({
    baseURL: '/api/dashboard',
    timeout: 30000,
    headers: {
      'Content-Type': 'application/json',
    },
  });

  // Add auth token if available
  client.interceptors.request.use((config) => {
    const token = localStorage.getItem('dashboard_token');
    if (token) {
      config.headers['X-Dashboard-Token'] = token;
    }
    return config;
  });

  return client;
};

const api = createApiClient();

// Dashboard API functions
export const dashboardApi = {
  // API Calls
  getApiCalls: async (params?: {
    limit?: number;
    service?: string;
    method?: string;
    errors_only?: boolean;
  }): Promise<ApiCallsResponse> => {
    const { data } = await api.get('/api-calls', { params });
    return data;
  },

  getApiStats: async (service?: string): Promise<ApiStats> => {
    const { data } = await api.get('/api-stats', { params: { service } });
    return data;
  },

  // Sync Metrics
  getSyncMetrics: async (hours?: number): Promise<SyncMetrics> => {
    const { data } = await api.get('/sync-metrics', { params: { hours } });
    return data;
  },

  // Error Suggestions
  getErrorSuggestions: async (hours?: number): Promise<ErrorSuggestionsResponse> => {
    const { data } = await api.get('/error-suggestions', { params: { hours } });
    return data;
  },

  // Vista Records
  getVistaRecords: async (timeRange: TimeRange): Promise<VistaRecordsResponse> => {
    const { data } = await api.get('/vista-records', { params: { time_range: timeRange } });
    return data;
  },

  // Sync History
  getSyncHistory: async (limit?: number): Promise<SyncHistoryResponse> => {
    const { data } = await api.get('/sync-history', { params: { limit } });
    return data;
  },

  // Entity Counts
  getEntityCounts: async (): Promise<EntityCounts> => {
    const { data } = await api.get('/entity-counts');
    return data;
  },

  // Cache Stats
  getCacheStats: async (): Promise<CacheStats> => {
    const { data } = await api.get('/cache-stats');
    return data;
  },

  // Live Status
  getLiveStatus: async (): Promise<LiveStatus> => {
    const { data } = await api.get('/live-status');
    return data;
  },

  // Failed Records
  getFailedRecords: async (entityType?: string): Promise<FailedRecordsResponse> => {
    const { data } = await api.get('/failed-records', { params: { entity_type: entityType } });
    return data;
  },

  // Dependency Health
  getDependencyHealth: async (): Promise<DependencyHealth> => {
    const { data } = await api.get('/dependency-health');
    return data;
  },

  // Duration Trends
  getDurationTrends: async (hours?: number): Promise<DurationTrendsResponse> => {
    const { data } = await api.get('/duration-trends', { params: { hours } });
    return data;
  },

  // --- Feature 1: Failed Records Queue ---
  getFailedRecordsList: async (params?: {
    entity_type?: string;
    limit?: number;
    offset?: number;
  }): Promise<FailedRecordsListResponse> => {
    const { data } = await api.get('/failed-records/list', { params });
    return data;
  },

  retryFailedRecord: async (recordId: string): Promise<{ status: string; record_id: string }> => {
    const { data } = await api.post(`/failed-records/${recordId}/retry`);
    return data;
  },

  dismissFailedRecord: async (recordId: string): Promise<{ status: string; record_id: string }> => {
    const { data } = await api.delete(`/failed-records/${recordId}`);
    return data;
  },

  retryAllFailedRecords: async (entityType?: string): Promise<{ status: string; count: number }> => {
    const { data } = await api.post('/failed-records/retry-all', null, { params: { entity_type: entityType } });
    return data;
  },

  // --- Feature 2: Cache Management ---
  invalidateCache: async (cacheName: string): Promise<{ status: string; cache: string }> => {
    const { data } = await api.post(`/cache/invalidate/${cacheName}`);
    return data;
  },

  refreshCache: async (cacheName: string): Promise<{ status: string; cache: string }> => {
    const { data } = await api.post(`/cache/refresh/${cacheName}`);
    return data;
  },

  // --- Feature 3: Sync Diff Viewer ---
  getSyncDiff: async (entityType: string, entityId: string): Promise<SyncDiff> => {
    const { data } = await api.get(`/sync-diff/${entityType}/${entityId}`);
    return data;
  },

  // --- Feature 5: Notification Log ---
  getNotifications: async (params?: { limit?: number; status?: string }): Promise<NotificationsResponse> => {
    const { data } = await api.get('/notifications', { params });
    return data;
  },

  // --- Feature 6: Configuration Status ---
  getConfigStatus: async (): Promise<ConfigStatus> => {
    const { data } = await api.get('/config-status');
    return data;
  },

  // --- Feature 7: Export Reports ---
  exportReport: async (reportType: string, format: 'csv' | 'json' = 'json', hours?: number): Promise<Blob> => {
    const response = await api.get(`/export/${reportType}`, {
      params: { format, hours },
      responseType: 'blob',
    });
    return response.data;
  },

  // --- Feature 8: Manual Sync Triggers ---
  triggerSync: async (syncType: string): Promise<{ status: string; sync_type: string; message: string }> => {
    const { data } = await api.post('/trigger-sync', { sync_type: syncType });
    return data;
  },

  getSyncTriggerStatus: async (): Promise<{ pending: boolean; running: boolean; last_manual_sync: string | null }> => {
    const { data } = await api.get('/sync-status');
    return data;
  },

  // --- Feature 9: Audit Log ---
  getAuditLog: async (params?: { limit?: number; action?: string; resource?: string }): Promise<AuditLogResponse> => {
    const { data } = await api.get('/audit-log', { params });
    return data;
  },
};

export default dashboardApi;
