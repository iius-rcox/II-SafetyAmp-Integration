#!/usr/bin/env pwsh
<#!
.SYNOPSIS
    Unified Troubleshooting Entry Point for SafetyAmp

.DESCRIPTION
    Consolidates fix and validation scripts into a single parameterized command.

.EXAMPLES
    ./troubleshoot.ps1 -Task data-quality -Action analyze -Hours 24
    ./troubleshoot.ps1 -Task employee-data -Action list-missing
    ./troubleshoot.ps1 -Task redis -Mode auth
    ./troubleshoot.ps1 -Task redis -Mode no-auth
    ./troubleshoot.ps1 -Task cache-manager
    ./troubleshoot.ps1 -Task notifications -Force
#>

[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidateSet("data-quality","employee-data","redis","cache-manager","notifications","rollout")]
    [string]$Task,

    # Common knobs
    [int]$Hours = 24,

    # fix-data-quality
    [ValidateSet("analyze","validate","cleanup","report")]
    [string]$Action,

    # fix-employee-data
    [ValidateSet("list-missing","list-duplicates","list-skipped","validate")]
    [string]$EmployeeAction,

    # redis modes
    [ValidateSet("auth","no-auth")]
    [string]$Mode = "auth",

    # notifications test
    [switch]$Force,
    [switch]$Status,
    [switch]$Cleanup,

    # rollout-validation
    [ValidateSet("validate","deploy","test","monitor","rollback")]
    [string]$RolloutAction = "deploy",
    [ValidateSet("production","staging","dev")]
    [string]$Environment = "production"
)

$scriptRoot = $PSScriptRoot
if (-not $scriptRoot) { $scriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path }

Write-Host "🛠️  SafetyAmp Troubleshooting (task: $Task)" -ForegroundColor Cyan

switch ($Task) {
    'data-quality' {
        $dqAction = if ($Action) { $Action } else { 'analyze' }
        & "$scriptRoot/fix-data-quality.ps1" -Action $dqAction -Hours $Hours
        break
    }
    'employee-data' {
        $empAction = if ($EmployeeAction) { $EmployeeAction } else { 'list-missing' }
        & "$scriptRoot/fix-employee-data.ps1" -Action $empAction
        break
    }
    'redis' {
        if ($Mode -eq 'auth') {
            & "$scriptRoot/fix-redis-auth.ps1"
        } else {
            & "$scriptRoot/fix-redis-no-auth.ps1"
        }
        break
    }
    'cache-manager' {
        & "$scriptRoot/fix-cache-manager.ps1"
        break
    }
    'notifications' {
        & "$scriptRoot/test-error-notifications.ps1" -Force:$Force -Status:$Status -Cleanup:$Cleanup
        break
    }
    'rollout' {
        & "$scriptRoot/rollout-validation.ps1" -Action $RolloutAction -Environment $Environment
        break
    }
    default {
        Write-Host "❌ Unknown task: $Task" -ForegroundColor Red
        exit 1
    }
}