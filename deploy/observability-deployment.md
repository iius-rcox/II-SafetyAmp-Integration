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

---

## 16) Recommendations and Phased Rollout

- Start simple:
  - Ship existing sync metrics first; stand up Managed Prometheus + Managed Grafana and basic panels
  - Add cache/change/error metrics next; only add Fluent Bit sidecar if Container Insights proves insufficient
- Establish baseline:
  - Run for 7 days to capture baseline before enabling alerts; use percentiles to avoid noisy thresholds
- Feature flag structured logging:
  - Add an environment toggle (e.g., `STRUCTURED_LOGGING_ENABLED=true`) or reuse `LOG_FORMAT=json` to control JSON log volume during rollout
  - Gradually enable in one replica, then all
- KQL resilience:
  - Use `todynamic()` and `coalesce()` to handle malformed JSON safely; guard with `isnotnull()` checks
- Gradual rollout:
  - Dev → Staging → Prod; canaries for metrics/logging enabled pods; monitor ingestion volume and costs

---

## 17) Exact Instrumentation Targets (Application)

Implement missing metrics in these files:
- `utils/cache_manager.py`
  - Emit: `safetyamp_cache_last_updated_timestamp_seconds{cache}`, `safetyamp_cache_items_total{cache}`, and optionally `safetyamp_cache_ttl_seconds{cache}` when `save_cache`, `mark_cache_refreshed`, and `get_cache_info` run
- `utils/change_tracker.py`
  - Increment: `safetyamp_changes_total{entity_type,operation,status}` in `log_creation`, `log_update`, `log_deletion`, `log_skip`
- `utils/error_notifier.py`
  - Increment: `safetyamp_errors_total{error_type,entity_type,source}` in `log_error`
- `main.py`
  - Maintain: `safetyamp_sync_in_progress` gauge around `run_sync_worker`
  - Set: `safetyamp_last_sync_timestamp_seconds` on successful cycle completion

Status:
- Currently implemented: sync op counters + durations (`safetyamp_sync_operations_total`, `safetyamp_sync_duration_seconds`, `safetyamp_records_processed_total`)
- Missing: cache, changes, errors, sync state gauges — required for dashboards/alerts in Sections 6/8

---

## 18) Workbook Parameterization and KQL Hardening

Add workbook parameters to avoid hard-coded container names and to tolerate malformed JSON:

- Define parameters in Workbook:
  - `containerName` (default: `safety-amp-agent`)
  - `namespace` (default: `safety-amp`)

- Use in queries:
```kusto
let containerName = '{containerName}';
let ns = '{namespace}';
ContainerLogV2
| where TimeGenerated >= ago(24h)
| where Namespace == ns
| where ContainerName =~ containerName
| extend d = todynamic(LogMessage)
| where isnotnull(d)
```

- Safer projections with fallbacks:
```kusto
| extend op = tostring(d.operation), et = tostring(d.entity_type)
| extend metrics = todynamic(d.metrics)
| extend duration = todouble(metrics.session_duration_seconds)
| project-away LogMessage
```

Replace earlier examples with the pattern above where applicable or provide an alternate “hardened” version alongside.

### 18.1 Workbook parameters (define once)

Add parameters in the Workbook UI (or via ARM):
- `containerName` (string) default: `safety-amp-agent`
- `namespace` (string) default: `safety-amp`

Example ARM parameters block (inline in workbook template):
```json
{
  "id": "containerName",
  "version": "KqlParameterItem/1.0",
  "name": "containerName",
  "type": 1,
  "value": "safety-amp-agent"
},
{
  "id": "namespace",
  "version": "KqlParameterItem/1.0",
  "name": "namespace",
  "type": 1,
  "value": "safety-amp"
}
```

### 18.2 Parameterized and hardened KQL examples

Use these forms instead of hard-coding container names. All queries conform to:
```kusto
let containerName = '{containerName}';
let ns = '{namespace}';
ContainerLogV2
| where TimeGenerated >= ago(24h)
| where Namespace == ns
| where ContainerName =~ containerName
| extend d = todynamic(LogMessage)
| where isnotnull(d)
```

