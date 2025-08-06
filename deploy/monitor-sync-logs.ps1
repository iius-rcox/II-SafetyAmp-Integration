# Monitor SafetyAmp Sync Logs
# This script provides comprehensive monitoring of sync operations

param(
    [string]$Filter = "all",  # all, sync, error, cache, api
    [int]$Lines = 50,
    [switch]$Follow,
    [switch]$Summary
)

Write-Host "🔍 SafetyAmp Sync Log Monitor" -ForegroundColor Cyan
Write-Host "==================================================" -ForegroundColor Cyan

# Get current pod
$pod = kubectl get pods -n safety-amp -l app=safety-amp-agent -o jsonpath='{.items[0].metadata.name}' 2>$null
if (-not $pod) {
    Write-Host "❌ No SafetyAmp pods found" -ForegroundColor Red
    exit 1
}

Write-Host "📱 Monitoring pod: $pod" -ForegroundColor Yellow

# Function to format log entries
function Format-LogEntry {
    param([string]$Line)
    
    if ($Line -match "\[(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\] \[(\w+)\] \[(\w+)\]: (.+)") {
        $timestamp = $matches[1]
        $level = $matches[2]
        $module = $matches[3]
        $message = $matches[4]
        
        $color = switch ($level) {
            "ERROR" { "Red" }
            "WARNING" { "Yellow" }
            "INFO" { "Green" }
            default { "White" }
        }
        
        Write-Host "[$timestamp] " -NoNewline -ForegroundColor Gray
        Write-Host "[$level] " -NoNewline -ForegroundColor $color
        Write-Host "[$module] " -NoNewline -ForegroundColor Cyan
        Write-Host $message -ForegroundColor White
    } elseif ($Line -match "(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}) - - \[(.+)\] `"(.+)`" (\d{3})") {
        # HTTP request
        $ip = $matches[1]
        $timestamp = $matches[2]
        $request = $matches[3]
        $status = $matches[4]
        
        $statusColor = if ($status -eq "200") { "Green" } else { "Red" }
        
        Write-Host "[$timestamp] " -NoNewline -ForegroundColor Gray
        Write-Host "$ip " -NoNewline -ForegroundColor Blue
        Write-Host "$request " -NoNewline -ForegroundColor White
        Write-Host "$status" -ForegroundColor $statusColor
    } else {
        Write-Host $Line -ForegroundColor Gray
    }
}

# Function to get filtered logs
function Get-FilteredLogs {
    param([string]$Filter, [int]$Lines, [switch]$Follow)
    
    $baseCmd = "kubectl logs $pod -n safety-amp --tail=$Lines"
    if ($Follow) { $baseCmd += " -f" }
    
    switch ($Filter.ToLower()) {
        "sync" {
            $baseCmd += " | Select-String -Pattern 'sync|Sync|SYNC'"
        }
        "error" {
            $baseCmd += " | Select-String -Pattern 'ERROR|Error|error|Exception|exception'"
        }
        "cache" {
            $baseCmd += " | Select-String -Pattern 'cache|Cache|CACHE'"
        }
        "api" {
            $baseCmd += " | Select-String -Pattern 'api|API|rate|Rate|429'"
        }
        "db" {
            $baseCmd += " | Select-String -Pattern 'database|Database|DB|connection|Connection|timeout|Timeout'"
        }
        default {
            # No filter
        }
    }
    
    return $baseCmd
}

# Function to show sync summary
function Show-SyncSummary {
    Write-Host "`n📊 Sync Summary" -ForegroundColor Cyan
    Write-Host "=================" -ForegroundColor Cyan
    
    # Get recent logs for analysis
    $logs = kubectl logs $pod -n safety-amp --tail=200 2>$null
    
    # Count different types of entries
    $syncEntries = ($logs | Select-String -Pattern "sync|Sync|SYNC").Count
    $errorEntries = ($logs | Select-String -Pattern "ERROR|Error|error|Exception|exception").Count
    $cacheEntries = ($logs | Select-String -Pattern "cache|Cache|CACHE").Count
    $apiEntries = ($logs | Select-String -Pattern "api|API|rate|Rate|429").Count
    $dbEntries = ($logs | Select-String -Pattern "database|Database|DB|connection|Connection|timeout|Timeout").Count
    
    Write-Host "Sync Operations: $syncEntries" -ForegroundColor Green
    Write-Host "Errors: $errorEntries" -ForegroundColor $(if ($errorEntries -gt 0) { "Red" } else { "Green" })
    Write-Host "Cache Operations: $cacheEntries" -ForegroundColor Blue
    Write-Host "API Calls: $apiEntries" -ForegroundColor Yellow
    Write-Host "Database Operations: $dbEntries" -ForegroundColor Magenta
    
    # Show last successful sync
    $lastSync = $logs | Select-String -Pattern "Sync operations completed successfully" | Select-Object -Last 1
    if ($lastSync) {
        Write-Host "`n✅ Last Successful Sync: $($lastSync.Line)" -ForegroundColor Green
    } else {
        Write-Host "`n❌ No successful sync found in recent logs" -ForegroundColor Red
    }
    
    # Show current errors
    $recentErrors = $logs | Select-String -Pattern "ERROR|Error|error|Exception|exception" | Select-Object -Last 3
    if ($recentErrors) {
        Write-Host "`n⚠️ Recent Errors:" -ForegroundColor Yellow
        foreach ($error in $recentErrors) {
            Write-Host "  - $($error.Line)" -ForegroundColor Red
        }
    }
}

# Main execution
if ($Summary) {
    Show-SyncSummary
} else {
    $cmd = Get-FilteredLogs -Filter $Filter -Lines $Lines -Follow:$Follow
    
    Write-Host "`n📋 Filter: $Filter" -ForegroundColor Yellow
    Write-Host "📄 Lines: $Lines" -ForegroundColor Yellow
    if ($Follow) { Write-Host "🔄 Following logs..." -ForegroundColor Yellow }
    Write-Host "`n"
    
    # Execute the command and format output
    Invoke-Expression $cmd | ForEach-Object {
        Format-LogEntry -Line $_
    }
}

Write-Host "`n💡 Tips:" -ForegroundColor Cyan
Write-Host "  - Use -Filter sync|error|cache|api|db to filter logs" -ForegroundColor Gray
Write-Host "  - Use -Follow to watch logs in real-time" -ForegroundColor Gray
Write-Host "  - Use -Summary to see sync statistics" -ForegroundColor Gray
Write-Host "  - Use -Lines N to show N lines of logs" -ForegroundColor Gray 