# Simplified Deployment Script for SafetyAmp Integration
# This script only handles building, pushing, and deploying the application
# Assumes all Azure resources already exist

param(
    [string]$Command = "deploy"
)

# Configuration - Update these values for your environment
$RESOURCE_GROUP = "rg_prod"    # Your existing resource group
$LOCATION = "southcentralus"
$CLUSTER_NAME = "dev-aks"      # Your existing AKS cluster
$ACR_NAME = "iiusacr"          # Your existing ACR
$KEY_VAULT_NAME = "iius-akv"   # Your existing Key Vault

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
        
        Write-Status "Azure CLI authenticated. Subscription: $($account.id)"
    }
    catch {
        Write-Error "Failed to get Azure account information"
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

# Function to build and push Docker image
function Build-AndPushImage {
    Write-Header "Building and Pushing Docker Image"
    
    try {
        # Get ACR login server
        $ACR_LOGIN_SERVER = az acr show --name $ACR_NAME --resource-group $RESOURCE_GROUP --query loginServer -o tsv
        Write-Status "ACR Login Server: $ACR_LOGIN_SERVER"
        
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
        
        # Get Key Vault URL
        $KEY_VAULT_URL = "https://$KEY_VAULT_NAME.vault.azure.net/"
        
        Write-Status "Updating SafetyAmp deployment with Azure-specific values..."
        
        # Create a backup of the original file
        if (Test-Path "k8s/safety-amp/safety-amp-deployment.yaml") {
            Copy-Item "k8s/safety-amp/safety-amp-deployment.yaml" "k8s/safety-amp/safety-amp-deployment.yaml.backup"
        }
        
        # Read the file content
        $content = Get-Content "k8s/safety-amp/safety-amp-deployment.yaml" -Raw
        
        # Replace values
        $content = $content -replace "iiusacr\.azurecr\.io/safety-amp-agent:latest", "$ACR_LOGIN_SERVER/safety-amp-agent:latest"
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
    
    Write-Status "2. Monitor the application:"
    Write-Host "   kubectl logs -f deployment/safety-amp-agent -n safety-amp"
    Write-Host ""
    
    Write-Status "3. Access the application:"
    Write-Host "   kubectl port-forward service/safety-amp-service 8080:8080 -n safety-amp"
    Write-Host "   Then visit: http://localhost:8080/health"
    Write-Host ""
    
    Write-Warning "Remember to secure your secrets and never commit them to version control!"
}

# Main function
function Main {
    Write-Header "SafetyAmp Integration Deployment"
    Write-Host ""
    
    # Check prerequisites
    Check-AzureCLI
    
    # Get cluster credentials
    Get-ClusterCredentials
    
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
    "deploy" {
        Main
    }
    "build" {
        Check-AzureCLI
        Build-AndPushImage
    }
    "status" {
        Check-AzureCLI
        Get-ClusterCredentials
        Show-Status
    }
    "help" {
        Write-Host "Usage: .\deploy-only.ps1 [deploy|build|status|help]"
        Write-Host ""
        Write-Host "Commands:"
        Write-Host "  deploy  - Build, push, and deploy application (default)"
        Write-Host "  build   - Build and push Docker image only"
        Write-Host "  status  - Show deployment status"
        Write-Host "  help    - Show this help message"
    }
    default {
        Write-Error "Unknown command: $Command"
        Write-Host "Use '.\deploy-only.ps1 help' for usage information."
        exit 1
    }
} 