- Last Cache Update (parameterized):
```kusto
let containerName = '{containerName}';
let ns = '{namespace}';
ContainerLogV2
| where TimeGenerated >= ago(24h)
| where Namespace == ns
| where ContainerName =~ containerName
| extend d = todynamic(LogMessage)
| where isnotnull(d)
| where tostring(d.operation) in ("cache_status", "cache_update") or LogMessage contains "cache_status" or LogMessage contains "cache_update"
| extend cache_name = tostring(d.cache_name),
         metrics = todynamic(d.metrics),
         cache_size_bytes = todouble(metrics.cache_size_bytes),
         items_cached = todouble(metrics.items_cached),
         cache_ttl_seconds = todouble(metrics.cache_ttl_seconds),
         cache_valid = tobool(metrics.cache_valid)
| where isnotempty(cache_name)
| summarize LastUpdate = max(TimeGenerated),
            Size = max(cache_size_bytes),
            Items = max(items_cached),
            TTL = max(cache_ttl_seconds),
            Valid = max(cache_valid)
  by CacheName = cache_name
| extend AgeMinutes = round((now() - LastUpdate) / 1m, 0)
```

- Recent Sync Runs (parameterized):
```kusto
let containerName = '{containerName}';
let ns = '{namespace}';
ContainerLogV2
| where TimeGenerated >= ago(24h)
| where Namespace == ns
| where ContainerName =~ containerName
| extend d = todynamic(LogMessage)
| where isnotnull(d)
| where tostring(d.operation) in ("sync_start", "sync_complete", "sync_failed")
| extend session_id = tostring(d.session_id),
         sync_type = tostring(d.sync_type),
         metrics = todynamic(d.metrics),
         duration = todouble(metrics.session_duration_seconds),
         records_processed = todouble(metrics.records_processed)
| where isnotempty(session_id)
| summarize StartTime = minif(TimeGenerated, tostring(d.operation)=="sync_start"),
            EndTime = maxif(TimeGenerated, tostring(d.operation) in ("sync_complete","sync_failed")),
            Status = iff(countif(tostring(d.operation)=="sync_complete")>0, "Success",
                         iff(countif(tostring(d.operation)=="sync_failed")>0, "Failed", "Running")),
            RecordsProcessed = maxif(records_processed, tostring(d.operation)=="sync_complete"),
            DurationSeconds = maxif(duration, tostring(d.operation)=="sync_complete")
  by SessionId = session_id, SyncType = sync_type
| order by StartTime desc
```

- Changes/Errors (parameterized):
```kusto
let containerName = '{containerName}';
let ns = '{namespace}';
ContainerLogV2
| where TimeGenerated >= ago(24h)
| where Namespace == ns
| where ContainerName =~ containerName
| extend d = todynamic(LogMessage)
| where isnotnull(d)
| extend op = tostring(d.operation), et = tostring(d.entity_type), err = tostring(d.error_type)
| where op in ("created","updated","deleted","error_logged") or LogLevel == "Error"
| summarize Count = count()
  by Action = op, EntityType = coalesce(et, "unknown"), ErrorType = coalesce(err, "")
| order by Count desc
```

---

## 19) Fluent Bit Sidecar — Full Deployment Example

The ConfigMap alone is insufficient. Mount shared volumes so the sidecar can tail app-written files, and inject workspace secrets.

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: safety-amp-agent
  namespace: safety-amp
spec:
  template:
    spec:
      volumes:
        - name: changes-volume
          emptyDir: {}
        - name: errors-volume
          emptyDir: {}
        - name: fluentbit-config
          configMap:
            name: fluentbit-config
      containers:
        - name: safety-amp-agent
          image: safetyampacr.azurecr.io/safetyamp-integration:latest
          volumeMounts:
            - name: changes-volume
              mountPath: /app/output/changes
            - name: errors-volume
              mountPath: /app/output/errors
          env:
            - name: STRUCTURED_LOGGING_ENABLED
              value: "true"  # feature flag
        - name: fluentbit-sidecar
          image: fluent/fluent-bit:2.2.0
          volumeMounts:
            - name: changes-volume
              mountPath: /app/output/changes
              readOnly: true
            - name: errors-volume
              mountPath: /app/output/errors
              readOnly: true
            - name: fluentbit-config
              mountPath: /fluent-bit/etc
          env:
            - name: WORKSPACE_ID
              valueFrom:
                secretKeyRef:
                  name: log-analytics-secrets
                  key: workspace-id
            - name: WORKSPACE_KEY
              valueFrom:
                secretKeyRef:
                  name: log-analytics-secrets
                  key: workspace-key
