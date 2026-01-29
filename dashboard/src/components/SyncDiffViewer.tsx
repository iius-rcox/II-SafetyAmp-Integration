import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { dashboardApi } from '../services/api';
import { GitCompare, Search, CheckCircle, AlertTriangle, XCircle, Minus } from 'lucide-react';

const ENTITY_TYPES = ['employee', 'vehicle', 'department', 'job', 'title'];

export function SyncDiffViewer() {
  const [entityType, setEntityType] = useState<string>('employee');
  const [entityId, setEntityId] = useState<string>('');
  const [searchId, setSearchId] = useState<string>('');

  const { data, isLoading, error } = useQuery({
    queryKey: ['sync-diff', entityType, searchId],
    queryFn: () => dashboardApi.getSyncDiff(entityType, searchId),
    enabled: !!searchId,
  });

  const handleSearch = () => {
    if (entityId.trim()) {
      setSearchId(entityId.trim());
    }
  };

  const getStatusIcon = (status?: string) => {
    switch (status) {
      case 'in_sync':
        return <CheckCircle className="w-5 h-5 text-green-600" />;
      case 'different':
        return <AlertTriangle className="w-5 h-5 text-yellow-600" />;
      case 'source_missing':
      case 'target_missing':
        return <XCircle className="w-5 h-5 text-red-600" />;
      default:
        return <Minus className="w-5 h-5 text-gray-400" />;
    }
  };

  const getStatusText = (status?: string) => {
    switch (status) {
      case 'in_sync': return 'In Sync';
      case 'different': return 'Has Differences';
      case 'source_missing': return 'Missing in Source (Viewpoint)';
      case 'target_missing': return 'Missing in Target (SafetyAmp)';
      case 'both_missing': return 'Not Found';
      default: return 'Unknown';
    }
  };

  return (
    <div className="bg-white dark:bg-gray-800 rounded-lg shadow">
      {/* Header */}
      <div className="px-6 py-4 border-b border-gray-200 dark:border-gray-700">
        <div className="flex items-center gap-3 mb-4">
          <GitCompare className="w-5 h-5 text-indigo-600" />
          <h2 className="text-lg font-semibold text-gray-900 dark:text-white">Sync Diff Viewer</h2>
        </div>

        {/* Search */}
        <div className="flex items-center gap-4">
          <select
            value={entityType}
            onChange={(e) => setEntityType(e.target.value)}
            className="text-sm border border-gray-300 dark:border-gray-600 dark:bg-gray-700 dark:text-white rounded px-3 py-2 focus:outline-none focus:ring-2 focus:ring-indigo-500"
          >
            {ENTITY_TYPES.map(type => (
              <option key={type} value={type}>{type.charAt(0).toUpperCase() + type.slice(1)}</option>
            ))}
          </select>
          <div className="flex-1 flex items-center gap-2">
            <input
              type="text"
              value={entityId}
              onChange={(e) => setEntityId(e.target.value)}
              onKeyPress={(e) => e.key === 'Enter' && handleSearch()}
              placeholder={`Enter ${entityType} ID...`}
              className="flex-1 text-sm border border-gray-300 dark:border-gray-600 dark:bg-gray-700 dark:text-white dark:placeholder-gray-400 rounded px-3 py-2 focus:outline-none focus:ring-2 focus:ring-indigo-500"
            />
            <button
              onClick={handleSearch}
              disabled={!entityId.trim() || isLoading}
              className="flex items-center gap-2 px-4 py-2 bg-indigo-600 text-white rounded hover:bg-indigo-700 disabled:opacity-50 transition-colors"
            >
              <Search className="w-4 h-4" />
              Compare
            </button>
          </div>
        </div>
      </div>

      {/* Results */}
      <div className="p-6">
        {isLoading ? (
          <div className="text-center text-gray-500 dark:text-gray-400 py-8">Loading...</div>
        ) : error ? (
          <div className="text-center text-red-600 dark:text-red-400 py-8">Error loading diff</div>
        ) : data ? (
          <div className="space-y-6">
            {/* Status Banner */}
            <div className={`flex items-center gap-3 p-4 rounded-lg ${
              data.diff?.status === 'in_sync' ? 'bg-green-50 dark:bg-green-900/30' :
              data.diff?.status === 'different' ? 'bg-yellow-50 dark:bg-yellow-900/30' :
              'bg-red-50 dark:bg-red-900/30'
            }`}>
              {getStatusIcon(data.diff?.status)}
              <div>
                <p className="font-medium dark:text-white">{getStatusText(data.diff?.status)}</p>
                {data.diff?.changed_fields && (
                  <p className="text-sm text-gray-600 dark:text-gray-400">
                    {data.diff.changed_fields.length} field(s) different
                  </p>
                )}
              </div>
            </div>

            {/* Changed Fields */}
            {data.diff?.changed_fields && data.diff.changed_fields.length > 0 && (
              <div>
                <h3 className="font-medium text-gray-900 dark:text-white mb-3">Changed Fields</h3>
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead className="bg-gray-50 dark:bg-gray-700">
                      <tr>
                        <th className="px-4 py-2 text-left font-medium text-gray-500 dark:text-gray-400">Field</th>
                        <th className="px-4 py-2 text-left font-medium text-gray-500 dark:text-gray-400">Source (Viewpoint)</th>
                        <th className="px-4 py-2 text-left font-medium text-gray-500 dark:text-gray-400">Target (SafetyAmp)</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-200 dark:divide-gray-700">
                      {data.diff.changed_fields.map((field, idx) => (
                        <tr key={idx} className="hover:bg-gray-50 dark:hover:bg-gray-700">
                          <td className="px-4 py-2 font-mono text-gray-900 dark:text-white">{field.field}</td>
                          <td className="px-4 py-2">
                            <span className="bg-green-100 dark:bg-green-900/50 text-green-800 dark:text-green-300 px-2 py-0.5 rounded text-xs font-mono">
                              {JSON.stringify(field.source_value)}
                            </span>
                          </td>
                          <td className="px-4 py-2">
                            <span className="bg-red-100 dark:bg-red-900/50 text-red-800 dark:text-red-300 px-2 py-0.5 rounded text-xs font-mono">
                              {JSON.stringify(field.target_value)}
                            </span>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}

            {/* Full Data View */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              {/* Source Data */}
              <div>
                <h3 className="font-medium text-gray-900 dark:text-white mb-2">Source Data (Viewpoint)</h3>
                <pre className="bg-gray-50 dark:bg-gray-700 dark:text-gray-300 p-4 rounded-lg text-xs font-mono overflow-auto max-h-80">
                  {data.source_data ? JSON.stringify(data.source_data, null, 2) : 'No data'}
                </pre>
              </div>

              {/* Target Data */}
              <div>
                <h3 className="font-medium text-gray-900 dark:text-white mb-2">Target Data (SafetyAmp)</h3>
                <pre className="bg-gray-50 dark:bg-gray-700 dark:text-gray-300 p-4 rounded-lg text-xs font-mono overflow-auto max-h-80">
                  {data.target_data ? JSON.stringify(data.target_data, null, 2) : 'No data'}
                </pre>
              </div>
            </div>
          </div>
        ) : (
          <div className="text-center text-gray-500 dark:text-gray-400 py-12">
            <GitCompare className="w-12 h-12 mx-auto mb-4 text-gray-300 dark:text-gray-600" />
            <p>Enter an entity ID to compare source and target data</p>
          </div>
        )}
      </div>
    </div>
  );
}

export default SyncDiffViewer;
