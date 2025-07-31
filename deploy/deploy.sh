#!/bin/bash

# AKS Deployment Script for dev-aks cluster
# This script deploys all applications to your AKS cluster

set -e

# Configuration
CLUSTER_NAME="dev-aks"
RESOURCE_GROUP="dev-group"
NAMESPACE_ORDER=("cert-manager" "ingress-nginx" "n8n" "safety-amp" "samsara")

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
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

# Function to check if kubectl is available and configured
check_kubectl() {
    print_status "Checking kubectl configuration..."
    
    if ! command -v kubectl &> /dev/null; then
        print_error "kubectl is not installed. Please install kubectl first."
        exit 1
    fi
    
    if ! kubectl cluster-info &> /dev/null; then
        print_error "kubectl is not configured or cluster is not accessible."
        print_status "Please run: az aks get-credentials --resource-group $RESOURCE_GROUP --name $CLUSTER_NAME"
        exit 1
    fi
    
    print_status "kubectl is configured and cluster is accessible."
}

# Function to check if user is authenticated to Azure
check_azure_auth() {
    print_status "Checking Azure authentication..."
    
    if ! command -v az &> /dev/null; then
        print_error "Azure CLI is not installed. Please install Azure CLI first."
        exit 1
    fi
    
    if ! az account show &> /dev/null; then
        print_error "Not authenticated to Azure. Please run: az login"
        exit 1
    fi
    
    print_status "Azure CLI is authenticated."
}

# Function to create namespaces
create_namespaces() {
    print_status "Creating namespaces..."
    kubectl apply -f k8s/namespaces/namespaces.yaml
    
    # Wait for namespaces to be ready
    for ns in "${NAMESPACE_ORDER[@]}"; do
        kubectl wait --for=condition=Active namespace/$ns --timeout=60s
    done
    
    print_status "All namespaces created successfully."
}

# Function to deploy cert-manager
deploy_cert_manager() {
    print_status "Deploying cert-manager..."
    
    # Install cert-manager CRDs first
    kubectl apply -f https://github.com/cert-manager/cert-manager/releases/download/v1.13.2/cert-manager.crds.yaml
    
    # Apply cert-manager configuration
    kubectl apply -f k8s/cert-manager/cert-manager.yaml
    
    # Wait for cert-manager to be ready
    kubectl wait --for=condition=Available deployment/cert-manager -n cert-manager --timeout=300s
    
    print_status "cert-manager deployed successfully."
}

# Function to deploy NGINX Ingress Controller
deploy_nginx_ingress() {
    print_status "Deploying NGINX Ingress Controller..."
    
    kubectl apply -f k8s/ingress/nginx-ingress-controller.yaml
    
    # Wait for ingress controller to be ready
    kubectl wait --for=condition=Available deployment/nginx-ingress-controller -n ingress-nginx --timeout=300s
    
    # Wait for LoadBalancer service to get external IP
    print_status "Waiting for LoadBalancer to get external IP..."
    kubectl wait --for=jsonpath='{.status.loadBalancer.ingress}' service/ingress-nginx -n ingress-nginx --timeout=300s
    
    # Display the external IP
    EXTERNAL_IP=$(kubectl get service ingress-nginx -n ingress-nginx -o jsonpath='{.status.loadBalancer.ingress[0].ip}')
    print_status "NGINX Ingress Controller deployed successfully."
    print_status "External IP: $EXTERNAL_IP"
    print_warning "Please update your DNS records to point n8n.dev.ii-us.com to $EXTERNAL_IP"
}

# Function to deploy RBAC configurations
deploy_rbac() {
    print_status "Deploying RBAC configurations..."
    kubectl apply -f k8s/rbac/service-accounts.yaml
    print_status "RBAC configurations deployed successfully."
}

# Function to deploy applications
deploy_applications() {
    print_status "Deploying applications..."
    
    # Deploy n8n
    print_status "Deploying n8n..."
    kubectl apply -f k8s/n8n/n8n-deployment.yaml
    
    # Deploy SafetyAmp
    print_status "Deploying SafetyAmp agent..."
    kubectl apply -f k8s/safety-amp/safety-amp-deployment.yaml
    
    # Deploy Samsara
    print_status "Deploying Samsara integration..."
    kubectl apply -f k8s/samsara/samsara-deployment.yaml
    
    print_status "All applications deployed successfully."
}

# Function to deploy monitoring
deploy_monitoring() {
    print_status "Deploying monitoring configuration..."
    kubectl apply -f k8s/monitoring/monitoring.yaml
    print_status "Monitoring configuration deployed successfully."
}

