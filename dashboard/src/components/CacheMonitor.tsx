import { useMutation, useQueryClient } from '@tanstack/react-query';
import { useCacheStats } from '../hooks/useDashboardData';
import { dashboardApi } from '../services/api';
import { formatRelativeTime } from '../utils/formatters';
import { Database, RefreshCw, Trash2, CheckCircle, XCircle } from 'lucide-react';

// Map backend cache keys to human-readable display names
const CACHE_DISPLAY_NAMES: Record<string, string> = {
  'users_by_id': 'Employees',
  'assets': 'Vehicles',
  'sites': 'Sites/Jobs',
  'titles': 'Titles',
  'roles': 'Roles',
  'asset_types': 'Asset Types',
  'audit:log': 'Audit Log',
};

const formatCacheName = (key: string): string => {
  // Remove 'safetyamp_' prefix if present
  const cleanKey = key.replace(/^safetyamp_/, '');
  return CACHE_DISPLAY_NAMES[cleanKey] || cleanKey.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
};

const formatSize = (sizeBytes: number, keyType?: string): string => {
  // For list/set/hash types, display as item count
  if (keyType && keyType !== 'string') {
    return `${sizeBytes} items`;
  }
  // For string types, display as bytes
  if (sizeBytes < 1024) return `${sizeBytes} B`;
  if (sizeBytes < 1024 * 1024) return `${(sizeBytes / 1024).toFixed(1)} KB`;
  return `${(sizeBytes / (1024 * 1024)).toFixed(1)} MB`;
};

