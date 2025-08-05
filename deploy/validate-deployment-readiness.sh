#!/bin/bash
set -e

# SafetyAmp Production Deployment Readiness Validation
# This script validates that all critical deployment blockers have been addressed

echo "🔍 SafetyAmp Production Deployment Readiness Check"
echo "=================================================="

ERRORS=0
WARNINGS=0

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

log_error() {
    echo -e "${RED}❌ $1${NC}"
    ((ERRORS++))
}

log_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
    ((WARNINGS++))
}

log_info() {
    echo -e "ℹ️  $1"
}

echo ""
echo "1. 🔐 Security Configuration Validation"
echo "========================================"

# Check 1: No exposed secrets in repository
log_info "Checking for exposed secrets..."
if find . -name "*.env*" -type f | grep -q .; then
    log_error "Found .env files in repository - IMMEDIATE SECURITY RISK"
    find . -name "*.env*" -type f
else
    log_success "No .env files found in repository"
fi

# Check hardcoded secrets in configuration files
if grep -r "eyJ0eXAiOiJKV1QiLCJhbGciOiJSUzI1NiJ9\|T~k8Q~\|Z\$539613135368on!" . --include="*.py" --include="*.yaml" --include="*.json" 2>/dev/null; then
    log_error "Found hardcoded secrets in codebase - IMMEDIATE SECURITY RISK"
else
    log_success "No hardcoded secrets found in codebase"
fi

echo ""
echo "2. 🏗️  Azure Workload Identity Configuration"
echo "============================================"

# Check 2: Workload Identity configuration
if grep -q "a2bcb3ce-a89b-43af-804c-e8029e0bafb4" k8s/safety-amp/safety-amp-deployment.yaml; then
    log_success "Managed Identity Client ID configured correctly"
else
    log_error "Managed Identity Client ID not configured in deployment"
fi

if grep -q "953922e6-5370-4a01-a3d5-773a30df726b" k8s/safety-amp/safety-amp-deployment.yaml; then
    log_success "Tenant ID configured correctly"
else
    log_error "Tenant ID not configured in deployment"
fi

if grep -q 'azure.workload.identity/use: "true"' k8s/safety-amp/safety-amp-deployment.yaml; then
    log_success "Workload Identity enabled in deployment"
else
    log_error "Workload Identity not enabled in deployment"
fi

if grep -q "serviceAccountName: safety-amp-workload-identity-sa" k8s/safety-amp/safety-amp-deployment.yaml; then
    log_success "Service Account configured correctly"
else
    log_error "Service Account not configured in deployment"
fi

echo ""
echo "3. 🗄️  SQL Server Configuration"
echo "==============================="

# Check 3: SQL Server configuration
if grep -q "inscolvsql.insulationsinc.local" deploy/setup-workload-identity.sh; then
    log_success "SQL Server FQDN configured correctly"
else
    log_error "SQL Server FQDN not configured"
fi

if grep -q 'SQL_AUTH_MODE.*managed_identity' k8s/safety-amp/safety-amp-deployment.yaml; then
    log_success "SQL authentication mode set to managed_identity"
else
    log_error "SQL authentication mode not set to managed_identity"
fi

if grep -q "Authentication=ActiveDirectoryMSI" config/settings.py; then
    log_success "Azure AD authentication configured for SQL Server"
else
    log_error "Azure AD authentication not configured for SQL Server"
fi

# Check 4: Database connection pooling
if grep -q "QueuePool" services/viewpoint_api.py; then
    log_success "Database connection pooling implemented"
else
    log_error "Database connection pooling not implemented"
fi

echo ""
echo "4. 📦 Container Registry Configuration"
echo "====================================="

# Check 5: Container registry references
if grep -q "your-registry" k8s/safety-amp/safety-amp-deployment.yaml; then
    log_error "Placeholder 'your-registry' still found in safety-amp deployment"
fi

if grep -q "iiusacr.azurecr.io" k8s/safety-amp/safety-amp-deployment.yaml; then
    log_warning "Generic ACR name 'iiusacr.azurecr.io' found - update with actual registry"
else
    log_success "Container registry references updated"
fi

echo ""
echo "5. 🔧 Application Configuration"
echo "==============================="

# Check 6: Application configuration files exist
required_files=(
    "config/settings.py"
    "services/viewpoint_api.py"
    "Dockerfile"
    "requirements.txt"
    "main.py"
)

for file in "${required_files[@]}"; do
    if [ -f "$file" ]; then
        log_success "Required file exists: $file"
    else
        log_error "Missing required file: $file"
    fi
done

# Check 7: Health check endpoints configured
if grep -q "/health" k8s/safety-amp/safety-amp-deployment.yaml; then
    log_success "Health check endpoints configured"
else
    log_error "Health check endpoints not configured"
fi

echo ""
echo "6. 🚀 Kubernetes Configuration"
echo "=============================="

# Check 8: Resource limits configured
if grep -q "limits:" k8s/safety-amp/safety-amp-deployment.yaml; then
    log_success "Resource limits configured"
else
    log_error "Resource limits not configured"
fi

# Check 9: Prometheus metrics configured
if grep -q "prometheus.io/scrape" k8s/safety-amp/safety-amp-deployment.yaml; then
    log_success "Prometheus metrics configured"
else
    log_warning "Prometheus metrics not configured"
fi

echo ""
echo "📋 DEPLOYMENT READINESS SUMMARY"
echo "==============================="

if [ $ERRORS -eq 0 ]; then
    if [ $WARNINGS -eq 0 ]; then
        log_success "🎉 ALL CHECKS PASSED - READY FOR PRODUCTION DEPLOYMENT"
        echo ""
        echo "Next steps:"
        echo "1. Replace 'iiusacr.azurecr.io' with your actual Azure Container Registry"
        echo "2. Build and push container images"
        echo "3. Run the setup-workload-identity.sh script"
        echo "4. Deploy using ./deploy/deploy.sh"
    else
        echo -e "${YELLOW}⚠️  DEPLOYMENT READY WITH $WARNINGS WARNING(S)${NC}"
        echo "Please review warnings above before deploying to production"
    fi
else
    log_error "🚨 DEPLOYMENT BLOCKED - $ERRORS CRITICAL ERROR(S) FOUND"
    echo ""
    echo "❌ CRITICAL DEPLOYMENT BLOCKERS DETECTED"
    echo "Fix all errors above before attempting deployment"
    exit 1
fi

echo ""
echo "🔍 Pre-Deployment Actions Required:"
echo "1. Update container registry name from 'iiusacr.azurecr.io' to your actual ACR"
echo "2. Build and push container images to your registry"
echo "3. Populate Azure Key Vault with actual secrets (see production-deployment-checklist.md)"
echo "4. Set up SQL Server Azure AD authentication"
echo "5. Run ./deploy/setup-workload-identity.sh"
echo "6. Deploy with ./deploy/deploy.sh"

exit 0