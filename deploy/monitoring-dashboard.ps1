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

param(
    [int]$Hours = 24,
    [string[]]$Sections = @('all')
)

Import-Module "$PSScriptRoot/modules/Output.psm1" -Force
Import-Module "$PSScriptRoot/modules/Kube.psm1" -Force

$includeAll = ($Sections -contains 'all')

Write-Host "📊 SafetyAmp Monitoring Dashboard" -ForegroundColor Cyan
Write-Host "=================================" -ForegroundColor Cyan
Write-Host ""

if ($includeAll -or $Sections -contains 'pods') {
    Write-SectionHeader "Pod Status"
    $pods = kubectl get pods -n safety-amp -o wide 2>$null
    if ($pods) { Write-Host $pods } else { Write-Status "No pods found in safety-amp namespace" $false }
}

if ($includeAll -or $Sections -contains 'services') {
    Write-SectionHeader "Service Status"
    $services = kubectl get services -n safety-amp 2>$null
    if ($services) { Write-Host $services } else { Write-Status "No services found in safety-amp namespace" $false }
}

if ($includeAll -or $Sections -contains 'logs') {
    Write-SectionHeader "Recent Logs Summary"
    $latestPod = Get-SafetyAmpPod -Namespace 'safety-amp' -Selector 'app=safety-amp-agent'
    if ($latestPod) {
        $sinceTime = (Get-Date).AddHours(-$Hours).ToString('yyyy-MM-ddTHH:mm:ssZ')
        $recentLogs = kubectl logs -n safety-amp $latestPod --since-time=$sinceTime 2>$null | Select-Object -Last 10
        if ($recentLogs) { Write-Host $recentLogs } else { Write-Status "No recent logs available" $false }
    } else { Write-Status "No SafetyAmp pods found" $false }
}

if ($includeAll -or $Sections -contains 'errors') {
    Write-SectionHeader "Error Summary"
    if (-not $latestPod) { $latestPod = Get-SafetyAmpPod -Namespace 'safety-amp' -Selector 'app=safety-amp-agent' }
    if ($latestPod) {
        $sinceTime = (Get-Date).AddHours(-$Hours).ToString('yyyy-MM-ddTHH:mm:ssZ')
        $errorLogs = kubectl logs -n safety-amp $latestPod --since-time=$sinceTime 2>$null | Select-String -Pattern "ERROR|Exception|Error|Failed|Failed to|Connection failed" | Select-Object -Last 5
        if ($errorLogs) { Write-Host $errorLogs } else { Write-Status "No recent errors found" $true }
    } else { Write-Status "Cannot check errors - no pods available" $false }
}

if ($includeAll -or $Sections -contains 'sync') {
    Write-SectionHeader "Sync Status"
    $syncJobs = kubectl get jobs -n safety-amp 2>$null
    if ($syncJobs) { Write-Host $syncJobs } else { Write-Status "No sync jobs found" $false }
}

if ($includeAll -or $Sections -contains 'resources') {
    Write-SectionHeader "Resource Usage"
    $resourceUsage = kubectl top pods -n safety-amp 2>$null
    if ($resourceUsage) { Write-Host $resourceUsage } else { Write-Status "Resource usage not available (metrics server may not be installed)" $false }
}

if ($includeAll -or $Sections -contains 'health') {
    Write-SectionHeader "Health Check"
    try {
        if (-not $latestPod) { $latestPod = Get-SafetyAmpPod -Namespace 'safety-amp' -Selector 'app=safety-amp-agent' }
        $healthResponse = kubectl exec -n safety-amp $latestPod -- curl -s http://localhost:8080/health 2>$null
        if ($healthResponse) {
            Write-Host "Health endpoint response:" -ForegroundColor Green
            Write-Host $healthResponse
        } else { Write-Status "Health endpoint not responding" $false }
    } catch { Write-Status "Cannot check health endpoint" $false }
}

if ($includeAll -or $Sections -contains 'connectivity') {
    Write-SectionHeader "Connectivity Test"
    try {
        if (-not $latestPod) { $latestPod = Get-SafetyAmpPod -Namespace 'safety-amp' -Selector 'app=safety-amp-agent' }
        $exit = 0
        kubectl exec -n safety-amp $latestPod -- python test-connections.py 2>$null
        $exit = $LASTEXITCODE
        if ($exit -eq 0) { Write-Status "Unified health endpoint indicates healthy or degraded" $true } else { Write-Status "Unified health endpoint indicates unhealthy" $false }
    } catch { Write-Status "Cannot run connectivity test" $false }
}

