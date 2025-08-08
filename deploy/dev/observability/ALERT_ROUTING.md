# Alert Routing (Severe → Email Developer)

## Developer email
- Source: secret `ALERT-EMAIL-TO` (env or Azure Key Vault)
- Helper: `scripts/prepare-alert-routing.ps1` resolves it pre-config

## Grafana (Managed or self-hosted)
1. Create Contact Point (Email)
   - Name: `cp-dev-email`
   - To: value from `ALERT-EMAIL-TO`
2. Create Route
   - Matching labels: `severity=critical`
   - Send to: `cp-dev-email`
3. Ensure alert rules include `labels: {severity: critical}` as appropriate

## Azure Monitor
1. Create Action Group `ag-safetyamp-dev`
   - Email receiver: `ALERT-EMAIL-TO`
2. Attach Action Group to:
   - Managed Prometheus alert rules
   - Log Analytics (KQL) scheduled query alerts

## Alertmanager (self-hosted)
Use the email receiver config as shown and set a top-level route matching `severity: critical`.

## Note on non-critical alerts
- Keep non-critical routed to a lower-noise channel (e.g., Teams only) until baseline is established
- Promote to critical (email) only after thresholds are tuned
