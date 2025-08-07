#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Monitor SafetyAmp Integration Changes
    
.DESCRIPTION
    This script provides various ways to monitor and track changes made during sync operations.
    It can show recent changes, generate reports, and provide real-time monitoring.
#>

param(
    [string]$Action = "summary",
    [int]$Hours = 24,
    [string]$EntityType = "",
    [string]$Operation = "",
    [switch]$RealTime,
    [switch]$Export
)

# Colors for output
$Colors = @{
    Success = "Green"
    Warning = "Yellow"
    Error = "Red"
    Info = "Cyan"
    Header = "Magenta"
}

function Write-ColorOutput {
    param([string]$Message, [string]$Color = "White")
    Write-Host $Message -ForegroundColor $Colors[$Color]
}

function Get-ChangeTrackerData {
    param([string]$PodName, [string]$Namespace = "safety-amp")
    
    try {
        # Execute the change tracker script in the pod
        $result = kubectl exec $PodName -n $Namespace -- python -c "
import sys
sys.path.append('/app')
from utils.change_tracker import ChangeTracker

tracker = ChangeTracker()
if '$Action' == 'summary':
    report = tracker.get_summary_report($Hours)
    print('CHANGE_TRACKER_DATA_START')
    import json
    print(json.dumps(report, indent=2))
    print('CHANGE_TRACKER_DATA_END')
elif '$Action' == 'changes':
    changes = tracker.get_recent_changes($Hours)
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
        Write-ColorOutput "Error getting change tracker data: $_" "Error"
    }
    return $null
}

function Show-SummaryReport {
    param($Data)
    
    Write-ColorOutput "`n=== SafetyAmp Integration Change Summary (Last $Hours hours) ===" "Header"
    
    if ($Data.total_changes -eq 0) {
        Write-ColorOutput "No changes recorded in the last $Hours hours." "Warning"
        return
    }
    
    Write-ColorOutput "`n📊 Overall Statistics:" "Info"
    Write-ColorOutput "  Total Changes: $($Data.total_changes)" "Info"
    
    Write-ColorOutput "`n🔄 Operations Breakdown:" "Info"
    foreach ($op in $Data.by_operation.GetEnumerator()) {
        $color = if ($op.Key -eq "created") { "Success" } elseif ($op.Key -eq "updated") { "Info" } elseif ($op.Key -eq "errors") { "Error" } else { "Warning" }
        Write-ColorOutput "  $($op.Key.ToUpper()): $($op.Value)" $color
    }
    
    Write-ColorOutput "`n🏷️  Entity Types:" "Info"
    foreach ($entity in $Data.by_entity_type.GetEnumerator()) {
        Write-ColorOutput "  $($entity.Key): $($entity.Value)" "Info"
    }
    
    Write-ColorOutput "`n📈 Recent Sessions:" "Info"
    foreach ($session in $Data.recent_sessions) {
        $status = if ($session.total_errors -eq 0) { "Success" } else { "Warning" }
        Write-ColorOutput "  Session: $($session.session_id)" $status
        Write-ColorOutput "    Type: $($session.sync_type)" "Info"
        Write-ColorOutput "    Duration: $($session.duration_seconds)s" "Info"
        Write-ColorOutput "    Processed: $($session.total_processed)" "Info"
        Write-ColorOutput "    Created: $($session.total_created)" "Success"
        Write-ColorOutput "    Updated: $($session.total_updated)" "Info"
        Write-ColorOutput "    Errors: $($session.total_errors)" $(if ($session.total_errors -eq 0) { "Success" } else { "Error" })
        Write-ColorOutput ""
    }
}

function Show-DetailedChanges {
    param($Data, [string]$EntityType, [string]$Operation)
    
    Write-ColorOutput "`n=== Detailed Changes (Last $Hours hours) ===" "Header"
    
    if ($Data.Count -eq 0) {
        Write-ColorOutput "No changes found in the last $Hours hours." "Warning"
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
        Write-ColorOutput "No changes match the specified filters." "Warning"
        return
    }
    
    foreach ($change in $filteredData) {
        $timestamp = [datetime]::Parse($change.timestamp).ToString("yyyy-MM-dd HH:mm:ss")
        $color = switch ($change.operation) {
            "created" { "Success" }
            "updated" { "Info" }
            "deleted" { "Warning" }
            "skipped" { "Warning" }
            "error" { "Error" }
            default { "White" }
        }
        
        Write-ColorOutput "`n[$timestamp] $($change.operation.ToUpper()) $($change.entity_type) $($change.entity_id)" $color
        
        if ($change.changes) {
            Write-ColorOutput "  Changes: $($change.changes | ConvertTo-Json -Compress)" "Info"
        }
        
        if ($change.reason) {
            Write-ColorOutput "  Reason: $($change.reason)" "Warning"
        }
        
        if ($change.error) {
            Write-ColorOutput "  Error: $($change.error)" "Error"
        }
        
        Write-ColorOutput "  Session: $($change.session_id)" "Info"
    }
}

function Start-RealTimeMonitoring {
    Write-ColorOutput "`n🔄 Starting real-time change monitoring..." "Info"
    Write-ColorOutput "Press Ctrl+C to stop monitoring" "Warning"
    
    $lastSessionId = ""
    
    while ($true) {
        try {
            $pod = Get-SafetyAmpPod
            if ($pod) {
                $data = Get-ChangeTrackerData -PodName $pod
                if ($data) {
                    $latestSession = $data.recent_sessions | Select-Object -First 1
                    if ($latestSession -and $latestSession.session_id -ne $lastSessionId) {
                        Write-ColorOutput "`n🆕 New sync session detected: $($latestSession.session_id)" "Success"
                        Write-ColorOutput "  Type: $($latestSession.sync_type)" "Info"
                        Write-ColorOutput "  Processed: $($latestSession.total_processed)" "Info"
                        Write-ColorOutput "  Created: $($latestSession.total_created)" "Success"
                        Write-ColorOutput "  Updated: $($latestSession.total_updated)" "Info"
                        Write-ColorOutput "  Errors: $($latestSession.total_errors)" $(if ($latestSession.total_errors -eq 0) { "Success" } else { "Error" })
                        
                        $lastSessionId = $latestSession.session_id
                    }
                }
            }
            
            Start-Sleep -Seconds 30
        }
        catch {
            Write-ColorOutput "Error in real-time monitoring: $_" "Error"
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
        
        Write-ColorOutput "`n✅ Data exported to: $filename" "Success"
    }
    catch {
        Write-ColorOutput "Error exporting data: $_" "Error"
    }
}

# Main execution
Write-ColorOutput "🔍 SafetyAmp Integration Change Monitor" "Header"
Write-ColorOutput "Action: $Action, Hours: $Hours" "Info"

$pod = Get-SafetyAmpPod
if (-not $pod) {
    Write-ColorOutput "❌ No SafetyAmp pods found running" "Error"
    exit 1
}

Write-ColorOutput "📦 Using pod: $pod" "Info"

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
                Write-ColorOutput "Unknown action: $Action" "Error"
                Write-ColorOutput "Available actions: summary, changes" "Info"
            }
        }
        
        if ($Export) {
            Export-ChangeData -Data $data
        }
    }
    else {
        Write-ColorOutput "❌ No change tracker data available" "Error"
    }
} 