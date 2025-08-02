#!/bin/bash

# SafetyAmp Integration - Helm Deployment Script
# Supports development, staging, and production environments

set -euo pipefail

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
CHART_PATH="$PROJECT_ROOT/helm/safety-amp"
NAMESPACE="safety-amp"

# Default values
ENVIRONMENT=${ENVIRONMENT:-production}
ACR_NAME=${ACR_NAME:-youracr.azurecr.io}
IMAGE_TAG=${IMAGE_TAG:-v1.0.0}
KEY_VAULT_NAME=${KEY_VAULT_NAME:-kv-safety-amp-${ENVIRONMENT}}
RELEASE_NAME=${RELEASE_NAME:-safety-amp-${ENVIRONMENT}}
DRY_RUN=${DRY_RUN:-false}

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
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

log_debug() {
    echo -e "${BLUE}[DEBUG]${NC} $1"
}

# Show usage
usage() {
    cat << EOF
Usage: $0 [OPTIONS] COMMAND

SafetyAmp Integration Helm Deployment Script

COMMANDS:
    install         Install the SafetyAmp chart
    upgrade         Upgrade the SafetyAmp chart
    uninstall       Uninstall the SafetyAmp chart
    template        Generate templates (dry-run)
    test            Run Helm tests
    status          Show release status
    values          Show computed values
    lint            Lint the Helm chart

OPTIONS:
    -e, --environment ENV    Environment (development|staging|production) [default: production]
    -r, --release NAME       Release name [default: safety-amp-\${environment}]
    -n, --namespace NS       Kubernetes namespace [default: safety-amp]
    -i, --image-tag TAG      Docker image tag [default: v1.0.0]
    -a, --acr-name NAME      Azure Container Registry name [default: youracr.azurecr.io]
    -k, --key-vault NAME     Azure Key Vault name [default: kv-safety-amp-\${environment}]
    -d, --dry-run            Perform dry-run [default: false]
    -h, --help               Show this help

EXAMPLES:
    # Install in development
    $0 -e development install

    # Upgrade production with new image
    $0 -e production -i v1.1.0 upgrade

    # Template generation for review
    $0 -e production template

    # Dry-run production upgrade
    $0 -e production -d upgrade

ENVIRONMENT VARIABLES:
    ENVIRONMENT     Target environment
    ACR_NAME        Azure Container Registry name
    IMAGE_TAG       Docker image tag
    KEY_VAULT_NAME  Azure Key Vault name
    RELEASE_NAME    Helm release name
    DRY_RUN         Enable dry-run mode

EOF
}

# Parse command line arguments
parse_args() {
    while [[ $# -gt 0 ]]; do
        case $1 in
            -e|--environment)
                ENVIRONMENT="$2"
                shift 2
                ;;
            -r|--release)
                RELEASE_NAME="$2"
                shift 2
                ;;
            -n|--namespace)
                NAMESPACE="$2"
                shift 2
                ;;
            -i|--image-tag)
                IMAGE_TAG="$2"
                shift 2
                ;;
            -a|--acr-name)
                ACR_NAME="$2"
                shift 2
                ;;
            -k|--key-vault)
                KEY_VAULT_NAME="$2"
                shift 2
                ;;
            -d|--dry-run)
                DRY_RUN=true
                shift
                ;;
            -h|--help)
                usage
                exit 0
                ;;
            install|upgrade|uninstall|template|test|status|values|lint)
                COMMAND="$1"
                shift
                break
                ;;
            *)
                log_error "Unknown option: $1"
                usage
                exit 1
                ;;
        esac
    done

    if [[ -z "${COMMAND:-}" ]]; then
        log_error "Command is required"
        usage
        exit 1
    fi

    # Validate environment
    case $ENVIRONMENT in
        development|staging|production)
            ;;
        *)
            log_error "Invalid environment: $ENVIRONMENT"
            log_error "Valid environments: development, staging, production"
            exit 1
            ;;
    esac

    # Update derived values
    RELEASE_NAME=${RELEASE_NAME:-safety-amp-${ENVIRONMENT}}
    KEY_VAULT_NAME=${KEY_VAULT_NAME:-kv-safety-amp-${ENVIRONMENT}}
}

