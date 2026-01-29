import { useState, useEffect } from 'react';
import { Pause, Play, Loader2, AlertCircle } from 'lucide-react';
import { useSyncPause, useSyncPauseMutation } from '../hooks/useDashboardData';

function formatTimestamp(timestamp: number | null): string {
  if (!timestamp) return '';
  const date = new Date(timestamp * 1000);
  return date.toLocaleString();
}

export default function SyncPauseToggle() {
  const { data: pauseState, isLoading, isError } = useSyncPause();
  const mutation = useSyncPauseMutation();
  const [showConfirm, setShowConfirm] = useState(false);
  const [showError, setShowError] = useState(false);

  const isPaused = pauseState?.paused ?? false;
  const isToggling = mutation.isPending;

  // Show error message when mutation fails
  useEffect(() => {
    if (mutation.isError) {
      setShowError(true);
      // Auto-hide error after 5 seconds
      const timer = setTimeout(() => setShowError(false), 5000);
      return () => clearTimeout(timer);
    }
  }, [mutation.isError]);

  const handleToggle = () => {
    if (isPaused) {
      // Resume immediately without confirmation
      mutation.mutate(false);
    } else {
      // Show confirmation before pausing
      setShowConfirm(true);
    }
  };

  const handleConfirmPause = () => {
    mutation.mutate(true);
    setShowConfirm(false);
  };

  const handleCancelPause = () => {
    setShowConfirm(false);
  };

  // Only show loading skeleton on initial load (no cached data yet)
  if (isLoading && !pauseState) {
    return (
      <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-gray-100 dark:bg-gray-700">
        <Loader2 className="w-4 h-4 animate-spin text-gray-500" />
        <span className="text-sm text-gray-500 dark:text-gray-400">Loading...</span>
      </div>
    );
  }

  if (isError) {
    return (
      <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-red-50 dark:bg-red-900/20">
        <span className="text-sm text-red-600 dark:text-red-400">Sync status unavailable</span>
      </div>
    );
  }

  return (
    <div className="relative">
      {/* Main Toggle Button */}
      <button
        onClick={handleToggle}
        disabled={isToggling}
        className={`flex items-center gap-2 px-4 py-2 rounded-lg font-medium text-sm transition-all ${
          isPaused
            ? 'bg-yellow-100 dark:bg-yellow-900/30 text-yellow-700 dark:text-yellow-400 hover:bg-yellow-200 dark:hover:bg-yellow-900/50 border border-yellow-300 dark:border-yellow-700'
            : 'bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-400 hover:bg-green-200 dark:hover:bg-green-900/50 border border-green-300 dark:border-green-700'
        } ${isToggling ? 'opacity-75 cursor-not-allowed' : ''}`}
        title={isPaused
          ? `Paused by ${pauseState?.paused_by || 'unknown'} at ${formatTimestamp(pauseState?.paused_at ?? null)}`
          : 'Click to pause sync operations'
        }
      >
        {isToggling ? (
          <Loader2 className="w-4 h-4 animate-spin" />
        ) : isPaused ? (
          <Play className="w-4 h-4" />
        ) : (
          <Pause className="w-4 h-4" />
        )}
        <span>
          {isToggling
            ? (isPaused ? 'Resuming...' : 'Pausing...')
            : (isPaused ? 'Resume Sync' : 'Pause Sync')
          }
        </span>
      </button>

      {/* Confirmation Dialog */}
      {showConfirm && (
        <div className="absolute right-0 top-full mt-2 z-50">
          <div className="bg-white dark:bg-gray-800 rounded-lg shadow-lg border border-gray-200 dark:border-gray-700 p-4 w-72">
            <h4 className="font-medium text-gray-900 dark:text-white mb-2">
              Pause Sync Operations?
            </h4>
            <p className="text-sm text-gray-600 dark:text-gray-400 mb-4">
              This will stop all sync operations until resumed. Data will not be synchronized with SafetyAmp while paused.
            </p>
            <div className="flex justify-end gap-2">
              <button
                onClick={handleCancelPause}
                className="px-3 py-1.5 text-sm font-medium text-gray-700 dark:text-gray-300 bg-gray-100 dark:bg-gray-700 rounded hover:bg-gray-200 dark:hover:bg-gray-600 transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={handleConfirmPause}
                className="px-3 py-1.5 text-sm font-medium text-white bg-yellow-600 rounded hover:bg-yellow-700 transition-colors"
              >
                Pause Sync
              </button>
            </div>
          </div>
          {/* Backdrop */}
          <div
            className="fixed inset-0 -z-10"
            onClick={handleCancelPause}
          />
        </div>
      )}

      {/* Paused Status Indicator */}
      {isPaused && pauseState?.paused_by && !showError && (
        <div className="absolute right-0 top-full mt-1 text-xs text-yellow-600 dark:text-yellow-400 whitespace-nowrap">
          Paused by {pauseState.paused_by}
        </div>
      )}

      {/* Error Message */}
      {showError && mutation.error && (
        <div className="absolute right-0 top-full mt-2 z-50">
          <div className="flex items-center gap-2 px-3 py-2 bg-red-50 dark:bg-red-900/30 border border-red-200 dark:border-red-800 rounded-lg text-sm text-red-700 dark:text-red-400 shadow-lg">
            <AlertCircle className="w-4 h-4 flex-shrink-0" />
            <span>
              {(mutation.error as Error).message?.includes('429')
                ? 'Rate limit exceeded. Please wait.'
                : 'Failed to update sync state. Please try again.'}
            </span>
            <button
              onClick={() => setShowError(false)}
              className="ml-2 text-red-500 hover:text-red-700 dark:hover:text-red-300"
            >
              ×
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
