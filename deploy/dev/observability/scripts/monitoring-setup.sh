#!/usr/bin/env bash
set -euo pipefail

#
# Configure AKS monitoring and apply observability manifests
# - Enables Container Insights
# - Creates/updates Log Analytics secret for Fluent Bit (optional)
# - Applies Fluent Bit ConfigMap, example sidecar Deployment, and NetworkPolicy
#
# Requirements:
# - az CLI logged in with access to the subscription/RG
# - kubectl configured (current-context points to the AKS cluster)
#
# Usage:
#   ./monitoring-setup.sh \
#     --resource-group <rg> \
#     --aks-name <cluster> \
#     --workspace-resource-id \
#       "/subscriptions/<sub>/resourceGroups/<rg>/providers/Microsoft.OperationalInsights/workspaces/<law>" \
#     [--workspace-id <id> --workspace-key <key>] \
#     [--namespace safety-amp]
#

RG=""
AKS=""
LAW_RESOURCE_ID=""
LAW_ID=""
LAW_KEY=""
NAMESPACE="safety-amp"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --resource-group|-g) RG="$2"; shift 2 ;;
    --aks-name|-n) AKS="$2"; shift 2 ;;
    --workspace-resource-id) LAW_RESOURCE_ID="$2"; shift 2 ;;
    --workspace-id) LAW_ID="$2"; shift 2 ;;
    --workspace-key) LAW_KEY="$2"; shift 2 ;;
    --namespace) NAMESPACE="$2"; shift 2 ;;
    *) echo "Unknown arg: $1" >&2; exit 2 ;;
  esac
done

if [[ -z "$RG" || -z "$AKS" ]]; then
  echo "Provide --resource-group and --aks-name" >&2
  exit 2
fi

echo "==> Enabling Container Insights on AKS '$AKS' (RG: $RG)"
if [[ -n "$LAW_RESOURCE_ID" ]]; then
  az aks enable-addons -g "$RG" -n "$AKS" --addons monitoring \
    --workspace-resource-id "$LAW_RESOURCE_ID" >/dev/null
else
  az aks enable-addons -g "$RG" -n "$AKS" --addons monitoring >/dev/null
fi
echo "✓ Container Insights enabled"

echo "==> Ensuring namespace '$NAMESPACE' exists"
kubectl get ns "$NAMESPACE" >/dev/null 2>&1 || kubectl create ns "$NAMESPACE" >/dev/null

# Optionally create/update secret for Fluent Bit sidecar
if [[ -n "$LAW_ID" && -n "$LAW_KEY" ]]; then
  echo "==> Creating/updating 'log-analytics-secrets' in ns/$NAMESPACE"
  kubectl -n "$NAMESPACE" delete secret log-analytics-secrets >/dev/null 2>&1 || true
  kubectl -n "$NAMESPACE" create secret generic log-analytics-secrets \
    --from-literal=workspace-id="$LAW_ID" \
    --from-literal=workspace-key="$LAW_KEY" >/dev/null
  echo "✓ Secret created"
else
  echo "i Skipping Log Analytics secret creation (no --workspace-id/--workspace-key provided)"
fi

echo "==> Applying observability Kubernetes manifests"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/../../../.." && pwd)"

kubectl apply -f "$ROOT_DIR/deploy/dev/observability/k8s/fluentbit-config.yaml" >/dev/null
kubectl apply -f "$ROOT_DIR/deploy/dev/observability/k8s/networkpolicy-monitoring.yaml" >/dev/null

echo "i Example sidecar Deployment is available at: deploy/dev/observability/k8s/fluentbit-sidecar-example.yaml"
echo "✓ Observability base setup complete"
