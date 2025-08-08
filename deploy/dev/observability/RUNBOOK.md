# Operator Runbook

## Dashboards blank (metrics)
- Check `/metrics` via port-forward; confirm core series present
- Ensure Prometheus scrape annotations/ServiceMonitor are correct

## Dashboards blank (logs)
- Verify Fluent Bit sidecar running and ConfigMap mounted
- Check workspace secret present and valid
- Query `ContainerLogV2` for recent entries

## High log ingestion cost
- Narrow Fluent Bit patterns; disable verbose sources
- Lower retention; switch to metrics for high-frequency signals

## Alert noise
- Revisit thresholds after baseline; add `for:` duration and P95-based buffers
