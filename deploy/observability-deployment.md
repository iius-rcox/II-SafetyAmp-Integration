# SafetyAmp Observability Deployment Plan (AKS)

This document memorializes a hybrid, production-ready observability strategy that combines:
- Managed Prometheus + Managed Grafana on AKS for near real-time metrics and alerting
- Azure Monitor (Container Insights + Log Analytics Workbooks) for structured logs, drill-down, governance, and sharing

Targets the following widgets:
- Last Cache Update
- Recent Sync Runs
- Recent Changes (Last 24h) with counts and details
- Recent Errors (Last 24h) with counts by type/category

---

## 1) Architecture Overview

- Metrics path (seconds-level):
  - App exposes `/metrics` → Managed Prometheus scrapes → Managed Grafana dashboards + alerts
- Logs path (1–2 min latency):
  - App emits structured JSON to stdout
  - Optional: ship `output/changes/*.json` and `output/errors/error_log.json` via Fluent Bit sidecar as custom logs
  - Container Insights forwards to Log Analytics → Workbooks + Azure Monitor alerts

Notes:
- AKS namespace: `safety-amp`
- Service ports: `8080` health, `9090` metrics (already defined)
- Pod annotations for Prometheus scraping already present in `k8s/safety-amp/safety-amp-deployment.yaml`

---

## 2) Prerequisites

- AKS cluster and `safety-amp` namespace deployed
- ACR access for app images
- Azure RBAC to enable:
  - Azure Managed Prometheus + Azure Managed Grafana
  - Container Insights (AKS monitoring add-on) + Log Analytics Workspace
- NetworkPolicy permits metrics scrape to `:9090` and health access to `:8080`

---

## 3) Metrics Specification (Prometheus)


- Counter: `safetyamp_sync_operations_total{operation="employees|departments|jobs|titles|vehicles",status="success|error"}`
- Histogram: `safetyamp_sync_duration_seconds{operation=...}` (+ `_bucket/_sum/_count`)
- Counter: `safetyamp_records_processed_total{sync_type=...}`
- Gauge: `safetyamp_cache_last_updated_timestamp_seconds{cache="users|sites|titles|..."}`
- Gauge: `safetyamp_cache_items_total{cache=...}`
- Optional Gauge: `safetyamp_cache_ttl_seconds{cache=...}`
- Counter: `safetyamp_changes_total{entity_type="employee|asset|site|title|...",operation="created|updated|deleted|skipped",status="success|error"}`
- Counter: `safetyamp_errors_total{error_type,entity_type,source}`
- Gauge: `safetyamp_sync_in_progress` (0/1)
- Gauge: `safetyamp_last_sync_timestamp_seconds`

Guidance:
- Keep label sets low-cardinality (no IDs)
- Timestamps as epoch seconds

---

## 4) Structured Logging Specification (Azure Monitor)

Emit structured JSON logs to stdout (and optionally to files) with these fields:
- `timestamp`, `level`, `logger`, `message`
- `sync_type`, `session_id`, `operation` in {`sync_start`|`sync_complete`|`sync_failed`}
- `entity_type`, `action` in {`created`|`updated`|`deleted`|`skipped`}
- `metrics` (object): counts, durations, sizes
- `error_type`, `error_details`

Example:
```json
{"timestamp":"2025-08-08T16:32:15Z","level":"INFO","logger":"sync_employees","message":"sync_run","sync_type":"employees","operation":"sync_complete","metrics":{"session_duration_seconds":135.2,"records_processed":1200,"records_created":42,"records_updated":118,"records_errors":3}}
```

Optional: retain session detail JSON files in `output/changes/*.json` and errors in `output/errors/error_log.json` for ingestion via Fluent Bit.

---

## 5) AKS Scraping and Log Shipping

### 5.1 Prometheus Scrape (Managed)

- Ensure annotations on the pod (already present):
  - `prometheus.io/scrape: "true"`
  - `prometheus.io/port: "9090"`
  - `prometheus.io/path: "/metrics"`
- Ensure NetworkPolicy allows collectors from the monitoring namespace to reach `:9090`

Validation:
- In Grafana Explore, query `safetyamp_sync_operations_total` to validate ingestion

### 5.2 Container Insights + Log Analytics

- Enable Container Insights add-on for AKS
- Link to a Log Analytics Workspace
- Retention: set 30–90 days per cost envelope

### 5.3 Fluent Bit Sidecar (optional)

Use a sidecar to ship custom JSON files (`output/changes`, `output/errors`) to Log Analytics.

