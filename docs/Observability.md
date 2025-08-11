# Observability Overview

Blend Managed Prometheus + Grafana for fast metrics with Azure Monitor for logs. Optional Fluent Bit sidecar ships custom JSON files.

## Metrics (Prometheus)
- safetyamp_sync_operations_total, safetyamp_sync_duration_seconds
- safetyamp_records_processed_total
- Recommended: safetyamp_cache_last_updated_timestamp_seconds, safetyamp_cache_items_total
- safetyamp_changes_total, safetyamp_errors_total
- safetyamp_sync_in_progress, safetyamp_last_sync_timestamp_seconds

## Enable Scrape
- Pod annotations:
  - prometheus.io/scrape: "true"
  - prometheus.io/port: "9090"
  - prometheus.io/path: "/metrics"

## Key Panels (PromQL)
- Last Cache Update (minutes):
```promql
(time() - max by (cache) (safetyamp_cache_last_updated_timestamp_seconds)) / 60
```
- Recent Sync Runs (24h):
```promql
sum by (operation, status) (increase(safetyamp_sync_operations_total[24h]))
```
- Errors (24h):
```promql
sum by (error_type, entity_type) (increase(safetyamp_errors_total[24h]))
```

## Azure Monitor (KQL)
Recent Sync Runs (24h):
```kusto
ContainerLogV2
| where TimeGenerated >= ago(24h)
| where ContainerName == "safety-amp-agent"
| extend d=parse_json(LogMessage)
| where isnotempty(d.session_id)
| summarize StartTime=minif(TimeGenerated, d.operation=="sync_start"),
          EndTime=maxif(TimeGenerated, d.operation in ("sync_complete","sync_failed")),
          Status=iff(countif(d.operation=="sync_complete")>0,"Success", iff(countif(d.operation=="sync_failed")>0,"Failed","Running")),
          RecordsProcessed=maxif(todouble(d.metrics.records_processed), d.operation=="sync_complete"),
          DurationSeconds=maxif(todouble(d.metrics.session_duration_seconds), d.operation=="sync_complete")
  by SessionId=tostring(d.session_id), SyncType=tostring(d.sync_type)
| order by StartTime desc
```

## Optional: Fluent Bit Sidecar
- Tail /app/output/changes/*.json and /app/output/errors/error_log.json
- Ship to Log Analytics with workspace credentials injected via Secret

## Alerts
- Cache staleness > 60m
- Error surge over 15m window
- Missing sync beyond cadence
- Long-running syncs (P95)

Refer to in-repo manifests under `deploy/dev/observability` for examples to adapt.