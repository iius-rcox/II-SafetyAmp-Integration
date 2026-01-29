import { useState } from 'react';
import { useMutation } from '@tanstack/react-query';
import { dashboardApi } from '../services/api';
import { Download, FileJson, FileSpreadsheet, Clock } from 'lucide-react';

const REPORT_TYPES = [
  { id: 'api-calls', label: 'API Calls', description: 'Recent API call history' },
  { id: 'sync-metrics', label: 'Sync Metrics', description: 'Sync operation statistics' },
  { id: 'errors', label: 'Error Log', description: 'Error suggestions and details' },
  { id: 'failed-records', label: 'Failed Records', description: 'Failed sync records queue' },
  { id: 'sync-history', label: 'Sync History', description: 'Past sync sessions' },
];

const TIME_RANGES = [
  { value: 24, label: '24 hours' },
  { value: 168, label: '7 days' },
  { value: 720, label: '30 days' },
];

export function ExportReports() {
  const [selectedReport, setSelectedReport] = useState<string>('api-calls');
  const [format, setFormat] = useState<'csv' | 'json'>('json');
  const [hours, setHours] = useState<number>(24);

  const exportMutation = useMutation({
    mutationFn: () => dashboardApi.exportReport(selectedReport, format, hours),
    onSuccess: (blob) => {
      // Create download link
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `${selectedReport}-${new Date().toISOString().split('T')[0]}.${format}`;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);
    },
  });

  return (
    <div className="bg-white dark:bg-gray-800 rounded-lg shadow">
      {/* Header */}
      <div className="px-6 py-4 border-b border-gray-200 dark:border-gray-700">
        <div className="flex items-center gap-3">
          <Download className="w-5 h-5 text-emerald-600" />
          <h2 className="text-lg font-semibold text-gray-900 dark:text-white">Export Reports</h2>
        </div>
      </div>

      {/* Content */}
      <div className="p-6">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {/* Report Type Selection */}
          <div>
            <h3 className="font-medium text-gray-900 dark:text-white mb-3">Select Report</h3>
            <div className="space-y-2">
              {REPORT_TYPES.map((report) => (
                <label
                  key={report.id}
                  className={`flex items-start gap-3 p-3 rounded-lg border cursor-pointer transition-colors ${
                    selectedReport === report.id
                      ? 'border-emerald-500 bg-emerald-50 dark:bg-emerald-900/30'
                      : 'border-gray-200 dark:border-gray-600 hover:border-gray-300 dark:hover:border-gray-500'
                  }`}
                >
                  <input
                    type="radio"
                    name="reportType"
                    value={report.id}
                    checked={selectedReport === report.id}
                    onChange={(e) => setSelectedReport(e.target.value)}
                    className="mt-1"
                  />
                  <div>
                    <p className="font-medium text-gray-900 dark:text-white">{report.label}</p>
                    <p className="text-sm text-gray-500 dark:text-gray-400">{report.description}</p>
                  </div>
                </label>
              ))}
            </div>
          </div>

          {/* Options */}
          <div className="space-y-6">
            {/* Format Selection */}
            <div>
              <h3 className="font-medium text-gray-900 dark:text-white mb-3">Format</h3>
              <div className="flex gap-4">
                <label
                  className={`flex items-center gap-3 px-4 py-3 rounded-lg border cursor-pointer transition-colors ${
                    format === 'json'
                      ? 'border-emerald-500 bg-emerald-50 dark:bg-emerald-900/30'
                      : 'border-gray-200 dark:border-gray-600 hover:border-gray-300 dark:hover:border-gray-500'
                  }`}
                >
                  <input
                    type="radio"
                    name="format"
                    value="json"
                    checked={format === 'json'}
                    onChange={() => setFormat('json')}
                  />
                  <FileJson className="w-5 h-5 text-yellow-600" />
                  <span className="font-medium dark:text-white">JSON</span>
                </label>
                <label
                  className={`flex items-center gap-3 px-4 py-3 rounded-lg border cursor-pointer transition-colors ${
                    format === 'csv'
                      ? 'border-emerald-500 bg-emerald-50 dark:bg-emerald-900/30'
                      : 'border-gray-200 dark:border-gray-600 hover:border-gray-300 dark:hover:border-gray-500'
                  }`}
                >
                  <input
                    type="radio"
                    name="format"
                    value="csv"
                    checked={format === 'csv'}
                    onChange={() => setFormat('csv')}
                  />
                  <FileSpreadsheet className="w-5 h-5 text-green-600" />
                  <span className="font-medium dark:text-white">CSV</span>
                </label>
              </div>
            </div>

            {/* Time Range */}
            <div>
              <h3 className="font-medium text-gray-900 dark:text-white mb-3">
                <Clock className="w-4 h-4 inline mr-2" />
                Time Range
              </h3>
              <div className="flex gap-2">
                {TIME_RANGES.map((range) => (
                  <button
                    key={range.value}
                    onClick={() => setHours(range.value)}
                    className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                      hours === range.value
                        ? 'bg-emerald-600 text-white'
                        : 'bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-600'
                    }`}
                  >
                    {range.label}
                  </button>
                ))}
              </div>
            </div>

            {/* Export Button */}
            <div className="pt-4">
              <button
                onClick={() => exportMutation.mutate()}
                disabled={exportMutation.isPending}
                className="w-full flex items-center justify-center gap-2 px-6 py-3 bg-emerald-600 text-white rounded-lg hover:bg-emerald-700 disabled:opacity-50 transition-colors"
              >
                <Download className={`w-5 h-5 ${exportMutation.isPending ? 'animate-bounce' : ''}`} />
                {exportMutation.isPending ? 'Generating...' : 'Download Report'}
              </button>
              {exportMutation.isError && (
                <p className="text-sm text-red-600 mt-2 text-center">
                  Failed to generate report. Please try again.
                </p>
              )}
              {exportMutation.isSuccess && (
                <p className="text-sm text-green-600 mt-2 text-center">
                  Report downloaded successfully!
                </p>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

export default ExportReports;
