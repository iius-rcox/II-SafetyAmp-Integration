import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { dashboardApi } from '../services/api';
import { formatRelativeTime } from '../utils/formatters';
import { Play, RefreshCw, Users, Truck, Building2, Briefcase, Tag, Loader2 } from 'lucide-react';

const SYNC_TYPES = [
  { id: 'employees', label: 'Employees', icon: Users, description: 'Sync employee data from Viewpoint' },
  { id: 'vehicles', label: 'Vehicles', icon: Truck, description: 'Sync vehicle data from Samsara' },
  { id: 'departments', label: 'Departments', icon: Building2, description: 'Sync department data' },
  { id: 'jobs', label: 'Jobs', icon: Briefcase, description: 'Sync job/project data' },
  { id: 'titles', label: 'Titles', icon: Tag, description: 'Sync title data' },
  { id: 'full', label: 'Full Sync', icon: RefreshCw, description: 'Run complete sync of all entities' },
];

export function SyncTriggers() {
  const queryClient = useQueryClient();

  const { data: status, refetch: refetchStatus } = useQuery({
    queryKey: ['sync-trigger-status'],
    queryFn: () => dashboardApi.getSyncTriggerStatus(),
    refetchInterval: 5000,
  });

  const triggerMutation = useMutation({
    mutationFn: (syncType: string) => dashboardApi.triggerSync(syncType),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['sync-trigger-status'] });
    },
  });

  const isDisabled = status?.pending || status?.running || triggerMutation.isPending;

  return (
    <div className="bg-white dark:bg-gray-800 rounded-lg shadow">
      {/* Header */}
      <div className="px-6 py-4 border-b border-gray-200 dark:border-gray-700">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Play className="w-5 h-5 text-orange-600" />
            <h2 className="text-lg font-semibold text-gray-900 dark:text-white">Manual Sync Triggers</h2>
          </div>
          <button
            onClick={() => refetchStatus()}
            className="flex items-center gap-2 px-3 py-1.5 text-sm text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white hover:bg-gray-100 dark:hover:bg-gray-700 rounded transition-colors"
          >
            <RefreshCw className="w-4 h-4" />
          </button>
        </div>

        {/* Status Banner */}
        {status && (status.pending || status.running) && (
          <div className="mt-4 flex items-center gap-3 p-3 bg-orange-50 dark:bg-orange-900/30 rounded-lg">
            <Loader2 className="w-5 h-5 text-orange-600 animate-spin" />
            <div>
              <p className="font-medium text-orange-900 dark:text-orange-300">
                {status.running ? 'Sync in Progress' : 'Sync Pending'}
              </p>
              <p className="text-sm text-orange-700 dark:text-orange-400">
                Please wait for the current operation to complete
              </p>
            </div>
          </div>
        )}

        {status?.last_manual_sync && (
          <p className="mt-4 text-sm text-gray-500 dark:text-gray-400">
            Last manual sync: {formatRelativeTime(status.last_manual_sync)}
          </p>
        )}
      </div>

      {/* Sync Options */}
      <div className="p-6">
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {SYNC_TYPES.map((syncType) => {
            const Icon = syncType.icon;
            const isFullSync = syncType.id === 'full';

            return (
              <button
                key={syncType.id}
                onClick={() => triggerMutation.mutate(syncType.id)}
                disabled={isDisabled}
                className={`flex items-start gap-4 p-4 rounded-lg border transition-colors text-left ${
                  isDisabled
                    ? 'bg-gray-50 dark:bg-gray-700 border-gray-200 dark:border-gray-600 cursor-not-allowed opacity-60'
                    : isFullSync
                    ? 'border-orange-300 dark:border-orange-600 hover:border-orange-500 hover:bg-orange-50 dark:hover:bg-orange-900/30'
                    : 'border-gray-200 dark:border-gray-600 hover:border-blue-300 dark:hover:border-blue-500 hover:bg-blue-50 dark:hover:bg-blue-900/30'
                }`}
              >
                <div className={`p-2 rounded-lg ${
                  isFullSync ? 'bg-orange-100 dark:bg-orange-900/50' : 'bg-blue-100 dark:bg-blue-900/50'
                }`}>
                  <Icon className={`w-5 h-5 ${
                    isFullSync ? 'text-orange-600' : 'text-blue-600'
                  }`} />
                </div>
                <div className="flex-1">
                  <p className="font-medium text-gray-900 dark:text-white">{syncType.label}</p>
                  <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">{syncType.description}</p>
                </div>
              </button>
            );
          })}
        </div>

        {/* Mutation Status */}
        {triggerMutation.isSuccess && (
          <div className="mt-4 p-3 bg-green-50 dark:bg-green-900/30 rounded-lg">
            <p className="text-green-800 dark:text-green-300">
              Sync triggered successfully! The operation is now running in the background.
            </p>
          </div>
        )}
        {triggerMutation.isError && (
          <div className="mt-4 p-3 bg-red-50 dark:bg-red-900/30 rounded-lg">
            <p className="text-red-800 dark:text-red-300">
              Failed to trigger sync. Please try again.
            </p>
          </div>
        )}

        {/* Help Text */}
        <div className="mt-6 p-4 bg-gray-50 dark:bg-gray-700 rounded-lg">
          <h3 className="font-medium text-gray-900 dark:text-white mb-2">About Manual Sync</h3>
          <ul className="text-sm text-gray-600 dark:text-gray-300 space-y-1">
            <li>• Manual syncs run immediately in the background</li>
            <li>• Only one sync can run at a time</li>
            <li>• Full sync processes all entity types sequentially</li>
            <li>• Check the Live Status panel for sync progress</li>
          </ul>
        </div>
      </div>
    </div>
  );
}

export default SyncTriggers;
