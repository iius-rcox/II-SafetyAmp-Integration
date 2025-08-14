#!/usr/bin/env pwsh
[CmdletBinding()]
param(
  [string]$GrafanaUrl,
  [string]$ApiToken,
  [string[]]$DashboardFiles,
  [int]$FolderId,
  [switch]$ConfigureAlerting,
  [string]$DeveloperEmail,
  [string]$ContactPointName = 'cp-dev-email',
  [string]$ApiTokenEnvVar = 'GRAFANA_API_TOKEN',
  [string]$KeyVaultName,
  [string]$KeyVaultSecretName = 'GRAFANA-API-TOKEN'
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Resolve-RepoRoot {
  if ($PSScriptRoot) { return (Split-Path -Parent $PSScriptRoot) }
  return (Get-Location).Path
}

function Resolve-GrafanaUrl {
  [CmdletBinding()]
  param([string]$Existing)
  if ($Existing) { return $Existing }
  if ($env:GRAFANA_URL) { return $env:GRAFANA_URL }

  $root = Resolve-RepoRoot
  $envFile = Join-Path $root 'output/azure_env.json'
  if (Test-Path $envFile) {
    try {
      $azureEnv = Get-Content -Raw -Path $envFile | ConvertFrom-Json
      $mg = $azureEnv.managedGrafana
      if ($mg -and $mg.resourceGroup -and $mg.name) {
        $endpoint = az grafana show -g $mg.resourceGroup -n $mg.name --query properties.endpoint -o tsv 2>$null
        if ($endpoint) { return $endpoint }
      }
    } catch {}
  }
  throw "Grafana URL not provided. Pass -GrafanaUrl or set GRAFANA_URL or ensure output/azure_env.json contains managedGrafana info."
}

function Resolve-GrafanaApiToken {
  [CmdletBinding()]
  param(
    [string]$Existing,
    [string]$EnvVarName = 'GRAFANA_API_TOKEN',
    [string]$KeyVaultName,
    [string]$SecretName = 'GRAFANA-API-TOKEN'
  )

  if ($Existing) { return $Existing }

  # 1) Env var
  try {
    $fromEnv = [System.Environment]::GetEnvironmentVariable($EnvVarName)
    if ($fromEnv) { return $fromEnv }
  } catch {}

  # 2) Azure Key Vault
  $resolvedKv = $KeyVaultName
  if (-not $resolvedKv) {
    $root = Resolve-RepoRoot
    $envFile = Join-Path $root 'output/azure_env.json'
    if (Test-Path $envFile) {
      try {
        $azureEnv = Get-Content -Raw -Path $envFile | ConvertFrom-Json
        $kvs = $azureEnv.keyVaults
        if ($kvs) {
          $iius = $kvs | Where-Object { $_.name -eq 'iius-akv' } | Select-Object -First 1
          if ($iius) { $resolvedKv = $iius.name }
          elseif ($kvs.Count -gt 0) { $resolvedKv = $kvs[0].name }
        }
      } catch {}
    }
  }

  if ($resolvedKv) {
    try {
      $val = az keyvault secret show --vault-name $resolvedKv --name $SecretName --query value -o tsv 2>$null
      if ($val) { return $val }
    } catch {}
  }

  throw "Grafana API token not provided. Pass -ApiToken or set $EnvVarName or provide -KeyVaultName/-KeyVaultSecretName (or populate output/azure_env.json)."
}

function Get-DefaultDashboardFiles {
  $root = Resolve-RepoRoot
  $paths = @(
    (Join-Path $root 'k8s/monitoring/grafana/safetyamp-status.json'),
    (Join-Path $PSScriptRoot 'grafana/safetyamp-status.json'),
    (Join-Path $PSScriptRoot 'grafana/safetyamp-detail.json'),
    (Join-Path $PSScriptRoot 'grafana/safetyamp-ops.json')
  )
  return $paths | Where-Object { Test-Path $_ }
}

function Publish-GrafanaDashboard {
  [CmdletBinding()]
  param(
    [Parameter(Mandatory=$true)][string]$GrafanaUrl,
    [Parameter(Mandatory=$true)][hashtable]$Headers,
    [Parameter(Mandatory=$true)][string]$FilePath,
    [int]$FolderId
  )

  Write-Host "📄 Importing dashboard from $FilePath" -ForegroundColor Yellow
  $raw = Get-Content -Raw -Path $FilePath | ConvertFrom-Json
  # Ensure Grafana treats as new/overwrite
  if ($raw.PSObject.Properties.Name -contains 'id') { $raw.id = $null }
  # If workspace variable exists but is empty, remove it so datasource default is used
  try {
    if ($raw.templating.list) {
      foreach ($v in $raw.templating.list) {
        if ($v.name -eq 'workspace' -and (-not $v.query -or $v.query -eq '')) { $v | Add-Member -NotePropertyName 'query' -NotePropertyValue '' -Force }
      }
    }
  } catch {}

  $payload = @{ dashboard = $raw; overwrite = $true }
  if ($FolderId) { $payload.folderId = $FolderId }

  $body = ($payload | ConvertTo-Json -Depth 10)
  $resp = Invoke-RestMethod -Method POST -Headers $Headers -Uri ("$GrafanaUrl/api/dashboards/db") -Body $body
  Write-Host "✅ Imported: $($resp.slug) (status: $($resp.status))" -ForegroundColor Green
}

function Set-GrafanaAlerting {
  [CmdletBinding()]
  param(
    [Parameter(Mandatory=$true)][string]$GrafanaUrl,
    [Parameter(Mandatory=$true)][string]$ApiToken,
    [Parameter(Mandatory=$true)][string]$DeveloperEmail,
    [string]$ContactPointName = 'cp-dev-email'
  )
  $script = Join-Path $PSScriptRoot 'dev/observability/scripts/grafana-apply-alerting.ps1'
  if (-not (Test-Path $script)) {
    Write-Host "⚠️  Alerting script not found: $script" -ForegroundColor Yellow
    return
  }
  & $script -GrafanaUrl $GrafanaUrl -ApiToken $ApiToken -DeveloperEmail $DeveloperEmail -ContactPointName $ContactPointName
}

# Prepare
$GrafanaUrl = Resolve-GrafanaUrl -Existing $GrafanaUrl
Write-Host "🔗 Grafana URL: $GrafanaUrl" -ForegroundColor Cyan
$ApiToken = Resolve-GrafanaApiToken -Existing $ApiToken -EnvVarName $ApiTokenEnvVar -KeyVaultName $KeyVaultName -SecretName $KeyVaultSecretName
$authHeaders = @{ Authorization = "Bearer $ApiToken"; 'Content-Type' = 'application/json' }
if (-not $DashboardFiles -or $DashboardFiles.Count -eq 0) {
  $DashboardFiles = Get-DefaultDashboardFiles
}
if (-not $DashboardFiles -or $DashboardFiles.Count -eq 0) {
  throw "No dashboard JSON files found to publish."
}

# Publish dashboards
foreach ($file in $DashboardFiles) {
  Publish-GrafanaDashboard -GrafanaUrl $GrafanaUrl -Headers $authHeaders -FilePath $file -FolderId $FolderId
}

# Optional alerting setup
if ($ConfigureAlerting -and $DeveloperEmail) {
  Set-GrafanaAlerting -GrafanaUrl $GrafanaUrl -ApiToken $ApiToken -DeveloperEmail $DeveloperEmail -ContactPointName $ContactPointName
}

Write-Host "🎉 Grafana dashboards update completed" -ForegroundColor Cyan


