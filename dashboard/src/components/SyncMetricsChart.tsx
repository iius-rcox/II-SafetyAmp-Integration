import { useState } from 'react';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from 'recharts';
import { useSyncMetrics } from '../hooks/useDashboardData';
import { format, parseISO } from 'date-fns';
import { RefreshCw, Activity } from 'lucide-react';
import { formatNumber, formatPercent } from '../utils/formatters';

const TIME_RANGES = [
  { label: '1h', hours: 1 },
  { label: '6h', hours: 6 },
  { label: '24h', hours: 24 },
  { label: '7d', hours: 168 },
];

interface TooltipPayload {
  dataKey: string;
  color: string;
  value: number;
  payload: {
    timestamp: string;
    updates: number;
    errors: number;
    skips: number;
    details?: {
      updates: string[];
      errors: string[];
      skips: string[];
    };
  };
}

interface CustomTooltipProps {
  active?: boolean;
  payload?: TooltipPayload[];
  label?: string;
}

function CustomTooltip({ active, payload, label }: CustomTooltipProps) {
  if (!active || !payload || !payload.length) return null;

  const data = payload[0]?.payload;
  if (!data) return null;

  return (
    <div className="bg-white dark:bg-gray-800 p-4 rounded-lg shadow-lg border border-gray-200 dark:border-gray-700 max-w-sm">
      <p className="text-sm font-medium text-gray-900 dark:text-white mb-2">
        {label && format(parseISO(label), 'MMM d, HH:mm')}
      </p>
      <div className="space-y-2">
        <div className="flex items-center justify-between gap-4">
          <span className="text-sm text-green-600">Updates:</span>
          <span className="font-medium dark:text-white">{formatNumber(data.updates)}</span>
        </div>
        <div className="flex items-center justify-between gap-4">
          <span className="text-sm text-red-600">Errors:</span>
          <span className="font-medium dark:text-white">{formatNumber(data.errors)}</span>
        </div>
        <div className="flex items-center justify-between gap-4">
          <span className="text-sm text-gray-600 dark:text-gray-400">Skipped:</span>
          <span className="font-medium dark:text-white">{formatNumber(data.skips)}</span>
        </div>
      </div>
      {data.details && (
        <div className="mt-3 pt-3 border-t border-gray-200 dark:border-gray-700 text-xs">
          {data.details.updates.length > 0 && (
            <div className="text-green-600 mb-1">
              <span className="font-medium">Updated:</span> {data.details.updates.slice(0, 3).join(', ')}
              {data.details.updates.length > 3 && ` +${data.details.updates.length - 3} more`}
            </div>
          )}
          {data.details.errors.length > 0 && (
            <div className="text-red-600">
              <span className="font-medium">Errors:</span> {data.details.errors.slice(0, 2).join(', ')}
              {data.details.errors.length > 2 && ` +${data.details.errors.length - 2} more`}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export function SyncMetricsChart() {
  const [hours, setHours] = useState(24);
  const { data, isLoading, error, refetch, isFetching } = useSyncMetrics(hours);

  if (error) {
    return (
      <div className="bg-white dark:bg-gray-800 rounded-lg shadow p-6">
        <div className="text-red-600">Failed to load sync metrics: {String(error)}</div>
      </div>
    );
  }

  return (
    <div className="bg-white dark:bg-gray-800 rounded-lg shadow">
      {/* Header */}
      <div className="px-6 py-4 border-b border-gray-200 dark:border-gray-700">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Activity className="w-5 h-5 text-blue-600" />
            <h2 className="text-lg font-semibold text-gray-900 dark:text-white">Sync Metrics</h2>
          </div>
          <div className="flex items-center gap-3">
            {/* Time Range Buttons */}
            <div className="flex rounded-md shadow-sm">
              {TIME_RANGES.map((range) => (
                <button
                  key={range.label}
                  onClick={() => setHours(range.hours)}
                  className={`px-3 py-1.5 text-sm font-medium border first:rounded-l-md last:rounded-r-md -ml-px first:ml-0 transition-colors ${
                    hours === range.hours
                      ? 'bg-blue-600 text-white border-blue-600 z-10'
                      : 'bg-white dark:bg-gray-700 text-gray-700 dark:text-gray-300 border-gray-300 dark:border-gray-600 hover:bg-gray-50 dark:hover:bg-gray-600'
                  }`}
                >
                  {range.label}
                </button>
              ))}
            </div>
            <button
              onClick={() => refetch()}
              disabled={isFetching}
              className="flex items-center gap-2 px-3 py-1.5 text-sm text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white hover:bg-gray-100 dark:hover:bg-gray-700 rounded transition-colors"
            >
              <RefreshCw className={`w-4 h-4 ${isFetching ? 'animate-spin' : ''}`} />
            </button>
          </div>
        </div>

        {/* Summary Stats */}
        {data && (
          <div className="mt-4 grid grid-cols-4 gap-4">
            <div className="text-center">
              <p className="text-2xl font-bold text-gray-900 dark:text-white">{formatNumber(data.total_syncs)}</p>
              <p className="text-sm text-gray-500 dark:text-gray-400">Total Syncs</p>
            </div>
            <div className="text-center">
              <p className="text-2xl font-bold text-green-600">{formatNumber(data.successful_syncs)}</p>
              <p className="text-sm text-gray-500 dark:text-gray-400">Successful</p>
            </div>
            <div className="text-center">
              <p className="text-2xl font-bold text-red-600">{formatNumber(data.failed_syncs)}</p>
              <p className="text-sm text-gray-500 dark:text-gray-400">Failed</p>
            </div>
            <div className="text-center">
              <p className="text-2xl font-bold text-blue-600">{formatPercent(data.success_rate)}</p>
              <p className="text-sm text-gray-500 dark:text-gray-400">Success Rate</p>
            </div>
          </div>
        )}
      </div>

      {/* Chart */}
      <div className="p-6">
        {isLoading ? (
          <div className="h-80 flex items-center justify-center text-gray-500 dark:text-gray-400">Loading...</div>
        ) : data?.time_series && data.time_series.length > 0 ? (
          <ResponsiveContainer width="100%" height={320}>
            <LineChart data={data.time_series}>
              <CartesianGrid strokeDasharray="3 3" stroke="#E5E7EB" />
              <XAxis
                dataKey="timestamp"
                tickFormatter={(value) => format(parseISO(value), hours <= 24 ? 'HH:mm' : 'MMM d')}
                stroke="#9CA3AF"
                fontSize={12}
              />
              <YAxis stroke="#9CA3AF" fontSize={12} />
              <Tooltip content={<CustomTooltip />} />
              <Legend />
              <Line
                type="monotone"
                dataKey="updates"
                name="Updates"
                stroke="#10B981"
                strokeWidth={2}
                dot={false}
                activeDot={{ r: 6 }}
              />
              <Line
                type="monotone"
                dataKey="errors"
                name="Errors"
                stroke="#EF4444"
                strokeWidth={2}
                dot={false}
                activeDot={{ r: 6 }}
              />
              <Line
                type="monotone"
                dataKey="skips"
                name="Skipped"
                stroke="#6B7280"
                strokeWidth={2}
                dot={false}
                activeDot={{ r: 6 }}
              />
            </LineChart>
          </ResponsiveContainer>
        ) : (
          <div className="h-80 flex items-center justify-center text-gray-500 dark:text-gray-400">
            No sync data available for the selected time range
          </div>
        )}
      </div>

      {/* Operation Breakdown */}
      {data?.by_operation && Object.keys(data.by_operation).length > 0 && (
        <div className="px-6 pb-6">
          <h3 className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-3">By Operation</h3>
          <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
            {Object.entries(data.by_operation).map(([op, stats]) => (
              <div key={op} className="bg-gray-50 dark:bg-gray-700 rounded-lg p-3">
                <p className="text-sm font-medium text-gray-900 dark:text-white capitalize">{op}</p>
                <div className="mt-1 text-xs text-gray-500 dark:text-gray-400">
                  <span className="text-green-600">{stats.successful}</span> ok /
                  <span className="text-red-600 ml-1">{stats.failed}</span> fail
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

export default SyncMetricsChart;
