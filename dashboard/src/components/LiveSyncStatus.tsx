import { useLiveStatus, useEntityCounts } from '../hooks/useDashboardData';
import { formatRelativeTime, formatNumber } from '../utils/formatters';
import { Activity, Clock, RefreshCw, Users, Briefcase, Building2, Car } from 'lucide-react';

export function LiveSyncStatus() {
  const { data: liveStatus, isLoading: statusLoading, isFetching: statusFetching } = useLiveStatus();
  const { data: entityCounts, isLoading: countsLoading, isFetching: countsFetching } = useEntityCounts();

  const isLoading = statusLoading || countsLoading;
  const isFetching = statusFetching || countsFetching;
  const hasData = liveStatus || entityCounts;

  return (
    <div className="bg-white dark:bg-gray-800 rounded-lg shadow">
      <div className="px-6 py-4 border-b border-gray-200 dark:border-gray-700">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Activity className="w-5 h-5 text-blue-600" />
            <h2 className="text-lg font-semibold text-gray-900 dark:text-white">Live Status</h2>
            {/* Refetch indicator */}
            {isFetching && hasData && !liveStatus?.sync_in_progress && (
              <span className="text-xs text-blue-500 dark:text-blue-400 animate-pulse">Updating...</span>
            )}
          </div>
          {liveStatus?.sync_in_progress && (
            <div className="flex items-center gap-2 text-blue-600">
              <RefreshCw className="w-4 h-4 animate-spin" />
              <span className="text-sm font-medium">Sync in progress</span>
            </div>
          )}
        </div>
      </div>

      <div className="p-6">
        {isLoading && !liveStatus && !entityCounts ? (
          <div className="space-y-6 animate-pulse">
            <div className="grid grid-cols-2 gap-4">
              <div className="bg-gray-100 dark:bg-gray-700 rounded-lg h-20" />
              <div className="bg-gray-100 dark:bg-gray-700 rounded-lg h-20" />
            </div>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
              {[1, 2, 3, 4].map((i) => (
                <div key={i} className="bg-gray-100 dark:bg-gray-700 rounded-lg h-16" />
              ))}
            </div>
          </div>
        ) : (
          <div className="space-y-6">
            {/* Sync Status */}
            <div className="grid grid-cols-2 gap-4">
              <div className="bg-gray-50 dark:bg-gray-700 rounded-lg p-4">
                <div className="flex items-center gap-2 text-gray-600 dark:text-gray-400 mb-1">
                  <Clock className="w-4 h-4" />
                  <span className="text-sm">Last Sync</span>
                </div>
                <p className="text-lg font-semibold text-gray-900 dark:text-white">
                  {liveStatus?.last_sync_time
                    ? formatRelativeTime(liveStatus.last_sync_time)
                    : 'Never'}
                </p>
              </div>
              <div className="bg-gray-50 dark:bg-gray-700 rounded-lg p-4">
                <div className="flex items-center gap-2 text-gray-600 dark:text-gray-400 mb-1">
                  <Activity className="w-4 h-4" />
                  <span className="text-sm">Current Operation</span>
                </div>
                <p className="text-lg font-semibold text-gray-900 dark:text-white">
                  {liveStatus?.current_operation || 'Idle'}
                </p>
              </div>
            </div>

            {/* Progress Bar (if syncing) */}
            {liveStatus?.sync_in_progress && liveStatus?.progress && (
              <div>
                <div className="flex items-center justify-between text-sm mb-2">
                  <span className="text-gray-600 dark:text-gray-400">
                    Processing {liveStatus.progress.entity_type}
                  </span>
                  <span className="text-gray-900 dark:text-white font-medium">
                    {liveStatus.progress.current} / {liveStatus.progress.total}
                  </span>
                </div>
                <div className="w-full bg-gray-200 dark:bg-gray-600 rounded-full h-2">
                  <div
                    className="bg-blue-600 h-2 rounded-full transition-all duration-300"
                    style={{
                      width: `${(liveStatus.progress.current / liveStatus.progress.total) * 100}%`,
                    }}
                  />
                </div>
              </div>
            )}

            {/* Entity Counts */}
            <div>
              <h3 className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-3">Entity Counts</h3>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                <div className="flex items-center gap-3 bg-blue-50 dark:bg-blue-900/30 rounded-lg p-3">
                  <Users className="w-5 h-5 text-blue-600" />
                  <div>
                    <p className="text-lg font-bold text-gray-900 dark:text-white">
                      {formatNumber(entityCounts?.employees || 0)}
                    </p>
                    <p className="text-xs text-gray-500 dark:text-gray-400">Employees</p>
                  </div>
                </div>
                <div className="flex items-center gap-3 bg-green-50 dark:bg-green-900/30 rounded-lg p-3">
                  <Briefcase className="w-5 h-5 text-green-600" />
                  <div>
                    <p className="text-lg font-bold text-gray-900 dark:text-white">
                      {formatNumber(entityCounts?.jobs || 0)}
                    </p>
                    <p className="text-xs text-gray-500 dark:text-gray-400">Jobs</p>
                  </div>
                </div>
                <div className="flex items-center gap-3 bg-purple-50 dark:bg-purple-900/30 rounded-lg p-3">
                  <Building2 className="w-5 h-5 text-purple-600" />
                  <div>
                    <p className="text-lg font-bold text-gray-900 dark:text-white">
                      {formatNumber(entityCounts?.departments || 0)}
                    </p>
                    <p className="text-xs text-gray-500 dark:text-gray-400">Departments</p>
                  </div>
                </div>
                <div className="flex items-center gap-3 bg-orange-50 dark:bg-orange-900/30 rounded-lg p-3">
                  <Car className="w-5 h-5 text-orange-600" />
                  <div>
                    <p className="text-lg font-bold text-gray-900 dark:text-white">
                      {formatNumber(entityCounts?.vehicles || 0)}
                    </p>
                    <p className="text-xs text-gray-500 dark:text-gray-400">Vehicles</p>
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

export default LiveSyncStatus;
