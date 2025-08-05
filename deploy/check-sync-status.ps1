# SafetyAmp Sync Status Checker
# This script helps you monitor the sync status and errors

param(
    [string]$Namespace = "safety-amp"
)

Write-Host "=== SafetyAmp Integration Status ===" -ForegroundColor Green
Write-Host ""

# Check pod status
Write-Host "Pod Status:" -ForegroundColor Yellow
kubectl get pods -n $Namespace

Write-Host ""
Write-Host "=== Sync Status ===" -ForegroundColor Yellow

# Get the most recent pod
$latestPod = kubectl get pods -n $Namespace --field-selector=status.phase=Running -l app=safety-amp --sort-by=.metadata.creationTimestamp -o jsonpath='{.items[-1].metadata.name}'

if ($latestPod) {
    Write-Host "Latest pod: $latestPod" -ForegroundColor Cyan
    
    # Check if port-forward is needed
    $portForwardRunning = Get-Process -Name "kubectl" -ErrorAction SilentlyContinue | Where-Object { $_.ProcessName -eq "kubectl" }
    
    if (-not $portForwardRunning) {
        Write-Host "Starting port-forward for health check..." -ForegroundColor Yellow
        Start-Process kubectl -ArgumentList "port-forward", "service/safety-amp-service", "8080:8080", "-n", $Namespace -WindowStyle Hidden
        Start-Sleep -Seconds 3
    }
    
    try {
        # Get detailed health status
        $healthResponse = Invoke-RestMethod -Uri "http://localhost:8080/health/detailed" -Method Get -TimeoutSec 5
        $healthData = $healthResponse | ConvertFrom-Json
        
        Write-Host "Application Status: $($healthData.status)" -ForegroundColor $(if ($healthData.status -eq "healthy") { "Green" } else { "Red" })
        Write-Host "Database Status: $($healthData.database_status)" -ForegroundColor $(if ($healthData.database_status -eq "healthy") { "Green" } else { "Yellow" })
        Write-Host "External APIs Status: $($healthData.external_apis_status)" -ForegroundColor $(if ($healthData.external_apis_status -eq "healthy") { "Green" } else { "Yellow" })
        Write-Host "Sync In Progress: $($healthData.sync_in_progress)" -ForegroundColor $(if ($healthData.sync_in_progress -eq $true) { "Yellow" } else { "Green" })
        
        if ($healthData.last_sync) {
            $lastSyncTime = [DateTimeOffset]::FromUnixTimeSeconds($healthData.last_sync).DateTime
            Write-Host "Last Sync: $lastSyncTime" -ForegroundColor Cyan
        } else {
            Write-Host "Last Sync: No sync completed yet" -ForegroundColor Yellow
        }
        
        if ($healthData.errors -and $healthData.errors.Count -gt 0) {
            Write-Host ""
            Write-Host "Recent Errors:" -ForegroundColor Red
            foreach ($error in $healthData.errors) {
                Write-Host "  - $error" -ForegroundColor Red
            }
        } else {
            Write-Host "Recent Errors: None" -ForegroundColor Green
        }
        
    } catch {
        Write-Host "Could not connect to health endpoint. Checking logs instead..." -ForegroundColor Yellow
    }
}

Write-Host ""
Write-Host "=== Recent Logs ===" -ForegroundColor Yellow
if ($latestPod) {
    Write-Host "Recent logs from $latestPod:" -ForegroundColor Cyan
    kubectl logs $latestPod -n $Namespace --tail=10
}

Write-Host ""
Write-Host "=== Commands to Monitor ===" -ForegroundColor Yellow
Write-Host "Live logs: kubectl logs -f deployment/safety-amp-agent -n $Namespace" -ForegroundColor Cyan
Write-Host "Pod status: kubectl get pods -n $Namespace" -ForegroundColor Cyan
Write-Host "CronJob status: kubectl get cronjobs -n $Namespace" -ForegroundColor Cyan
Write-Host "Health check: curl http://localhost:8080/health/detailed" -ForegroundColor Cyan 