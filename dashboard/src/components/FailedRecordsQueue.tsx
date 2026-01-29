import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { dashboardApi } from '../services/api';
import { formatRelativeTime } from '../utils/formatters';
import { AlertTriangle, RefreshCw, Trash2, RotateCcw, ChevronDown, ChevronUp, Filter } from 'lucide-react';
import type { FailedRecord } from '../types/dashboard';

const ENTITY_TYPES = ['all', 'employee', 'vehicle', 'department', 'job', 'title'];

export function FailedRecordsQueue() {
  const [entityFilter, setEntityFilter] = useState<string>('all');
  const [expandedRecord, setExpandedRecord] = useState<string | null>(null);
  const [page, setPage] = useState(0);
  const limit = 20;

  const queryClient = useQueryClient();

  const { data, isLoading, refetch, isFetching } = useQuery({
    queryKey: ['failed-records-list', entityFilter, page],
    queryFn: () => dashboardApi.getFailedRecordsList({
      entity_type: entityFilter === 'all' ? undefined : entityFilter,
      limit,
      offset: page * limit,
    }),
    refetchInterval: 30000,
  });

  const retryMutation = useMutation({
    mutationFn: (recordId: string) => dashboardApi.retryFailedRecord(recordId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['failed-records-list'] });
    },
  });

  const dismissMutation = useMutation({
    mutationFn: (recordId: string) => dashboardApi.dismissFailedRecord(recordId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['failed-records-list'] });
    },
  });

  const retryAllMutation = useMutation({
    mutationFn: () => dashboardApi.retryAllFailedRecords(entityFilter === 'all' ? undefined : entityFilter),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['failed-records-list'] });
    },
  });

  const getRecordId = (record: FailedRecord) => `${record.entity_type}:${record.entity_id}`;

  return (
    <div className="bg-white dark:bg-gray-800 rounded-lg shadow">
      {/* Header */}
      <div className="px-6 py-4 border-b border-gray-200 dark:border-gray-700">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <AlertTriangle className="w-5 h-5 text-red-600" />
            <h2 className="text-lg font-semibold text-gray-900 dark:text-white">Failed Records Queue</h2>
            {data && <span className="text-sm text-gray-500 dark:text-gray-400">({data.total} total)</span>}
          </div>
          <div className="flex items-center gap-3">
            <button
              onClick={() => retryAllMutation.mutate()}
              disabled={retryAllMutation.isPending || !data?.total}
              className="flex items-center gap-2 px-3 py-1.5 text-sm bg-blue-600 text-white rounded hover:bg-blue-700 disabled:opacity-50 transition-colors"
            >
              <RotateCcw className={`w-4 h-4 ${retryAllMutation.isPending ? 'animate-spin' : ''}`} />
              Retry All
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

        {/* Filters */}
        <div className="mt-4 flex items-center gap-4">
          <div className="flex items-center gap-2">
            <Filter className="w-4 h-4 text-gray-400" />
            <span className="text-sm text-gray-500 dark:text-gray-400">Entity Type:</span>
          </div>
          <select
            value={entityFilter}
            onChange={(e) => { setEntityFilter(e.target.value); setPage(0); }}
            className="text-sm border border-gray-300 dark:border-gray-600 dark:bg-gray-700 dark:text-white rounded px-2 py-1 focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            {ENTITY_TYPES.map(type => (
              <option key={type} value={type}>{type === 'all' ? 'All Types' : type}</option>
            ))}
          </select>
        </div>
      </div>

      {/* Records List */}
      <div className="divide-y divide-gray-200 dark:divide-gray-700">
        {isLoading && !data ? (
          <div className="p-8 text-center text-gray-500 dark:text-gray-400">Loading...</div>
        ) : data?.records && data.records.length > 0 ? (
          data.records.map((record) => {
            const recordId = getRecordId(record);
            const isExpanded = expandedRecord === recordId;

            return (
              <div key={recordId} className="hover:bg-gray-50 dark:hover:bg-gray-700">
                <div
                  className="px-6 py-4 cursor-pointer"
                  onClick={() => setExpandedRecord(isExpanded ? null : recordId)}
                >
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-4">
                      <div>
                        <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-gray-100 dark:bg-gray-700 text-gray-800 dark:text-gray-300">
                          {record.entity_type}
                        </span>
                      </div>
                      <div>
                        <p className="font-medium text-gray-900 dark:text-white">{record.entity_id}</p>
                        <p className="text-sm text-gray-500 dark:text-gray-400">{record.failure_reason}</p>
                      </div>
                    </div>
                    <div className="flex items-center gap-4">
                      <div className="text-right text-sm">
                        <p className="text-gray-600 dark:text-gray-400">{record.attempt_count} attempts</p>
                        <p className="text-gray-500 dark:text-gray-400">Last: {formatRelativeTime(record.last_failed_at)}</p>
                      </div>
                      <div className="flex items-center gap-2">
                        <button
                          onClick={(e) => { e.stopPropagation(); retryMutation.mutate(recordId); }}
                          disabled={retryMutation.isPending}
                          className="p-2 text-blue-600 hover:bg-blue-50 dark:hover:bg-blue-900/30 rounded transition-colors"
                          title="Retry"
                        >
                          <RotateCcw className="w-4 h-4" />
                        </button>
                        <button
                          onClick={(e) => { e.stopPropagation(); dismissMutation.mutate(recordId); }}
                          disabled={dismissMutation.isPending}
                          className="p-2 text-red-600 hover:bg-red-50 dark:hover:bg-red-900/30 rounded transition-colors"
                          title="Dismiss"
                        >
                          <Trash2 className="w-4 h-4" />
                        </button>
                        {isExpanded ? <ChevronUp className="w-4 h-4 text-gray-400" /> : <ChevronDown className="w-4 h-4 text-gray-400" />}
                      </div>
                    </div>
                  </div>
                </div>

                {isExpanded && (
                  <div className="px-6 pb-4 bg-gray-50 dark:bg-gray-700/50">
                    <div className="space-y-3 text-sm">
                      <div>
                        <span className="font-medium text-gray-700 dark:text-gray-300">First Failed:</span>
                        <span className="ml-2 text-gray-600 dark:text-gray-400">{formatRelativeTime(record.first_failed_at)}</span>
                      </div>
                      <div>
                        <span className="font-medium text-gray-700 dark:text-gray-300">HTTP Status:</span>
                        <span className="ml-2 text-gray-600 dark:text-gray-400">{record.http_status}</span>
                      </div>
                      {record.last_error_message && (
                        <div>
                          <span className="font-medium text-gray-700 dark:text-gray-300">Error:</span>
                          <p className="mt-1 text-gray-600 dark:text-gray-400 bg-white dark:bg-gray-800 p-2 rounded border border-gray-200 dark:border-gray-600 font-mono text-xs">
                            {record.last_error_message}
                          </p>
                        </div>
                      )}
                      {Object.keys(record.failed_fields || {}).length > 0 && (
                        <div>
                          <span className="font-medium text-gray-700 dark:text-gray-300">Failed Fields:</span>
                          <div className="mt-1 space-y-1">
                            {Object.entries(record.failed_fields).map(([field, info]) => (
                              <div key={field} className="flex items-center gap-2 text-xs">
                                <span className="font-mono bg-red-100 dark:bg-red-900/50 text-red-800 dark:text-red-300 px-1 rounded">{field}</span>
                                <span className="text-gray-600 dark:text-gray-400">{info.error}</span>
                                {info.value && <span className="text-gray-400 dark:text-gray-500">({info.value})</span>}
                              </div>
                            ))}
                          </div>
                        </div>
                      )}
                    </div>
                  </div>
                )}
              </div>
            );
          })
        ) : (
          <div className="p-8 text-center text-gray-500 dark:text-gray-400">
            No failed records found
          </div>
        )}
      </div>

      {/* Pagination */}
      {data && data.total > limit && (
        <div className="px-6 py-4 border-t border-gray-200 dark:border-gray-700 flex items-center justify-between">
          <span className="text-sm text-gray-500 dark:text-gray-400">
            Showing {page * limit + 1} - {Math.min((page + 1) * limit, data.total)} of {data.total}
          </span>
          <div className="flex gap-2">
            <button
              onClick={() => setPage(p => Math.max(0, p - 1))}
              disabled={page === 0}
              className="px-3 py-1 text-sm border border-gray-300 dark:border-gray-600 dark:text-gray-300 rounded hover:bg-gray-50 dark:hover:bg-gray-700 disabled:opacity-50"
            >
              Previous
            </button>
            <button
              onClick={() => setPage(p => p + 1)}
              disabled={(page + 1) * limit >= data.total}
              className="px-3 py-1 text-sm border border-gray-300 dark:border-gray-600 dark:text-gray-300 rounded hover:bg-gray-50 dark:hover:bg-gray-700 disabled:opacity-50"
            >
              Next
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

export default FailedRecordsQueue;
