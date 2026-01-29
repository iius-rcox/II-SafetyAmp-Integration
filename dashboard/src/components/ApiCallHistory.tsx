import { useState } from 'react';
import { useApiCalls } from '../hooks/useDashboardData';
import { formatDateTime, formatDuration, getStatusColor, getStatusBgColor } from '../utils/formatters';
import { RefreshCw, Filter, ChevronDown, ChevronUp } from 'lucide-react';
import type { ApiCall } from '../types/dashboard';

const SERVICE_OPTIONS = ['all', 'safetyamp', 'samsara', 'msgraph', 'viewpoint'];
const METHOD_OPTIONS = ['all', 'GET', 'POST', 'PUT', 'PATCH', 'DELETE'];

export function ApiCallHistory() {
  const [filters, setFilters] = useState({
    limit: 100,
    service: undefined as string | undefined,
    method: undefined as string | undefined,
    errors_only: false,
  });
  const [expandedRow, setExpandedRow] = useState<string | null>(null);

  const { data, isLoading, error, refetch, isFetching } = useApiCalls(filters);

  const handleFilterChange = (key: string, value: string | boolean) => {
    setFilters(prev => ({
      ...prev,
      [key]: value === 'all' ? undefined : value,
    }));
  };

  if (error) {
    return (
      <div className="bg-white dark:bg-gray-800 rounded-lg shadow p-6">
        <div className="text-red-600">Failed to load API calls: {String(error)}</div>
      </div>
    );
  }

  return (
    <div className="bg-white dark:bg-gray-800 rounded-lg shadow">
      {/* Header */}
      <div className="px-6 py-4 border-b border-gray-200 dark:border-gray-700">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-semibold text-gray-900 dark:text-white">API Call History</h2>
          <button
            onClick={() => refetch()}
            disabled={isFetching}
            className="flex items-center gap-2 px-3 py-1.5 text-sm text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white hover:bg-gray-100 dark:hover:bg-gray-700 rounded transition-colors"
          >
            <RefreshCw className={`w-4 h-4 ${isFetching ? 'animate-spin' : ''}`} />
            Refresh
          </button>
        </div>

        {/* Filters */}
        <div className="mt-4 flex flex-wrap items-center gap-4">
          <div className="flex items-center gap-2">
            <Filter className="w-4 h-4 text-gray-400" />
            <span className="text-sm text-gray-500 dark:text-gray-400">Filters:</span>
          </div>

          <select
            value={filters.service || 'all'}
            onChange={(e) => handleFilterChange('service', e.target.value)}
            className="text-sm border border-gray-300 dark:border-gray-600 dark:bg-gray-700 dark:text-white rounded px-2 py-1 focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            {SERVICE_OPTIONS.map(opt => (
              <option key={opt} value={opt}>{opt === 'all' ? 'All Services' : opt}</option>
            ))}
          </select>

          <select
            value={filters.method || 'all'}
            onChange={(e) => handleFilterChange('method', e.target.value)}
            className="text-sm border border-gray-300 dark:border-gray-600 dark:bg-gray-700 dark:text-white rounded px-2 py-1 focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            {METHOD_OPTIONS.map(opt => (
              <option key={opt} value={opt}>{opt === 'all' ? 'All Methods' : opt}</option>
            ))}
          </select>

          <label className="flex items-center gap-2 text-sm text-gray-600 dark:text-gray-400">
            <input
              type="checkbox"
              checked={filters.errors_only}
              onChange={(e) => handleFilterChange('errors_only', e.target.checked)}
              className="rounded border-gray-300 dark:border-gray-600 text-blue-600 focus:ring-blue-500"
            />
            Errors only
          </label>

          {data && (
            <span className="text-sm text-gray-500 dark:text-gray-400 ml-auto">
              Showing {data.calls.length} of {data.total} calls
            </span>
          )}
        </div>
      </div>

      {/* Table */}
      <div className="overflow-x-auto">
        {isLoading ? (
          <div className="p-8 text-center text-gray-500 dark:text-gray-400">Loading...</div>
        ) : (
          <table className="w-full">
            <thead className="bg-gray-50 dark:bg-gray-700">
              <tr>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">Time</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">Service</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">Method</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">Endpoint</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">Status</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">Duration</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider"></th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200 dark:divide-gray-700">
              {data?.calls.map((call: ApiCall) => (
                <>
                  <tr
                    key={call.id}
                    className={`hover:bg-gray-50 dark:hover:bg-gray-700 cursor-pointer ${expandedRow === call.id ? 'bg-blue-50 dark:bg-blue-900/30' : ''}`}
                    onClick={() => setExpandedRow(expandedRow === call.id ? null : call.id)}
                  >
                    <td className="px-4 py-3 text-sm text-gray-600 dark:text-gray-400 whitespace-nowrap">
                      {formatDateTime(call.timestamp)}
                    </td>
                    <td className="px-4 py-3">
                      <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-gray-100 dark:bg-gray-600 text-gray-800 dark:text-gray-200">
                        {call.service}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${
                        call.method === 'GET' ? 'bg-green-100 dark:bg-green-900/50 text-green-800 dark:text-green-300' :
                        call.method === 'POST' ? 'bg-blue-100 dark:bg-blue-900/50 text-blue-800 dark:text-blue-300' :
                        call.method === 'PUT' || call.method === 'PATCH' ? 'bg-yellow-100 dark:bg-yellow-900/50 text-yellow-800 dark:text-yellow-300' :
                        'bg-red-100 dark:bg-red-900/50 text-red-800 dark:text-red-300'
                      }`}>
                        {call.method}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-sm text-gray-900 dark:text-gray-200 font-mono truncate max-w-xs" title={call.endpoint}>
                      {call.endpoint}
                    </td>
                    <td className="px-4 py-3">
                      <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${getStatusBgColor(call.status_code)} ${getStatusColor(call.status_code)}`}>
                        {call.status_code}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-sm text-gray-600 dark:text-gray-400 whitespace-nowrap">
                      {formatDuration(call.duration_ms)}
                    </td>
                    <td className="px-4 py-3 text-gray-400">
                      {expandedRow === call.id ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
                    </td>
                  </tr>
                  {expandedRow === call.id && (
                    <tr key={`${call.id}-details`}>
                      <td colSpan={7} className="px-4 py-4 bg-gray-50 dark:bg-gray-700">
                        <div className="space-y-2 text-sm">
                          {call.correlation_id && (
                            <div><span className="font-medium text-gray-700 dark:text-gray-300">Correlation ID:</span> <span className="text-gray-600 dark:text-gray-400 font-mono">{call.correlation_id}</span></div>
                          )}
                          {call.error_message && (
                            <div><span className="font-medium text-red-700 dark:text-red-400">Error:</span> <span className="text-red-600 dark:text-red-400">{call.error_message}</span></div>
                          )}
                          {call.request_summary && (
                            <div><span className="font-medium text-gray-700 dark:text-gray-300">Request:</span> <span className="text-gray-600 dark:text-gray-400 font-mono text-xs">{call.request_summary}</span></div>
                          )}
                          {call.response_summary && (
                            <div><span className="font-medium text-gray-700 dark:text-gray-300">Response:</span> <span className="text-gray-600 dark:text-gray-400 font-mono text-xs">{call.response_summary}</span></div>
                          )}
                        </div>
                      </td>
                    </tr>
                  )}
                </>
              ))}
              {data?.calls.length === 0 && (
                <tr>
                  <td colSpan={7} className="px-4 py-8 text-center text-gray-500 dark:text-gray-400">
                    No API calls found
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}

export default ApiCallHistory;
