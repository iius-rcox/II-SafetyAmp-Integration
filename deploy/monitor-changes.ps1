#!/usr/bin/env pwsh
param(
    [string]$Action = "summary",
    [int]$Hours = 24,
    [string]$EntityType = "",
    [string]$Operation = "",
    [switch]$RealTime,
    [switch]$Export
)

Write-Host "⚠️  'monitor-changes.ps1' is deprecated. Use 'monitor.ps1 -Feature changes' instead." -ForegroundColor Yellow
& "$PSScriptRoot/monitor.ps1" -Feature changes -Hours $Hours -Action $Action -EntityType $EntityType -Operation $Operation -RealTime:$RealTime -Export:$Export

function Get-ChangeTrackerData {
    param([string]$PodName, [string]$Namespace = "safety-amp")
    
    try {
        # Execute the change/event manager script in the pod
        $result = kubectl exec $PodName -n $Namespace -- python -c "
import sys
sys.path.append('/app')
from services.event_manager import event_manager

if '$Action' == 'summary':
    # event_manager wraps ChangeTracker internally; reuse summary file outputs
    report = event_manager.change_tracker.get_summary_report($Hours)
    print('CHANGE_TRACKER_DATA_START')
    import json
    print(json.dumps(report, indent=2))
    print('CHANGE_TRACKER_DATA_END')
elif '$Action' == 'changes':
    changes = event_manager.change_tracker.get_recent_changes($Hours)
    print('CHANGE_TRACKER_DATA_START')
    import json
    print(json.dumps(changes, indent=2))
    print('CHANGE_TRACKER_DATA_END')
"
        
        if ($result -match 'CHANGE_TRACKER_DATA_START(.*?)CHANGE_TRACKER_DATA_END') {
            $jsonData = $matches[1].Trim()
            return $jsonData | ConvertFrom-Json
        }
    }
    catch {
            Write-ColorOutput "Error getting change tracker data: $_" -Color Red
    }
    return $null
}

function Show-SummaryReport {
    param($Data)
    
    Write-ColorOutput "`n=== SafetyAmp Integration Change Summary (Last $Hours hours) ===" -Color Magenta
    
    if ($Data.total_changes -eq 0) {
        Write-ColorOutput "No changes recorded in the last $Hours hours." -Color Yellow
        return
    }
    
    Write-ColorOutput "`n📊 Overall Statistics:" -Color Cyan
    Write-ColorOutput "  Total Changes: $($Data.total_changes)" -Color Cyan
    
    Write-ColorOutput "`n🔄 Operations Breakdown:" -Color Cyan
    foreach ($op in $Data.by_operation.GetEnumerator()) {
        $color = if ($op.Key -eq "created") { 'Green' } elseif ($op.Key -eq "updated") { 'Cyan' } elseif ($op.Key -eq "errors") { 'Red' } else { 'Yellow' }
        Write-ColorOutput "  $($op.Key.ToUpper()): $($op.Value)" -Color $color
    }
    
    Write-ColorOutput "`n🏷️  Entity Types:" -Color Cyan
    foreach ($entity in $Data.by_entity_type.GetEnumerator()) {
        Write-ColorOutput "  $($entity.Key): $($entity.Value)" -Color Cyan
    }
    
    Write-ColorOutput "`n📈 Recent Sessions:" -Color Cyan
    foreach ($session in $Data.recent_sessions) {
        $statusColor = if ($session.total_errors -eq 0) { 'Green' } else { 'Yellow' }
        Write-ColorOutput "  Session: $($session.session_id)" -Color $statusColor
        Write-ColorOutput "    Type: $($session.sync_type)" -Color Cyan
        Write-ColorOutput "    Duration: $($session.duration_seconds)s" -Color Cyan
        Write-ColorOutput "    Processed: $($session.total_processed)" -Color Cyan
        Write-ColorOutput "    Created: $($session.total_created)" -Color Green
        Write-ColorOutput "    Updated: $($session.total_updated)" -Color Cyan
        Write-ColorOutput "    Errors: $($session.total_errors)" -Color $(if ($session.total_errors -eq 0) { 'Green' } else { 'Red' })
        Write-ColorOutput ""
    }
}

function Show-DetailedChanges {
    param($Data, [string]$EntityType, [string]$Operation)
    
    Write-ColorOutput "`n=== Detailed Changes (Last $Hours hours) ===" -Color Magenta
    
    if ($Data.Count -eq 0) {
        Write-ColorOutput "No changes found in the last $Hours hours." -Color Yellow
        return
    }
    
    $filteredData = $Data
    
    # Apply filters
    if ($EntityType) {
        $filteredData = $filteredData | Where-Object { $_.entity_type -eq $EntityType }
    }
    
    if ($Operation) {
        $filteredData = $filteredData | Where-Object { $_.operation -eq $Operation }
    }
    
    if ($filteredData.Count -eq 0) {
        Write-ColorOutput "No changes match the specified filters." -Color Yellow
        return
    }
    
    foreach ($change in $filteredData) {
        $timestamp = [datetime]::Parse($change.timestamp).ToString("yyyy-MM-dd HH:mm:ss")
        $color = switch ($change.operation) {
            "created" { 'Green' }
            "updated" { 'Cyan' }
            "deleted" { 'Yellow' }
            "skipped" { 'Yellow' }
            "error" { 'Red' }
            default { 'White' }
        }
        
        Write-ColorOutput "`n[$timestamp] $($change.operation.ToUpper()) $($change.entity_type) $($change.entity_id)" -Color $color
        
        if ($change.changes) {
            Write-ColorOutput "  Changes: $($change.changes | ConvertTo-Json -Compress)" -Color Cyan
        }
        
        if ($change.reason) {
            Write-ColorOutput "  Reason: $($change.reason)" -Color Yellow
        }
        
        if ($change.error) {
            Write-ColorOutput "  Error: $($change.error)" -Color Red
        }
        
        Write-ColorOutput "  Session: $($change.session_id)" -Color Cyan
    }
}

