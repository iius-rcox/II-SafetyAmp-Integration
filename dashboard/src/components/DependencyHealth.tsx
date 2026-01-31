import { useDependencyHealth } from '../hooks/useDashboardData';
import { formatRelativeTime, getHealthStatusColor, formatDuration } from '../utils/formatters';
import { Heart, Database, Cloud, Server, RefreshCw, CheckCircle, AlertTriangle, XCircle, HelpCircle } from 'lucide-react';
import type { HealthStatus } from '../types/dashboard';

const STATUS_ICONS: Record<HealthStatus, typeof CheckCircle> = {
  healthy: CheckCircle,
  degraded: AlertTriangle,
  unhealthy: XCircle,
  unknown: HelpCircle,
};

const SERVICE_ICONS: Record<string, typeof Cloud> = {
  safetyamp: Cloud,
  samsara: Server,
  msgraph: Server,
  redis: Database,
};

const SERVICE_DISPLAY_NAMES: Record<string, string> = {
  safetyamp: 'SafetyAmp',
  samsara: 'Samsara',
  msgraph: 'MS Graph',
  redis: 'Redis',
  database: 'Database',
};

interface HealthCardProps {
  name: string;
  status: HealthStatus;
  latency_ms?: number;
  last_check?: string;
  error?: string;
}

function HealthCard({ name, status, latency_ms, last_check, error }: HealthCardProps) {
  const StatusIcon = STATUS_ICONS[status];
  const ServiceIcon = SERVICE_ICONS[name.toLowerCase()] || Server;
  const displayName = SERVICE_DISPLAY_NAMES[name.toLowerCase()] || name;

  return (
    <div className={`rounded-lg p-4 ${getHealthStatusColor(status)}`}>
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2">
          <ServiceIcon className="w-5 h-5" />
          <span className="font-medium">{displayName}</span>
        </div>
        <StatusIcon className="w-5 h-5" />
      </div>
      <div className="space-y-1 text-sm">
        <div className="flex items-center justify-between">
          <span className="opacity-75">Status</span>
          <span className="font-medium capitalize">{status}</span>
        </div>
        {latency_ms !== undefined && (
          <div className="flex items-center justify-between">
            <span className="opacity-75">Latency</span>
            <span className="font-medium">{formatDuration(latency_ms)}</span>
          </div>
        )}
        {last_check && (
          <div className="flex items-center justify-between">
            <span className="opacity-75">Checked</span>
            <span className="font-medium">{formatRelativeTime(last_check)}</span>
          </div>
        )}
        {error && (
          <div className="mt-2 pt-2 border-t border-current/20">
            <p className="text-xs opacity-90">{error}</p>
          </div>
        )}
      </div>
    </div>
  );
}

export function DependencyHealth() {
  const { data, isLoading, error, refetch, isFetching } = useDependencyHealth();

  if (error) {
    return (
      <div className="bg-white dark:bg-gray-800 rounded-lg shadow p-6">
        <div className="text-red-600">Failed to load health status: {String(error)}</div>
      </div>
    );
  }

  const allHealthy =
    data?.database?.status === 'healthy' &&
    (!data?.redis || data.redis.status === 'healthy') &&
    Object.values(data?.services || {}).every((s) => s.status === 'healthy');

  return (
    <div className="bg-white dark:bg-gray-800 rounded-lg shadow">
      {/* Header */}
      <div className="px-6 py-4 border-b border-gray-200 dark:border-gray-700">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Heart className={`w-5 h-5 ${allHealthy ? 'text-green-600' : 'text-yellow-600'}`} />
            <h2 className="text-lg font-semibold text-gray-900 dark:text-white">Dependency Health</h2>
          </div>
          <button
            onClick={() => refetch()}
            disabled={isFetching}
            className="flex items-center gap-2 px-3 py-1.5 text-sm text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white hover:bg-gray-100 dark:hover:bg-gray-700 rounded transition-colors"
          >
            <RefreshCw className={`w-4 h-4 ${isFetching ? 'animate-spin' : ''}`} />
            Refresh
          </button>
        </div>
      </div>

      <div className="p-6">
        {isLoading && !data ? (
          <div className="text-center text-gray-500 dark:text-gray-400 py-4">Loading...</div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {/* Database */}
            {data?.database && (
              <HealthCard
                name="database"
                status={data.database.status}
                latency_ms={data.database.latency_ms}
                error={data.database.error}
              />
            )}

            {/* Redis Cache */}
            {data?.redis && (
              <HealthCard
                name="redis"
                status={data.redis.status}
                latency_ms={data.redis.latency_ms}
                error={data.redis.error}
              />
            )}

            {/* External Services */}
            {data?.services &&
              Object.entries(data.services).map(([name, service]) => (
                <HealthCard
                  key={name}
                  name={name}
                  status={service.status}
                  latency_ms={service.latency_ms}
                  last_check={service.last_check}
                  error={service.error}
                />
              ))}
          </div>
        )}

        {/* Overall Status Summary */}
        {data && (
          <div className="mt-6 pt-4 border-t border-gray-200 dark:border-gray-700">
            <div
              className={`flex items-center justify-center gap-2 py-2 rounded-lg ${
                allHealthy
                  ? 'bg-green-50 dark:bg-green-900/30 text-green-700 dark:text-green-400'
                  : 'bg-yellow-50 dark:bg-yellow-900/30 text-yellow-700 dark:text-yellow-400'
              }`}
            >
              {allHealthy ? (
                <>
                  <CheckCircle className="w-5 h-5" />
                  <span className="font-medium">All systems operational</span>
                </>
              ) : (
                <>
                  <AlertTriangle className="w-5 h-5" />
                  <span className="font-medium">Some systems need attention</span>
                </>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

export default DependencyHealth;
