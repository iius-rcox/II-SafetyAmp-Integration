#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Monitor SafetyAmp application logs in Azure Kubernetes

.DESCRIPTION
    Provides various options to monitor logs from the SafetyAmp application
    running in Azure Kubernetes Service (AKS) with enhanced error tracking
    and historical context.

.PARAMETER Mode
    The monitoring mode:
    - "realtime": Follow logs in real-time (default)
    - "recent": Show recent logs (last 50 lines)
    - "errors": Show only error logs with history
    - "errors-history": Show error history from last 24 hours
    - "errors-persistent": Show persistent errors (recurring)
    - "sync": Show sync-related logs only
    - "health": Show health check logs only
    - "summary": Show error summary and statistics

.PARAMETER Pod
    Specific pod name to monitor (optional)

.PARAMETER Hours
    Number of hours to look back for errors (default: 4)

.PARAMETER SaveErrors
    Save errors to a local file for persistent tracking

.EXAMPLE
    .\monitor-logs.ps1
    .\monitor-logs.ps1 -Mode "errors" -Hours 6
    .\monitor-logs.ps1 -Mode "errors-history" -SaveErrors
    .\monitor-logs.ps1 -Mode "summary"
    .\monitor-logs.ps1 -Mode "realtime" -Pod "safety-amp-agent-abc123"
#>

param(
    [string]$Mode = "realtime",
    [string]$Pod = "",
    [int]$Hours = 4,
    [switch]$SaveErrors
)

Write-Host "🔍 SafetyAmp Log Monitor (Enhanced)" -ForegroundColor Cyan
Write-Host "===================================" -ForegroundColor Cyan

# Create logs directory if it doesn't exist
$logsDir = "logs"
if (-not (Test-Path $logsDir)) {
    New-Item -ItemType Directory -Path $logsDir | Out-Null
}

# Get pod name if not specified
if (-not $Pod) {
    $pods = kubectl get pods -n safety-amp -l app=safety-amp,component=agent -o jsonpath='{.items[0].metadata.name}' 2>$null
    if ($pods) {
        $Pod = $pods
        Write-Host "📦 Using pod: $Pod" -ForegroundColor Yellow
    } else {
        Write-Host "❌ No SafetyAmp pods found!" -ForegroundColor Red
        return
    }
}

# Function to get logs with time filtering
function Get-LogsWithTimeFilter {
    param([string]$PodName, [int]$HoursBack)
    
    $sinceTime = (Get-Date).AddHours(-$HoursBack).ToString("yyyy-MM-ddTHH:mm:ssZ")
    $logs = kubectl logs -n safety-amp $PodName --since-time=$sinceTime 2>$null
    return $logs
}

# Function to save errors to file
function Save-ErrorsToFile {
    param([string]$Errors, [string]$PodName)
    
    $timestamp = Get-Date -Format "yyyy-MM-dd_HH-mm-ss"
    $filename = "$logsDir\errors_${PodName}_${timestamp}.log"
    $Errors | Out-File -FilePath $filename -Encoding UTF8
    Write-Host "💾 Errors saved to: $filename" -ForegroundColor Green
    return $filename
}

# Function to analyze error patterns
function Get-ErrorPatterns {
    param([string]$Logs)
    
    $errorPatterns = @{}
    $lines = $Logs -split "`n"
    
    foreach ($line in $lines) {
        if ($line -match "ERROR|Exception|Error|Failed|Failed to|Connection failed") {
            # Extract error type
            if ($line -match "TypeError: (.+)") {
                $errorType = "TypeError"
                $errorPatterns[$errorType]++
            } elseif ($line -match "Connection failed") {
                $errorType = "ConnectionError"
                $errorPatterns[$errorType]++
            } elseif ($line -match "timeout") {
                $errorType = "TimeoutError"
                $errorPatterns[$errorType]++
            } else {
                $errorType = "GeneralError"
                $errorPatterns[$errorType]++
            }
        }
    }
    
    return $errorPatterns
}

# Function to show error summary
function Show-ErrorSummary {
    param([string]$PodName, [int]$HoursBack)
    
    Write-Host "📊 Error Summary (Last $HoursBack hours)" -ForegroundColor Cyan
    Write-Host "=========================================" -ForegroundColor Cyan
    
    $logs = Get-LogsWithTimeFilter -PodName $PodName -HoursBack $HoursBack
    $errorPatterns = Get-ErrorPatterns -Logs $logs
    
    if ($errorPatterns.Count -eq 0) {
        Write-Host "✅ No errors found in the last $HoursBack hours" -ForegroundColor Green
    } else {
        Write-Host "❌ Error Summary:" -ForegroundColor Red
        foreach ($pattern in $errorPatterns.GetEnumerator()) {
            Write-Host "  - $($pattern.Key): $($pattern.Value) occurrences" -ForegroundColor Yellow
        }
    }
    
    # Show recent error trends
    $recentErrors = $logs | Select-String -Pattern "ERROR|Exception|Error|Failed" | Select-Object -Last 5
    if ($recentErrors) {
        Write-Host "`n🕒 Recent Errors:" -ForegroundColor Cyan
        foreach ($errorEntry in $recentErrors) {
            Write-Host "  $($errorEntry.Line)" -ForegroundColor Red
        }
    }
}

