#!/usr/bin/env pwsh
<#!
.SYNOPSIS
    Main Deployment Entry Point for SafetyAmp

.DESCRIPTION
    Standardizes deployment actions behind a single script and parameters.
    It wraps current rollout steps and provides convenience commands.

.EXAMPLES
    ./deploy.ps1 -Action validate
    ./deploy.ps1 -Action deploy -Environment production
    ./deploy.ps1 -Action monitor
    ./deploy.ps1 -Action rollback
#>

[CmdletBinding()]
param(
    [ValidateSet("validate","deploy","test","monitor","status","restart","rollback")]
    [string]$Action = "deploy",
    [ValidateSet("production","staging","dev")]
    [string]$Environment = "production",
    [string]$Namespace = "safety-amp",
    [string]$DeploymentName = "safety-amp-agent"
)

$scriptRoot = $PSScriptRoot
if (-not $scriptRoot) { $scriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path }

function Get-DeploymentStatus {
    Write-Host "📊 Getting deployment status..." -ForegroundColor Cyan
    $deployment_status = kubectl get deployment $DeploymentName -n $Namespace -o json 2>$null | ConvertFrom-Json
    if ($deployment_status) {
        $replicas = $deployment_status.status.replicas
        $available = $deployment_status.status.availableReplicas
        $ready = $deployment_status.status.readyReplicas
        Write-Host "  Replicas: $replicas" -ForegroundColor White
        Write-Host "  Available: $available" -ForegroundColor White
        Write-Host "  Ready: $ready" -ForegroundColor White
    } else {
        Write-Host "❌ Could not get deployment status" -ForegroundColor Red
    }
}

switch ($Action) {
    'validate' {
        & "$scriptRoot/rollout-validation.ps1" -Action validate -Environment $Environment
        break
    }
    'deploy' {
        & "$scriptRoot/rollout-validation.ps1" -Action deploy -Environment $Environment
        break
    }
    'test' {
        & "$scriptRoot/rollout-validation.ps1" -Action test -Environment $Environment
        break
    }
    'monitor' {
        & "$scriptRoot/rollout-validation.ps1" -Action monitor -Environment $Environment
        break
    }
    'rollback' {
        & "$scriptRoot/rollout-validation.ps1" -Action rollback -Environment $Environment
        break
    }
    'status' {
        Get-DeploymentStatus
        break
    }
    'restart' {
        Write-Host "🔄 Restarting deployment $DeploymentName in $Namespace..." -ForegroundColor Yellow
        kubectl rollout restart deployment/$DeploymentName -n $Namespace
        Write-Host "⏳ Waiting for rollout to complete..." -ForegroundColor Yellow
        kubectl rollout status deployment/$DeploymentName -n $Namespace --timeout=300s
        Get-DeploymentStatus
        break
    }
    default {
        Write-Host "❌ Unknown action: $Action" -ForegroundColor Red
        exit 1
    }
}