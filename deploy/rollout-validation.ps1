#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Rollout SafetyAmp Data Validation Solution
    
.DESCRIPTION
    This script deploys the comprehensive data validation solution to ensure
    required fields are always present and valid before sending to SafetyAmp API.
    
.PARAMETER Action
    The rollout action to perform:
    - "validate": Validate the current deployment
    - "deploy": Deploy the validation solution
    - "test": Test the validation functionality
    - "monitor": Monitor validation improvements
    - "rollback": Rollback to previous version (if needed)
    
.PARAMETER Environment
    Target environment (default: "production")
    
.EXAMPLE
    .\rollout-validation.ps1 -Action "validate"
    .\rollout-validation.ps1 -Action "deploy" -Environment "production"
    .\rollout-validation.ps1 -Action "test"
#>

param(
    [string]$Action = "deploy",
    [string]$Environment = "production"
)

Write-Host "🚀 SafetyAmp Data Validation Rollout" -ForegroundColor Cyan
Write-Host "====================================" -ForegroundColor Cyan
Write-Host "Environment: $Environment" -ForegroundColor Yellow
Write-Host "Action: $Action" -ForegroundColor Yellow
Write-Host "Timestamp: $(Get-Date)" -ForegroundColor Gray

# Configuration
$namespace = "safety-amp"
$deployment_name = "safety-amp-agent"

function Test-Prerequisites {
    Write-Host "`n🔍 Checking Prerequisites..." -ForegroundColor Green
    
    # Check kubectl
    try {
        $kubectl_version = kubectl version --client --short 2>$null
        Write-Host "✅ kubectl: $kubectl_version" -ForegroundColor Green
    } catch {
        Write-Host "❌ kubectl not found or not working" -ForegroundColor Red
        return $false
    }
    
    # Check namespace
    try {
        $ns_exists = kubectl get namespace $namespace 2>$null
        if ($ns_exists) {
            Write-Host "✅ Namespace '$namespace' exists" -ForegroundColor Green
        } else {
            Write-Host "❌ Namespace '$namespace' not found" -ForegroundColor Red
            return $false
        }
    } catch {
        Write-Host "❌ Error checking namespace" -ForegroundColor Red
        return $false
    }
    
    # Check current deployment
    try {
        $deployment = kubectl get deployment $deployment_name -n $namespace 2>$null
        if ($deployment) {
            Write-Host "✅ Deployment '$deployment_name' exists" -ForegroundColor Green
        } else {
            Write-Host "❌ Deployment '$deployment_name' not found" -ForegroundColor Red
            return $false
        }
    } catch {
        Write-Host "❌ Error checking deployment" -ForegroundColor Red
        return $false
    }
    
    return $true
}

function Get-CurrentStatus {
    Write-Host "`n📊 Current Deployment Status..." -ForegroundColor Green
    
    # Get deployment status
    $deployment_status = kubectl get deployment $deployment_name -n $namespace -o json 2>$null | ConvertFrom-Json
    
    if ($deployment_status) {
        $replicas = $deployment_status.status.replicas
        $available = $deployment_status.status.availableReplicas
        $ready = $deployment_status.status.readyReplicas
        
        Write-Host "  Replicas: $replicas" -ForegroundColor White
        Write-Host "  Available: $available" -ForegroundColor White
        Write-Host "  Ready: $ready" -ForegroundColor White
        
        # Get pod status
        $pods = kubectl get pods -n $namespace -l app=safety-amp,component=agent -o json 2>$null | ConvertFrom-Json
        
        if ($pods.items) {
            Write-Host "  Active Pods: $($pods.items.Count)" -ForegroundColor White
            
            foreach ($pod in $pods.items) {
                $pod_name = $pod.metadata.name
                $pod_status = $pod.status.phase
                $pod_ready = $pod.status.containerStatuses[0].ready
                
                $status_color = if ($pod_status -eq "Running" -and $pod_ready) { "Green" } else { "Red" }
                Write-Host "    $pod_name : $pod_status (Ready: $pod_ready)" -ForegroundColor $status_color
            }
        } else {
            Write-Host "  No active pods found" -ForegroundColor Yellow
        }
    } else {
        Write-Host "❌ Could not get deployment status" -ForegroundColor Red
    }
}

