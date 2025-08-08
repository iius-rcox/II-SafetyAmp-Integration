#!/usr/bin/env pwsh
param(
  [string]$ResourceGroup = "rg-prod",
  [string]$AksName = "dev-aks",
  [string]$Namespace = "safety-amp",
  [string]$Image = "safetyampacr.azurecr.io/safetyamp-integration",
  [string]$Tag = "",
  [string]$WorkbookSourceId = "", # "/subscriptions/<sub>/resourceGroups/<rg>/providers/Microsoft.OperationalInsights/workspaces/<law>"
  [string]$WorkspaceId = "",
  [string]$WorkspaceKey = "",
  [string]$GrafanaUrl = "",
  [string]$GrafanaApiToken = "",
  [string]$DeveloperEmail = ""
)

$ErrorActionPreference = 'Stop'

function Test-CliPresent {
  if (-not (Get-Command $name -ErrorAction SilentlyContinue)) {
    throw "Required CLI '$name' not found in PATH"
  }
}

Write-Host "==> Validating CLIs"
Test-CliPresent az
Test-CliPresent kubectl

if (-not $DeveloperEmail) {
  if ($env:ALERT_EMAIL_TO) { $DeveloperEmail = $env:ALERT_EMAIL_TO }
  else {
    try {
      # Attempt resolve from Key Vault configured in cluster manifests
      $kvUrl = "https://iius-akv.vault.azure.net/"
      $name = "ALERT-EMAIL-TO"
      $val = az keyvault secret show --vault-name ($kvUrl -replace "https://|\\.vault\\.azure\\.net/", "") --name $name --query value -o tsv 2>$null
      if ($LASTEXITCODE -eq 0 -and $val) { $DeveloperEmail = $val }
    } catch { }
  }
}

if (-not $Tag) { $Tag = (Get-Date -Format 'yyyyMMddHHmmss') }

Write-Host "==> Enabling Container Insights on AKS: $AksName (RG: $ResourceGroup)"
if ($WorkbookSourceId) {
  az aks enable-addons -g $ResourceGroup -n $AksName --addons monitoring --workspace-resource-id $WorkbookSourceId | Out-Null
} else {
  az aks enable-addons -g $ResourceGroup -n $AksName --addons monitoring | Out-Null
}
Write-Host "✓ Container Insights enabled"

Write-Host "==> Ensuring namespace '$Namespace' exists"
kubectl get ns $Namespace 2>$null | Out-Null
if ($LASTEXITCODE -ne 0) { kubectl create ns $Namespace | Out-Null }

if ($WorkspaceId -and $WorkspaceKey) {
  Write-Host "==> Creating/updating Log Analytics secret"
  kubectl -n $Namespace delete secret log-analytics-secrets 2>$null | Out-Null
  kubectl -n $Namespace create secret generic log-analytics-secrets `
    --from-literal=workspace-id=$WorkspaceId `
    --from-literal=workspace-key=$WorkspaceKey | Out-Null
}

Write-Host "==> Applying observability manifests"
$root = Resolve-Path "$PSScriptRoot/../../../.."
kubectl apply -f "$root/deploy/dev/observability/k8s/fluentbit-config.yaml" | Out-Null
kubectl apply -f "$root/deploy/dev/observability/k8s/networkpolicy-monitoring.yaml" | Out-Null
Write-Host "✓ Manifests applied"

Write-Host "==> Rolling deployment to latest image tag (if image accessible)"
try {
  $fullImage = "$Image`:$Tag"
  kubectl -n $Namespace set image deployment/safety-amp-agent safety-amp-agent=$fullImage | Out-Null
  kubectl -n $Namespace rollout status deployment/safety-amp-agent | Out-String | Write-Host
  Write-Host "✓ Rolled out image $fullImage"
} catch {
  Write-Warning "Failed to set image (ensure registry access). Proceeding with current image."
}

if ($WorkbookSourceId) {
  Write-Host "==> Deploying Azure Monitor Workbook"
  $script = Join-Path $PSScriptRoot 'deploy-azure-monitor-dashboard.sh'
  bash $script --resource-group $ResourceGroup --location (az group show -n $ResourceGroup --query location -o tsv) --workbook-source-id $WorkbookSourceId | Write-Host
}

if ($DeveloperEmail) {
  Write-Host "==> Ensuring Azure Monitor Action Group"
  & "$PSScriptRoot/azure-create-action-group.ps1" -ResourceGroup $ResourceGroup -DeveloperEmail $DeveloperEmail
}

if ($GrafanaUrl -and $GrafanaApiToken -and $DeveloperEmail) {
  Write-Host "==> Configuring Grafana alert routing"
  & "$PSScriptRoot/grafana-apply-alerting.ps1" -GrafanaUrl $GrafanaUrl -ApiToken $GrafanaApiToken -DeveloperEmail $DeveloperEmail
}

Write-Host "==> Running validation checks"
& "$PSScriptRoot/validate-dashboard.sh"
& "$PSScriptRoot/test-dashboard-data.sh"

Write-Host "🎉 Observability setup completed. Review Grafana and Azure Workbook for data."


