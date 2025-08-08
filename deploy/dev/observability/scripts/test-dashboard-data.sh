#!/usr/bin/env bash
set -euo pipefail

# Validate data flow to Prometheus and Azure Monitor (basic checks)

METRICS_URL=${1:-http://localhost:8080/metrics}
NAMESPACE=${NAMESPACE:-safety-amp}
POD_LABEL_SELECTOR=${POD_LABEL_SELECTOR:-app=safety-amp,component=agent}

echo "==> Checking Prometheus metrics endpoint: $METRICS_URL"
if curl -fsS "$METRICS_URL" | grep -q "safetyamp_sync_in_progress"; then
  echo "✓ Metrics endpoint exposes expected series"
else
  echo "❌ Metrics missing expected series" >&2
  exit 2
fi

echo "==> Verifying pod annotations for Prometheus scraping in ns/$NAMESPACE"
if kubectl -n "$NAMESPACE" get pods -l "$POD_LABEL_SELECTOR" -o jsonpath='{range .items[*]}{.metadata.annotations.prometheus\.io/scrape}{"\n"}{end}' | grep -q "true"; then
  echo "✓ Pods annotated for scraping"
else
  echo "❌ Pods are not annotated for scraping" >&2
  exit 2
fi

echo "i For Log Analytics validation, run a KQL query in the Azure Portal (ContainerLogV2) as per deploy/observability-deployment.md Section 7"
echo "✓ Basic data flow checks passed"
