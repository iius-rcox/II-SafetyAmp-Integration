# Monitoring Runbook

- High log ingestion cost: investigate Fluent Bit filters and volume of SafetyAmpCustom logs.
- Alert noise: tune thresholds in `monitoring-stack.yaml` PrometheusRule.
- Dashboards blank metrics: verify ServiceMonitor and NetworkPolicy, pod labels `app: safety-amp`, `component: agent`.