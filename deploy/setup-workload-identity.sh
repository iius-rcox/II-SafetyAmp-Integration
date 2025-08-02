#!/bin/bash
set -e

# Azure Workload Identity Setup for SafetyAmp Integration
# This script sets up the necessary Azure resources for Workload Identity

# Configuration
RESOURCE_GROUP="${RESOURCE_GROUP:-rg-dev-aks}"
AKS_CLUSTER_NAME="${AKS_CLUSTER_NAME:-dev-aks}"
NAMESPACE="${NAMESPACE:-safety-amp}"
SERVICE_ACCOUNT_NAME="${SERVICE_ACCOUNT_NAME:-safety-amp-workload-identity-sa}"
USER_ASSIGNED_IDENTITY_NAME="${USER_ASSIGNED_IDENTITY_NAME:-safety-amp-workload-identity}"
KEYVAULT_NAME="${KEYVAULT_NAME:-kv-safety-amp-dev}"
SQL_SERVER_NAME="${SQL_SERVER_NAME:-your-sql-server}"
SQL_DATABASE_NAME="${SQL_DATABASE_NAME:-ViewPoint}"

echo "🚀 Setting up Azure Workload Identity for SafetyAmp Integration"
echo "Resource Group: $RESOURCE_GROUP"
echo "AKS Cluster: $AKS_CLUSTER_NAME"
echo "Namespace: $NAMESPACE"

# 1. Enable Workload Identity on AKS cluster
echo "✅ Enabling Workload Identity on AKS cluster..."
az aks update \
    --resource-group "$RESOURCE_GROUP" \
    --name "$AKS_CLUSTER_NAME" \
    --enable-oidc-issuer \
    --enable-workload-identity

# 2. Get OIDC issuer URL
echo "✅ Getting OIDC issuer URL..."
OIDC_ISSUER=$(az aks show --resource-group "$RESOURCE_GROUP" --name "$AKS_CLUSTER_NAME" --query "oidcIssuerProfile.issuerUrl" -o tsv)
echo "OIDC Issuer: $OIDC_ISSUER"

# 3. Create User Assigned Managed Identity
echo "✅ Creating User Assigned Managed Identity..."
az identity create \
    --name "$USER_ASSIGNED_IDENTITY_NAME" \
    --resource-group "$RESOURCE_GROUP"

# 4. Get identity details
USER_ASSIGNED_CLIENT_ID=$(az identity show --resource-group "$RESOURCE_GROUP" --name "$USER_ASSIGNED_IDENTITY_NAME" --query 'clientId' -o tsv)
USER_ASSIGNED_OBJECT_ID=$(az identity show --resource-group "$RESOURCE_GROUP" --name "$USER_ASSIGNED_IDENTITY_NAME" --query 'principalId' -o tsv)

echo "Client ID: $USER_ASSIGNED_CLIENT_ID"
echo "Object ID: $USER_ASSIGNED_OBJECT_ID"

# 5. Create federated identity credential
echo "✅ Creating federated identity credential..."
az identity federated-credential create \
    --name "safety-amp-federated-credential" \
    --identity-name "$USER_ASSIGNED_IDENTITY_NAME" \
    --resource-group "$RESOURCE_GROUP" \
    --issuer "$OIDC_ISSUER" \
    --subject "system:serviceaccount:$NAMESPACE:$SERVICE_ACCOUNT_NAME" \
    --audience api://AzureADTokenExchange

# 6. Grant Key Vault access
echo "✅ Granting Key Vault access to Managed Identity..."
az keyvault set-policy \
    --name "$KEYVAULT_NAME" \
    --object-id "$USER_ASSIGNED_OBJECT_ID" \
    --secret-permissions get list

# 7. Grant SQL Database access (if SQL Server exists)
if az sql server show --name "$SQL_SERVER_NAME" --resource-group "$RESOURCE_GROUP" >/dev/null 2>&1; then
    echo "✅ Granting SQL Database access to Managed Identity..."
    
    # Note: This requires Azure AD admin to be set on SQL Server
    # The following SQL commands need to be run by an Azure AD admin:
    cat << EOF > setup-sql-user.sql
-- Connect to your SQL Database as an Azure AD admin and run:
CREATE USER [$USER_ASSIGNED_IDENTITY_NAME] FROM EXTERNAL PROVIDER;
ALTER ROLE db_datareader ADD MEMBER [$USER_ASSIGNED_IDENTITY_NAME];
ALTER ROLE db_datawriter ADD MEMBER [$USER_ASSIGNED_IDENTITY_NAME];
ALTER ROLE db_ddladmin ADD MEMBER [$USER_ASSIGNED_IDENTITY_NAME];
GO
EOF
    
    echo "📝 SQL setup commands saved to setup-sql-user.sql"
    echo "⚠️  You need to run these commands as an Azure AD admin on your SQL Database"
else
    echo "⚠️  SQL Server '$SQL_SERVER_NAME' not found. Skipping SQL access setup."
fi

# 8. Update Kubernetes deployment with actual values
echo "✅ Updating Kubernetes deployment with identity values..."
sed -i "s/\${USER_ASSIGNED_CLIENT_ID}/$USER_ASSIGNED_CLIENT_ID/g" ../k8s/safety-amp/safety-amp-deployment.yaml
sed -i "s/\${AZURE_TENANT_ID}/$(az account show --query tenantId -o tsv)/g" ../k8s/safety-amp/safety-amp-deployment.yaml

# 9. Create namespace if it doesn't exist
echo "✅ Creating Kubernetes namespace..."
kubectl create namespace "$NAMESPACE" --dry-run=client -o yaml | kubectl apply -f -

# 10. Apply the updated deployment
echo "✅ Applying Kubernetes manifests..."
kubectl apply -f ../k8s/safety-amp/safety-amp-deployment.yaml

echo ""
echo "🎉 Azure Workload Identity setup complete!"
echo ""
echo "📋 Summary:"
echo "   - User Assigned Identity: $USER_ASSIGNED_IDENTITY_NAME"
echo "   - Client ID: $USER_ASSIGNED_CLIENT_ID"
echo "   - Object ID: $USER_ASSIGNED_OBJECT_ID"
echo "   - Federated Credential: safety-amp-federated-credential"
echo ""
echo "📝 Next steps:"
echo "   1. Run the SQL commands in setup-sql-user.sql as an Azure AD admin"
echo "   2. Update your Key Vault with the necessary secrets"
echo "   3. Test the deployment: kubectl get pods -n $NAMESPACE"
echo ""
echo "🔧 To test the identity:"
echo "   kubectl run test-pod --image=mcr.microsoft.com/azure-cli --namespace=$NAMESPACE --serviceaccount=$SERVICE_ACCOUNT_NAME --rm -it -- bash"
echo "   # Inside the pod: az login --identity && az keyvault secret list --vault-name $KEYVAULT_NAME"