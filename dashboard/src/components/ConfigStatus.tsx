import { useQuery } from '@tanstack/react-query';
import { dashboardApi } from '../services/api';
import { Settings, RefreshCw, CheckCircle, XCircle, Key, Shield } from 'lucide-react';

export function ConfigStatus() {
  const { data, isLoading, refetch, isFetching } = useQuery({
    queryKey: ['config-status'],
    queryFn: () => dashboardApi.getConfigStatus(),
  });

  const getValidationStatus = () => {
    if (!data?.validation) return null;
    return data.validation.is_valid;
  };

  const isValid = getValidationStatus();

  return (
    <div className="bg-white dark:bg-gray-800 rounded-lg shadow">
      {/* Header */}
      <div className="px-6 py-4 border-b border-gray-200 dark:border-gray-700">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Settings className="w-5 h-5 text-gray-600 dark:text-gray-400" />
            <h2 className="text-lg font-semibold text-gray-900 dark:text-white">Configuration Status</h2>
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

      {/* Content */}
      <div className="p-6">
        {isLoading ? (
          <div className="text-center text-gray-500 dark:text-gray-400">Loading...</div>
        ) : data?.error ? (
          <div className="text-center text-red-600">{data.error}</div>
        ) : (
          <div className="space-y-6">
            {/* Validation Status Banner */}
            <div className={`flex items-center gap-3 p-4 rounded-lg ${
              isValid ? 'bg-green-50 dark:bg-green-900/30' : 'bg-red-50 dark:bg-red-900/30'
            }`}>
              {isValid ? (
                <CheckCircle className="w-5 h-5 text-green-600" />
              ) : (
                <XCircle className="w-5 h-5 text-red-600" />
              )}
              <div>
                <p className={`font-medium ${isValid ? 'text-green-900 dark:text-green-300' : 'text-red-900 dark:text-red-300'}`}>
                  {isValid ? 'Configuration Valid' : 'Configuration Invalid'}
                </p>
                {data?.validation?.missing && data.validation.missing.length > 0 && (
                  <p className="text-sm text-red-600 dark:text-red-400 mt-1">
                    Missing: {data.validation.missing.join(', ')}
                  </p>
                )}
              </div>
            </div>

            {/* Azure Key Vault Status */}
            {data?.azure && (
              <div className="border dark:border-gray-700 rounded-lg p-4">
                <div className="flex items-center gap-2 mb-3">
                  <Key className="w-4 h-4 text-blue-600" />
                  <h3 className="font-medium text-gray-900 dark:text-white">Azure Key Vault</h3>
                </div>
                <div className="space-y-2 text-sm">
                  <div className="flex items-center justify-between">
                    <span className="text-gray-600 dark:text-gray-400">Status</span>
                    <span className={`font-medium ${data.azure.azure_key_vault_enabled ? 'text-green-600' : 'text-gray-500 dark:text-gray-400'}`}>
                      {data.azure.azure_key_vault_enabled ? 'Enabled' : 'Disabled'}
                    </span>
                  </div>
                  {data.azure.key_vault_name && (
                    <div className="flex items-center justify-between">
                      <span className="text-gray-600 dark:text-gray-400">Vault Name</span>
                      <span className="font-mono text-gray-900 dark:text-white">{data.azure.key_vault_name}</span>
                    </div>
                  )}
                </div>
              </div>
            )}

            {/* Present Configuration Keys */}
            {data?.validation?.present && data.validation.present.length > 0 && (
              <div className="border dark:border-gray-700 rounded-lg p-4">
                <div className="flex items-center gap-2 mb-3">
                  <Shield className="w-4 h-4 text-green-600" />
                  <h3 className="font-medium text-gray-900 dark:text-white">Configured Settings</h3>
                  <span className="text-sm text-gray-500 dark:text-gray-400">({data.validation.present.length} keys)</span>
                </div>
                <div className="flex flex-wrap gap-2">
                  {data.validation.present.map((key) => (
                    <span
                      key={key}
                      className="px-2 py-1 bg-green-100 dark:bg-green-900/50 text-green-800 dark:text-green-300 rounded text-xs font-mono"
                    >
                      {key}
                    </span>
                  ))}
                </div>
              </div>
            )}

            {/* Configuration Settings (masked) */}
            {data?.settings && Object.keys(data.settings).length > 0 && (
              <div className="border dark:border-gray-700 rounded-lg p-4">
                <h3 className="font-medium text-gray-900 dark:text-white mb-3">Settings Overview</h3>
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead className="bg-gray-50 dark:bg-gray-700">
                      <tr>
                        <th className="px-4 py-2 text-left font-medium text-gray-500 dark:text-gray-400">Setting</th>
                        <th className="px-4 py-2 text-left font-medium text-gray-500 dark:text-gray-400">Value</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-200 dark:divide-gray-700">
                      {Object.entries(data.settings).map(([key, value]) => (
                        <tr key={key} className="hover:bg-gray-50 dark:hover:bg-gray-700">
                          <td className="px-4 py-2 font-mono text-gray-900 dark:text-white">{key}</td>
                          <td className="px-4 py-2 font-mono text-gray-600 dark:text-gray-400">{value}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

export default ConfigStatus;
