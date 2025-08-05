# Azure AKS Setup Script for SafetyAmp Integration (PowerShell Version)
# This script creates and configures an AKS cluster with all necessary components

param(
    [string]$Command = "setup"
)

# Configuration - Update these values for your environment
$RESOURCE_GROUP = "rg_prod"    # Your existing resource group
$LOCATION = "southcentralus"
$CLUSTER_NAME = "dev-aks"      # Your existing AKS cluster
$ACR_NAME = "iiusacr"          # Your existing ACR
$KEY_VAULT_NAME = "iius-akv"   # Your existing Key Vault
$SUBSCRIPTION_ID = ""
$TENANT_ID = ""

# Function to print colored output
function Write-Status {
    param([string]$Message)
    Write-Host "[INFO] $Message" -ForegroundColor Green
}

function Write-Warning {
    param([string]$Message)
    Write-Host "[WARNING] $Message" -ForegroundColor Yellow
}

function Write-Error {
    param([string]$Message)
    Write-Host "[ERROR] $Message" -ForegroundColor Red
}

function Write-Header {
    param([string]$Message)
    Write-Host "=== $Message ===" -ForegroundColor Blue
}

# Function to check if Azure CLI is installed and authenticated
function Check-AzureCLI {
    Write-Status "Checking Azure CLI..."
    
    if (-not (Get-Command az -ErrorAction SilentlyContinue)) {
        Write-Error "Azure CLI is not installed. Please install it first:"
        Write-Host "https://docs.microsoft.com/en-us/cli/azure/install-azure-cli"
        exit 1
    }
    
    try {
        $account = az account show 2>$null | ConvertFrom-Json
        if (-not $account) {
            Write-Error "Not authenticated to Azure. Please run: az login"
            exit 1
        }
        
        # Get current subscription and tenant
        $script:SUBSCRIPTION_ID = $account.id
        $script:TENANT_ID = $account.tenantId
        
        Write-Status "Azure CLI authenticated. Subscription: $SUBSCRIPTION_ID"
    }
    catch {
        Write-Error "Failed to get Azure account information"
        exit 1
    }
}

# Function to create resource group
function Create-ResourceGroup {
    Write-Header "Creating Resource Group"
    
    try {
        $existingGroup = az group show --name $RESOURCE_GROUP --query id -o tsv 2>$null
        if ($existingGroup) {
            Write-Warning "Resource group $RESOURCE_GROUP already exists"
        }
        else {
            Write-Status "Creating resource group $RESOURCE_GROUP in $LOCATION..."
            az group create --name $RESOURCE_GROUP --location $LOCATION
            Write-Status "Resource group created successfully"
        }
    }
    catch {
        Write-Error "Failed to create resource group: $_"
        exit 1
    }
}

# Function to create Azure Container Registry
function Create-ACR {
    Write-Header "Creating Azure Container Registry"
    
    try {
        $existingACR = az acr show --name $ACR_NAME --resource-group $RESOURCE_GROUP --query id -o tsv 2>$null
        if ($existingACR) {
            Write-Warning "ACR $ACR_NAME already exists"
        }
        else {
            Write-Status "Creating ACR $ACR_NAME..."
            az acr create --resource-group $RESOURCE_GROUP --name $ACR_NAME --sku Standard --admin-enabled true
            Write-Status "ACR created successfully"
        }
        
        # Get ACR login server
        $ACR_LOGIN_SERVER = az acr show --name $ACR_NAME --resource-group $RESOURCE_GROUP --query loginServer -o tsv
        Write-Status "ACR Login Server: $ACR_LOGIN_SERVER"
    }
    catch {
        Write-Error "Failed to create ACR: $_"
        exit 1
    }
}

# Function to create Azure Key Vault
function Create-KeyVault {
    Write-Header "Creating Azure Key Vault"
    
    try {
        $existingKV = az keyvault show --name $KEY_VAULT_NAME --resource-group $RESOURCE_GROUP --query id -o tsv 2>$null
        if ($existingKV) {
            Write-Warning "Key Vault $KEY_VAULT_NAME already exists"
        }
        else {
            Write-Status "Creating Key Vault $KEY_VAULT_NAME..."
            az keyvault create --resource-group $RESOURCE_GROUP --name $KEY_VAULT_NAME --location $LOCATION --enable-rbac-authorization true
            Write-Status "Key Vault created successfully"
        }
    }
    catch {
        Write-Error "Failed to create Key Vault: $_"
        exit 1
    }
}