# Build kubectl command based on mode
switch ($Mode.ToLower()) {
    "realtime" {
        Write-Host "📺 Following logs in real-time..." -ForegroundColor Green
        Write-Host "Press Ctrl+C to stop" -ForegroundColor Yellow
        Write-Host ""
        & kubectl logs -f -n safety-amp $Pod
    }
    "recent" {
        Write-Host "📋 Showing recent logs (last 50 lines)..." -ForegroundColor Green
        Write-Host ""
        & kubectl logs -n safety-amp $Pod --tail=50
    }
    "errors" {
        Write-Host "❌ Showing error logs (last $Hours hours)..." -ForegroundColor Red
        Write-Host ""
        $logs = Get-LogsWithTimeFilter -PodName $Pod -HoursBack $Hours
        $errors = $logs | Select-String -Pattern "ERROR|Exception|Error|Failed|Failed to|Connection failed"
        
        if ($errors) {
            $errors | ForEach-Object { Write-Host $_.Line -ForegroundColor Red }
            
            if ($SaveErrors) {
                Save-ErrorsToFile -Errors ($errors -join "`n") -PodName $Pod
            }
        } else {
            Write-Host "✅ No errors found in the last $Hours hours" -ForegroundColor Green
        }
    }
    "errors-history" {
        Write-Host "📚 Showing error history (last $Hours hours)..." -ForegroundColor Magenta
        Write-Host ""
        $logs = Get-LogsWithTimeFilter -PodName $Pod -HoursBack $Hours
        $errors = $logs | Select-String -Pattern "ERROR|Exception|Error|Failed|Failed to|Connection failed"
        
        if ($errors) {
            # Group errors by time
            $groupedErrors = $errors | Group-Object { 
                if ($_.Line -match "\[(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\]") {
                    $matches[1]
                } else {
                    "Unknown"
                }
            }
            
            foreach ($group in $groupedErrors | Sort-Object Name) {
                Write-Host "`n🕒 $($group.Name):" -ForegroundColor Cyan
                foreach ($errorEntry in $group.Group) {
                    Write-Host "  $($errorEntry.Line)" -ForegroundColor Red
                }
            }
            
            if ($SaveErrors) {
                Save-ErrorsToFile -Errors ($errors -join "`n") -PodName $Pod
            }
        } else {
            Write-Host "✅ No errors found in the last $Hours hours" -ForegroundColor Green
        }
    }
    "errors-persistent" {
        Write-Host "🔄 Showing persistent/recurring errors..." -ForegroundColor Yellow
        Write-Host ""
        $logs = Get-LogsWithTimeFilter -PodName $Pod -HoursBack $Hours
        $errors = $logs | Select-String -Pattern "ERROR|Exception|Error|Failed|Failed to|Connection failed"
        
        if ($errors) {
            # Find recurring errors
            $errorCounts = $errors | Group-Object { 
                # Extract error message without timestamp
                if ($_.Line -match "\[.*?\] \[.*?\] \[.*?\]: (.+)") {
                    $matches[1]
                } else {
                    $_.Line
                }
            } | Where-Object { $_.Count -gt 1 }
            
            if ($errorCounts) {
                Write-Host "🔄 Recurring Errors:" -ForegroundColor Yellow
                foreach ($errorGroup in $errorCounts | Sort-Object Count -Descending) {
                    Write-Host "  [$($errorGroup.Count)x] $($errorGroup.Name)" -ForegroundColor Red
                }
            } else {
                Write-Host "✅ No recurring errors found" -ForegroundColor Green
            }
        } else {
            Write-Host "✅ No errors found in the last $Hours hours" -ForegroundColor Green
        }
    }
    "sync" {
        Write-Host "🔄 Showing sync-related logs..." -ForegroundColor Blue
        Write-Host ""
        & kubectl logs -n safety-amp $Pod | Select-String -Pattern "sync|Sync|SYNC|employee|Employee|vehicle|Vehicle|department|Department"
    }
    "health" {
        Write-Host "💚 Showing health check logs..." -ForegroundColor Green
        Write-Host ""
        & kubectl logs -n safety-amp $Pod | Select-String -Pattern "health|Health|ready|Ready|GET /health|GET /ready"
    }
    "summary" {
        Show-ErrorSummary -PodName $Pod -HoursBack $Hours
    }
    default {
        Write-Host "❌ Unknown mode: $Mode" -ForegroundColor Red
        Write-Host "Available modes: realtime, recent, errors, errors-history, errors-persistent, sync, health, summary" -ForegroundColor Yellow
        return
    }
}

Write-Host "`n💡 Tips:" -ForegroundColor Cyan
Write-Host "  - Use -Hours N to specify time range for error analysis" -ForegroundColor Gray
Write-Host "  - Use -SaveErrors to save errors to local files" -ForegroundColor Gray
Write-Host "  - Use 'errors-history' to see errors grouped by time" -ForegroundColor Gray
Write-Host "  - Use 'errors-persistent' to find recurring issues" -ForegroundColor Gray
Write-Host "  - Use 'summary' for quick error statistics" -ForegroundColor Gray 