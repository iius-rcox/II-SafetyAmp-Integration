#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Monitor SafetyAmp application logs in Azure Kubernetes

.DESCRIPTION
    Provides various options to monitor logs from the SafetyAmp application
    running in Azure Kubernetes Service (AKS).

.PARAMETER Mode
    The monitoring mode:
    - "realtime": Follow logs in real-time (default)
    - "recent": Show recent logs (last 50 lines)
    - "errors": Show only error logs
    - "sync": Show sync-related logs only
    - "health": Show health check logs only

.PARAMETER Pod
    Specific pod name to monitor (optional)

.EXAMPLE
    .\monitor-logs.ps1
    .\monitor-logs.ps1 -Mode "errors"
    .\monitor-logs.ps1 -Mode "realtime" -Pod "safety-amp-agent-abc123"
#>

param(
    [string]$Mode = "realtime",
    [string]$Pod = ""
)

Write-Host "🔍 SafetyAmp Log Monitor" -ForegroundColor Cyan
Write-Host "=========================" -ForegroundColor Cyan

# Get pod name if not specified
if (-not $Pod) {
    $pods = kubectl get pods -n safety-amp -l app=safety-amp-agent -o jsonpath='{.items[0].metadata.name}' 2>$null
    if ($pods) {
        $Pod = $pods
        Write-Host "📦 Using pod: $Pod" -ForegroundColor Yellow
    } else {
        Write-Host "❌ No SafetyAmp pods found!" -ForegroundColor Red
        exit 1
    }
}

# Build kubectl command based on mode
$kubectlCmd = "kubectl logs -n safety-amp"

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
        Write-Host "❌ Showing error logs only..." -ForegroundColor Red
        Write-Host ""
        & kubectl logs -n safety-amp $Pod | Select-String -Pattern "ERROR|Exception|Error|Failed|Failed to|Connection failed"
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
    default {
        Write-Host "❌ Unknown mode: $Mode" -ForegroundColor Red
        Write-Host "Available modes: realtime, recent, errors, sync, health" -ForegroundColor Yellow
        exit 1
    }
} 