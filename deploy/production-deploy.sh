#!/bin/bash

# SafetyAmp Integration - Production Deployment Script
# Implements phased rollout strategy for 5000 records/hour processing

set -euo pipefail

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
ACR_NAME="${ACR_NAME:-iiusacr.azurecr.io}"
IMAGE_TAG="${IMAGE_TAG:-v1.0.0}"
NAMESPACE="safety-amp"
KEY_VAULT_NAME="${KEY_VAULT_NAME:-kv-safety-amp-dev}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Logging functions
log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check prerequisites
check_prerequisites() {
    log_info "Checking prerequisites..."
    
    # Check required tools
    for tool in kubectl docker az; do
        if ! command -v $tool &> /dev/null; then
            log_error "$tool is required but not installed"
            exit 1
        fi
    done
    
    # Check kubectl context
    CONTEXT=$(kubectl config current-context)
    log_info "Using kubectl context: $CONTEXT"
    
    # Check Azure CLI login
    if ! az account show &> /dev/null; then
        log_error "Please login to Azure CLI first: az login"
        exit 1
    fi
    
    log_info "Prerequisites check passed"
}

# Phase 1: Infrastructure Setup
phase1_infrastructure() {
    log_info "=== Phase 1: Infrastructure Setup ==="
    
    # Build and push container image
    log_info "Building container image..."
    cd "$PROJECT_ROOT"
    docker build -t "${ACR_NAME}/safety-amp-agent:${IMAGE_TAG}" .
    
    log_info "Pushing image to ACR..."
    docker push "${ACR_NAME}/safety-amp-agent:${IMAGE_TAG}"
    
    # Update image references in deployment files
    log_info "Updating image references..."
    find k8s/ -name "*.yaml" -exec sed -i "s|iiusacr\.azurecr\.io/safety-amp-agent:latest|${ACR_NAME}/safety-amp-agent:${IMAGE_TAG}|g" {} \;
    
    # Deploy infrastructure
    log_info "Deploying namespaces..."
    kubectl apply -f k8s/namespaces/namespaces.yaml
    
    log_info "Deploying RBAC..."
    kubectl apply -f k8s/rbac/service-accounts.yaml
    
    log_info "Phase 1 completed successfully"
}

# Phase 2: Secrets & Configuration
phase2_secrets() {
    log_info "=== Phase 2: Secrets & Configuration ==="
    
    # Verify Key Vault secrets exist
    log_info "Verifying Key Vault secrets..."
    required_secrets=(
        "SAFETYAMP-TOKEN"
        "MS-GRAPH-CLIENT-SECRET"
        "SAMSARA-API-KEY"
        "SQL-SERVER"
        "SQL-DATABASE"
    )
    
    for secret in "${required_secrets[@]}"; do
        if ! az keyvault secret show --vault-name "$KEY_VAULT_NAME" --name "$secret" &> /dev/null; then
            log_warn "Secret $secret not found in Key Vault. Please set it manually:"
            log_warn "az keyvault secret set --vault-name $KEY_VAULT_NAME --name \"$secret\" --value \"<VALUE>\""
        else
            log_info "✓ Secret $secret found"
        fi
    done
    
    # Setup Workload Identity
    log_info "Setting up Workload Identity..."
    if [ -f "$SCRIPT_DIR/setup-workload-identity.sh" ]; then
        bash "$SCRIPT_DIR/setup-workload-identity.sh"
    else
        log_warn "Workload Identity setup script not found, skipping..."
    fi
    
    # Deploy monitoring configuration
    log_info "Deploying monitoring alerts..."
    kubectl apply -f k8s/monitoring/safety-amp-alerts.yaml
    
    log_info "Phase 2 completed successfully"
}

# Phase 3: Testing & Validation (Small Batches)
phase3_testing() {
    log_info "=== Phase 3: Testing & Validation ==="
    
    # Deploy application in test mode
    log_info "Deploying application in test mode..."
    kubectl apply -f k8s/safety-amp/safety-amp-deployment.yaml
    
    # Patch deployment for test mode
    log_info "Configuring test mode with small batches..."
    kubectl patch deployment safety-amp-agent -n safety-amp -p '{
        "spec": {
            "template": {
                "spec": {
                    "containers": [
                        {
                            "name": "safety-amp-agent",
                            "env": [
                                {"name": "TEST_MODE", "value": "true"},
                                {"name": "BATCH_SIZE", "value": "10"}
                            ]
                        }
                    ]
                }
            }
        }
    }'
    
    # Wait for deployment to be ready
    log_info "Waiting for deployment to be ready..."
    kubectl rollout status deployment/safety-amp-agent -n safety-amp --timeout=300s
    
    # Monitor logs for initial startup
    log_info "Monitoring initial startup logs..."
    kubectl logs -f deployment/safety-amp-agent -n safety-amp --tail=50 &
    LOG_PID=$!
    sleep 30
    kill $LOG_PID 2>/dev/null || true
    
    # Test health endpoints
    log_info "Testing health endpoints..."
    kubectl port-forward svc/safety-amp-service 8080:8080 -n safety-amp &
    PORT_FORWARD_PID=$!
    sleep 5
    
    # Test health endpoint
    if curl -f http://localhost:8080/health > /dev/null 2>&1; then
        log_info "✓ Health endpoint responding"
    else
        log_error "✗ Health endpoint not responding"
        kill $PORT_FORWARD_PID 2>/dev/null || true
        exit 1
    fi
    
    # Test readiness endpoint
    if curl -f http://localhost:8080/ready > /dev/null 2>&1; then
        log_info "✓ Readiness endpoint responding"
    else
        log_warn "✗ Readiness endpoint not ready (may be normal during startup)"
    fi
    
    # Test metrics endpoint
    if curl -f http://localhost:8080/metrics > /dev/null 2>&1; then
        log_info "✓ Metrics endpoint responding"
    else
        log_warn "✗ Metrics endpoint not responding"
    fi
    
    kill $PORT_FORWARD_PID 2>/dev/null || true
    
    log_info "Phase 3 completed successfully"
}