function Start-RealTimeMonitoring {
    Write-ColorOutput "`n🔄 Starting real-time change monitoring..." -Color Cyan
    Write-ColorOutput "Press Ctrl+C to stop monitoring" -Color Yellow
    
    $lastSessionId = ""
    
    while ($true) {
        try {
            $pod = Get-SafetyAmpPod
            if ($pod) {
                $data = Get-ChangeTrackerData -PodName $pod
                if ($data) {
                    $latestSession = $data.recent_sessions | Select-Object -First 1
                    if ($latestSession -and $latestSession.session_id -ne $lastSessionId) {
                        Write-ColorOutput "`n🆕 New sync session detected: $($latestSession.session_id)" -Color Green
                        Write-ColorOutput "  Type: $($latestSession.sync_type)" -Color Cyan
                        Write-ColorOutput "  Processed: $($latestSession.total_processed)" -Color Cyan
                        Write-ColorOutput "  Created: $($latestSession.total_created)" -Color Green
                        Write-ColorOutput "  Updated: $($latestSession.total_updated)" -Color Cyan
                        Write-ColorOutput "  Errors: $($latestSession.total_errors)" -Color $(if ($latestSession.total_errors -eq 0) { 'Green' } else { 'Red' })
                        
                        $lastSessionId = $latestSession.session_id
                    }
                }
            }
            
            Start-Sleep -Seconds 30
        }
        catch {
            Write-ColorOutput "Error in real-time monitoring: $_" -Color Red
            Start-Sleep -Seconds 60
        }
    }
}

function Get-SafetyAmpPod {
    try {
        $pods = kubectl get pods -n safety-amp -l app=safety-amp --no-headers -o custom-columns=":metadata.name" 2>$null
        if ($pods) {
            return ($pods -split "`n" | Where-Object { $_ -match "safety-amp-agent" } | Select-Object -First 1).Trim()
        }
    }
    catch {
        Write-ColorOutput "Error getting SafetyAmp pod: $_" "Error"
    }
    return $null
}

function Export-ChangeData {
    param($Data, [string]$Format = "json")
    
    $timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
    $filename = "safetyamp_changes_$timestamp.$Format"
    
    try {
        if ($Format -eq "json") {
            $Data | ConvertTo-Json -Depth 10 | Out-File -FilePath $filename -Encoding UTF8
        }
        elseif ($Format -eq "csv") {
            # Convert to CSV format for changes
            $csvData = @()
            foreach ($change in $Data) {
                $csvData += [PSCustomObject]@{
                    Timestamp = $change.timestamp
                    Operation = $change.operation
                    EntityType = $change.entity_type
                    EntityID = $change.entity_id
                    Status = $change.status
                    SessionID = $change.session_id
                    SyncType = $change.sync_type
                }
            }
            $csvData | Export-Csv -Path $filename -NoTypeInformation
        }
        
    Write-ColorOutput "`n✅ Data exported to: $filename" -Color Green
    }
    catch {
        Write-ColorOutput "Error exporting data: $_" -Color Red
    }
}

# Main execution
Write-ColorOutput "🔍 SafetyAmp Integration Change Monitor" -Color Magenta
Write-ColorOutput "Action: $Action, Hours: $Hours" -Color Cyan

$pod = Get-SafetyAmpPod
if (-not $pod) {
    Write-ColorOutput "❌ No SafetyAmp pods found running" -Color Red
    exit 1
}

Write-ColorOutput "📦 Using pod: $pod" -Color Cyan

if ($RealTime) {
    Start-RealTimeMonitoring
}
else {
    $data = Get-ChangeTrackerData -PodName $pod
    
    if ($data) {
        switch ($Action.ToLower()) {
            "summary" {
                Show-SummaryReport -Data $data
            }
            "changes" {
                Show-DetailedChanges -Data $data -EntityType $EntityType -Operation $Operation
            }
            default {
                Write-ColorOutput "Unknown action: $Action" -Color Red
                Write-ColorOutput "Available actions: summary, changes" -Color Cyan
            }
        }
        
        if ($Export) {
            Export-ChangeData -Data $data
        }
    }
    else {
        Write-ColorOutput "❌ No change tracker data available" -Color Red
    }
} 