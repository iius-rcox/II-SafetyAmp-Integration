import { useMutation, useQueryClient } from '@tanstack/react-query';
import { useCacheStats } from '../hooks/useDashboardData';
import { dashboardApi } from '../services/api';
import { formatRelativeTime } from '../utils/formatters';
import { Database, RefreshCw, Trash2, CheckCircle, XCircle } from 'lucide-react';

const CACHE_NAMES = ['employees', 'vehicles', 'departments', 'jobs', 'titles'];

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
        {isLoading ? (
          <div className="text-center text-gray-500 dark:text-gray-400">Loading...</div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {CACHE_NAMES.map((cacheName) => {
              const cacheInfo = data?.caches?.[cacheName];
              const hasData = cacheInfo && cacheInfo.size > 0;

              return (
                <div
                  key={cacheName}
                  className={`rounded-lg border p-4 ${
                    hasData ? 'border-green-200 dark:border-green-700 bg-green-50 dark:bg-green-900/30' : 'border-gray-200 dark:border-gray-600 bg-gray-50 dark:bg-gray-700'
                  }`}
                >
                  <div className="flex items-center justify-between mb-3">
                    <h3 className="font-medium text-gray-900 dark:text-white capitalize">{cacheName}</h3>
                    <div className="flex items-center gap-1">
                      <button
                        onClick={() => refreshMutation.mutate(cacheName)}
                        disabled={refreshMutation.isPending}
                        className="p-1.5 text-blue-600 hover:bg-blue-100 dark:hover:bg-blue-900/30 rounded transition-colors"
                        title="Refresh"
                      >
                        <RefreshCw className="w-4 h-4" />
                      </button>
                      <button
                        onClick={() => invalidateMutation.mutate(cacheName)}
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
                      <span className="font-medium dark:text-white">{cacheInfo?.size || 0} items</span>
                    </div>
                    <div className="flex items-center justify-between">
                      <span className="text-gray-600 dark:text-gray-400">TTL Remaining</span>
                      <span className="font-medium dark:text-white">{formatTTL(cacheInfo?.ttl_remaining)}</span>
                    </div>
                    {cacheInfo?.last_updated && (
                      <div className="flex items-center justify-between">
                        <span className="text-gray-600 dark:text-gray-400">Updated</span>
                        <span className="font-medium dark:text-white">{formatRelativeTime(cacheInfo.last_updated)}</span>
                      </div>
                    )}
                  </div>

                  {/* TTL Progress Bar */}
                  {cacheInfo?.ttl_remaining && data?.cache_ttl_hours && (
                    <div className="mt-3">
                      <div className="w-full bg-gray-200 dark:bg-gray-600 rounded-full h-1.5">
                        <div
                          className="bg-green-600 h-1.5 rounded-full transition-all"
                          style={{
                            width: `${Math.min(100, (cacheInfo.ttl_remaining / (data.cache_ttl_hours * 3600)) * 100)}%`,
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