# Check prerequisites
check_prerequisites() {
    log_info "Checking prerequisites..."

    # Check required tools
    for tool in helm kubectl az; do
        if ! command -v $tool &> /dev/null; then
            log_error "$tool is required but not installed"
            exit 1
        fi
    done

    # Check Helm version
    HELM_VERSION=$(helm version --short --client 2>/dev/null | cut -d' ' -f1 | cut -d'v' -f2)
    if [[ "${HELM_VERSION%%.*}" -lt 3 ]]; then
        log_error "Helm 3.x is required (found: $HELM_VERSION)"
        exit 1
    fi

    # Check kubectl context
    CONTEXT=$(kubectl config current-context)
    log_info "Using kubectl context: $CONTEXT"

    # Check Azure CLI login
    if ! az account show &> /dev/null; then
        log_error "Please login to Azure CLI first: az login"
        exit 1
    fi

    # Check if chart exists
    if [[ ! -f "$CHART_PATH/Chart.yaml" ]]; then
        log_error "Helm chart not found at: $CHART_PATH"
        exit 1
    fi

    log_info "Prerequisites check passed"
}

# Build Helm command arguments
build_helm_args() {
    local args=()

    # Namespace
    args+=(--namespace "$NAMESPACE")
    args+=(--create-namespace)

    # Values files
    if [[ -f "$CHART_PATH/values-${ENVIRONMENT}.yaml" ]]; then
        args+=(--values "$CHART_PATH/values-${ENVIRONMENT}.yaml")
        log_info "Using environment-specific values: values-${ENVIRONMENT}.yaml"
    else
        log_warn "Environment-specific values file not found: values-${ENVIRONMENT}.yaml"
    fi

    # Set overrides
    args+=(--set "image.registry=${ACR_NAME}")
    args+=(--set "image.tag=${IMAGE_TAG}")
    args+=(--set "keyVault.name=${KEY_VAULT_NAME}")
    args+=(--set "namespace=${NAMESPACE}")

    # Environment-specific namespace overrides
    case $ENVIRONMENT in
        development)
            args+=(--set "monitoring.alerts.enabled=false")
            args+=(--set "cronjob.enabled=false")
            ;;
        staging)
            args+=(--set "monitoring.alerts.namespace=monitoring-staging")
            ;;
        production)
            args+=(--set "monitoring.alerts.namespace=monitoring")
            ;;
    esac

    # Dry-run flag
    if [[ "$DRY_RUN" == "true" ]]; then
        args+=(--dry-run)
        log_info "Dry-run mode enabled"
    fi

    echo "${args[@]}"
}

# Lint Helm chart
lint_chart() {
    log_info "Linting Helm chart..."
    
    helm lint "$CHART_PATH" \
        --values "$CHART_PATH/values-${ENVIRONMENT}.yaml" \
        --set "image.registry=${ACR_NAME}" \
        --set "image.tag=${IMAGE_TAG}" \
        --set "keyVault.name=${KEY_VAULT_NAME}"
    
    log_info "Chart linting completed"
}

# Generate templates
template_chart() {
    log_info "Generating Helm templates for environment: $ENVIRONMENT"
    
    local args
    args=($(build_helm_args))
    
    helm template "$RELEASE_NAME" "$CHART_PATH" "${args[@]}"
}

# Install chart
install_chart() {
    log_info "Installing SafetyAmp chart for environment: $ENVIRONMENT"
    log_info "Release: $RELEASE_NAME"
    log_info "Namespace: $NAMESPACE"
    log_info "Image: ${ACR_NAME}/safety-amp-agent:${IMAGE_TAG}"
    
    local args
    args=($(build_helm_args))
    
    # Add install-specific flags
    args+=(--wait)
    args+=(--timeout=10m)
    
    if [[ "$DRY_RUN" != "true" ]]; then
        # Verify Key Vault secrets exist
        verify_key_vault_secrets
    fi
    
    helm install "$RELEASE_NAME" "$CHART_PATH" "${args[@]}"
    
    if [[ "$DRY_RUN" != "true" ]]; then
        log_info "Installation completed successfully!"
        show_post_install_info
    fi
}

# Upgrade chart
upgrade_chart() {
    log_info "Upgrading SafetyAmp chart for environment: $ENVIRONMENT"
    log_info "Release: $RELEASE_NAME"
    log_info "New image: ${ACR_NAME}/safety-amp-agent:${IMAGE_TAG}"
    
    local args
    args=($(build_helm_args))
    
    # Add upgrade-specific flags
    args+=(--wait)
    args+=(--timeout=10m)
    args+=(--reset-values)  # Start from values files, not previous release
    
    helm upgrade "$RELEASE_NAME" "$CHART_PATH" "${args[@]}"
    
    if [[ "$DRY_RUN" != "true" ]]; then
        log_info "Upgrade completed successfully!"
        show_post_install_info
    fi
}