export function CacheMonitor() {
  const queryClient = useQueryClient();
  const { data, isLoading, refetch, isFetching } = useCacheStats();

  const invalidateMutation = useMutation({
    mutationFn: (cacheName: string) => dashboardApi.invalidateCache(cacheName),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['dashboard', 'cache-stats'] });
    },
  });

  const refreshMutation = useMutation({
    mutationFn: (cacheName: string) => dashboardApi.refreshCache(cacheName),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['dashboard', 'cache-stats'] });
    },
  });

  const invalidateAllMutation = useMutation({
    mutationFn: () => dashboardApi.invalidateCache('all'),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['dashboard', 'cache-stats'] });
    },
  });

  const formatTTL = (seconds?: number) => {
    if (!seconds) return 'N/A';
    const hours = Math.floor(seconds / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    if (hours > 0) return `${hours}h ${minutes}m`;
    return `${minutes}m`;
  };

  return (
    <div className="bg-white dark:bg-gray-800 rounded-lg shadow">
      {/* Header */}
      <div className="px-6 py-4 border-b border-gray-200 dark:border-gray-700">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Database className="w-5 h-5 text-cyan-600" />
            <h2 className="text-lg font-semibold text-gray-900 dark:text-white">Cache Monitor</h2>
          </div>
          <div className="flex items-center gap-3">
            <button
              onClick={() => invalidateAllMutation.mutate()}
              disabled={invalidateAllMutation.isPending}
              className="flex items-center gap-2 px-3 py-1.5 text-sm text-red-600 border border-red-300 dark:border-red-600 rounded hover:bg-red-50 dark:hover:bg-red-900/30 disabled:opacity-50 transition-colors"
            >
              <Trash2 className={`w-4 h-4 ${invalidateAllMutation.isPending ? 'animate-spin' : ''}`} />
              Clear All
            </button>
            <button
              onClick={() => refetch()}
              disabled={isFetching}
              className="flex items-center gap-2 px-3 py-1.5 text-sm text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white hover:bg-gray-100 dark:hover:bg-gray-700 rounded transition-colors"
            >
              <RefreshCw className={`w-4 h-4 ${isFetching ? 'animate-spin' : ''}`} />
            </button>
          </div>
        </div>

        {/* Redis Status */}
        <div className="mt-4 flex items-center gap-4">
          <div className="flex items-center gap-2">
            {data?.redis_connected ? (
              <>
                <CheckCircle className="w-4 h-4 text-green-600" />
                <span className="text-sm text-green-600 dark:text-green-400">Redis Connected</span>
              </>
            ) : (
              <>
                <XCircle className="w-4 h-4 text-red-600" />
                <span className="text-sm text-red-600 dark:text-red-400">Redis Disconnected</span>
              </>
            )}
          </div>
          {data?.cache_ttl_hours && (
            <span className="text-sm text-gray-500 dark:text-gray-400">
              Default TTL: {data.cache_ttl_hours}h
            </span>
          )}
        </div>
      </div>

      {/* Cache List */}
      <div className="p-6">
        {isLoading && !data ? (
          <div className="text-center text-gray-500 dark:text-gray-400">Loading...</div>
        ) : !data?.caches || Object.keys(data.caches).length === 0 ? (
          <div className="text-center text-gray-500 dark:text-gray-400">No caches available</div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {Object.entries(data.caches)
              .filter(([key]) => !key.includes('rate_limit') && !key.endsWith(':metadata'))
              .sort(([, a], [, b]) => ((b?.size_bytes ?? b?.size) || 0) - ((a?.size_bytes ?? a?.size) || 0))
              .map(([cacheKey, cacheInfo]) => {
              const hasData = cacheInfo && ((cacheInfo.size_bytes ?? 0) > 0 || (cacheInfo.size ?? 0) > 0);
              const displayName = formatCacheName(cacheKey);

              return (
                <div
                  key={cacheKey}
                  className={`rounded-lg border p-4 ${
                    hasData ? 'border-green-200 dark:border-green-700 bg-green-50 dark:bg-green-900/30' : 'border-gray-200 dark:border-gray-600 bg-gray-50 dark:bg-gray-700'
                  }`}
                >
                  <div className="flex items-center justify-between mb-3">
                    <div>
                      <h3 className="font-medium text-gray-900 dark:text-white">{displayName}</h3>
                      {cacheInfo?.key_type && cacheInfo.key_type !== 'string' && (
                        <span className="text-xs text-gray-500 dark:text-gray-400">({cacheInfo.key_type})</span>
                      )}
                    </div>
                    <div className="flex items-center gap-1">
                      <button
                        onClick={() => refreshMutation.mutate(cacheKey)}
                        disabled={refreshMutation.isPending}
                        className="p-1.5 text-blue-600 hover:bg-blue-100 dark:hover:bg-blue-900/30 rounded transition-colors"
                        title="Refresh"
                      >
                        <RefreshCw className="w-4 h-4" />
                      </button>
                      <button
                        onClick={() => invalidateMutation.mutate(cacheKey)}
                        disabled={invalidateMutation.isPending}
                        className="p-1.5 text-red-600 hover:bg-red-100 dark:hover:bg-red-900/30 rounded transition-colors"
                        title="Invalidate"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </div>
                  </div>

                  <div className="space-y-2 text-sm">
                    <div className="flex items-center justify-between">
                      <span className="text-gray-600 dark:text-gray-400">Size</span>
                      <span className="font-medium dark:text-white">
                        {formatSize(cacheInfo?.size_bytes || cacheInfo?.size || 0, cacheInfo?.key_type)}
                      </span>
                    </div>
                    <div className="flex items-center justify-between">
                      <span className="text-gray-600 dark:text-gray-400">TTL Remaining</span>
                      <span className="font-medium dark:text-white">{formatTTL(cacheInfo?.ttl_seconds || cacheInfo?.ttl_remaining)}</span>
                    </div>
                    {cacheInfo?.last_updated && (
                      <div className="flex items-center justify-between">
                        <span className="text-gray-600 dark:text-gray-400">Updated</span>
                        <span className="font-medium dark:text-white">{formatRelativeTime(cacheInfo.last_updated)}</span>
                      </div>
                    )}
                  </div>

                  {/* TTL Progress Bar */}
                  {(cacheInfo?.ttl_seconds || cacheInfo?.ttl_remaining) && data?.cache_ttl_hours && (
                    <div className="mt-3">
                      <div className="w-full bg-gray-200 dark:bg-gray-600 rounded-full h-1.5">
                        <div
                          className="bg-green-600 h-1.5 rounded-full transition-all"
                          style={{
                            width: `${Math.min(100, ((cacheInfo?.ttl_seconds ?? cacheInfo?.ttl_remaining ?? 0) / (data.cache_ttl_hours * 3600)) * 100)}%`,
                          }}
                        />
                      </div>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}

export default CacheMonitor;
