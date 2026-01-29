import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { dashboardApi } from '../services/api';
import { formatRelativeTime } from '../utils/formatters';
import { ClipboardList, RefreshCw, Filter, User, Globe } from 'lucide-react';

const ACTION_FILTERS = ['all', 'cache_invalidate', 'cache_refresh', 'retry_record', 'dismiss_record', 'trigger_sync', 'export'];

export function AuditLog() {
  const [actionFilter, setActionFilter] = useState<string>('all');

  const { data, isLoading, refetch, isFetching } = useQuery({
    queryKey: ['audit-log', actionFilter],
    queryFn: () => dashboardApi.getAuditLog({
      limit: 100,
      action: actionFilter === 'all' ? undefined : actionFilter,
    }),
  });

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
    <div className="bg-white rounded-lg shadow">
      {/* Header */}
      <div className="px-6 py-4 border-b border-gray-200">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <ClipboardList className="w-5 h-5 text-slate-600" />
            <h2 className="text-lg font-semibold text-gray-900">Audit Log</h2>
            {data && <span className="text-sm text-gray-500">({data.total} entries)</span>}
          </div>
          <button
            onClick={() => refetch()}
            disabled={isFetching}
            className="flex items-center gap-2 px-3 py-1.5 text-sm text-gray-600 hover:text-gray-900 hover:bg-gray-100 rounded transition-colors"
          >
            <RefreshCw className={`w-4 h-4 ${isFetching ? 'animate-spin' : ''}`} />
          </button>
        </div>

        {/* Filters */}
        <div className="mt-4 flex items-center gap-4">
          <div className="flex items-center gap-2">
            <Filter className="w-4 h-4 text-gray-400" />
            <span className="text-sm text-gray-500">Action:</span>
          </div>
          <select
            value={actionFilter}
            onChange={(e) => setActionFilter(e.target.value)}
            className="text-sm border border-gray-300 rounded px-2 py-1 focus:outline-none focus:ring-2 focus:ring-slate-500"
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
      <div className="divide-y divide-gray-200 max-h-[600px] overflow-y-auto">
        {isLoading ? (
          <div className="p-8 text-center text-gray-500">Loading...</div>
        ) : data?.entries && data.entries.length > 0 ? (
          data.entries.map((entry) => (
            <div key={entry.id} className="px-6 py-4 hover:bg-gray-50">
              <div className="flex items-start justify-between">
                <div className="space-y-2">
                  <div className="flex items-center gap-2">
                    <span className={`px-2 py-0.5 rounded text-xs font-medium ${getActionBadgeClass(entry.action)}`}>
                      {entry.action.replace(/_/g, ' ')}
                    </span>
                    <span className="text-sm text-gray-600">{entry.resource}</span>
                  </div>

                  <div className="flex items-center gap-4 text-sm text-gray-500">
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
                    <div className="text-xs text-gray-500 bg-gray-50 p-2 rounded font-mono">
                      {Object.entries(entry.details).map(([key, value]) => (
                        <div key={key}>
                          <span className="text-gray-400">{key}:</span> {JSON.stringify(value)}
                        </div>
                      ))}
                    </div>
                  )}
                </div>
                <div className="text-sm text-gray-500 whitespace-nowrap">
                  {formatRelativeTime(entry.timestamp)}
                </div>
              </div>
            </div>
          ))
        ) : (
          <div className="p-8 text-center text-gray-500">
            <ClipboardList className="w-12 h-12 mx-auto mb-4 text-gray-300" />
            <p>No audit entries found</p>
          </div>
        )}
      </div>
    </div>
  );
}

export default AuditLog;
