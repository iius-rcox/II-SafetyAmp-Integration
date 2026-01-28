#!/bin/bash
#
# ArgoCD Installation Script for SafetyAmp Integration
#
# This script installs ArgoCD in the Kubernetes cluster and configures
# the SafetyAmp Integration project and applications.
#
# Prerequisites:
#   - kubectl configured with cluster access
#   - Helm 3.x installed
#   - Git repository URL updated in application manifests
#
# Usage:
#   ./scripts/install-argocd.sh [--namespace argocd] [--skip-install]
#

set -euo pipefail

# Configuration
ARGOCD_NAMESPACE="${ARGOCD_NAMESPACE:-argocd}"
ARGOCD_VERSION="${ARGOCD_VERSION:-stable}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Parse arguments
SKIP_INSTALL=false
while [[ $# -gt 0 ]]; do
    case $1 in
        --namespace)
            ARGOCD_NAMESPACE="$2"
            shift 2
            ;;
        --skip-install)
            SKIP_INSTALL=true
            shift
            ;;
        --help)
            echo "Usage: $0 [--namespace argocd] [--skip-install]"
            echo ""
            echo "Options:"
            echo "  --namespace    ArgoCD namespace (default: argocd)"
            echo "  --skip-install Skip ArgoCD installation, only apply manifests"
            exit 0
            ;;
        *)
            log_error "Unknown option: $1"
            exit 1
            ;;
    esac
done

# Check prerequisites
check_prerequisites() {
    log_info "Checking prerequisites..."

    if ! command -v kubectl &> /dev/null; then
        log_error "kubectl is not installed"
        exit 1
    fi

    if ! kubectl cluster-info &> /dev/null; then
        log_error "Cannot connect to Kubernetes cluster"
        exit 1
    fi

    log_info "Prerequisites check passed"
}

# Install ArgoCD
install_argocd() {
    if [[ "$SKIP_INSTALL" == "true" ]]; then
        log_info "Skipping ArgoCD installation (--skip-install flag)"
        return
    fi

    log_info "Installing ArgoCD in namespace: $ARGOCD_NAMESPACE"

    # Create namespace if it doesn't exist
    kubectl create namespace "$ARGOCD_NAMESPACE" --dry-run=client -o yaml | kubectl apply -f -

    # Install ArgoCD using the official manifest
    kubectl apply -n "$ARGOCD_NAMESPACE" -f "https://raw.githubusercontent.com/argoproj/argo-cd/${ARGOCD_VERSION}/manifests/install.yaml"

    log_info "Waiting for ArgoCD to be ready..."
    kubectl wait --for=condition=available --timeout=300s deployment/argocd-server -n "$ARGOCD_NAMESPACE"

    log_info "ArgoCD installed successfully"
}

# Get initial admin password
get_admin_password() {
    log_info "Retrieving initial admin password..."

    ADMIN_PASSWORD=$(kubectl -n "$ARGOCD_NAMESPACE" get secret argocd-initial-admin-secret -o jsonpath="{.data.password}" 2>/dev/null | base64 -d || echo "")

    if [[ -n "$ADMIN_PASSWORD" ]]; then
        echo ""
        log_info "ArgoCD Admin Credentials:"
        echo "  Username: admin"
        echo "  Password: $ADMIN_PASSWORD"
        echo ""
        log_warn "Change this password after first login!"
    else
        log_warn "Initial admin secret not found. Password may have been changed."
    fi
}

# Apply SafetyAmp project and applications
apply_manifests() {
    log_info "Applying SafetyAmp Integration ArgoCD manifests..."

    ARGOCD_DIR="$PROJECT_ROOT/k8s/argocd"

    if [[ ! -d "$ARGOCD_DIR" ]]; then
        log_error "ArgoCD manifests directory not found: $ARGOCD_DIR"
        exit 1
    fi

    # Apply project first
    if [[ -f "$ARGOCD_DIR/project.yaml" ]]; then
        log_info "Applying AppProject..."
        kubectl apply -f "$ARGOCD_DIR/project.yaml"
    fi

    # Apply applications
    if [[ -d "$ARGOCD_DIR/applications" ]]; then
        log_info "Applying Applications..."
        kubectl apply -f "$ARGOCD_DIR/applications/"
    fi

    log_info "Manifests applied successfully"
}

# Setup port forwarding for UI access
setup_port_forward() {
    log_info "To access ArgoCD UI, run:"
    echo ""
    echo "  kubectl port-forward svc/argocd-server -n $ARGOCD_NAMESPACE 8080:443"
    echo ""
    echo "Then open: https://localhost:8080"
    echo ""
}

# Print repository configuration reminder
print_config_reminder() {
    log_warn "IMPORTANT: Update the following before deploying:"
    echo ""
    echo "1. Update repository URL in application manifests:"
    echo "   - k8s/argocd/applications/dev.yaml"
    echo "   - k8s/argocd/applications/staging.yaml"
    echo "   - k8s/argocd/applications/prod.yaml"
    echo ""
    echo "   Replace 'YOUR_ORG' with your GitHub organization/username"
    echo ""
    echo "2. Configure repository credentials in ArgoCD:"
    echo "   argocd repo add https://github.com/YOUR_ORG/II-SafetyAmp-Integration.git \\"
    echo "     --username <github-user> --password <github-token>"
    echo ""
    echo "3. Create staging/prod overlay directories if they don't exist:"
    echo "   - k8s/overlays/staging/kustomization.yaml"
    echo "   - k8s/overlays/prod/kustomization.yaml"
    echo ""
}

# Main execution
main() {
    echo "========================================"
    echo "ArgoCD Installation for SafetyAmp"
    echo "========================================"
    echo ""

    check_prerequisites
    install_argocd
    apply_manifests
    get_admin_password
    setup_port_forward
    print_config_reminder

    log_info "Installation complete!"
}

main
