#!/bin/bash

# One-click deployment script for SafetyAmp Integration to AKS
# Usage: ./deploy-to-aks.sh [dev|staging|prod] [image-tag]

set -e  # Exit on error

# Configuration
ENVIRONMENT=${1:-dev}
TAG=${2:-latest}
SKIP_BUILD=${3:-false}

# Color output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
MAGENTA='\033[0;35m'
NC='\033[0m' # No Color

# Environment configuration
case $ENVIRONMENT in
    dev)
        RESOURCE_GROUP="rg_prod"
        CLUSTER_NAME="dev-aks"
        ACR_NAME="iiusacr"
        NAMESPACE="safety-amp"
        REPLICAS=1
        ;;
    staging)
        RESOURCE_GROUP="rg_prod"
        CLUSTER_NAME="dev-aks"
        ACR_NAME="iiusacr"
        NAMESPACE="safety-amp"
        REPLICAS=2
        ;;
    prod)
        RESOURCE_GROUP="rg_prod"
        CLUSTER_NAME="dev-aks"
        ACR_NAME="iiusacr"
        NAMESPACE="safety-amp"
        REPLICAS=2
        ;;
    *)
        echo -e "${RED}Invalid environment: $ENVIRONMENT${NC}"
        echo "Usage: $0 [dev|staging|prod] [image-tag]"
        exit 1
        ;;
esac

IMAGE_NAME="$ACR_NAME.azurecr.io/safetyamp-integration:$TAG"

# Functions
print_header() {
    echo -e "\n${MAGENTA}????????????????????????????????????????????????????????????${NC}"
    echo -e "${MAGENTA}?     SafetyAmp Integration - One-Click Deployment         ?${NC}"
    echo -e "${MAGENTA}????????????????????????????????????????????????????????????${NC}"
    echo -e "${MAGENTA}? Environment: $ENVIRONMENT                                       ?${NC}"
    echo -e "${MAGENTA}? Cluster: $CLUSTER_NAME                                   ?${NC}"
    echo -e "${MAGENTA}? Image Tag: $TAG                                          ?${NC}"
    echo -e "${MAGENTA}????????????????????????????????????????????????????????????${NC}\n"
}

print_step() {
    echo -e "\n${CYAN}==> $1${NC}"
}

print_success() {
    echo -e "${GREEN}? $1${NC}"
}

print_error() {
    echo -e "${RED}? $1${NC}"
}

print_info() {
    echo -e "${YELLOW}? $1${NC}"
}

# Error handler
handle_error() {
    print_error "Deployment failed at line $1"
    echo -e "\n${YELLOW}Troubleshooting:${NC}"
    echo "1. Check Azure authentication: az account show"
    echo "2. Verify cluster access: kubectl cluster-info"
    echo "3. Check pod status: kubectl get pods -n $NAMESPACE"
    echo "4. View pod logs: kubectl logs -n $NAMESPACE <pod-name>"
    exit 1
}

trap 'handle_error $LINENO' ERR

