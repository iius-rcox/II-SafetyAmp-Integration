#!/usr/bin/env pwsh
[CmdletBinding()]
param(
    [string]$ResourceGroup,
    [string]$AksName,

    [string]$AcrName = 'iiusacr',
    [string]$AcrLoginServer = 'iiusacr.azurecr.io',

    [string]$Namespace = 'safety-amp',
    [string]$DeploymentName = 'safety-amp-agent',
    [string]$ImageName = 'safety-amp-agent',
    [string]$Tag = 'latest',

    [string]$DockerfilePath,
    [string]$ContextDir,
    [string]$KustomizePath,

    [switch]$CreateAcrSecret,
    [switch]$SkipKustomizeApply,
    [switch]$SkipAksCredentials,

    [switch]$UpdateGrafana,
    [string]$GrafanaUrl,
    [string]$GrafanaApiToken,
    [int]$GrafanaFolderId,
    [switch]$ConfigureGrafanaAlerting,
    [string]$GrafanaDeveloperEmail
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Resolve-PathOrDefault {
    [CmdletBinding()]
    param(
        [string]$Path,
        [Parameter(Mandatory = $true)]
        [string]$DefaultRelative
    )

    if ($Path) {
        return $Path
    }

    $root = if ($PSScriptRoot) {
        Split-Path -Parent $PSScriptRoot
    } else {
        (Get-Location).Path
    }

    return (Join-Path $root $DefaultRelative)
}

function Write-Step {
    param([string]$Message)
    Write-Host "==> $Message" -ForegroundColor Cyan
}

function Write-Success {
    param([string]$Message)
    Write-Host "[OK] $Message" -ForegroundColor Green
}

function Write-Info {
    param([string]$Message)
    Write-Host "[INFO] $Message" -ForegroundColor Yellow
}

function Write-ErrorMessage {
    param([string]$Message)
    Write-Host "[ERROR] $Message" -ForegroundColor Red
}

$ContextDir     = Resolve-PathOrDefault -Path $ContextDir     -DefaultRelative '.'
$DockerfilePath = Resolve-PathOrDefault -Path $DockerfilePath -DefaultRelative 'Dockerfile'
$KustomizePath  = Resolve-PathOrDefault -Path $KustomizePath  -DefaultRelative 'k8s'

Write-Host '============================================================' -ForegroundColor Magenta
Write-Host ' SafetyAmp Deployment' -ForegroundColor Magenta
Write-Host " Namespace      : $Namespace" -ForegroundColor Magenta
Write-Host " Deployment     : $DeploymentName" -ForegroundColor Magenta
Write-Host " Image          : $ImageName" -ForegroundColor Magenta
Write-Host " Tag            : $Tag" -ForegroundColor Magenta
Write-Host " ACR Login      : $AcrLoginServer" -ForegroundColor Magenta
Write-Host '============================================================' -ForegroundColor Magenta

try {
    az account show -o none | Out-Null
    Write-Success 'Azure CLI is authenticated.'
} catch {
    throw 'Azure CLI not authenticated. Run az login and retry.'
}

if (-not $SkipAksCredentials -and $ResourceGroup -and $AksName) {
    Write-Step "Fetching AKS credentials for $ResourceGroup/$AksName"
    az aks get-credentials -g $ResourceGroup -n $AksName --overwrite-existing | Out-Null
    if ($LASTEXITCODE -ne 0) {
        throw 'Failed to get AKS credentials.'
    }
    Write-Success 'AKS credentials updated.'
} elseif (-not $ResourceGroup -or -not $AksName) {
    Write-Info 'Skipping AKS credential update (ResourceGroup or AksName not provided).'
}

if (-not $AcrLoginServer) {
    if (-not $AcrName) {
        throw 'Provide either -AcrLoginServer or -AcrName.'
    }
    Write-Step "Resolving login server for ACR $AcrName"
    $AcrLoginServer = az acr show -n $AcrName --query loginServer -o tsv
    if (-not $AcrLoginServer) {
        throw "Unable to resolve ACR login server for '$AcrName'."
    }
    Write-Success "ACR login server: $AcrLoginServer"
}

$imageTag = "{0}:{1}" -f $ImageName, $Tag
$imageRef = "{0}/{1}" -f $AcrLoginServer, $imageTag

Write-Step "Building Docker image $imageTag"
docker build -f $DockerfilePath -t $imageTag $ContextDir
if ($LASTEXITCODE -ne 0) {
    throw 'Docker build failed.'
}
Write-Success "Docker image built: $imageTag"

Write-Step "Logging into ACR $AcrLoginServer"
if ($AcrName) {
    az acr login --name $AcrName | Out-Null
} else {
    docker login $AcrLoginServer | Out-Null
}
if ($LASTEXITCODE -ne 0) {
    throw 'ACR login failed.'
}
Write-Success 'ACR login successful.'

Write-Step "Tagging and pushing image to $imageRef"
docker tag $imageTag $imageRef
if ($LASTEXITCODE -ne 0) {
    throw 'Docker tag failed.'
}
docker push $imageRef
if ($LASTEXITCODE -ne 0) {
    throw 'Docker push failed.'
}
Write-Success "Image pushed: $imageRef"

Write-Step "Ensuring namespace $Namespace exists"
$nsResult = kubectl get namespace $Namespace 2>$null
if (-not $nsResult) {
    kubectl create namespace $Namespace | Out-Null
}
Write-Success "Namespace ready: $Namespace"

if ($CreateAcrSecret) {
    if (-not $AcrName) {
        throw '-CreateAcrSecret requires -AcrName.'
    }
    Write-Step 'Creating or updating acr-secret pull secret'
    $acrUser = az acr credential show -n $AcrName --query username -o tsv
    $acrPwd  = az acr credential show -n $AcrName --query "passwords[0].value" -o tsv
    if (-not $acrUser -or -not $acrPwd) {
        throw 'Failed to retrieve ACR credentials. Ensure admin access is enabled.'
    }
    kubectl create secret docker-registry acr-secret `
        --docker-server $AcrLoginServer `
        --docker-username $acrUser `
        --docker-password $acrPwd `
        -n $Namespace `
        --dry-run=client -o yaml | kubectl apply -f - | Out-Null
    Write-Success 'acr-secret updated.'
}

if (-not $SkipKustomizeApply) {
    Write-Step "Applying kustomization at $KustomizePath"
    $applyOutput = & kubectl apply -k $KustomizePath 2>&1
    $applyText = ($applyOutput | Out-String).Trim()
    if ($applyText) {
        Write-Host $applyText
    }

    if ($LASTEXITCODE -ne 0) {
        $nonExistingErrors = ($applyText -split "`n") | Where-Object { $_ -match 'Error from server' -and $_ -notmatch 'AlreadyExists' }
        if ($nonExistingErrors -and $nonExistingErrors.Count -gt 0) {
            throw 'kubectl apply -k failed.'
        }
        Write-Info 'kubectl apply reported existing resources; continuing.'
    }

    Write-Success 'Kubernetes manifests applied.'
} else {
    Write-Info 'Skipping kustomize apply as requested.'
}

