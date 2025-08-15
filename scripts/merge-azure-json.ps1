param(
  [string]$OutputDir = "output"
)

$ErrorActionPreference = 'Stop'

if (-not (Test-Path $OutputDir)) {
  New-Item -ItemType Directory -Path $OutputDir -Force | Out-Null
}

$files = [ordered]@{
  subscription        = 'subscription.json'
  resourceGroups      = 'resource_groups.json'
  aksClusters         = 'aks_clusters.json'
  logAnalytics        = 'log_analytics.json'
  managedGrafana      = 'managed_grafana.json'
  monitorAccounts     = 'monitor_accounts.json'
  keyVaults           = 'key_vaults.json'
  containerRegistries = 'container_registries.json'
}

$result = [ordered]@{}

foreach ($key in $files.Keys) {
  $path = Join-Path $OutputDir $files[$key]
  if (Test-Path $path) {
    try {
      $json = Get-Content -Raw -Path $path | ConvertFrom-Json
    } catch {
      $json = $null
    }
    $result[$key] = $json
  } else {
    $result[$key] = $null
  }
}

$outPath = Join-Path $OutputDir 'azure_env.json'
$result | ConvertTo-Json -Depth 12 | Set-Content -Path $outPath -Encoding UTF8

# Cleanup originals
foreach ($key in $files.Keys) {
  $path = Join-Path $OutputDir $files[$key]
  if (Test-Path $path) {
    Remove-Item $path -Force
  }
}

Write-Host "Wrote $outPath and removed individual files"


