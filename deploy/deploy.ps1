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
    [ValidateSet("validate","deploy","test","monitor","status","restart","rollback","build","push","publish","apply","release")]
    [string]$Action = "deploy",
    [ValidateSet("production","staging","dev")]
    [string]$Environment = "production",
    [string]$Namespace = "safety-amp",
    [string]$DeploymentName = "safety-amp-agent",
    [string]$AcrName,
    [string]$AcrLoginServer,
    [string]$ImageName = "safety-amp-agent",
    [string]$Tag = "latest",
    [string]$DockerfilePath = "$(Join-Path $PSScriptRoot '..' 'Dockerfile')"
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

function Get-AcrLoginServer {
    [CmdletBinding()] param([string]$Name,[string]$LoginServer)
    if ($LoginServer) { return $LoginServer }
    if (-not $Name) { throw "Provide -AcrName or -AcrLoginServer" }
    $server = az acr show -n $Name --query loginServer -o tsv 2>$null
    if (-not $server) { throw "Unable to resolve ACR login server for '$Name'" }
    return $server
}

function New-DockerImage {
    [CmdletBinding()] param([string]$Image,[string]$Tag,[string]$Dockerfile)
    Write-Host "🐳 Building image $($Image):$Tag..." -ForegroundColor Yellow
    docker build -f $Dockerfile -t "$($Image):$Tag" (Join-Path $scriptRoot '..')
    if ($LASTEXITCODE -ne 0) { throw "Docker build failed" }
}

function Publish-ContainerImage {
    [CmdletBinding()] param([string]$LocalImage,[string]$Tag,[string]$AcrName,[string]$AcrServer)
    $server = Get-AcrLoginServer -Name $AcrName -LoginServer $AcrServer
    $full = "$server/$($LocalImage):$Tag"
    Write-Host "🔐 Logging into ACR $server..." -ForegroundColor Yellow
    if ($AcrName) { az acr login --name $AcrName } else { docker login $server }
    if ($LASTEXITCODE -ne 0) { throw "ACR login failed" }
    Write-Host "🏷️  Tagging $($LocalImage):$Tag as $full" -ForegroundColor Yellow
    docker tag "$($LocalImage):$Tag" "$full"
    Write-Host "📤 Pushing $full..." -ForegroundColor Yellow
    docker push "$full"
    if ($LASTEXITCODE -ne 0) { throw "Docker push failed" }
    return $full
}

function Invoke-KustomizeApply {
    [CmdletBinding()] param([string]$KustomizePath = (Join-Path $scriptRoot '..' 'k8s'))
    Write-Host "📦 Applying Kubernetes kustomization at $KustomizePath..." -ForegroundColor Yellow
    kubectl apply -k $KustomizePath
}

function Set-DeploymentImage {
    [CmdletBinding()] param([string]$Deployment,[string]$Namespace,[string]$ContainerName,[string]$ImageRef,[int]$TimeoutSeconds = 300)
    Write-Host "🚀 Setting image for $Deployment/$ContainerName to $ImageRef..." -ForegroundColor Yellow
    kubectl set image deployment/$Deployment $ContainerName=$ImageRef -n $Namespace
    Write-Host "⏳ Waiting for rollout to complete..." -ForegroundColor Yellow
    kubectl rollout status deployment/$Deployment -n $Namespace --timeout=${TimeoutSeconds}s
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
    'build' {
        New-DockerImage -Image $ImageName -Tag $Tag -Dockerfile $DockerfilePath
        break
    }
    'push' {
        Publish-ContainerImage -LocalImage $ImageName -Tag $Tag -AcrName $AcrName -AcrServer $AcrLoginServer | Out-Null
        break
    }
    'publish' {
        New-DockerImage -Image $ImageName -Tag $Tag -Dockerfile $DockerfilePath
        Publish-ContainerImage -LocalImage $ImageName -Tag $Tag -AcrName $AcrName -AcrServer $AcrLoginServer | Out-Null
        break
    }
    'apply' {
        Invoke-KustomizeApply
        break
    }
    'release' {
        $server = Get-AcrLoginServer -Name $AcrName -LoginServer $AcrLoginServer
        $imageRef = "$server/$($ImageName):$Tag"
        Set-DeploymentImage -Deployment $DeploymentName -Namespace $Namespace -ContainerName $DeploymentName -ImageRef $imageRef -TimeoutSeconds 300
        Get-DeploymentStatus
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