# Function to create AKS cluster
function Create-AKSCluster {
    Write-Header "Creating AKS Cluster"
    
    try {
        $existingCluster = az aks show --name $CLUSTER_NAME --resource-group $RESOURCE_GROUP --query id -o tsv 2>$null
        if ($existingCluster) {
            Write-Warning "AKS cluster $CLUSTER_NAME already exists"
        }
        else {
            Write-Status "Creating AKS cluster $CLUSTER_NAME..."
            
            # Get ACR login server
            $ACR_LOGIN_SERVER = az acr show --name $ACR_NAME --resource-group $RESOURCE_GROUP --query loginServer -o tsv
            
            az aks create `
                --resource-group $RESOURCE_GROUP `
                --name $CLUSTER_NAME `
                --location $LOCATION `
                --node-count 3 `
                --node-vm-size Standard_D4s_v3 `
                --enable-addons monitoring `
                --enable-managed-identity `
                --enable-oidc-issuer `
                --enable-workload-identity `
                --attach-acr $ACR_LOGIN_SERVER `
                --network-plugin azure `
                --network-policy azure `
                --generate-ssh-keys
            
            Write-Status "AKS cluster created successfully"
        }
    }
    catch {
        Write-Error "Failed to create AKS cluster: $_"
        exit 1
    }
}

# Function to configure workload identity
function Configure-WorkloadIdentity {
    Write-Header "Configuring Workload Identity"
    
    try {
        # Get cluster OIDC issuer URL
        $OIDC_ISSUER = az aks show --name $CLUSTER_NAME --resource-group $RESOURCE_GROUP --query "oidcIssuerProfile.issuerUrl" -o tsv
        Write-Status "OIDC Issuer: $OIDC_ISSUER"
        
        # Create user-assigned managed identity for SafetyAmp
        Write-Status "Creating managed identity for SafetyAmp..."
        az identity create --resource-group $RESOURCE_GROUP --name "safetyamp-identity"
        
        # Get managed identity details
        $USER_ASSIGNED_CLIENT_ID = az identity show --name "safetyamp-identity" --resource-group $RESOURCE_GROUP --query clientId -o tsv
        $USER_ASSIGNED_PRINCIPAL_ID = az identity show --name "safetyamp-identity" --resource-group $RESOURCE_GROUP --query principalId -o tsv
        
        Write-Status "Managed Identity Client ID: $USER_ASSIGNED_CLIENT_ID"
        Write-Status "Managed Identity Principal ID: $USER_ASSIGNED_PRINCIPAL_ID"
        
        # Grant Key Vault access to managed identity
        Write-Status "Granting Key Vault access to managed identity..."
        az keyvault set-policy `
            --name $KEY_VAULT_NAME `
            --resource-group $RESOURCE_GROUP `
            --object-id $USER_ASSIGNED_PRINCIPAL_ID `
            --secret-permissions get list `
            --certificate-permissions get list
        
        # Create federated identity credential
        Write-Status "Creating federated identity credential..."
        az identity federated-credential create `
            --name "safetyamp-federated-credential" `
            --identity-name "safetyamp-identity" `
            --resource-group $RESOURCE_GROUP `
            --issuer $OIDC_ISSUER `
            --subject "system:serviceaccount:safety-amp:safety-amp-workload-identity-sa" `
            --audience api://AzureADTokenExchange
    }
    catch {
        Write-Error "Failed to configure workload identity: $_"
        exit 1
    }
}

# Function to get cluster credentials
function Get-ClusterCredentials {
    Write-Header "Getting Cluster Credentials"
    
    try {
        Write-Status "Getting AKS credentials..."
        az aks get-credentials --resource-group $RESOURCE_GROUP --name $CLUSTER_NAME --overwrite-existing
        
        Write-Status "Testing cluster connection..."
        kubectl cluster-info
        Write-Status "Cluster connection successful"
    }
    catch {
        Write-Error "Failed to get cluster credentials: $_"
        exit 1
    }
}

# Function to install cluster add-ons
function Install-ClusterAddons {
    Write-Header "Installing Cluster Add-ons"
    
    try {
        # Install NGINX Ingress Controller
        Write-Status "Installing NGINX Ingress Controller..."
        kubectl create namespace ingress-nginx
        helm repo add ingress-nginx https://kubernetes.github.io/ingress-nginx
        helm repo update
        helm install ingress-nginx ingress-nginx/ingress-nginx `
            --namespace ingress-nginx `
            --set controller.replicaCount=2 `
            --set controller.nodeSelector."kubernetes\.io/os"=linux `
            --set defaultBackend.nodeSelector."kubernetes\.io/os"=linux
        
        # Install cert-manager
        Write-Status "Installing cert-manager..."
        kubectl create namespace cert-manager
        helm repo add jetstack https://charts.jetstack.io
        helm repo update
        helm install cert-manager jetstack/cert-manager `
            --namespace cert-manager `
            --set installCRDs=true `
            --set replicaCount=2
        
        # Install Prometheus Operator
        Write-Status "Installing Prometheus Operator..."
        kubectl create namespace monitoring
        helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
        helm repo update
        helm install prometheus prometheus-community/kube-prometheus-stack `
            --namespace monitoring `
            --set grafana.enabled=true `
            --set prometheus.prometheusSpec.replicaCount=2
    }
    catch {
        Write-Error "Failed to install cluster add-ons: $_"
        exit 1
    }
}

# Function to build and push Docker image
function Build-AndPushImage {
    Write-Header "Building and Pushing Docker Image"
    
    try {
        # Get ACR login server
        $ACR_LOGIN_SERVER = az acr show --name $ACR_NAME --resource-group $RESOURCE_GROUP --query loginServer -o tsv
        
        Write-Status "Logging into ACR..."
        az acr login --name $ACR_NAME
        
        Write-Status "Building Docker image..."
        docker build -t "$ACR_LOGIN_SERVER/safety-amp-agent:latest" .
        
        Write-Status "Pushing Docker image..."
        docker push "$ACR_LOGIN_SERVER/safety-amp-agent:latest"
        
        Write-Status "Image pushed successfully: $ACR_LOGIN_SERVER/safety-amp-agent:latest"
    }
    catch {
        Write-Error "Failed to build and push image: $_"
        exit 1
    }
}

# Function to update Kubernetes manifests
function Update-K8sManifests {
    Write-Header "Updating Kubernetes Manifests"
    
    try {
        # Get ACR login server
        $ACR_LOGIN_SERVER = az acr show --name $ACR_NAME --resource-group $RESOURCE_GROUP --query loginServer -o tsv
        
        # Get managed identity client ID
        $USER_ASSIGNED_CLIENT_ID = az identity show --name "safetyamp-identity" --resource-group $RESOURCE_GROUP --query clientId -o tsv
        
        # Get Key Vault URL
        $KEY_VAULT_URL = "https://$KEY_VAULT_NAME.vault.azure.net/"
        
        Write-Status "Updating SafetyAmp deployment with Azure-specific values..."
        
        # Create a backup of the original file
        Copy-Item "k8s/safety-amp/safety-amp-deployment.yaml" "k8s/safety-amp/safety-amp-deployment.yaml.backup"
        
        # Read the file content
        $content = Get-Content "k8s/safety-amp/safety-amp-deployment.yaml" -Raw
        
        # Replace values
        $content = $content -replace "iiusacr\.azurecr\.io/safety-amp-agent:latest", "$ACR_LOGIN_SERVER/safety-amp-agent:latest"
        $content = $content -replace "a2bcb3ce-a89b-43af-804c-e8029e0bafb4", $USER_ASSIGNED_CLIENT_ID
        $content = $content -replace "953922e6-5370-4a01-a3d5-773a30df726b", $TENANT_ID
        $content = $content -replace "https://your-keyvault\.vault\.azure\.net/", $KEY_VAULT_URL
        
        # Write back to file
        Set-Content "k8s/safety-amp/safety-amp-deployment.yaml" $content
        
        Write-Status "Kubernetes manifests updated successfully"
    }
    catch {
        Write-Error "Failed to update Kubernetes manifests: $_"
        exit 1
    }
}

# Function to deploy to AKS
function Deploy-ToAKS {
    Write-Header "Deploying to AKS"
    
    try {
        Write-Status "Creating namespaces..."
        kubectl apply -f k8s/namespaces/namespaces.yaml
        
        Write-Status "Waiting for namespaces to be ready..."
        kubectl wait --for=condition=Active namespace/safety-amp --timeout=60s
        
        Write-Status "Deploying SafetyAmp application..."
        kubectl apply -f k8s/safety-amp/safety-amp-deployment.yaml
        
        Write-Status "Waiting for deployment to be ready..."
        kubectl wait --for=condition=Available deployment/safety-amp-agent -n safety-amp --timeout=300s
        
        Write-Status "Deployment completed successfully"
    }
    catch {
        Write-Error "Failed to deploy to AKS: $_"
        exit 1
    }
}

# Function to show deployment status
function Show-Status {
    Write-Header "Deployment Status"
    
    Write-Status "Resource Group: $RESOURCE_GROUP"
    Write-Status "AKS Cluster: $CLUSTER_NAME"
    Write-Status "ACR: $ACR_NAME"
    Write-Status "Key Vault: $KEY_VAULT_NAME"
    
    Write-Host ""
    Write-Status "AKS Cluster Status:"
    kubectl get nodes
    
    Write-Host ""
    Write-Status "SafetyAmp Pods:"
    kubectl get pods -n safety-amp
    
    Write-Host ""
    Write-Status "Services:"
    kubectl get services -n safety-amp
    
    Write-Host ""
    Write-Status "Ingress:"
    kubectl get ingress --all-namespaces
}

# Function to show next steps
function Show-NextSteps {
    Write-Header "Next Steps"
    
    Write-Host ""
    Write-Status "1. Add secrets to Key Vault:"
    Write-Host "   az keyvault secret set --vault-name $KEY_VAULT_NAME --name safetyamp-api-key --value <your-api-key>"
    Write-Host "   az keyvault secret set --vault-name $KEY_VAULT_NAME --name samsara-api-key --value <your-api-key>"
    Write-Host "   az keyvault secret set --vault-name $KEY_VAULT_NAME --name viewpoint-connection-string --value <your-connection-string>"
    Write-Host ""
    
    Write-Status "2. Update DNS records for your domain to point to the LoadBalancer IP"
    Write-Host ""
    
    Write-Status "3. Monitor the application:"
    Write-Host "   kubectl logs -f deployment/safety-amp-agent -n safety-amp"
    Write-Host ""
    
    Write-Status "4. Access the application:"
    Write-Host "   kubectl port-forward service/safety-amp-service 8080:8080 -n safety-amp"
    Write-Host "   Then visit: http://localhost:8080/health"
    Write-Host ""
    
    Write-Warning "Remember to secure your secrets and never commit them to version control!"
}

# Main function
function Main {
    Write-Header "Azure AKS Setup for SafetyAmp Integration"
    Write-Host ""
    
    # Check prerequisites
    Check-AzureCLI
    
    # Get cluster credentials (connect to existing cluster)
    Get-ClusterCredentials
    
    # Create Key Vault if it doesn't exist
    Create-KeyVault
    
    # Configure workload identity for existing cluster
    Configure-WorkloadIdentity
    
    # Install add-ons (skip if already installed)
    Install-ClusterAddons
    
    # Build and push image
    Build-AndPushImage
    
    # Update manifests
    Update-K8sManifests
    
    # Deploy application
    Deploy-ToAKS
    
    # Show status and next steps
    Show-Status
    Show-NextSteps
}

# Handle command line arguments
switch ($Command.ToLower()) {
    "setup" {
        Main
    }
    "status" {
        Show-Status
    }
    "deploy" {
        Deploy-ToAKS
    }
    "build" {
        Build-AndPushImage
    }
    "help" {
        Write-Host "Usage: .\azure-aks-setup.ps1 [setup|status|deploy|build|help]"
        Write-Host ""
        Write-Host "Commands:"
        Write-Host "  setup   - Complete AKS setup and deployment (default)"
        Write-Host "  status  - Show deployment status"
        Write-Host "  deploy  - Deploy application to existing AKS cluster"
        Write-Host "  build   - Build and push Docker image only"
        Write-Host "  help    - Show this help message"
    }
    default {
        Write-Error "Unknown command: $Command"
        Write-Host "Use '.\azure-aks-setup.ps1 help' for usage information."
        exit 1
    }
} 