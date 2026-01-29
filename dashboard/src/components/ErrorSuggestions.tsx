import { useState } from 'react';
import { useErrorSuggestions } from '../hooks/useDashboardData';
import { formatRelativeTime, getSeverityColor } from '../utils/formatters';
import { AlertTriangle, AlertCircle, Info, ChevronDown, ChevronUp, RefreshCw, Lightbulb, Copy, Users, Zap, Link2, FileWarning } from 'lucide-react';
import type { ErrorSuggestion, ErrorCategory } from '../types/dashboard';

const CATEGORY_ICONS: Record<ErrorCategory, typeof AlertTriangle> = {
  duplicate_field: Users,
  missing_field: FileWarning,
  rate_limit: Zap,
  validation: AlertCircle,
  connectivity: Link2,
};

const SEVERITY_ICONS = {
  high: AlertTriangle,
  medium: AlertCircle,
  low: Info,
};

function SuggestionCard({ suggestion }: { suggestion: ErrorSuggestion }) {
  const [expanded, setExpanded] = useState(false);
  const SeverityIcon = SEVERITY_ICONS[suggestion.severity];
  const CategoryIcon = CATEGORY_ICONS[suggestion.category] || AlertCircle;

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text);
  };

  return (
    <div className={`rounded-lg border p-4 ${getSeverityColor(suggestion.severity)}`}>
      <div className="flex items-start gap-3">
        <div className="flex-shrink-0 mt-0.5">
          <SeverityIcon className="w-5 h-5" />
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <h3 className="font-medium">{suggestion.title}</h3>
            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs bg-white/50">
              <CategoryIcon className="w-3 h-3" />
              {suggestion.category.replace('_', ' ')}
            </span>
          </div>
          <p className="text-sm opacity-90">{suggestion.description}</p>

          <div className="mt-3 flex items-center gap-4 text-xs opacity-75">
            <span>{suggestion.occurrence_count} occurrences</span>
            <span>First seen {formatRelativeTime(suggestion.first_seen)}</span>
            <span>{suggestion.affected_records.length} records affected</span>
          </div>

          <button
            onClick={() => setExpanded(!expanded)}
            className="mt-2 flex items-center gap-1 text-sm hover:opacity-75 transition-opacity"
          >
            {expanded ? (
              <>
                <ChevronUp className="w-4 h-4" /> Hide details
              </>
            ) : (
              <>
                <ChevronDown className="w-4 h-4" /> Show details
              </>
            )}
          </button>

          <div
            className={`grid transition-all duration-200 ease-in-out ${
              expanded ? 'grid-rows-[1fr]' : 'grid-rows-[0fr]'
            }`}
          >
            <div className="overflow-hidden">
              <div className="mt-3 pt-3 border-t border-current/20 space-y-3">
                {/* Recommended Action */}
                <div className="bg-white/30 rounded p-3">
                  <div className="flex items-center gap-2 mb-1">
                    <Lightbulb className="w-4 h-4" />
                    <span className="text-sm font-medium">Recommended Action</span>
                  </div>
                  <p className="text-sm">{suggestion.recommended_action}</p>
                </div>

                {/* Affected Records */}
                {suggestion.affected_records.length > 0 && (
                  <div>
                    <div className="flex items-center justify-between mb-2">
                      <span className="text-sm font-medium">Affected Records ({suggestion.affected_records.length})</span>
                      <button
                        onClick={() => copyToClipboard(suggestion.affected_records.join(', '))}
                        className="text-xs flex items-center gap-1 hover:opacity-75"
                      >
                        <Copy className="w-3 h-3" /> Copy IDs
                      </button>
                    </div>
                    <div className="flex flex-wrap gap-1">
                      {suggestion.affected_records.slice(0, 10).map((id) => (
                        <span key={id} className="inline-block px-2 py-0.5 text-xs bg-white/50 rounded font-mono">
                          {id}
                        </span>
                      ))}
                      {suggestion.affected_records.length > 10 && (
                        <span className="inline-block px-2 py-0.5 text-xs bg-white/30 rounded">
                          +{suggestion.affected_records.length - 10} more
                        </span>
                      )}
                    </div>
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

export function ErrorSuggestions() {
  const [hours, setHours] = useState(24);
  const { data, isLoading, error, refetch, isFetching } = useErrorSuggestions(hours);

  if (error) {
    return (
      <div className="bg-white dark:bg-gray-800 rounded-lg shadow p-6">
        <div className="text-red-600">Failed to load error suggestions: {String(error)}</div>
      </div>
    );
  }

  const highCount = data?.suggestions.filter(s => s.severity === 'high').length || 0;
  const mediumCount = data?.suggestions.filter(s => s.severity === 'medium').length || 0;
  const lowCount = data?.suggestions.filter(s => s.severity === 'low').length || 0;

  return (
    <div className="bg-white dark:bg-gray-800 rounded-lg shadow">
      {/* Header */}
      <div className="px-6 py-4 border-b border-gray-200 dark:border-gray-700">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Lightbulb className="w-5 h-5 text-yellow-600" />
            <h2 className="text-lg font-semibold text-gray-900 dark:text-white">Error Suggestions</h2>
          </div>
          <div className="flex items-center gap-3">
            <select
              value={hours}
              onChange={(e) => setHours(Number(e.target.value))}
              className="text-sm border border-gray-300 dark:border-gray-600 dark:bg-gray-700 dark:text-white rounded px-2 py-1.5 focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              <option value={6}>Last 6 hours</option>
              <option value={24}>Last 24 hours</option>
              <option value={72}>Last 3 days</option>
              <option value={168}>Last 7 days</option>
            </select>
            <button
              onClick={() => refetch()}
              disabled={isFetching}
              className="flex items-center gap-2 px-3 py-1.5 text-sm text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white hover:bg-gray-100 dark:hover:bg-gray-700 rounded transition-colors"
            >
              <RefreshCw className={`w-4 h-4 ${isFetching ? 'animate-spin' : ''}`} />
            </button>
          </div>
        </div>

        {/* Summary */}
        <div className="mt-4 flex items-center gap-6 text-sm">
          <span className="text-gray-500 dark:text-gray-400">
            {data?.total || 0} suggestions found
          </span>
          {highCount > 0 && (
            <span className="flex items-center gap-1 text-red-600">
              <AlertTriangle className="w-4 h-4" /> {highCount} high
            </span>
          )}
          {mediumCount > 0 && (
            <span className="flex items-center gap-1 text-yellow-600">
              <AlertCircle className="w-4 h-4" /> {mediumCount} medium
            </span>
          )}
          {lowCount > 0 && (
            <span className="flex items-center gap-1 text-blue-600">
              <Info className="w-4 h-4" /> {lowCount} low
            </span>
          )}
        </div>
      </div>

      {/* Suggestions List */}
      <div className="p-6">
        {isLoading && !data ? (
          <div className="text-center text-gray-500 dark:text-gray-400 py-8">Loading...</div>
        ) : data?.suggestions && data.suggestions.length > 0 ? (
          <div className="space-y-4">
            {/* High severity first, then medium, then low */}
            {data.suggestions
              .sort((a, b) => {
                const order = { high: 0, medium: 1, low: 2 };
                return order[a.severity] - order[b.severity];
              })
              .map((suggestion) => (
                <SuggestionCard key={suggestion.id} suggestion={suggestion} />
              ))}
          </div>
        ) : (
          <div className="text-center py-12">
            <div className="inline-flex items-center justify-center w-16 h-16 rounded-full bg-green-100 dark:bg-green-900/30 mb-4">
              <Lightbulb className="w-8 h-8 text-green-600" />
            </div>
            <p className="text-gray-600 dark:text-gray-300 font-medium">No issues detected</p>
            <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">All systems are running smoothly</p>
          </div>
        )}
      </div>
    </div>
  );
}

export default ErrorSuggestions;
