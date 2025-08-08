# CI/CD Steps (No-Deploy Prep)

1. Lint/Test
2. Build app image (tagged with commit SHA)
3. Metrics smoke test (local):
   - Run app container locally and `scripts/metrics-smoke-test.sh http://localhost:8080/metrics`
4. Artifact publish:
   - Grafana JSON to artifact storage
   - Workbook ARM template
   - Prometheus alert rules
5. Manual gate: review dashboard JSON and alert thresholds before deployment