Write-Step "Updating deployment/$DeploymentName image to $imageRef"
kubectl set image deployment/$DeploymentName $DeploymentName=$imageRef -n $Namespace
if ($LASTEXITCODE -ne 0) {
    throw 'Failed to update deployment image.'
}

Write-Step 'Waiting for rollout to complete'
kubectl rollout status deployment/$DeploymentName -n $Namespace --timeout=300s
if ($LASTEXITCODE -ne 0) {
    throw 'Deployment rollout did not complete successfully.'
}
Write-Success 'Deployment rollout succeeded.'

Write-Step 'Current workload status'
kubectl get deployment $DeploymentName -n $Namespace -o wide
kubectl get pods -n $Namespace -l app=safety-amp,component=agent -o wide

if ($UpdateGrafana) {
    if (-not $GrafanaUrl -or -not $GrafanaApiToken) {
        Write-Info 'Skipping Grafana update: GrafanaUrl and GrafanaApiToken are required.'
    } else {
        Write-Step "Publishing Grafana dashboards to $GrafanaUrl"
        & (Join-Path $PSScriptRoot 'publish-grafana-dashboards.ps1') `
            -GrafanaUrl $GrafanaUrl `
            -ApiToken $GrafanaApiToken `
            -FolderId $GrafanaFolderId `
            -ConfigureAlerting:$ConfigureGrafanaAlerting `
            -DeveloperEmail $GrafanaDeveloperEmail
    }
}

Write-Host '============================================================' -ForegroundColor Green
Write-Host "Deployment completed. Image: $imageRef" -ForegroundColor Green
Write-Host "Namespace: $Namespace" -ForegroundColor Green
Write-Host '============================================================' -ForegroundColor Green