# Function to wait for deployments to be ready
wait_for_deployments() {
    print_status "Waiting for all deployments to be ready..."
    
    # Wait for n8n
    kubectl wait --for=condition=Available deployment/n8n -n n8n --timeout=300s
    
    # Wait for SafetyAmp (if image is available)
    if kubectl get deployment safety-amp-agent -n safety-amp &> /dev/null; then
        kubectl wait --for=condition=Available deployment/safety-amp-agent -n safety-amp --timeout=300s
    else
        print_warning "SafetyAmp deployment not found or image not available."
    fi
    
    # Wait for Samsara (if image is available)
    if kubectl get deployment samsara-integration -n samsara &> /dev/null; then
        kubectl wait --for=condition=Available deployment/samsara-integration -n samsara --timeout=300s
    else
        print_warning "Samsara deployment not found or image not available."
    fi
    
    print_status "All available deployments are ready."
}

# Function to display deployment status
show_status() {
    print_status "Deployment Status:"
    echo ""
    
    print_status "Namespaces:"
    kubectl get namespaces
    echo ""
    
    print_status "Ingress Controller:"
    kubectl get pods -n ingress-nginx
    kubectl get service ingress-nginx -n ingress-nginx
    echo ""
    
    print_status "n8n:"
    kubectl get pods -n n8n
    kubectl get service -n n8n
    kubectl get ingress -n n8n
    echo ""
    
    print_status "SafetyAmp:"
    kubectl get pods -n safety-amp
    echo ""
    
    print_status "Samsara:"
    kubectl get pods -n samsara
    echo ""
    
    print_status "Certificates:"
    kubectl get certificates --all-namespaces
    echo ""
}

# Function to show next steps
show_next_steps() {
    echo ""
    print_status "=== DEPLOYMENT COMPLETE ==="
    echo ""
    print_status "Next Steps:"
    echo "1. Update DNS records to point n8n.dev.ii-us.com to the LoadBalancer IP"
    echo "2. Update secrets in the following files with actual values:"
    echo "   - k8s/n8n/n8n-deployment.yaml (n8n-secrets)"
    echo "   - k8s/safety-amp/safety-amp-deployment.yaml (safety-amp-secrets)"
    echo "   - k8s/samsara/samsara-deployment.yaml (samsara-secrets)"
    echo "   - k8s/monitoring/monitoring.yaml (azure-monitor-secrets)"
    echo "3. Update container images in deployment files with your actual images"
    echo "4. Apply updated configurations: kubectl apply -f <updated-file>"
    echo ""
    print_status "Access your applications:"
    echo "- n8n: https://n8n.dev.ii-us.com (after DNS update)"
    echo "- Kubernetes Dashboard: kubectl proxy"
    echo ""
    print_warning "Remember to secure your secrets and never commit them to version control!"
}

# Main deployment function
main() {
    print_status "Starting AKS deployment for $CLUSTER_NAME..."
    echo ""
    
    # Pre-deployment checks
    check_azure_auth
    check_kubectl
    
    # Deploy infrastructure components
    create_namespaces
    deploy_cert_manager
    deploy_nginx_ingress
    deploy_rbac
    deploy_monitoring
    
    # Deploy applications
    deploy_applications
    
    # Wait for deployments
    wait_for_deployments
    
    # Show status
    show_status
    
    # Show next steps
    show_next_steps
}

# Handle command line arguments
case "${1:-deploy}" in
    "deploy")
        main
        ;;
    "status")
        show_status
        ;;
    "cleanup")
        print_warning "This will delete all deployments. Are you sure? (y/N)"
        read -r response
        if [[ "$response" =~ ^([yY][eE][sS]|[yY])$ ]]; then
            print_status "Cleaning up deployments..."
            kubectl delete -f k8s/samsara/samsara-deployment.yaml --ignore-not-found=true
            kubectl delete -f k8s/safety-amp/safety-amp-deployment.yaml --ignore-not-found=true
            kubectl delete -f k8s/n8n/n8n-deployment.yaml --ignore-not-found=true
            kubectl delete -f k8s/monitoring/monitoring.yaml --ignore-not-found=true
            kubectl delete -f k8s/rbac/service-accounts.yaml --ignore-not-found=true
            kubectl delete -f k8s/ingress/nginx-ingress-controller.yaml --ignore-not-found=true
            kubectl delete -f k8s/cert-manager/cert-manager.yaml --ignore-not-found=true
            kubectl delete -f k8s/namespaces/namespaces.yaml --ignore-not-found=true
            print_status "Cleanup complete."
        else
            print_status "Cleanup cancelled."
        fi
        ;;
    "help"|"-h"|"--help")
        echo "Usage: $0 [deploy|status|cleanup|help]"
        echo ""
        echo "Commands:"
        echo "  deploy   - Deploy all applications (default)"
        echo "  status   - Show deployment status"
        echo "  cleanup  - Remove all deployments"
        echo "  help     - Show this help message"
        ;;
    *)
        print_error "Unknown command: $1"
        echo "Use '$0 help' for usage information."
        exit 1
        ;;
esac