import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { dashboardApi } from '../services/api';
import type { TimeRange } from '../types/dashboard';

// Query key factory
export const dashboardKeys = {
  all: ['dashboard'] as const,
  apiCalls: (filters?: { limit?: number; service?: string; method?: string; errors_only?: boolean }) =>
    [...dashboardKeys.all, 'api-calls', filters] as const,
  apiStats: (service?: string) => [...dashboardKeys.all, 'api-stats', service] as const,
  syncMetrics: (hours?: number) => [...dashboardKeys.all, 'sync-metrics', hours] as const,
  errorSuggestions: (hours?: number) => [...dashboardKeys.all, 'error-suggestions', hours] as const,
  vistaRecords: (timeRange: TimeRange) => [...dashboardKeys.all, 'vista-records', timeRange] as const,
  syncHistory: (limit?: number) => [...dashboardKeys.all, 'sync-history', limit] as const,
  entityCounts: () => [...dashboardKeys.all, 'entity-counts'] as const,
  cacheStats: () => [...dashboardKeys.all, 'cache-stats'] as const,
  liveStatus: () => [...dashboardKeys.all, 'live-status'] as const,
  failedRecords: (entityType?: string) => [...dashboardKeys.all, 'failed-records', entityType] as const,
  dependencyHealth: () => [...dashboardKeys.all, 'dependency-health'] as const,
  durationTrends: (hours?: number) => [...dashboardKeys.all, 'duration-trends', hours] as const,
  syncPause: () => [...dashboardKeys.all, 'sync-pause'] as const,
};

// API Calls hook
export function useApiCalls(filters?: {
  limit?: number;
  service?: string;
  method?: string;
  errors_only?: boolean;
}) {
  return useQuery({
    queryKey: dashboardKeys.apiCalls(filters),
    queryFn: () => dashboardApi.getApiCalls(filters),
    refetchInterval: 30000, // Refresh every 30 seconds
  });
}

// API Stats hook
export function useApiStats(service?: string) {
  return useQuery({
    queryKey: dashboardKeys.apiStats(service),
    queryFn: () => dashboardApi.getApiStats(service),
    refetchInterval: 30000,
  });
}

// Sync Metrics hook
export function useSyncMetrics(hours: number = 24) {
  return useQuery({
    queryKey: dashboardKeys.syncMetrics(hours),
    queryFn: () => dashboardApi.getSyncMetrics(hours),
    refetchInterval: 60000, // Refresh every minute
  });
}

// Error Suggestions hook
export function useErrorSuggestions(hours: number = 24) {
  return useQuery({
    queryKey: dashboardKeys.errorSuggestions(hours),
    queryFn: () => dashboardApi.getErrorSuggestions(hours),
    refetchInterval: 60000,
  });
}

// Vista Records hook
export function useVistaRecords(timeRange: TimeRange) {
  return useQuery({
    queryKey: dashboardKeys.vistaRecords(timeRange),
    queryFn: () => dashboardApi.getVistaRecords(timeRange),
    refetchInterval: 60000,
  });
}

// Sync History hook
export function useSyncHistory(limit: number = 10) {
  return useQuery({
    queryKey: dashboardKeys.syncHistory(limit),
    queryFn: () => dashboardApi.getSyncHistory(limit),
    refetchInterval: 30000,
  });
}

// Entity Counts hook
export function useEntityCounts() {
  return useQuery({
    queryKey: dashboardKeys.entityCounts(),
    queryFn: () => dashboardApi.getEntityCounts(),
    refetchInterval: 60000,
  });
}

// Cache Stats hook
export function useCacheStats() {
  return useQuery({
    queryKey: dashboardKeys.cacheStats(),
    queryFn: () => dashboardApi.getCacheStats(),
    refetchInterval: 30000,
  });
}

// Live Status hook
export function useLiveStatus() {
  return useQuery({
    queryKey: dashboardKeys.liveStatus(),
    queryFn: () => dashboardApi.getLiveStatus(),
    refetchInterval: 5000, // Refresh every 5 seconds for live updates
  });
}

// Failed Records hook
export function useFailedRecords(entityType?: string) {
  return useQuery({
    queryKey: dashboardKeys.failedRecords(entityType),
    queryFn: () => dashboardApi.getFailedRecords(entityType),
    refetchInterval: 30000,
  });
}

// Dependency Health hook
export function useDependencyHealth() {
  return useQuery({
    queryKey: dashboardKeys.dependencyHealth(),
    queryFn: () => dashboardApi.getDependencyHealth(),
    refetchInterval: 15000, // Refresh every 15 seconds
  });
}

// Duration Trends hook
export function useDurationTrends(hours: number = 24) {
  return useQuery({
    queryKey: dashboardKeys.durationTrends(hours),
    queryFn: () => dashboardApi.getDurationTrends(hours),
    refetchInterval: 60000,
  });
}

// Sync Pause hook
export function useSyncPause() {
  return useQuery({
    queryKey: dashboardKeys.syncPause(),
    queryFn: () => dashboardApi.getSyncPauseState(),
    refetchInterval: 10000, // Refresh every 10 seconds
  });
}

// Sync Pause mutation hook
export function useSyncPauseMutation() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (paused: boolean) => dashboardApi.setSyncPauseState(paused),
    onSuccess: () => {
      // Invalidate sync pause query to refetch current state
      queryClient.invalidateQueries({ queryKey: dashboardKeys.syncPause() });
      // Also invalidate live status as it may reflect pause state
      queryClient.invalidateQueries({ queryKey: dashboardKeys.liveStatus() });
    },
    onError: (error: Error) => {
      // Log error for debugging - component can access via mutation.error
      console.error('Failed to toggle sync pause state:', error.message);
      // The error will be available to components via mutation.isError and mutation.error
    },
  });
}