ConfigMap example (abbreviated):
```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: fluentbit-config
  namespace: safety-amp
data:
  fluent-bit.conf: |
    [SERVICE]
        Flush         1
        Log_Level     info
        Parsers_File  parsers.conf
    [INPUT]
        Name   tail
        Path   /app/output/changes/*.json
        Parser json
        Tag    safetyamp.changes
    [INPUT]
        Name   tail
        Path   /app/output/errors/error_log.json
        Parser json
        Tag    safetyamp.errors
    [FILTER]
        Name modify
        Match safetyamp.*
        Add source safetyamp-integration
        Add namespace safety-amp
    [OUTPUT]
        Name        azure
        Match       safetyamp.*
        Customer_ID ${WORKSPACE_ID}
        Shared_Key  ${WORKSPACE_KEY}
        Log_Type    SafetyAmpCustom
  parsers.conf: |
    [PARSER]
      Name        json
      Format      json
      Time_Key    timestamp
      Time_Format %Y-%m-%dT%H:%M:%S.%L%z
```

Mount the volumes and sidecar container in the deployment; inject workspace credentials from a Secret (`log-analytics-secrets`).

---

## 6) Managed Grafana Dashboards (PromQL)

Create a dashboard “SafetyAmp Sync Overview” with the following panels.

- Last Cache Update (per cache)
```promql
(time() - max by (cache) (safetyamp_cache_last_updated_timestamp_seconds)) / 60
```
Stat; thresholds: warn > 60m, critical > 240m

- Cache Items (per cache)
```promql
max by (cache) (safetyamp_cache_items_total)
```

- Recent Sync Runs (24h) by operation/status
```promql
sum by (operation, status) (increase(safetyamp_sync_operations_total[24h]))
```

- Sync Duration (P95) by operation
```promql
histogram_quantile(0.95, sum by (le, operation) (rate(safetyamp_sync_duration_seconds_bucket[15m])))
```

- Changes (Last 24h) by entity_type/operation
```promql
sum by (entity_type, operation) (increase(safetyamp_changes_total[24h]))
```

- Errors (Last 24h) by error_type/entity_type
```promql
sum by (error_type, entity_type) (increase(safetyamp_errors_total[24h]))
```

- Current Sync State
```promql
max(safetyamp_sync_in_progress)
```
```promql
(time() - max(safetyamp_last_sync_timestamp_seconds)) / 60
```

---

## 7) Azure Monitor Workbooks (KQL)

Use `ContainerLogV2` (stdout) and/or a custom table for sidecar-ingested logs.

- Last Cache Update
```kusto
ContainerLogV2
| where TimeGenerated >= ago(24h)
| where ContainerName == "safety-amp-agent"
| where LogMessage contains "cache_status" or LogMessage contains "cache_update"
| extend d=parse_json(LogMessage)
| where isnotempty(d.cache_name)
| summarize LastUpdate=max(TimeGenerated),
          Size=max(todouble(d.metrics.cache_size_bytes)),
          Items=max(todouble(d.metrics.items_cached)),
          TTL=max(todouble(d.metrics.cache_ttl_seconds)),
          Valid=max(tobool(d.metrics.cache_valid))
  by CacheName=tostring(d.cache_name)
| extend AgeMinutes=round((now()-LastUpdate)/1m,0)
```

- Recent Sync Runs
```kusto
ContainerLogV2
| where TimeGenerated >= ago(24h)
| where ContainerName == "safety-amp-agent"
| where LogMessage contains "sync_start" or LogMessage contains "sync_complete" or LogMessage contains "sync_failed"
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

- Changes/Errors (24h) breakdown
```kusto
ContainerLogV2
| where TimeGenerated >= ago(24h)
| where ContainerName == "safety-amp-agent"
| extend d=parse_json(LogMessage)
| where d.operation in ("created","updated","deleted") or d.operation == "error_logged" or LogLevel == "Error"
| summarize Count=count()
  by Action=coalesce(tostring(d.operation),"log"), EntityType=coalesce(tostring(d.entity_type),"unknown"), ErrorType=coalesce(tostring(d.error_type),"")
