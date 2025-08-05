#!/usr/bin/env pwsh
<#
.SYNOPSIS
    SafetyAmp Monitoring Dashboard

.DESCRIPTION
    Comprehensive monitoring dashboard for the SafetyAmp application
    running in Azure Kubernetes Service (AKS).

.EXAMPLE
    .\monitoring-dashboard.ps1
#>

Write-Host "📊 SafetyAmp Monitoring Dashboard" -ForegroundColor Cyan
Write-Host "=================================" -ForegroundColor Cyan
Write-Host ""

# Function to print section headers
function Write-SectionHeader {
    param([string]$Title)
    Write-Host ""
    Write-Host "🔍 $Title" -ForegroundColor Yellow
    Write-Host ("=" * (4 + $Title.Length)) -ForegroundColor Yellow
}

# Function to print status
function Write-Status {
    param([string]$Message, [bool]$Success)
    $icon = if ($Success) { "✅" } else { "❌" }
    $color = if ($Success) { "Green" } else { "Red" }
    Write-Host "$icon $Message" -ForegroundColor $color
}

# 1. Pod Status
Write-SectionHeader "Pod Status"
$pods = kubectl get pods -n safety-amp -o wide 2>$null
if ($pods) {
    Write-Host $pods
} else {
    Write-Status "No pods found in safety-amp namespace" $false
}

# 2. Service Status
Write-SectionHeader "Service Status"
$services = kubectl get services -n safety-amp 2>$null
if ($services) {
    Write-Host $services
} else {
    Write-Status "No services found in safety-amp namespace" $false
}

# 3. Recent Logs Summary
Write-SectionHeader "Recent Logs Summary"
$latestPod = kubectl get pods -n safety-amp -l app=safety-amp-agent -o jsonpath='{.items[0].metadata.name}' 2>$null
if ($latestPod) {
    $recentLogs = kubectl logs -n safety-amp $latestPod --tail=10 2>$null
    if ($recentLogs) {
        Write-Host $recentLogs
    } else {
        Write-Status "No recent logs available" $false
    }
} else {
    Write-Status "No SafetyAmp pods found" $false
}

# 4. Error Summary
Write-SectionHeader "Error Summary"
if ($latestPod) {
    $errorLogs = kubectl logs -n safety-amp $latestPod --tail=100 2>$null | Select-String -Pattern "ERROR|Exception|Error|Failed|Failed to|Connection failed" | Select-Object -Last 5
    if ($errorLogs) {
        Write-Host $errorLogs
    } else {
        Write-Status "No recent errors found" $true
    }
} else {
    Write-Status "Cannot check errors - no pods available" $false
}

# 5. Sync Status
Write-SectionHeader "Sync Status"
$syncJobs = kubectl get jobs -n safety-amp 2>$null
if ($syncJobs) {
    Write-Host $syncJobs
} else {
    Write-Status "No sync jobs found" $false
}

# 6. Resource Usage
Write-SectionHeader "Resource Usage"
$resourceUsage = kubectl top pods -n safety-amp 2>$null
if ($resourceUsage) {
    Write-Host $resourceUsage
} else {
    Write-Status "Resource usage not available (metrics server may not be installed)" $false
}

# 7. Health Check
Write-SectionHeader "Health Check"
try {
    $healthResponse = kubectl exec -n safety-amp $latestPod -- curl -s http://localhost:8080/health 2>$null
    if ($healthResponse) {
        Write-Host "Health endpoint response:" -ForegroundColor Green
        Write-Host $healthResponse
    } else {
        Write-Status "Health endpoint not responding" $false
    }
} catch {
    Write-Status "Cannot check health endpoint" $false
}

# 8. Connectivity Test
Write-SectionHeader "Connectivity Test"
try {
    $connectivityResult = kubectl exec -n safety-amp $latestPod -- python test-connections.py 2>$null
    if ($connectivityResult -match "All services are connected successfully") {
        Write-Status "All external services connected" $true
    } else {
        Write-Status "Some services failed to connect" $false
        Write-Host $connectivityResult
    }
} catch {
    Write-Status "Cannot run connectivity test" $false
}

# 9. Cache Status
Write-SectionHeader "Cache Status"
try {
    $cacheInfo = kubectl exec -n safety-amp $latestPod -- ls -la /app/cache 2>$null
    if ($cacheInfo) {
        Write-Host "Cache directory contents:" -ForegroundColor Green
        Write-Host $cacheInfo
    } else {
        Write-Status "Cache directory not accessible" $false
    }
} catch {
    Write-Status "Cannot check cache status" $false
}

# 10. Configuration Summary
Write-SectionHeader "Configuration Summary"
$configMap = kubectl get configmap safety-amp-config -n safety-amp -o yaml 2>$null
if ($configMap) {
    Write-Host "Configuration loaded successfully" -ForegroundColor Green
} else {
    Write-Status "Configuration not found" $false
}

Write-Host ""
Write-Host "📈 Dashboard completed at $(Get-Date)" -ForegroundColor Cyan
Write-Host "For real-time monitoring, run: .\monitor-logs.ps1" -ForegroundColor Yellow 