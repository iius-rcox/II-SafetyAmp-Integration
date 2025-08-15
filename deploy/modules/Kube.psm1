# Kubernetes helper functions for SafetyAmp deployment scripts

Set-StrictMode -Version Latest

function Get-ScriptRoot {
    if ($PSScriptRoot) { return $PSScriptRoot }
    return (Split-Path -Parent $MyInvocation.MyCommand.Path)
}

function Get-SafetyAmpPod {
    [CmdletBinding()]
    param(
        [string]$Namespace = 'safety-amp',
        [string]$Selector = 'app=safety-amp,component=agent'
    )
    try {
        # Prefer a Running pod
        $running = kubectl get pods -n $Namespace -l $Selector --field-selector=status.phase=Running -o jsonpath='{.items[0].metadata.name}' 2>$null
        if ($running) { return $running }
        # Fallback to any pod matching the selector
        $any = kubectl get pods -n $Namespace -l $Selector -o jsonpath='{.items[0].metadata.name}' 2>$null
        if ($any) { return $any }
    } catch { }
    return $null
}

function Get-LogsSince {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory=$true)][string]$PodName,
        [Parameter(Mandatory=$true)][int]$Hours,
        [string]$Namespace = 'safety-amp'
    )
    $sinceTime = (Get-Date).AddHours(-$Hours).ToString('yyyy-MM-ddTHH:mm:ssZ')
    return (kubectl logs -n $Namespace $PodName --since-time=$sinceTime 2>$null)
}

function Restart-Deployment {
    [CmdletBinding()]
    param(
        [string]$DeploymentName = 'safety-amp-agent',
        [string]$Namespace = 'safety-amp',
        [int]$TimeoutSeconds = 300
    )
    kubectl rollout restart deployment/$DeploymentName -n $Namespace
    kubectl rollout status deployment/$DeploymentName -n $Namespace --timeout=${TimeoutSeconds}s
}

function Get-DeploymentStatus {
    [CmdletBinding()]
    param(
        [string]$DeploymentName = 'safety-amp-agent',
        [string]$Namespace = 'safety-amp'
    )
    return (kubectl get deployment $DeploymentName -n $Namespace -o json 2>$null | ConvertFrom-Json)
}

Export-ModuleMember -Function Get-ScriptRoot,Get-SafetyAmpPod,Get-LogsSince,Restart-Deployment,Get-DeploymentStatus


