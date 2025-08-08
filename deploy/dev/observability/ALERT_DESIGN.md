# Alert Design (Baseline-First)

## Goals
- Detect sustained anomalies while avoiding noise during normal operations
- Route actionable alerts with clear remediation steps

## Signals
- Errors: `safetyamp_errors_total`
- Changes: `safetyamp_changes_total`
- Sync state: `safetyamp_sync_in_progress`, `safetyamp_last_sync_timestamp_seconds`
- Cache freshness: `safetyamp_cache_last_updated_timestamp_seconds`

## Baseline-first rollout
1. Collect 7 days of data without alerting
2. Compute P95 for: 15m error increases, sync durations, cache intervals
3. Initial thresholds: P95 * 1.2 (or TTL + 25%)
4. Stage warning alerts first; promote to critical after validation

## Routing
- Primary: Teams channel/email via Grafana or Azure Monitor action groups
- Escalation: on-call after 30m sustained breach

## Examples (PromQL)
- Error surge: `sum(increase(safetyamp_errors_total[15m])) > THRESHOLD`
- Missing sync: `time() - max(safetyamp_last_sync_timestamp_seconds) > THRESHOLD`
- Cache stale: `time() - max by (cache) (safetyamp_cache_last_updated_timestamp_seconds) > THRESHOLD`
- Long-running syncs (P95): `histogram_quantile(0.95, sum by (le) (rate(safetyamp_sync_duration_seconds_bucket[15m]))) > THRESHOLD`