function Deploy-ValidationSolution {
    Write-Host "`n🚀 Deploying Data Validation Solution..." -ForegroundColor Green
    
    # Create backup of current deployment
    Write-Host "📦 Creating backup of current deployment..." -ForegroundColor Yellow
    $backup_file = "backup-deployment-$(Get-Date -Format 'yyyyMMdd-HHmmss').yaml"
    kubectl get deployment $deployment_name -n $namespace -o yaml > $backup_file 2>$null
    
    if (Test-Path $backup_file) {
        Write-Host "✅ Backup created: $backup_file" -ForegroundColor Green
    } else {
        Write-Host "⚠️  Could not create backup" -ForegroundColor Yellow
    }
    
    # Update deployment with new image or restart to pick up code changes
    Write-Host "🔄 Restarting deployment to apply validation changes..." -ForegroundColor Yellow
    
    # Method 1: Restart deployment (if code is already in the image)
    kubectl rollout restart deployment/$deployment_name -n $namespace
    
    # Wait for rollout to complete
    Write-Host "⏳ Waiting for rollout to complete..." -ForegroundColor Yellow
    kubectl rollout status deployment/$deployment_name -n $namespace --timeout=300s
    
    if ($LASTEXITCODE -eq 0) {
        Write-Host "✅ Deployment rollout completed successfully" -ForegroundColor Green
    } else {
        Write-Host "❌ Deployment rollout failed" -ForegroundColor Red
        return $false
    }
    
    # Verify deployment
    Start-Sleep -Seconds 10
    Get-CurrentStatus
    
    return $true
}

function Test-ValidationFunctionality {
    Write-Host "`n🧪 Testing Validation Functionality..." -ForegroundColor Green
    
    # Get a running pod
    $pods = kubectl get pods -n $namespace -l app=safety-amp,component=agent --field-selector=status.phase=Running -o jsonpath='{.items[0].metadata.name}' 2>$null
    
    if (-not $pods) {
        Write-Host "❌ No running pods found for testing" -ForegroundColor Red
        return $false
    }
    
    Write-Host "📦 Testing with pod: $pods" -ForegroundColor Yellow
    
    # Test 1: Check if data validator module is available
    Write-Host "`n🔍 Test 1: Data Validator Module..." -ForegroundColor Cyan
    $test_result = kubectl exec $pods -n $namespace -- python -c "
import sys
sys.path.append('/app')
try:
    from utils.data_validator import validator
    print('✅ Data validator module imported successfully')
    print(f'Validator class: {type(validator).__name__}')
except Exception as e:
    print(f'❌ Error importing data validator: {e}')
    sys.exit(1)
" 2>$null
    
    if ($LASTEXITCODE -eq 0) {
        Write-Host $test_result -ForegroundColor Green
    } else {
        Write-Host "❌ Data validator module test failed" -ForegroundColor Red
        return $false
    }
    
    # Test 2: Test validation functionality
    Write-Host "`n🔍 Test 2: Validation Functionality..." -ForegroundColor Cyan
    $validation_test = kubectl exec $pods -n $namespace -- python -c "
import sys
sys.path.append('/app')
try:
    from utils.data_validator import validator
    
    # Test employee validation
    test_payload = {
        'first_name': '',
        'last_name': 'Test',
        'email': 'invalid-email'
    }
    
    is_valid, errors, cleaned = validator.validate_employee_data(test_payload, '12345', 'Test User')
    
    print('✅ Validation test completed')
    print(f'Is valid: {is_valid}')
    print(f'Errors: {errors}')
    print(f'Cleaned payload keys: {list(cleaned.keys())}')
    
    if not is_valid and 'first_name' in cleaned and cleaned['first_name'] == 'Unknown':
        print('✅ Auto-generation working correctly')
    else:
        print('❌ Auto-generation not working as expected')
        sys.exit(1)
        
except Exception as e:
    print(f'❌ Validation test failed: {e}')
    sys.exit(1)
" 2>$null
    
    if ($LASTEXITCODE -eq 0) {
        Write-Host $validation_test -ForegroundColor Green
    } else {
        Write-Host "❌ Validation functionality test failed" -ForegroundColor Red
        return $false
    }
    
    # Test 3: Check sync modules
    Write-Host "`n🔍 Test 3: Sync Modules..." -ForegroundColor Cyan
    $sync_test = kubectl exec $pods -n $namespace -- python -c "
import sys
sys.path.append('/app')
try:
    from sync.sync_employees import EmployeeSyncer
    from sync.sync_vehicles import VehicleSync
    
    print('✅ Sync modules imported successfully')
    print('✅ Employee sync with validation ready')
    print('✅ Vehicle sync with validation ready')
    
except Exception as e:
    print(f'❌ Sync module test failed: {e}')
    sys.exit(1)
" 2>$null
    
    if ($LASTEXITCODE -eq 0) {
        Write-Host $sync_test -ForegroundColor Green
    } else {
        Write-Host "❌ Sync module test failed" -ForegroundColor Red
        return $false
    }
    
    Write-Host "`n✅ All validation tests passed!" -ForegroundColor Green
    return $true
}

