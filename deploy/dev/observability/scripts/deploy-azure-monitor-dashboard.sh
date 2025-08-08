#!/usr/bin/env bash
set -euo pipefail

# Deploy Azure Monitor Workbook from ARM template (dev scaffold)
#
# Usage:
#   ./deploy-azure-monitor-dashboard.sh \
#     --resource-group <rg> \
#     --location <region> \
#     --workbook-source-id \
#       "/subscriptions/<sub>/resourceGroups/<rg>/providers/Microsoft.OperationalInsights/workspaces/<law>" \
#     [--display-name "SafetyAmp Integration Dashboard"]

RG=""
LOCATION=""
SOURCE_ID=""
DISPLAY_NAME="SafetyAmp Integration Dashboard"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --resource-group|-g) RG="$2"; shift 2 ;;
    --location|-l) LOCATION="$2"; shift 2 ;;
    --workbook-source-id) SOURCE_ID="$2"; shift 2 ;;
    --display-name) DISPLAY_NAME="$2"; shift 2 ;;
    *) echo "Unknown arg: $1" >&2; exit 2 ;;
  esac
done

if [[ -z "$RG" || -z "$LOCATION" || -z "$SOURCE_ID" ]]; then
  echo "Provide --resource-group, --location, and --workbook-source-id" >&2
  exit 2
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TEMPLATE="$SCRIPT_DIR/../workbooks/workbook-deployment-template.json"

if [[ ! -f "$TEMPLATE" ]]; then
  echo "Template not found: $TEMPLATE" >&2
  exit 1
fi

DEPLOY_NAME="workbook-$(date +%Y%m%d%H%M%S)"

echo "==> Deploying Azure Monitor workbook ($DISPLAY_NAME)"
az deployment group create \
  -g "$RG" \
  -n "$DEPLOY_NAME" \
  --template-file "$TEMPLATE" \
  --parameters workbookDisplayName="$DISPLAY_NAME" workbookSourceId="$SOURCE_ID" \
  --query properties.outputs.workbookResourceId.value -o tsv | tee /dev/stderr

echo "✓ Workbook deployment initiated"