if ($includeAll -or $Sections -contains 'cache') {
    Write-SectionHeader "Cache Status"
    try {
        if (-not $latestPod) { $latestPod = Get-SafetyAmpPod -Namespace 'safety-amp' -Selector 'app=safety-amp-agent' }
        $cacheInfo = kubectl exec -n safety-amp $latestPod -- ls -la /app/cache 2>$null
        if ($cacheInfo) { Write-Host "Cache directory contents:" -ForegroundColor Green; Write-Host $cacheInfo } else { Write-Status "Cache directory not accessible" $false }
    } catch { Write-Status "Cannot check cache status" $false }
}

if ($includeAll -or $Sections -contains 'config') {
    Write-SectionHeader "Configuration Summary"
    $configMap = kubectl get configmap safety-amp-config -n safety-amp -o yaml 2>$null
    if ($configMap) { Write-Host "Configuration loaded successfully" -ForegroundColor Green } else { Write-Status "Configuration not found" $false }
}

# 11. Validation Summary (lightweight)
if ($includeAll -or $Sections -contains 'validation') {
    Write-SectionHeader "Validation Summary"
    $latestPod = if ($latestPod) { $latestPod } else { Get-SafetyAmpPod -Namespace 'safety-amp' -Selector 'app=safety-amp-agent' }
    if ($latestPod) {
        $sinceTime = (Get-Date).AddHours(-$Hours).ToString('yyyy-MM-ddTHH:mm:ssZ')
        $logs = kubectl logs -n safety-amp $latestPod --since-time=$sinceTime 2>$null
        if ($logs) {
            $stats = @{
                'Generated Default Names' = ($logs | Select-String -Pattern "Generated default.*name").Count
                'Generated Emails' = ($logs | Select-String -Pattern "Generated email").Count
                'Missing Required Fields' = ($logs | Select-String -Pattern "Missing required field").Count
                'Validation Errors' = ($logs | Select-String -Pattern "Validation errors|Validation failed").Count
            }
            $stats.GetEnumerator() | ForEach-Object { Write-Host ("  {0}: {1}" -f $_.Key, $_.Value) -ForegroundColor (if ($_.Value -gt 0) { 'Yellow' } else { 'Green' }) }
        } else { Write-Status "No logs available for validation analysis" $false }
    } else { Write-Status "No SafetyAmp pods found" $false }
}

# 12. Changes Summary
if ($includeAll -or $Sections -contains 'changes') {
    Write-SectionHeader "Change Tracker Summary"
    $latestPod = if ($latestPod) { $latestPod } else { Get-SafetyAmpPod -Namespace 'safety-amp' -Selector 'app=safety-amp-agent' }
    if ($latestPod) {
        $py = @"
import sys, json
sys.path.append('/app')
from services.event_manager import event_manager
report = event_manager.change_tracker.get_summary_report($Hours)
print('START')
print(json.dumps(report))
print('END')
"@
        $result = kubectl exec $latestPod -n safety-amp -- python -c "$py" 2>$null
        if ($result -match 'START(.*?)END') {
            $data = ($matches[1].Trim() | ConvertFrom-Json)
            if ($data) {
                Write-Host ("  Total Changes: {0}" -f $data.total_changes) -ForegroundColor Cyan
                if ($data.by_operation) {
                    Write-Host "  By Operation:" -ForegroundColor Cyan
                    foreach ($op in $data.by_operation.GetEnumerator()) { Write-Host ("    {0}: {1}" -f $op.Key, $op.Value) }
                }
            } else { Write-Status "No change tracker data" $false }
        } else { Write-Status "Unable to retrieve change tracker data" $false }
    } else { Write-Status "No SafetyAmp pods found" $false }
}

# 13. Sync Summary (logs analysis)
if ($includeAll -or $Sections -contains 'sync-summary') {
    Write-SectionHeader "Sync Summary"
    $latestPod = if ($latestPod) { $latestPod } else { Get-SafetyAmpPod -Namespace 'safety-amp' -Selector 'app=safety-amp-agent' }
    if ($latestPod) {
        $logs = kubectl logs $latestPod -n safety-amp --tail=200 2>$null
        if ($logs) {
            $syncEntries = ($logs | Select-String -Pattern "sync|Sync|SYNC").Count
            $errorEntries = ($logs | Select-String -Pattern "ERROR|Error|error|Exception|exception").Count
            $apiEntries = ($logs | Select-String -Pattern "api|API|rate|Rate|429").Count
            Write-Host "  Sync Operations: $syncEntries" -ForegroundColor Green
            Write-Host "  Errors: $errorEntries" -ForegroundColor $(if ($errorEntries -gt 0) { 'Red' } else { 'Green' })
            Write-Host "  API Calls: $apiEntries" -ForegroundColor Yellow
        } else { Write-Status "No logs available for sync summary" $false }
    } else { Write-Status "No SafetyAmp pods found" $false }
}

Write-Host ""
Write-Host "📈 Dashboard completed at $(Get-Date)" -ForegroundColor Cyan
Write-Host "For real-time monitoring, run: .\monitor.ps1 -Feature dashboard" -ForegroundColor Yellow