# Phase 4: Production Rollout
phase4_production() {
    log_info "=== Phase 4: Production Rollout ==="
    
    # Scale up for production
    log_info "Scaling up for production workload..."
    kubectl patch deployment safety-amp-agent -n safety-amp -p '{
        "spec": {
            "replicas": 2,
            "template": {
                "spec": {
                    "containers": [
                        {
                            "name": "safety-amp-agent",
                            "env": [
                                {"name": "TEST_MODE", "value": "false"},
                                {"name": "BATCH_SIZE", "value": "125"}
                            ]
                        }
                    ]
                }
            }
        }
    }'
    
    # Wait for scaled deployment
    kubectl rollout status deployment/safety-amp-agent -n safety-amp --timeout=300s
    
    # Verify sync operations
    log_info "Verifying sync operations..."
    kubectl get cronjobs -n safety-amp
    kubectl get jobs -n safety-amp
    
    # Final health check
    log_info "Performing final health checks..."
    kubectl port-forward svc/safety-amp-service 8080:8080 -n safety-amp &
    PORT_FORWARD_PID=$!
    sleep 5
    
    # Test detailed health endpoint
    if curl -f http://localhost:8080/health/detailed > /dev/null 2>&1; then
        log_info "✓ Detailed health endpoint responding"
        curl -s http://localhost:8080/health/detailed | jq .
    else
        log_warn "✗ Detailed health endpoint not responding"
    fi
    
    kill $PORT_FORWARD_PID 2>/dev/null || true
    
    log_info "Phase 4 completed successfully"
}

# Deployment validation
validate_deployment() {
    log_info "=== Deployment Validation ==="
    
    # Check pod status
    log_info "Checking pod status..."
    kubectl get pods -n safety-amp -o wide
    
    # Check resource usage
    log_info "Checking resource usage..."
    kubectl top pods -n safety-amp 2>/dev/null || log_warn "Metrics server not available"
    
    # Show deployment summary
    log_info "Deployment Summary:"
    echo "- Namespace: $NAMESPACE"
    echo "- Image: ${ACR_NAME}/safety-amp-agent:${IMAGE_TAG}"
    echo "- Replicas: $(kubectl get deployment safety-amp-agent -n safety-amp -o jsonpath='{.spec.replicas}')"
    echo "- Ready Replicas: $(kubectl get deployment safety-amp-agent -n safety-amp -o jsonpath='{.status.readyReplicas}')"
    echo "- Sync Schedule: Every 15 minutes"
    echo "- Batch Size: 125 records per sync"
    echo "- Target: 5000 records/hour"
    
    log_info "Deployment validation completed"
}

# Main deployment function
main() {
    log_info "Starting SafetyAmp Integration Production Deployment"
    log_info "Target: 5000 records/hour processing capability"
    
    check_prerequisites
    
    case "${1:-all}" in
        "phase1"|"infrastructure")
            phase1_infrastructure
            ;;
        "phase2"|"secrets")
            phase2_secrets
            ;;
        "phase3"|"testing")
            phase3_testing
            ;;
        "phase4"|"production")
            phase4_production
            ;;
        "validate")
            validate_deployment
            ;;
        "all")
            phase1_infrastructure
            phase2_secrets
            phase3_testing
            phase4_production
            validate_deployment
            ;;
        *)
            echo "Usage: $0 [phase1|phase2|phase3|phase4|validate|all]"
            echo "  phase1      - Infrastructure setup"
            echo "  phase2      - Secrets & configuration"
            echo "  phase3      - Testing & validation"
            echo "  phase4      - Production rollout"
            echo "  validate    - Deployment validation"
            echo "  all         - Run all phases (default)"
            exit 1
            ;;
    esac
    
    log_info "SafetyAmp Integration deployment completed successfully!"
    log_info "Monitor the application:"
    log_info "  kubectl logs -f deployment/safety-amp-agent -n safety-amp"
    log_info "  kubectl get cronjobs -n safety-amp"
    log_info "  kubectl port-forward svc/safety-amp-service 8080:8080 -n safety-amp"
}

# Run main function with all arguments
main "$@"