function Watch-ValidationImprovements {
    Write-Host "`n📊 Monitoring Validation Improvements..." -ForegroundColor Green
    
    # Run validation monitoring via dashboard
    Write-Host "`n🔍 Running validation monitoring..." -ForegroundColor Yellow
    & "$PSScriptRoot\monitoring-dashboard.ps1" -Hours 1 -Sections @('validation')
    
    # Check for recent validation logs
    Write-Host "`n🔍 Checking recent validation logs..." -ForegroundColor Yellow
    $pods = kubectl get pods -n $namespace -l app=safety-amp,component=agent --field-selector=status.phase=Running -o jsonpath='{.items[0].metadata.name}' 2>$null
    
    if ($pods) {
        $recent_logs = kubectl logs $pods -n $namespace --tail=20 2>$null | Select-String -Pattern "Generated|Validation|validation"
        
        if ($recent_logs) {
            Write-Host "`n📋 Recent Validation Activity:" -ForegroundColor Cyan
            foreach ($log in $recent_logs) {
                Write-Host "  $($log.Line)" -ForegroundColor Gray
            }
        } else {
            Write-Host "`nℹ️  No recent validation activity found" -ForegroundColor Yellow
        }
    }
}

function Restore-Deployment {
    Write-Host "`n🔄 Rolling back deployment..." -ForegroundColor Yellow
    
    # Find the most recent backup file
    $backup_files = Get-ChildItem -Path "." -Filter "backup-deployment-*.yaml" | Sort-Object LastWriteTime -Descending
    
    if ($backup_files.Count -eq 0) {
        Write-Host "❌ No backup files found for rollback" -ForegroundColor Red
        return $false
    }
    
    $latest_backup = $backup_files[0].Name
    Write-Host "📦 Using backup: $latest_backup" -ForegroundColor Yellow
    
    # Apply the backup
    kubectl apply -f $latest_backup
    
    if ($LASTEXITCODE -eq 0) {
        Write-Host "✅ Rollback completed successfully" -ForegroundColor Green
        
        # Wait for rollout
        kubectl rollout status deployment/$deployment_name -n $namespace --timeout=300s
        
        Get-CurrentStatus
        return $true
    } else {
        Write-Host "❌ Rollback failed" -ForegroundColor Red
        return $false
    }
}

# Main execution
Write-Host "`n🎯 Starting rollout process..." -ForegroundColor Cyan

# Check prerequisites
if (-not (Test-Prerequisites)) {
    Write-Host "`n❌ Prerequisites check failed. Cannot proceed with rollout." -ForegroundColor Red
    exit 1
}

# Get current status
Get-CurrentStatus

# Execute requested action
switch ($Action.ToLower()) {
    "validate" {
        Write-Host "`n🔍 Validating current deployment..." -ForegroundColor Green
        Get-CurrentStatus
        Test-ValidationFunctionality
    }
    "deploy" {
        Write-Host "`n🚀 Deploying validation solution..." -ForegroundColor Green
        if (Deploy-ValidationSolution) {
            Write-Host "`n✅ Deployment completed successfully!" -ForegroundColor Green
            Write-Host "`n🧪 Running validation tests..." -ForegroundColor Yellow
            Test-ValidationFunctionality
        } else {
            Write-Host "`n❌ Deployment failed!" -ForegroundColor Red
            exit 1
        }
    }
    "test" {
        Write-Host "`n🧪 Testing validation functionality..." -ForegroundColor Green
        Test-ValidationFunctionality
    }
    "monitor" {
        Write-Host "`n📊 Monitoring validation improvements..." -ForegroundColor Green
        Watch-ValidationImprovements
    }
    "rollback" {
        Write-Host "`n🔄 Rolling back deployment..." -ForegroundColor Yellow
        if (Restore-Deployment) {
            Write-Host "`n✅ Rollback completed successfully!" -ForegroundColor Green
        } else {
            Write-Host "`n❌ Rollback failed!" -ForegroundColor Red
            exit 1
        }
    }
    default {
        Write-Host "❌ Unknown action: $Action" -ForegroundColor Red
        Write-Host "Available actions: validate, deploy, test, monitor, rollback" -ForegroundColor Yellow
        exit 1
    }
}

Write-Host "`n🎉 Rollout process completed!" -ForegroundColor Green
Write-Host "`n📋 Next Steps:" -ForegroundColor Cyan
Write-Host "  1. Monitor the deployment for any issues" -ForegroundColor White
Write-Host "  2. Run validation tests to ensure functionality" -ForegroundColor White
Write-Host "  3. Check logs for validation improvements" -ForegroundColor White
Write-Host "  4. Monitor error rates to confirm 422 errors are reduced" -ForegroundColor White

Write-Host "`n📞 Support Commands:" -ForegroundColor Cyan
Write-Host "  .\monitor.ps1 -Feature validation -Hours 1" -ForegroundColor Gray
Write-Host "  .\monitor.ps1 -Feature logs -Mode errors -Hours 1" -ForegroundColor Gray
Write-Host "  .\rollout-validation.ps1 -Action 'monitor'" -ForegroundColor Gray
