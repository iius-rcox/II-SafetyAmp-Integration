#!/bin/bash

# Azure AKS Setup Script for SafetyAmp Integration
# This script creates and configures an AKS cluster with all necessary components

set -e

# Configuration - Update these values for your environment
RESOURCE_GROUP="safetyamp-rg"
LOCATION="eastus"
CLUSTER_NAME="safetyamp-aks"
ACR_NAME="safetyampacr"
KEY_VAULT_NAME="safetyamp-kv"
SUBSCRIPTION_ID=""
TENANT_ID=""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_header() {
    echo -e "${BLUE}=== $1 ===${NC}"
}

# Function to check if Azure CLI is installed and authenticated
check_azure_cli() {
    print_status "Checking Azure CLI..."
    
    if ! command -v az &> /dev/null; then
        print_error "Azure CLI is not installed. Please install it first:"
        echo "https://docs.microsoft.com/en-us/cli/azure/install-azure-cli"
        exit 1
    fi
    
    if ! az account show &> /dev/null; then
        print_error "Not authenticated to Azure. Please run: az login"
        exit 1
    fi
    
    # Get current subscription and tenant
    SUBSCRIPTION_ID=$(az account show --query id -o tsv)
    TENANT_ID=$(az account show --query tenantId -o tsv)
    
    print_status "Azure CLI authenticated. Subscription: $SUBSCRIPTION_ID"
}

# Function to create resource group
create_resource_group() {
    print_header "Creating Resource Group"
    
    if az group show --name $RESOURCE_GROUP --query id -o tsv &> /dev/null; then
        print_warning "Resource group $RESOURCE_GROUP already exists"
    else
        print_status "Creating resource group $RESOURCE_GROUP in $LOCATION..."
        az group create --name $RESOURCE_GROUP --location $LOCATION
        print_status "Resource group created successfully"
    fi
}

# Function to create Azure Container Registry
create_acr() {
    print_header "Creating Azure Container Registry"
    
    if az acr show --name $ACR_NAME --resource-group $RESOURCE_GROUP --query id -o tsv &> /dev/null; then
        print_warning "ACR $ACR_NAME already exists"
    else
        print_status "Creating ACR $ACR_NAME..."
        az acr create \
            --resource-group $RESOURCE_GROUP \
            --name $ACR_NAME \
            --sku Standard \
            --admin-enabled true
        
        print_status "ACR created successfully"
    fi
    
    # Get ACR login server
    ACR_LOGIN_SERVER=$(az acr show --name $ACR_NAME --resource-group $RESOURCE_GROUP --query loginServer -o tsv)
    print_status "ACR Login Server: $ACR_LOGIN_SERVER"
}

# Function to create Azure Key Vault
create_key_vault() {
    print_header "Creating Azure Key Vault"
    
    if az keyvault show --name $KEY_VAULT_NAME --resource-group $RESOURCE_GROUP --query id -o tsv &> /dev/null; then
        print_warning "Key Vault $KEY_VAULT_NAME already exists"
    else
        print_status "Creating Key Vault $KEY_VAULT_NAME..."
        az keyvault create \
            --resource-group $RESOURCE_GROUP \
            --name $KEY_VAULT_NAME \
            --location $LOCATION \
            --enable-rbac-authorization true
        
        print_status "Key Vault created successfully"
    fi
}

# Function to create AKS cluster
create_aks_cluster() {
    print_header "Creating AKS Cluster"
    
    if az aks show --name $CLUSTER_NAME --resource-group $RESOURCE_GROUP --query id -o tsv &> /dev/null; then
        print_warning "AKS cluster $CLUSTER_NAME already exists"
    else
        print_status "Creating AKS cluster $CLUSTER_NAME..."
        
        # Get ACR login server
        ACR_LOGIN_SERVER=$(az acr show --name $ACR_NAME --resource-group $RESOURCE_GROUP --query loginServer -o tsv)
        
        az aks create \
            --resource-group $RESOURCE_GROUP \
            --name $CLUSTER_NAME \
            --location $LOCATION \
            --node-count 3 \
            --node-vm-size Standard_D4s_v3 \
            --enable-addons monitoring \
            --enable-managed-identity \
            --enable-oidc-issuer \
            --enable-workload-identity \
            --attach-acr $ACR_LOGIN_SERVER \
            --network-plugin azure \
            --network-policy azure \
            --generate-ssh-keys
        
        print_status "AKS cluster created successfully"
    fi
}

