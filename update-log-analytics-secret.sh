#!/bin/bash
# Script to update Log Analytics credentials for fluentbit

# Get your Log Analytics workspace ID and key from Azure Portal:
# 1. Go to Azure Portal > Log Analytics workspaces > Your workspace
# 2. Click "Agents management" in the left menu
# 3. Copy "Workspace ID" and "Primary key"

# Then run this script with those values:
# ./update-log-analytics-secret.sh <workspace-id> <primary-key>

if [ "$#" -ne 2 ]; then
    echo "Usage: $0 <workspace-id> <primary-key>"
    echo ""
    echo "To get these values:"
    echo "  1. Azure Portal > Log Analytics workspaces"
    echo "  2. Select your workspace"
    echo "  3. Click 'Agents management'"
    echo "  4. Copy Workspace ID and Primary key"
    exit 1
fi

WORKSPACE_ID=$1
PRIMARY_KEY=$2

echo "Updating log-analytics-secrets with real credentials..."

kubectl create secret generic log-analytics-secrets \
  --from-literal=workspace-id="$WORKSPACE_ID" \
  --from-literal=workspace-key="$PRIMARY_KEY" \
  --namespace=safety-amp \
  --dry-run=client -o yaml | kubectl apply -f -

echo "Secret updated. Restarting fluentbit pod..."
kubectl delete pod -n safety-amp -l component=agent

echo "Done! Check pod status with:"
echo "  kubectl get pods -n safety-amp -l component=agent"
