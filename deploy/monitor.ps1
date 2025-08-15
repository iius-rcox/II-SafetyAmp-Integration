#!/usr/bin/env pwsh
<#!
.SYNOPSIS
    Unified Monitoring Entry Point for SafetyAmp

.DESCRIPTION
    Consolidates multiple monitoring scripts into a single parameterized command.

.EXAMPLES
    ./monitor.ps1 -Feature logs -Mode summary -Hours 6
    ./monitor.ps1 -Feature validation -Action validation-summary -Hours 24
    ./monitor.ps1 -Feature changes -Action changes -Hours 12 -EntityType employee -Operation updated
    ./monitor.ps1 -Feature sync -Filter error -Lines 200 -Follow
    ./monitor.ps1 -Feature dashboard

.NOTES
    Features map to existing scripts under the hood for now:
      - logs       -> monitor-logs.ps1
      - validation -> monitor-validation.ps1
      - changes    -> monitor-changes.ps1
      - sync       -> monitor-sync-logs.ps1
      - dashboard  -> monitoring-dashboard.ps1
#>

[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidateSet("logs","validation","changes","sync","dashboard")]
    [string]$Feature,

    # Common knobs
    [int]$Hours = 24,
    [string]$Pod = "",

    # monitor-logs
    [ValidateSet("realtime","recent","errors","errors-history","errors-persistent","sync","health","summary")]
    [string]$Mode = "realtime",
    [switch]$SaveErrors,

    # monitor-validation / monitor-changes
    [string]$Action,
    [string]$EntityType,
    [string]$Operation,
    [switch]$RealTime,
    [switch]$Export,

    # monitor-sync-logs
    [ValidateSet("all","sync","error","cache","api","db")]
    [string]$Filter = "all",
    [int]$Lines = 50,
    [switch]$Follow,
    [switch]$Summary
)

$scriptRoot = $PSScriptRoot
if (-not $scriptRoot) { $scriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path }

Import-Module "$scriptRoot/modules/Output.psm1" -Force
Import-Module "$scriptRoot/modules/Kube.psm1" -Force
Import-Module "$scriptRoot/modules/Monitoring.psm1" -Force

Write-Host "📊 SafetyAmp Monitoring (feature: $Feature)" -ForegroundColor Cyan

switch ($Feature) {
    'logs' {
        & "$scriptRoot/monitoring-dashboard.ps1" -Hours $Hours -Sections @('logs')
        break
    }
    'validation' {
        & "$scriptRoot/monitoring-dashboard.ps1" -Hours $Hours -Sections @('validation')
        break
    }
    'changes' {
        & "$scriptRoot/monitoring-dashboard.ps1" -Hours $Hours -Sections @('changes')
        break
    }
    'sync' {
        & "$scriptRoot/monitoring-dashboard.ps1" -Hours $Hours -Sections @('sync-summary')
        break
    }
    'dashboard' {
        & "$scriptRoot/monitoring-dashboard.ps1" -Hours $Hours -Sections @('pods','services','logs','errors','resources','health','connectivity','cache','config')
        break
    }
    default {
        Write-Host "❌ Unknown feature: $Feature" -ForegroundColor Red
        exit 1
    }
}