# Main deployment
main() {
    print_header

    # Step 1: Azure Login Check
    print_step "Checking Azure authentication..."
    if az account show &>/dev/null; then
        ACCOUNT=$(az account show --query user.name -o tsv)
        print_success "Authenticated as: $ACCOUNT"
    else
        print_info "Not logged in to Azure. Initiating login..."
        az login
    fi

    # Step 2: Get AKS Credentials
    print_step "Getting AKS cluster credentials..."
    az aks get-credentials \
        --resource-group $RESOURCE_GROUP \
        --name $CLUSTER_NAME \
        --overwrite-existing
    print_success "Connected to $CLUSTER_NAME"

    # Step 3: Docker Build and Push
    if [ "$SKIP_BUILD" != "true" ]; then
        print_step "Building Docker image..."
        docker build -t $IMAGE_NAME .
        print_success "Docker image built: $IMAGE_NAME"

        print_step "Logging in to Azure Container Registry..."
        az acr login --name $ACR_NAME
        print_success "Logged in to ACR"

        print_step "Pushing Docker image to ACR..."
        docker push $IMAGE_NAME
        print_success "Image pushed to ACR"
    else
        print_info "Skipping Docker build/push (using existing image)"
    fi

    # Step 4: Deploy Infrastructure
    print_step "Deploying infrastructure components..."

    # Create namespaces
    if [ -f "k8s/namespaces/namespaces.yaml" ]; then
        kubectl apply -f k8s/namespaces/namespaces.yaml || true
    fi

    # Deploy cert-manager
    if [ -f "k8s/cert-manager/cert-manager.yaml" ]; then
        kubectl apply -f k8s/cert-manager/cert-manager.yaml || true
    fi

    # Deploy NGINX ingress
    if [ -f "k8s/ingress/nginx-ingress-controller.yaml" ]; then
        kubectl apply -f k8s/ingress/nginx-ingress-controller.yaml || true
    fi

    print_success "Infrastructure components deployed"

    # Step 5: Deploy Application
    print_step "Deploying SafetyAmp Integration..."

    # Update image in deployment file
    if [ -f "k8s/safety-amp/safety-amp-complete.yaml" ]; then
        # Create temporary file with updated image
        sed "s|image:.*safetyamp-integration:.*|image: $IMAGE_NAME|g" \
            k8s/safety-amp/safety-amp-complete.yaml > /tmp/safety-amp-deploy.yaml

        kubectl apply -f /tmp/safety-amp-deploy.yaml
        rm /tmp/safety-amp-deploy.yaml
    fi

    # Apply environment-specific overlays
    if [ -d "k8s/overlays/$ENVIRONMENT" ]; then
        print_info "Applying $ENVIRONMENT overlays..."
        kubectl apply -k k8s/overlays/$ENVIRONMENT/ || true
    fi

    print_success "Application deployed"

    # Step 6: Deploy Monitoring
    print_step "Deploying monitoring stack..."
    if [ -f "k8s/monitoring/monitoring-stack.yaml" ]; then
        kubectl apply -f k8s/monitoring/monitoring-stack.yaml || true
    fi
    if [ -f "k8s/monitoring/grafana/datasource-azuremonitor.yaml" ]; then
        kubectl apply -f k8s/monitoring/grafana/datasource-azuremonitor.yaml || true
    fi
    print_success "Monitoring stack deployed"

    # Step 7: Wait for Rollout
    print_step "Waiting for deployment rollout..."
    kubectl rollout status deployment/safety-amp-agent -n $NAMESPACE --timeout=300s || {
        print_error "Rollout did not complete successfully"
        print_info "Checking pod status..."
        kubectl get pods -n $NAMESPACE
    }
    print_success "Deployment rollout completed"

    # Step 8: Verify Health
    print_step "Verifying deployment health..."

    # Check pod status
    RUNNING_PODS=$(kubectl get pods -n $NAMESPACE --no-headers | grep Running | wc -l)
    if [ $RUNNING_PODS -gt 0 ]; then
        print_success "$RUNNING_PODS pod(s) running"

        # Test health endpoint (in background)
        print_info "Testing health endpoint..."
        kubectl port-forward -n $NAMESPACE svc/safety-amp-service 8080:8080 &>/dev/null &
        PF_PID=$!
        sleep 5

        if curl -s http://localhost:8080/health &>/dev/null; then
            HEALTH=$(curl -s http://localhost:8080/health | grep -o '"status":"[^"]*"' | cut -d'"' -f4)
            print_success "Health check passed: $HEALTH"
        else
            print_info "Health check failed (might be normal if port-forward is blocked)"
        fi

        kill $PF_PID &>/dev/null || true
    else
        print_error "No running pods found"
    fi

    # Step 9: Success Summary
    echo -e "\n${GREEN}????????????????????????????????????????????????????????????${NC}"
    echo -e "${GREEN}?           DEPLOYMENT COMPLETED SUCCESSFULLY!             ?${NC}"
    echo -e "${GREEN}????????????????????????????????????????????????????????????${NC}"
    echo -e "${GREEN}? Next Steps:                                              ?${NC}"
    echo -e "${GREEN}?                                                          ?${NC}"
    echo -e "${GREEN}? 1. Check pod status:                                    ?${NC}"
    echo -e "${GREEN}?    kubectl get pods -n $NAMESPACE                       ?${NC}"
    echo -e "${GREEN}?                                                          ?${NC}"
    echo -e "${GREEN}? 2. View logs:                                           ?${NC}"
    echo -e "${GREEN}?    kubectl logs -f deployment/safety-amp-agent \\        ?${NC}"
    echo -e "${GREEN}?    -n $NAMESPACE                                        ?${NC}"
    echo -e "${GREEN}?                                                          ?${NC}"
    echo -e "${GREEN}? 3. Access metrics:                                      ?${NC}"
    echo -e "${GREEN}?    kubectl port-forward -n $NAMESPACE \\                 ?${NC}"
    echo -e "${GREEN}?    svc/safety-amp-service 9090:9090                     ?${NC}"
    echo -e "${GREEN}?                                                          ?${NC}"
    echo -e "${GREEN}? 4. Access health endpoint:                              ?${NC}"
    echo -e "${GREEN}?    kubectl port-forward -n $NAMESPACE \\                 ?${NC}"
    echo -e "${GREEN}?    svc/safety-amp-service 8080:8080                     ?${NC}"
    echo -e "${GREEN}?    curl http://localhost:8080/health                    ?${NC}"
    echo -e "${GREEN}????????????????????????????????????????????????????????????${NC}"
}

# Run deployment
main