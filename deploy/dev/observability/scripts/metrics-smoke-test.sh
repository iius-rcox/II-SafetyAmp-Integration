#!/usr/bin/env bash
set -euo pipefail
METRICS_URL=${1:-http://localhost:8080/metrics}
echo "🔍 Metrics smoke test: $METRICS_URL"
CONTENT=$(curl -fsS "$METRICS_URL")
MISSING=()
for n in \
  safetyamp_sync_in_progress \
  safetyamp_last_sync_timestamp_seconds \
  safetyamp_changes_total \
  safetyamp_errors_total \
  safetyamp_cache_last_updated_timestamp_seconds \
  safetyamp_cache_items_total; do
  if ! grep -q "$n" <<<"$CONTENT"; then MISSING+=("$n"); fi
done
if (( ${#MISSING[@]} > 0 )); then
  echo "❌ Missing expected metrics: ${MISSING[*]}" >&2; exit 2
fi
echo "✅ All expected metrics present"
