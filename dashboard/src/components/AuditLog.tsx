import { useState, useRef, useEffect } from 'react';
import { useQuery } from '@tanstack/react-query';
import { dashboardApi } from '../services/api';
import { formatRelativeTime } from '../utils/formatters';
import { ClipboardList, RefreshCw, Filter, User, Globe } from 'lucide-react';

const ACTION_FILTERS = ['all', 'cache_invalidate', 'cache_refresh', 'retry_record', 'dismiss_record', 'trigger_sync', 'export'];

export function AuditLog() {
  const [actionFilter, setActionFilter] = useState<string>('all');
  const scrollContainerRef = useRef<HTMLDivElement>(null);
  const scrollPositionRef = useRef<number>(0);

  const { data, isLoading, refetch, isFetching } = useQuery({
    queryKey: ['audit-log', actionFilter],
    queryFn: () => dashboardApi.getAuditLog({
      limit: 100,
      action: actionFilter === 'all' ? undefined : actionFilter,
    }),
  });

  // Save scroll position before refetch
  useEffect(() => {
    const container = scrollContainerRef.current;
    if (!container) return;

    const handleScroll = () => {
      scrollPositionRef.current = container.scrollTop;
    };

    container.addEventListener('scroll', handleScroll);
    return () => container.removeEventListener('scroll', handleScroll);
  }, []);

  // Restore scroll position after data loads (only for refetches, not filter changes)
  useEffect(() => {
    if (data && scrollContainerRef.current && scrollPositionRef.current > 0) {
      scrollContainerRef.current.scrollTop = scrollPositionRef.current;
    }
  }, [data]);

  const handleFilterChange = (newFilter: string) => {
    // Reset scroll position when filter changes
    scrollPositionRef.current = 0;
    if (scrollContainerRef.current) {
      scrollContainerRef.current.scrollTop = 0;
    }
    setActionFilter(newFilter);
  };

  const getActionBadgeClass = (action: string) => {
    if (action.includes('invalidate') || action.includes('dismiss')) {
      return 'bg-red-100 text-red-800';
    }
    if (action.includes('retry') || action.includes('refresh')) {
      return 'bg-blue-100 text-blue-800';
    }
    if (action.includes('sync') || action.includes('trigger')) {
      return 'bg-orange-100 text-orange-800';
    }
    if (action.includes('export')) {
      return 'bg-green-100 text-green-800';
    }
    return 'bg-gray-100 text-gray-800';
  };

  return (
    <div className="bg-white dark:bg-gray-800 rounded-lg shadow">
      {/* Header */}
      <div className="px-6 py-4 border-b border-gray-200 dark:border-gray-700">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <ClipboardList className="w-5 h-5 text-slate-600 dark:text-slate-400" />
            <h2 className="text-lg font-semibold text-gray-900 dark:text-white">Audit Log</h2>
            {data && <span className="text-sm text-gray-500 dark:text-gray-400">({data.total} entries)</span>}
            {/* Refetch indicator */}
            {isFetching && data && (
              <span className="text-xs text-blue-500 dark:text-blue-400 animate-pulse">Updating...</span>
            )}
          </div>
          <button
            onClick={() => refetch()}
            disabled={isFetching}
            className="flex items-center gap-2 px-3 py-1.5 text-sm text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white hover:bg-gray-100 dark:hover:bg-gray-700 rounded transition-colors"
          >
            <RefreshCw className={`w-4 h-4 ${isFetching ? 'animate-spin' : ''}`} />
          </button>
        </div>

        {/* Filters */}
        <div className="mt-4 flex items-center gap-4">
          <div className="flex items-center gap-2">
            <Filter className="w-4 h-4 text-gray-400" />
            <span className="text-sm text-gray-500 dark:text-gray-400">Action:</span>
          </div>
          <select
            value={actionFilter}
            onChange={(e) => handleFilterChange(e.target.value)}
            className="text-sm border border-gray-300 dark:border-gray-600 dark:bg-gray-700 dark:text-white rounded px-2 py-1 focus:outline-none focus:ring-2 focus:ring-slate-500"
          >
            {ACTION_FILTERS.map(action => (
              <option key={action} value={action}>
                {action === 'all' ? 'All Actions' : action.replace(/_/g, ' ')}
              </option>
            ))}
          </select>
        </div>
      </div>

      {/* Audit Entries */}
      <div
        ref={scrollContainerRef}
        className="divide-y divide-gray-200 dark:divide-gray-700 max-h-[600px] overflow-y-auto"
      >
        {isLoading && !data ? (
          <div className="p-8 text-center text-gray-500 dark:text-gray-400">Loading...</div>
        ) : data?.entries && data.entries.length > 0 ? (
          data.entries.map((entry) => (
            <div key={entry.id} className="px-6 py-4 hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors">
              <div className="flex items-start justify-between">
                <div className="space-y-2">
                  <div className="flex items-center gap-2">
                    <span className={`px-2 py-0.5 rounded text-xs font-medium ${getActionBadgeClass(entry.action)}`}>
                      {entry.action.replace(/_/g, ' ')}
                    </span>
                    <span className="text-sm text-gray-600 dark:text-gray-400">{entry.resource}</span>
                  </div>

                  <div className="flex items-center gap-4 text-sm text-gray-500 dark:text-gray-400">
                    <div className="flex items-center gap-1">
                      <User className="w-3 h-3" />
                      <span>{entry.user}</span>
                    </div>
                    {entry.ip_address && (
                      <div className="flex items-center gap-1">
                        <Globe className="w-3 h-3" />
                        <span>{entry.ip_address}</span>
                      </div>
                    )}
                  </div>

                  {entry.details && Object.keys(entry.details).length > 0 && (
                    <div className="text-xs text-gray-500 dark:text-gray-400 bg-gray-50 dark:bg-gray-700 p-2 rounded font-mono">
                      {Object.entries(entry.details).map(([key, value]) => (
                        <div key={key}>
                          <span className="text-gray-400 dark:text-gray-500">{key}:</span> {JSON.stringify(value)}
                        </div>
                      ))}
                    </div>
                  )}
                </div>
                <div className="text-sm text-gray-500 dark:text-gray-400 whitespace-nowrap">
                  {formatRelativeTime(entry.timestamp)}
                </div>
              </div>
            </div>
          ))
        ) : (
          <div className="p-8 text-center text-gray-500 dark:text-gray-400">
            <ClipboardList className="w-12 h-12 mx-auto mb-4 text-gray-300 dark:text-gray-600" />
            <p>No audit entries found</p>
          </div>
        )}
      </div>
    </div>
  );
}

export default AuditLog;
