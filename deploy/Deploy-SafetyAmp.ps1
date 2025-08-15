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
  [switch]$SkipAksCredentials
  , [switch]$UpdateGrafana
  , [string]$GrafanaUrl
  , [string]$GrafanaApiToken
  , [int]$GrafanaFolderId
  , [switch]$ConfigureGrafanaAlerting
  , [string]$GrafanaDeveloperEmail
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Resolve-PathOrDefault {
  [CmdletBinding()]
  param(
    [string]$Path,
    [Parameter(Mandatory=$true)][string]$DefaultRelative
  )
  if ($Path) { return $Path }
  $root = if ($PSScriptRoot) { Split-Path -Parent $PSScriptRoot } else { (Get-Location).Path }
  return (Join-Path $root $DefaultRelative)
}

# Resolve paths assuming this script sits in repo/deploy or anywhere else
$ContextDir     = Resolve-PathOrDefault -Path $ContextDir     -DefaultRelative '.'
$DockerfilePath = Resolve-PathOrDefault -Path $DockerfilePath -DefaultRelative 'Dockerfile'
$KustomizePath  = Resolve-PathOrDefault -Path $KustomizePath  -DefaultRelative 'k8s'

Write-Host "=== SafetyAmp Deploy ===" -ForegroundColor Cyan
Write-Host "ContextDir:       $ContextDir"
Write-Host "DockerfilePath:   $DockerfilePath"
Write-Host "KustomizePath:    $KustomizePath"
Write-Host "Namespace:        $Namespace"
Write-Host "DeploymentName:   $DeploymentName"
Write-Host "Image:            $ImageName"
Write-Host "Tag:              $Tag"
Write-Host "ACR Name:         $AcrName"
Write-Host "ACR LoginServer:  $AcrLoginServer"
Write-Host ""

# 1) Ensure az authenticated and (optionally) get AKS credentials
try { az account show -o none | Out-Null } catch { throw "Azure CLI not authenticated. Run: az login" }
if (-not $SkipAksCredentials -and $ResourceGroup -and $AksName) {
  Write-Host "⛓️  Fetching AKS credentials: $ResourceGroup/$AksName" -ForegroundColor Yellow
  az aks get-credentials -g $ResourceGroup -n $AksName --overwrite-existing | Out-Null
}

# 2) Resolve ACR login server
if (-not $AcrLoginServer) {
  if (-not $AcrName) { throw "Provide -AcrName or -AcrLoginServer" }
  $AcrLoginServer = az acr show -n $AcrName --query loginServer -o tsv
  if (-not $AcrLoginServer) { throw "Unable to resolve ACR login server for '$AcrName'" }
}

# 3) Docker build
Write-Host "🐳 Building image $($ImageName):$Tag ..." -ForegroundColor Yellow
docker build -f $DockerfilePath -t "$($ImageName):$Tag" $ContextDir
if ($LASTEXITCODE -ne 0) { throw "Docker build failed" }

# 4) ACR login and push
Write-Host "🔐 Logging into ACR $AcrLoginServer ..." -ForegroundColor Yellow
if ($AcrName) { az acr login --name $AcrName | Out-Null } else { docker login $AcrLoginServer | Out-Null }

$imageRef = "$AcrLoginServer/$($ImageName):$Tag"
Write-Host "🏷️  Tagging: $($ImageName):$Tag -> $imageRef" -ForegroundColor Yellow
docker tag "$($ImageName):$Tag" "$imageRef"

Write-Host "📤 Pushing: $imageRef" -ForegroundColor Yellow
docker push "$imageRef"
if ($LASTEXITCODE -ne 0) { throw "Docker push failed" }

# 5) Ensure namespace exists
Write-Host "📦 Ensuring namespace '$Namespace' exists..." -ForegroundColor Yellow
$ns = kubectl get ns $Namespace 2>$null
if (-not $ns) { kubectl create namespace $Namespace | Out-Null }

# 6) Optionally create acr-secret pull secret (only if requested)
if ($CreateAcrSecret) {
  if (-not $AcrName) { throw "-CreateAcrSecret requires -AcrName" }
  Write-Host "🔑 Creating/updating imagePullSecret 'acr-secret' in namespace '$Namespace'..." -ForegroundColor Yellow
  $acrUser = az acr credential show -n $AcrName --query username -o tsv
  $acrPwd  = az acr credential show -n $AcrName --query 'passwords[0].value' -o tsv
  if (-not $acrUser -or -not $acrPwd) { throw "Failed to retrieve ACR credentials. Is admin enabled on ACR?" }
  kubectl create secret docker-registry acr-secret `
    --docker-server $AcrLoginServer `
    --docker-username $acrUser `
    --docker-password $acrPwd `
    -n $Namespace `
    --dry-run=client -o yaml | kubectl apply -f -
}

# 7) Apply Kubernetes resources (kustomize)
if (-not $SkipKustomizeApply) {
  Write-Host "🧩 Applying Kubernetes kustomization at '$KustomizePath'..." -ForegroundColor Yellow
  kubectl apply -k $KustomizePath
}

# 8) Release: set image on deployment and wait for rollout
Write-Host "🚀 Setting image on deployment/${DeploymentName}: $imageRef" -ForegroundColor Yellow
kubectl set image deployment/$DeploymentName $DeploymentName=$imageRef -n $Namespace
Write-Host "⏳ Waiting for rollout..." -ForegroundColor Yellow
kubectl rollout status deployment/$DeploymentName -n $Namespace --timeout=300s

# 9) Show current status
Write-Host "📊 Deployment status:" -ForegroundColor Cyan
kubectl get deployment $DeploymentName -n $Namespace -o wide
kubectl get pods -n $Namespace -l app=safety-amp,component=agent -o wide

# 10) Optional: Update Grafana dashboards
if ($UpdateGrafana) {
  if (-not $GrafanaUrl -or -not $GrafanaApiToken) {
    Write-Host "⚠️  Skipping Grafana update: -GrafanaUrl and -GrafanaApiToken are required" -ForegroundColor Yellow
  } else {
    Write-Host "📈 Publishing Grafana dashboards to $GrafanaUrl" -ForegroundColor Yellow
    & (Join-Path $PSScriptRoot 'publish-grafana-dashboards.ps1') `
      -GrafanaUrl $GrafanaUrl `
      -ApiToken $GrafanaApiToken `
      -FolderId $GrafanaFolderId `
      -ConfigureAlerting:$ConfigureGrafanaAlerting `
      -DeveloperEmail $GrafanaDeveloperEmail
  }
}

Write-Host ""
Write-Host "✅ Done. Released $imageRef to $Namespace/$DeploymentName" -ForegroundColor Green