# Uninstall chart
uninstall_chart() {
    log_warn "Uninstalling SafetyAmp chart: $RELEASE_NAME"
    read -p "Are you sure? (y/N): " -n 1 -r
    echo
    
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        helm uninstall "$RELEASE_NAME" --namespace "$NAMESPACE"
        log_info "Uninstallation completed"
    else
        log_info "Uninstallation cancelled"
    fi
}

# Run Helm tests
test_chart() {
    log_info "Running Helm tests for release: $RELEASE_NAME"
    
    helm test "$RELEASE_NAME" --namespace "$NAMESPACE"
    
    log_info "Helm tests completed"
}

# Show release status
show_status() {
    log_info "Release status for: $RELEASE_NAME"
    
    helm status "$RELEASE_NAME" --namespace "$NAMESPACE"
    
    log_info ""
    log_info "Pod status:"
    kubectl get pods -n "$NAMESPACE" -l "app.kubernetes.io/instance=$RELEASE_NAME"
    
    log_info ""
    log_info "Service status:"
    kubectl get services -n "$NAMESPACE" -l "app.kubernetes.io/instance=$RELEASE_NAME"
}

# Show computed values
show_values() {
    log_info "Computed values for release: $RELEASE_NAME"
    
    helm get values "$RELEASE_NAME" --namespace "$NAMESPACE" --all
}

# Verify Key Vault secrets
verify_key_vault_secrets() {
    log_info "Verifying Key Vault secrets..."
    
    local required_secrets=(
        "SAFETYAMP-TOKEN"
        "MS-GRAPH-CLIENT-SECRET"
        "SAMSARA-API-KEY"
        "SQL-SERVER"
        "SQL-DATABASE"
    )
    
    local missing_secrets=()
    
    for secret in "${required_secrets[@]}"; do
        if ! az keyvault secret show --vault-name "$KEY_VAULT_NAME" --name "$secret" &> /dev/null; then
            missing_secrets+=("$secret")
        fi
    done
    
    if [[ ${#missing_secrets[@]} -gt 0 ]]; then
        log_error "Missing secrets in Key Vault '$KEY_VAULT_NAME':"
        for secret in "${missing_secrets[@]}"; do
            log_error "  - $secret"
        done
        log_error "Please set missing secrets before deployment"
        exit 1
    fi
    
    log_info "✓ All required secrets found in Key Vault"
}

# Show post-installation information
show_post_install_info() {
    log_info ""
    log_info "🎉 SafetyAmp Integration deployed successfully!"
    log_info ""
    log_info "Environment: $ENVIRONMENT"
    log_info "Release: $RELEASE_NAME"
    log_info "Namespace: $NAMESPACE"
    log_info "Image: ${ACR_NAME}/safety-amp-agent:${IMAGE_TAG}"
    log_info ""
    log_info "Useful commands:"
    log_info "  # Check deployment status"
    log_info "  kubectl get pods -n $NAMESPACE"
    log_info ""
    log_info "  # View logs"
    log_info "  kubectl logs -f deployment/${RELEASE_NAME}-agent -n $NAMESPACE"
    log_info ""
    log_info "  # Port forward to access health endpoint"
    log_info "  kubectl port-forward svc/${RELEASE_NAME}-service 8080:8080 -n $NAMESPACE"
    log_info ""
    log_info "  # Check CronJob status"
    log_info "  kubectl get cronjobs -n $NAMESPACE"
    log_info ""
    log_info "  # View Helm release status"
    log_info "  helm status $RELEASE_NAME -n $NAMESPACE"
    log_info ""
    
    if [[ "$ENVIRONMENT" == "production" ]]; then
        log_info "📊 Production Configuration:"
        log_info "  • Processing Target: 5000 records/hour"
        log_info "  • Sync Interval: Every 15 minutes"
        log_info "  • Batch Size: 125 records per sync"
        log_info "  • Replicas: 2 (with autoscaling 2-5)"
        log_info "  • Monitoring: Enabled with alerts"
        log_info ""
    fi
}

# Main function
main() {
    parse_args "$@"
    
    log_info "SafetyAmp Integration Helm Deployment"
    log_info "Environment: $ENVIRONMENT"
    log_info "Command: $COMMAND"
    log_info "Release: $RELEASE_NAME"
    
    check_prerequisites
    
    case $COMMAND in
        lint)
            lint_chart
            ;;
        template)
            template_chart
            ;;
        install)
            install_chart
            ;;
        upgrade)
            upgrade_chart
            ;;
        uninstall)
            uninstall_chart
            ;;
        test)
            test_chart
            ;;
        status)
            show_status
            ;;
        values)
            show_values
            ;;
        *)
            log_error "Unknown command: $COMMAND"
            usage
            exit 1
            ;;
    esac
}

# Run main function with all arguments
main "$@"