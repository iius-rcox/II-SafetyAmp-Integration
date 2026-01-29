import { useState } from 'react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import {
  LayoutDashboard,
  Activity,
  AlertTriangle,
  Database,
  History,
  Heart,
  HardDrive,
  GitCompare,
  Bell,
  Download,
  Play,
  ClipboardList,
  Settings,
} from 'lucide-react';
import { ThemeProvider } from './contexts/ThemeContext';
import ThemeToggle from './components/ThemeToggle';
import SyncPauseToggle from './components/SyncPauseToggle';
import ApiCallHistory from './components/ApiCallHistory';
import SyncMetricsChart from './components/SyncMetricsChart';
import ErrorSuggestions from './components/ErrorSuggestions';
import VistaRecordsChart from './components/VistaRecordsChart';
import LiveSyncStatus from './components/LiveSyncStatus';
import DependencyHealth from './components/DependencyHealth';
import FailedRecordsQueue from './components/FailedRecordsQueue';
import CacheMonitor from './components/CacheMonitor';
import SyncDiffViewer from './components/SyncDiffViewer';
import NotificationLog from './components/NotificationLog';
import ConfigStatus from './components/ConfigStatus';
import ExportReports from './components/ExportReports';
import SyncTriggers from './components/SyncTriggers';
import AuditLog from './components/AuditLog';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 2,
      staleTime: 10000,
    },
  },
});

type Tab = 'overview' | 'api-calls' | 'errors' | 'vista' | 'health' | 'failed' | 'cache' | 'diff' | 'notifications' | 'config' | 'export' | 'triggers' | 'audit';

const TABS: { id: Tab; label: string; icon: typeof LayoutDashboard }[] = [
  { id: 'overview', label: 'Overview', icon: LayoutDashboard },
  { id: 'api-calls', label: 'API Calls', icon: History },
  { id: 'errors', label: 'Errors', icon: AlertTriangle },
  { id: 'failed', label: 'Failed Queue', icon: AlertTriangle },
  { id: 'vista', label: 'Vista Data', icon: Database },
  { id: 'cache', label: 'Cache', icon: HardDrive },
  { id: 'diff', label: 'Sync Diff', icon: GitCompare },
  { id: 'triggers', label: 'Sync', icon: Play },
  { id: 'notifications', label: 'Notifications', icon: Bell },
  { id: 'health', label: 'Health', icon: Heart },
  { id: 'config', label: 'Config', icon: Settings },
  { id: 'export', label: 'Export', icon: Download },
  { id: 'audit', label: 'Audit', icon: ClipboardList },
];

function Dashboard() {
  const [activeTab, setActiveTab] = useState<Tab>('overview');

  return (
    <div className="min-h-screen bg-gray-100 dark:bg-gray-900 transition-colors">
      {/* Header */}
      <header className="bg-white dark:bg-gray-800 shadow-sm">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between h-16">
            <div className="flex items-center gap-3">
              <Activity className="w-8 h-8 text-blue-600" />
              <h1 className="text-xl font-bold text-gray-900 dark:text-white">SafetyAmp Integration Dashboard</h1>
            </div>
            <div className="flex items-center gap-4">
              <SyncPauseToggle />
              <span className="text-sm text-gray-500 dark:text-gray-400">
                Auto-refreshing every 30s
              </span>
              <ThemeToggle />
            </div>
          </div>
        </div>
      </header>

      {/* Navigation */}
      <nav className="bg-white dark:bg-gray-800 border-b border-gray-200 dark:border-gray-700 overflow-x-auto">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex space-x-4">
            {TABS.map((tab) => {
              const Icon = tab.icon;
              return (
                <button
                  key={tab.id}
                  onClick={() => setActiveTab(tab.id)}
                  className={`flex items-center gap-2 px-2 py-4 border-b-2 font-medium text-sm transition-colors whitespace-nowrap ${
                    activeTab === tab.id
                      ? 'border-blue-600 text-blue-600 dark:text-blue-400'
                      : 'border-transparent text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-300 hover:border-gray-300'
                  }`}
                >
                  <Icon className="w-4 h-4" />
                  {tab.label}
                </button>
              );
            })}
          </div>
        </div>
      </nav>

      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {activeTab === 'overview' && (
          <div className="space-y-8">
            {/* Top Row: Live Status + Health */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
              <LiveSyncStatus />
              <DependencyHealth />
            </div>

            {/* Sync Metrics Chart */}
            <SyncMetricsChart />

            {/* Error Suggestions (limited view) */}
            <ErrorSuggestions />
          </div>
        )}

        {activeTab === 'api-calls' && (
          <div className="space-y-8">
            <ApiCallHistory />
          </div>
        )}

        {activeTab === 'errors' && (
          <div className="space-y-8">
            <ErrorSuggestions />
          </div>
        )}

        {activeTab === 'failed' && (
          <div className="space-y-8">
            <FailedRecordsQueue />
          </div>
        )}

        {activeTab === 'vista' && (
          <div className="space-y-8">
            <VistaRecordsChart />
          </div>
        )}

        {activeTab === 'cache' && (
          <div className="space-y-8">
            <CacheMonitor />
          </div>
        )}

        {activeTab === 'diff' && (
          <div className="space-y-8">
            <SyncDiffViewer />
          </div>
        )}

        {activeTab === 'triggers' && (
          <div className="space-y-8">
            <SyncTriggers />
            <LiveSyncStatus />
          </div>
        )}

        {activeTab === 'notifications' && (
          <div className="space-y-8">
            <NotificationLog />
          </div>
        )}

        {activeTab === 'health' && (
          <div className="space-y-8">
            <DependencyHealth />
            <LiveSyncStatus />
          </div>
        )}

        {activeTab === 'config' && (
          <div className="space-y-8">
            <ConfigStatus />
          </div>
        )}

        {activeTab === 'export' && (
          <div className="space-y-8">
            <ExportReports />
          </div>
        )}

        {activeTab === 'audit' && (
          <div className="space-y-8">
            <AuditLog />
          </div>
        )}
      </main>

      {/* Footer */}
      <footer className="bg-white dark:bg-gray-800 border-t border-gray-200 dark:border-gray-700 mt-auto">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
          <p className="text-sm text-gray-500 dark:text-gray-400 text-center">
            SafetyAmp Integration Service &middot; Dashboard v2.0
          </p>
        </div>
      </footer>
    </div>
  );
}

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <ThemeProvider>
        <Dashboard />
      </ThemeProvider>
    </QueryClientProvider>
  );
}

export default App;