| order by Count desc
```

---

## 8) Alerts

### 8.1 Grafana/Prometheus alerts

- Cache staleness
```promql
time() - max by (cache) (safetyamp_cache_last_updated_timestamp_seconds) > 3600
```
For: 15m

- Error surge
```promql
sum(increase(safetyamp_errors_total[15m])) > 20
```

- Missing sync
```promql
time() - max(safetyamp_last_sync_timestamp_seconds) > 5400
```

- Long-running syncs (P95)
```promql
histogram_quantile(0.95, sum by (le) (rate(safetyamp_sync_duration_seconds_bucket[15m]))) > 600
```

### 8.2 Azure Monitor alerts (KQL)

- Errors last 5m
```kusto
ContainerLogV2
| where TimeGenerated >= ago(5m)
| where ContainerName == "safety-amp-agent"
| where LogLevel == "Error" or LogMessage contains "error_logged"
| count
```
Create Azure Monitor alert rule with a threshold and Action Group (Email/Teams/PagerDuty).

---

## 9) Security, SLOs, Governance

- NetworkPolicy: allow scrape to `:9090` only from monitoring agents
- RBAC: restrict Log Analytics and Grafana access via Azure AD
- Retention/cost: set Log Analytics retention to 30–90 days; scope Fluent Bit input patterns to control volume
- SLOs:
  - Cache freshness < 60 minutes
  - Sync success rate target and error budget (alert only on sustained breach)
  - MTTR targets with routed alerts

---

## 10) CI/CD & Automation

- Pipelines should:
  - Deploy/update Azure resources (IaC recommended)
  - Roll app with new metrics/logging changes
  - Apply Grafana dashboards and alert rules
  - Deploy Workbook template
- Secrets: store Log Analytics workspace ID/key for Fluent Bit in a Kubernetes Secret
- Health gates: block rollout if `/ready` fails; validate presence of key metrics post-deploy

---

## 11) Rollout & Validation

- Dev/Staging:
  - Enable Prom scrape and Grafana
  - Validate targets and test metrics
  - Dry-run dashboard queries with sample data
- Production:
  - Roll out metrics/logging additions
  - Confirm Grafana panels and Workbook tiles populate
  - Enable alerts and validate by simulation (stale cache, error spikes)

Checklist:
- Metrics visible within 15–60s (Prom/Grafana)
- Logs visible within ~2–5 minutes (Log Analytics)
- Panels show non-empty data for last 24h
- Alerts fire and route correctly

---

## 12) Implementation Timeline & Checklist (Two Weeks)

Week 1 — Foundation & Setup
- Enhanced logging (structured JSON) in key modules (logger, CacheManager events, sync session lifecycle, change/error events)
- Container/Dockerfile envs for JSON logging
- AKS deployment updates: optional Fluent Bit sidecar, annotations verified
- Enable Container Insights; verify data flow

Week 2 — Dashboards & Alerts
- Managed Grafana dashboard: panels and PromQL queries (Sections 6 & 8.1)
- Azure Workbook: tabs and KQL queries (Section 7 & 8.2)
- Alerts configured and tested
- Documentation and handover

Acceptance Criteria
- Last Cache Update shows recent timestamps per cache
- Recent Sync Runs displays last sessions with durations and outcomes
- Recent Changes (24h) shows quantity and details by entity type
- Recent Errors (24h) shows quantity by error type/category
- Near real-time: metrics < 60s, logs ~2–5m

---

## 13) Risk Mitigation & Rollback

Risks
- Log volume impact (cost) → narrow inputs and set retention
- Performance impact → avoid excessive logging; prefer metrics for high-frequency counters
- Initial data latency → expect 5–10 minutes for first logs

Rollback
- Disable new Grafana alerts; hide dashboard panels
- Rollback image; toggle off structured logging envs if needed
- Remove sidecar if ingestion cost spikes
- Revert NetworkPolicy changes if scrape blocked

---

## 14) Appendices

### A) Quick Azure CLI snippets

Enable Container Insights on AKS (if not enabled):
```bash
az aks enable-addons \
  -g <rg> \
  -n <aks-name> \
  --addons monitoring \
  --workspace-resource-id \
    "/subscriptions/<sub>/resourcegroups/<rg>/providers/microsoft.operationalinsights/workspaces/<law-name>"
```

Get workspace credentials:
```bash
az monitor log-analytics workspace show -g <rg> -n <law> --query customerId -o tsv
az monitor log-analytics workspace get-shared-keys -g <rg> -n <law> --query primarySharedKey -o tsv
```

Create Kubernetes Secret for Fluent Bit:
```bash
kubectl create secret generic log-analytics-secrets \
  -n safety-amp \
  --from-literal=workspace-id="<id>" \
  --from-literal=workspace-key="<key>"
```

### B) Panel/Tile Mapping to Requirements
- Last Cache Update → PromQL (Section 6) and KQL (Section 7)
- Recent Sync Runs → PromQL counters/histograms and KQL session grouping
- Recent Changes (24h) → PromQL `safetyamp_changes_total` and KQL created/updated/deleted
- Recent Errors (24h) → PromQL `safetyamp_errors_total` and KQL error breakdown

---

## 15) Summary

This plan blends Managed Prometheus/Grafana (fast metrics, alerting) with Azure Monitor Workbooks (structured logs, governance). It uses the app’s existing `/metrics` and augments metrics/logging in a minimal, low-risk manner to deliver the four required views with near real-time performance.
