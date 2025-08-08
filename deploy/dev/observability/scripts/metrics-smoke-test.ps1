#!/usr/bin/env pwsh
param(
  [string]$MetricsUrl = "http://localhost:8080/metrics"
)

Write-Host "🔍 Metrics smoke test: $MetricsUrl"
try {
  $resp = (Invoke-WebRequest -UseBasicParsing -Uri $MetricsUrl -TimeoutSec 5).Content
} catch {
  Write-Error "Failed to fetch metrics: $($_.Exception.Message)"; exit 1
}

$names = @(
  'safetyamp_sync_in_progress',
  'safetyamp_last_sync_timestamp_seconds',
  'safetyamp_changes_total',
  'safetyamp_errors_total',
  'safetyamp_cache_last_updated_timestamp_seconds',
  'safetyamp_cache_items_total'
)

$missing = @()
foreach ($n in $names) {
  if (-not ($resp -match [regex]::Escape($n))) { $missing += $n }
}

if ($missing.Count -gt 0) {
  Write-Error "❌ Missing expected metrics: $($missing -join ', ')"; exit 2
}

Write-Host "✅ All expected metrics present" -ForegroundColor Green
