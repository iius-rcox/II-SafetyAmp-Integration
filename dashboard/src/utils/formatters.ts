import { format, formatDistanceToNow, parseISO } from 'date-fns';

export function formatDateTime(dateString: string): string {
  try {
    const date = parseISO(dateString);
    return format(date, 'MMM d, yyyy HH:mm:ss');
  } catch {
    return dateString;
  }
}

export function formatRelativeTime(dateString: string): string {
  try {
    const date = parseISO(dateString);
    return formatDistanceToNow(date, { addSuffix: true });
  } catch {
    return dateString;
  }
}

export function formatDuration(ms: number): string {
  if (ms < 1000) return `${Math.round(ms)}ms`;
  if (ms < 60000) return `${(ms / 1000).toFixed(1)}s`;
  return `${(ms / 60000).toFixed(1)}m`;
}

export function formatNumber(num: number): string {
  return new Intl.NumberFormat().format(num);
}

export function formatPercent(value: number, decimals = 1): string {
  return `${value.toFixed(decimals)}%`;
}

export function getStatusColor(statusCode: number): string {
  if (statusCode >= 200 && statusCode < 300) return 'text-green-600';
  if (statusCode >= 300 && statusCode < 400) return 'text-blue-600';
  if (statusCode >= 400 && statusCode < 500) return 'text-yellow-600';
  return 'text-red-600';
}

export function getStatusBgColor(statusCode: number): string {
  if (statusCode >= 200 && statusCode < 300) return 'bg-green-100';
  if (statusCode >= 300 && statusCode < 400) return 'bg-blue-100';
  if (statusCode >= 400 && statusCode < 500) return 'bg-yellow-100';
  return 'bg-red-100';
}

export function getSeverityColor(severity: string): string {
  switch (severity) {
    case 'high': return 'text-red-600 bg-red-100 border-red-200';
    case 'medium': return 'text-yellow-600 bg-yellow-100 border-yellow-200';
    case 'low': return 'text-blue-600 bg-blue-100 border-blue-200';
    default: return 'text-gray-600 bg-gray-100 border-gray-200';
  }
}

export function getHealthStatusColor(status: string): string {
  switch (status) {
    case 'healthy': return 'text-green-600 bg-green-100';
    case 'degraded': return 'text-yellow-600 bg-yellow-100';
    case 'unhealthy': return 'text-red-600 bg-red-100';
    default: return 'text-gray-600 bg-gray-100';
  }
}
