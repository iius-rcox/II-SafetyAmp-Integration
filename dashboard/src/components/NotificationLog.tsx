import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { dashboardApi } from '../services/api';
import { formatRelativeTime } from '../utils/formatters';
import { Bell, RefreshCw, CheckCircle, XCircle, Clock, Filter } from 'lucide-react';
import type { Notification } from '../types/dashboard';

const STATUS_OPTIONS = ['all', 'sent', 'failed', 'pending'];

export function NotificationLog() {
  const [statusFilter, setStatusFilter] = useState<string>('all');

  const { data, isLoading, refetch, isFetching } = useQuery({
    queryKey: ['notifications', statusFilter],
    queryFn: () => dashboardApi.getNotifications({
      limit: 50,
      status: statusFilter === 'all' ? undefined : statusFilter,
    }),
    refetchInterval: 60000,
  });

  const getStatusIcon = (status: Notification['status']) => {
    switch (status) {
      case 'sent':
        return <CheckCircle className="w-4 h-4 text-green-600" />;
      case 'failed':
        return <XCircle className="w-4 h-4 text-red-600" />;
      case 'pending':
        return <Clock className="w-4 h-4 text-yellow-600" />;
      default:
        return null;
    }
  };

  const getStatusBadgeClass = (status: Notification['status']) => {
    switch (status) {
      case 'sent':
        return 'bg-green-100 text-green-800';
      case 'failed':
        return 'bg-red-100 text-red-800';
      case 'pending':
        return 'bg-yellow-100 text-yellow-800';
      default:
        return 'bg-gray-100 text-gray-800';
    }
  };

  return (
    <div className="bg-white dark:bg-gray-800 rounded-lg shadow">
      {/* Header */}
      <div className="px-6 py-4 border-b border-gray-200 dark:border-gray-700">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Bell className="w-5 h-5 text-purple-600" />
            <h2 className="text-lg font-semibold text-gray-900 dark:text-white">Notification Log</h2>
            {data && <span className="text-sm text-gray-500 dark:text-gray-400">({data.total} total)</span>}
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
            <span className="text-sm text-gray-500 dark:text-gray-400">Status:</span>
          </div>
          <div className="flex gap-2">
            {STATUS_OPTIONS.map(status => (
              <button
                key={status}
                onClick={() => setStatusFilter(status)}
                className={`px-3 py-1 text-sm rounded-full transition-colors ${
                  statusFilter === status
                    ? 'bg-purple-600 text-white'
                    : 'bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-600'
                }`}
              >
                {status.charAt(0).toUpperCase() + status.slice(1)}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Notification List */}
      <div className="divide-y divide-gray-200 dark:divide-gray-700">
        {isLoading && !data ? (
          <div className="p-8 text-center text-gray-500 dark:text-gray-400">Loading...</div>
        ) : data?.notifications && data.notifications.length > 0 ? (
          data.notifications.map((notification) => (
            <div key={notification.id} className="px-6 py-4 hover:bg-gray-50 dark:hover:bg-gray-700">
              <div className="flex items-start justify-between">
                <div className="flex items-start gap-3">
                  {getStatusIcon(notification.status)}
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="font-medium text-gray-900 dark:text-white">{notification.type}</span>
                      <span className={`px-2 py-0.5 rounded text-xs font-medium ${getStatusBadgeClass(notification.status)}`}>
                        {notification.status}
                      </span>
                    </div>
                    {notification.subject && (
                      <p className="text-sm text-gray-600 dark:text-gray-400 mt-1">{notification.subject}</p>
                    )}
                    {notification.recipient && (
                      <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">To: {notification.recipient}</p>
                    )}
                    {notification.error && (
                      <p className="text-sm text-red-600 dark:text-red-400 mt-1">{notification.error}</p>
                    )}
                  </div>
                </div>
                <div className="text-right text-sm">
                  <p className="text-gray-500 dark:text-gray-400">{formatRelativeTime(notification.timestamp)}</p>
                  {notification.error_count && notification.error_count > 1 && (
                    <p className="text-red-600 dark:text-red-400">{notification.error_count} errors</p>
                  )}
                </div>
              </div>
            </div>
          ))
        ) : (
          <div className="p-8 text-center text-gray-500 dark:text-gray-400">
            <Bell className="w-12 h-12 mx-auto mb-4 text-gray-300 dark:text-gray-600" />
            <p>No notifications found</p>
          </div>
        )}
      </div>
    </div>
  );
}

export default NotificationLog;