# Function to configure workload identity
configure_workload_identity() {
    print_header "Configuring Workload Identity"
    
    # Get cluster OIDC issuer URL
    OIDC_ISSUER=$(az aks show --name $CLUSTER_NAME --resource-group $RESOURCE_GROUP --query "oidcIssuerProfile.issuerUrl" -o tsv)
    print_status "OIDC Issuer: $OIDC_ISSUER"
    
    # Create user-assigned managed identity for SafetyAmp
    print_status "Creating managed identity for SafetyAmp..."
    az identity create \
        --resource-group $RESOURCE_GROUP \
        --name "safetyamp-identity"
    
    # Get managed identity details
    USER_ASSIGNED_CLIENT_ID=$(az identity show --name "safetyamp-identity" --resource-group $RESOURCE_GROUP --query clientId -o tsv)
    USER_ASSIGNED_PRINCIPAL_ID=$(az identity show --name "safetyamp-identity" --resource-group $RESOURCE_GROUP --query principalId -o tsv)
    
    print_status "Managed Identity Client ID: $USER_ASSIGNED_CLIENT_ID"
    print_status "Managed Identity Principal ID: $USER_ASSIGNED_PRINCIPAL_ID"
    
    # Grant Key Vault access to managed identity
    print_status "Granting Key Vault access to managed identity..."
    az keyvault set-policy \
        --name $KEY_VAULT_NAME \
        --resource-group $RESOURCE_GROUP \
        --object-id $USER_ASSIGNED_PRINCIPAL_ID \
        --secret-permissions get list \
        --certificate-permissions get list
    
    # Create federated identity credential
    print_status "Creating federated identity credential..."
    az identity federated-credential create \
        --name "safetyamp-federated-credential" \
        --identity-name "safetyamp-identity" \
        --resource-group $RESOURCE_GROUP \
        --issuer $OIDC_ISSUER \
        --subject "system:serviceaccount:safety-amp:safety-amp-workload-identity-sa" \
        --audience api://AzureADTokenExchange
}

# Function to get cluster credentials
get_cluster_credentials() {
    print_header "Getting Cluster Credentials"
    
    print_status "Getting AKS credentials..."
    az aks get-credentials --resource-group $RESOURCE_GROUP --name $CLUSTER_NAME --overwrite-existing
    
    print_status "Testing cluster connection..."
    kubectl cluster-info
    print_status "Cluster connection successful"
}

# Function to install cluster add-ons
install_cluster_addons() {
    print_header "Installing Cluster Add-ons"
    
    # Install NGINX Ingress Controller
    print_status "Installing NGINX Ingress Controller..."
    kubectl create namespace ingress-nginx
    helm repo add ingress-nginx https://kubernetes.github.io/ingress-nginx
    helm repo update
    helm install ingress-nginx ingress-nginx/ingress-nginx \
        --namespace ingress-nginx \
        --set controller.replicaCount=2 \
        --set controller.nodeSelector."kubernetes\.io/os"=linux \
        --set defaultBackend.nodeSelector."kubernetes\.io/os"=linux
    
    # Install cert-manager
    print_status "Installing cert-manager..."
    kubectl create namespace cert-manager
    helm repo add jetstack https://charts.jetstack.io
    helm repo update
    helm install cert-manager jetstack/cert-manager \
        --namespace cert-manager \
        --set installCRDs=true \
        --set replicaCount=2
    
    # Install Prometheus Operator
    print_status "Installing Prometheus Operator..."
    kubectl create namespace monitoring
    helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
    helm repo update
    helm install prometheus prometheus-community/kube-prometheus-stack \
        --namespace monitoring \
        --set grafana.enabled=true \
        --set prometheus.prometheusSpec.replicaCount=2
}

# Function to create secrets in Key Vault
create_key_vault_secrets() {
    print_header "Creating Key Vault Secrets"
    
    print_warning "Please add the following secrets to your Key Vault manually:"
    echo ""
    echo "Key Vault: $KEY_VAULT_NAME"
    echo ""
    echo "Required secrets:"
    echo "- safetyamp-api-key"
    echo "- samsara-api-key"
    echo "- viewpoint-connection-string"
    echo "- redis-password"
    echo "- azure-key-vault-url (value: https://$KEY_VAULT_NAME.vault.azure.net/)"
    echo ""
    echo "You can add them using:"
    echo "az keyvault secret set --vault-name $KEY_VAULT_NAME --name <secret-name> --value <secret-value>"
}

# Function to build and push Docker image
build_and_push_image() {
    print_header "Building and Pushing Docker Image"
    
    # Get ACR login server
    ACR_LOGIN_SERVER=$(az acr show --name $ACR_NAME --resource-group $RESOURCE_GROUP --query loginServer -o tsv)
    
    print_status "Logging into ACR..."
    az acr login --name $ACR_NAME
    
    print_status "Building Docker image..."
    docker build -t $ACR_LOGIN_SERVER/safety-amp-agent:latest .
    
    print_status "Pushing Docker image..."
    docker push $ACR_LOGIN_SERVER/safety-amp-agent:latest
    
    print_status "Image pushed successfully: $ACR_LOGIN_SERVER/safety-amp-agent:latest"
}

