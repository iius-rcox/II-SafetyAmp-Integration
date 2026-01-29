import { useState } from 'react';
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from 'recharts';
import { useVistaRecords } from '../hooks/useDashboardData';
import { format, parseISO } from 'date-fns';
import { RefreshCw, Database } from 'lucide-react';
import { formatNumber } from '../utils/formatters';
import type { TimeRange } from '../types/dashboard';

const TIME_RANGE_OPTIONS: { label: string; value: TimeRange }[] = [
  { label: '1 Day', value: '1d' },
  { label: '7 Days', value: '7d' },
  { label: '30 Days', value: '30d' },
  { label: '6 Months', value: '6mo' },
];

interface TooltipPayload {
  dataKey: string;
  color: string;
  value: number;
  payload: {
    timestamp: string;
    count: number;
    entity_type?: string;
  };
}

interface CustomTooltipProps {
  active?: boolean;
  payload?: TooltipPayload[];
  label?: string;
  timeRange: TimeRange;
}

function CustomTooltip({ active, payload, label, timeRange }: CustomTooltipProps) {
  if (!active || !payload || !payload.length) return null;

  const formatStr = timeRange === '1d' ? 'MMM d, HH:mm' : 'MMM d, yyyy';

  return (
    <div className="bg-white dark:bg-gray-800 p-3 rounded-lg shadow-lg border border-gray-200 dark:border-gray-700">
      <p className="text-sm font-medium text-gray-900 dark:text-white mb-1">
        {label && format(parseISO(label), formatStr)}
      </p>
      <p className="text-lg font-bold text-blue-600 dark:text-blue-400">
        {formatNumber(payload[0]?.value || 0)} records
      </p>
    </div>
  );
}

export function VistaRecordsChart() {
  const [timeRange, setTimeRange] = useState<TimeRange>('7d');
  const { data, isLoading, error, refetch, isFetching } = useVistaRecords(timeRange);

  if (error) {
    return (
      <div className="bg-white dark:bg-gray-800 rounded-lg shadow p-6">
        <div className="text-red-600 dark:text-red-400">Failed to load Vista records: {String(error)}</div>
      </div>
    );
  }

  const formatXAxis = (value: string) => {
    try {
      const date = parseISO(value);
      switch (timeRange) {
        case '1d':
          return format(date, 'HH:mm');
        case '7d':
          return format(date, 'EEE');
        case '30d':
          return format(date, 'MMM d');
        case '6mo':
          return format(date, 'MMM');
        default:
          return format(date, 'MMM d');
      }
    } catch {
      return value;
    }
  };

  return (
    <div className="bg-white dark:bg-gray-800 rounded-lg shadow">
      {/* Header */}
      <div className="px-6 py-4 border-b border-gray-200 dark:border-gray-700">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Database className="w-5 h-5 text-purple-600" />
            <h2 className="text-lg font-semibold text-gray-900 dark:text-white">Viewpoint Records Retrieved</h2>
          </div>
          <div className="flex items-center gap-3">
            {/* Time Range Buttons */}
            <div className="flex rounded-md shadow-sm">
              {TIME_RANGE_OPTIONS.map((option) => (
                <button
                  key={option.value}
                  onClick={() => setTimeRange(option.value)}
                  className={`px-3 py-1.5 text-sm font-medium border first:rounded-l-md last:rounded-r-md -ml-px first:ml-0 transition-colors ${
                    timeRange === option.value
                      ? 'bg-purple-600 text-white border-purple-600 z-10'
                      : 'bg-white dark:bg-gray-700 text-gray-700 dark:text-gray-300 border-gray-300 dark:border-gray-600 hover:bg-gray-50 dark:hover:bg-gray-600'
                  }`}
                >
                  {option.label}
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
          <div className="mt-4 flex items-center gap-8">
            <div>
              <p className="text-2xl font-bold text-gray-900 dark:text-white">{formatNumber(data.total_records)}</p>
              <p className="text-sm text-gray-500 dark:text-gray-400">Total Records</p>
            </div>
            {data.by_entity_type && Object.entries(data.by_entity_type).length > 0 && (
              <div className="flex items-center gap-4 text-sm">
                {Object.entries(data.by_entity_type).map(([type, count]) => (
                  <div key={type} className="text-center">
                    <p className="font-medium text-gray-900 dark:text-white">{formatNumber(count)}</p>
                    <p className="text-gray-500 dark:text-gray-400 capitalize">{type}</p>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>

      {/* Chart */}
      <div className="p-6">
        {isLoading && !data ? (
          <div className="h-80 flex items-center justify-center text-gray-500 dark:text-gray-400">Loading...</div>
        ) : data?.data_points && data.data_points.length > 0 ? (
          <ResponsiveContainer width="100%" height={320}>
            <AreaChart data={data.data_points}>
              <defs>
                <linearGradient id="colorRecords" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#8B5CF6" stopOpacity={0.3} />
                  <stop offset="95%" stopColor="#8B5CF6" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" className="stroke-gray-200 dark:stroke-gray-700" />
              <XAxis
                dataKey="timestamp"
                tickFormatter={formatXAxis}
                className="fill-gray-500 dark:fill-gray-400"
                stroke="currentColor"
                fontSize={12}
              />
              <YAxis
                className="fill-gray-500 dark:fill-gray-400"
                stroke="currentColor"
                fontSize={12}
                tickFormatter={(value) => formatNumber(value)}
              />
              <Tooltip content={<CustomTooltip timeRange={timeRange} />} />
              <Area
                type="monotone"
                dataKey="count"
                name="Records"
                stroke="#8B5CF6"
                strokeWidth={2}
                fill="url(#colorRecords)"
                activeDot={{ r: 6, fill: '#8B5CF6' }}
              />
            </AreaChart>
          </ResponsiveContainer>
        ) : (
          <div className="h-80 flex items-center justify-center text-gray-500 dark:text-gray-400">
            No data available for the selected time range
          </div>
        )}
      </div>
    </div>
  );
}

export default VistaRecordsChart;
