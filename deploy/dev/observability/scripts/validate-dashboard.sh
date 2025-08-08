#!/usr/bin/env bash
set -euo pipefail

# End-to-end validation of observability setup

NAMESPACE=${NAMESPACE:-safety-amp}

echo "==> Checking pods in ns/$NAMESPACE"
kubectl -n "$NAMESPACE" get pods -o wide | cat

echo "==> Verifying service and endpoints"
kubectl -n "$NAMESPACE" get svc safety-amp-service | cat
kubectl -n "$NAMESPACE" get endpointslices -l kubernetes.io/service-name=safety-amp-service | cat || true

echo "==> Port-forward to metrics (background)"
PF_LOG=$(mktemp)
kubectl -n "$NAMESPACE" port-forward svc/safety-amp-service 9099:9090 >/dev/null 2>"$PF_LOG" &
PF_PID=$!
trap 'kill $PF_PID 2>/dev/null || true; rm -f "$PF_LOG"' EXIT
sleep 2

echo "==> Running metrics smoke test"
"$(dirname "$0")/metrics-smoke-test.sh" http://localhost:9099/metrics

echo "==> Checking logs for recent JSON entries (stdout via ContainerLogV2 expected in Azure)"
echo "i Validate in Azure Portal: run parameterized KQL queries per deploy/observability-deployment.md Sections 7 & 18"

echo "✓ Observability validation checks completed"
