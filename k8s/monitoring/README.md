# Monitoring Stack

- Apply all monitoring resources with:

```
kubectl apply -f k8s/monitoring/monitoring-stack.yaml
```

- Grafana dashboards are under `k8s/monitoring/grafana/`.
- Prometheus alert runbooks referenced via `file://k8s/monitoring/RUNBOOK.md`.