# Function to update Kubernetes manifests
update_k8s_manifests() {
    print_header "Updating Kubernetes Manifests"
    
    # Get ACR login server
    ACR_LOGIN_SERVER=$(az acr show --name $ACR_NAME --resource-group $RESOURCE_GROUP --query loginServer -o tsv)
    
    # Get managed identity client ID
    USER_ASSIGNED_CLIENT_ID=$(az identity show --name "safetyamp-identity" --resource-group $RESOURCE_GROUP --query clientId -o tsv)
    
    # Get Key Vault URL
    KEY_VAULT_URL="https://$KEY_VAULT_NAME.vault.azure.net/"
    
    print_status "Updating SafetyAmp deployment with Azure-specific values..."
    
    # Create a backup of the original file
    cp k8s/safety-amp/safety-amp-deployment.yaml k8s/safety-amp/safety-amp-deployment.yaml.backup
    
    # Update the deployment file with Azure-specific values
    sed -i "s|iiusacr.azurecr.io/safety-amp-agent:latest|$ACR_LOGIN_SERVER/safety-amp-agent:latest|g" k8s/safety-amp/safety-amp-deployment.yaml
    sed -i "s|a2bcb3ce-a89b-43af-804c-e8029e0bafb4|$USER_ASSIGNED_CLIENT_ID|g" k8s/safety-amp/safety-amp-deployment.yaml
    sed -i "s|953922e6-5370-4a01-a3d5-773a30df726b|$TENANT_ID|g" k8s/safety-amp/safety-amp-deployment.yaml
    sed -i "s|https://your-keyvault.vault.azure.net/|$KEY_VAULT_URL|g" k8s/safety-amp/safety-amp-deployment.yaml
    
    print_status "Kubernetes manifests updated successfully"
}

# Function to deploy to AKS
deploy_to_aks() {
    print_header "Deploying to AKS"
    
    print_status "Creating namespaces..."
    kubectl apply -f k8s/namespaces/namespaces.yaml
    
    print_status "Waiting for namespaces to be ready..."
    kubectl wait --for=condition=Active namespace/safety-amp --timeout=60s
    
    print_status "Deploying SafetyAmp application..."
    kubectl apply -f k8s/safety-amp/safety-amp-deployment.yaml
    
    print_status "Waiting for deployment to be ready..."
    kubectl wait --for=condition=Available deployment/safety-amp-agent -n safety-amp --timeout=300s
    
    print_status "Deployment completed successfully"
}

# Function to show deployment status
show_status() {
    print_header "Deployment Status"
    
    print_status "Resource Group: $RESOURCE_GROUP"
    print_status "AKS Cluster: $CLUSTER_NAME"
    print_status "ACR: $ACR_NAME"
    print_status "Key Vault: $KEY_VAULT_NAME"
    
    echo ""
    print_status "AKS Cluster Status:"
    kubectl get nodes
    
    echo ""
    print_status "SafetyAmp Pods:"
    kubectl get pods -n safety-amp
    
    echo ""
    print_status "Services:"
    kubectl get services -n safety-amp
    
    echo ""
    print_status "Ingress:"
    kubectl get ingress --all-namespaces
}

# Function to show next steps
show_next_steps() {
    print_header "Next Steps"
    
    echo ""
    print_status "1. Add secrets to Key Vault:"
    echo "   az keyvault secret set --vault-name $KEY_VAULT_NAME --name safetyamp-api-key --value <your-api-key>"
    echo "   az keyvault secret set --vault-name $KEY_VAULT_NAME --name samsara-api-key --value <your-api-key>"
    echo "   az keyvault secret set --vault-name $KEY_VAULT_NAME --name viewpoint-connection-string --value <your-connection-string>"
    echo ""
    
    print_status "2. Update DNS records for your domain to point to the LoadBalancer IP"
    echo ""
    
    print_status "3. Monitor the application:"
    echo "   kubectl logs -f deployment/safety-amp-agent -n safety-amp"
    echo ""
    
    print_status "4. Access the application:"
    echo "   kubectl port-forward service/safety-amp-service 8080:8080 -n safety-amp"
    echo "   Then visit: http://localhost:8080/health"
    echo ""
    
    print_warning "Remember to secure your secrets and never commit them to version control!"
}

# Main function
main() {
    print_header "Azure AKS Setup for SafetyAmp Integration"
    echo ""
    
    # Check prerequisites
    check_azure_cli
    
    # Create Azure resources
    create_resource_group
    create_acr
    create_key_vault
    create_aks_cluster
    
    # Configure workload identity
    configure_workload_identity
    
    # Get cluster credentials
    get_cluster_credentials
    
    # Install add-ons
    install_cluster_addons
    
    # Build and push image
    build_and_push_image
    
    # Update manifests
    update_k8s_manifests
    
    # Deploy application
    deploy_to_aks
    
    # Show status and next steps
    show_status
    show_next_steps
}

# Handle command line arguments
case "${1:-setup}" in
    "setup")
        main
        ;;
    "status")
        show_status
        ;;
    "deploy")
        deploy_to_aks
        ;;
    "build")
        build_and_push_image
        ;;
    "help"|"-h"|"--help")
        echo "Usage: $0 [setup|status|deploy|build|help]"
        echo ""
        echo "Commands:"
        echo "  setup   - Complete AKS setup and deployment (default)"
        echo "  status  - Show deployment status"
        echo "  deploy  - Deploy application to existing AKS cluster"
        echo "  build   - Build and push Docker image only"
        echo "  help    - Show this help message"
        ;;
    *)
        print_error "Unknown command: $1"
        echo "Use '$0 help' for usage information."
        exit 1
        ;;
esac 