```

Secret for workspace credentials:
```yaml
apiVersion: v1
kind: Secret
metadata:
  name: log-analytics-secrets
  namespace: safety-amp
type: Opaque
stringData:
  workspace-id: "<LAW_CUSTOMER_ID>"
  workspace-key: "<LAW_PRIMARY_KEY>"
```

Notes:
- Ensure the app writes change/error files under `/app/output/changes` and `/app/output/errors` (default paths already align)
- Consider scoping tail inputs to limit volume (e.g., only latest files)

---

## 20) Dashboard Panel Clarifications

- Current Sync State: split into two panels for clarity
  - Panel A (Stat): Sync in progress
    ```promql
    max(safetyamp_sync_in_progress)
    ```
    Value mappings: 0 → “Idle”, 1 → “Running”
  - Panel B (Stat): Minutes since last sync
    ```promql
    (time() - max(safetyamp_last_sync_timestamp_seconds)) / 60
    ```
    Thresholds: warn > 60, critical > 90 (tune to schedule)

- Add panel descriptions/tooltips documenting expected ranges and SLOs

---

## 21) Alert Thresholds After Baseline

After 7-day baseline, set initial thresholds:
- Cache staleness: > TTL + 25% buffer
- Error surge: 95th percentile of 15m increases + 20% buffer
- Missing sync: expected cadence + 50% buffer
- Long-running syncs: P95 duration + 25% buffer

Review/adjust monthly based on incident postmortems.

---

## 22) Baseline-First Alert Rollout

- Baseline window: operate without alerts for 7 days; record 15m windows of error increases, sync durations, and cache update intervals
- Initial thresholds (examples):
  - Error surge: `sum(increase(safetyamp_errors_total[15m])) > P95_baseline * 1.2`
  - Cache staleness: `TTL + 25%` buffer
  - Missing sync: `expected cadence + 50%`
  - Long-running syncs: `P95 + 25%`
- Gradual enablement: start with warning-only; escalate to critical after validation

## 23) CI/CD Hooks and Post-Deploy Validation

- Pipeline gates:
  - Lint/format and unit tests
  - Deploy to dev; wait for `DeploymentAvailable` and `/ready` success
  - Post-deploy probes:
    - Query metrics endpoint and assert presence of: `safetyamp_sync_in_progress`, `safetyamp_last_sync_timestamp_seconds`, `safetyamp_changes_total`, `safetyamp_errors_total`, cache gauges
    - If Fluent Bit used: check pod has `fluentbit-sidecar` and ConfigMap mounted
- Observability smoke tests:
  - Trigger a small sync cycle and confirm metrics increments
  - Run a sample error path (mock) and confirm `safetyamp_errors_total` increments

## 24) Panel Design Clarifications

- Split Current Sync State into two stat panels (Running/Idle, Minutes Since Last Sync) with thresholds and value mappings (example JSON in `deploy/dev/observability/grafana/safetyamp-sync-overview.json`)
- Add panel descriptions and SLO notes to aid interpretation

---

## 25) Pre-Deploy Assets (Dev Only)

- Scripts:
  - `deploy/dev/observability/scripts/metrics-smoke-test.ps1` and `.sh`
- Grafana:
  - `deploy/dev/observability/grafana/safetyamp-sync-overview.json`
  - `deploy/dev/observability/grafana/safetyamp-observability.json`
- Prometheus:
  - `deploy/dev/observability/prometheus/safetyamp-alerts.yaml` (placeholders)
  - `deploy/dev/observability/prometheus/servicemonitor.yaml` (self-hosted only)
- Workbooks:
  - `deploy/dev/observability/workbooks/workbook-deployment-template.json` (with parameters)
- K8s:
  - `deploy/dev/observability/k8s/fluentbit-config.yaml` and `fluentbit-sidecar-example.yaml`
  - `deploy/dev/observability/k8s/networkpolicy-monitoring.yaml`
- Docs:
  - `deploy/dev/observability/ALERT_DESIGN.md`
  - `deploy/dev/observability/SECURITY_GOVERNANCE.md`
  - `deploy/dev/observability/COST_GUARDRAILS.md`
  - `deploy/dev/observability/CI_STEPS.md`
  - `deploy/dev/observability/RUNBOOK.md`

Use these for reviews and local verification before any cluster rollout.
