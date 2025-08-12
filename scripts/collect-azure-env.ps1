param(
  [string]$OutputDir = "output"
)

$ErrorActionPreference = 'Continue'

if (-not (Get-Command az -ErrorAction SilentlyContinue)) {
  Write-Error "Azure CLI (az) not found on PATH. Install Azure CLI and run az login."
  exit 1
}

if (-not (Test-Path $OutputDir)) {
  New-Item -ItemType Directory -Path $OutputDir -Force | Out-Null
}

function Write-Json($Path, $ScriptBlock) {
  try {
    $data = & $ScriptBlock
    if ($LASTEXITCODE -ne 0) { $data = $null }
  } catch { $data = $null }
  if ($null -ne $data) {
    $data | Out-File -FilePath $Path -Encoding UTF8
  } else {
    # Write empty array/object depending on file intent
    if ($Path -match 'subscription.json') { '{}' | Out-File -FilePath $Path -Encoding UTF8 }
    else { '[]' | Out-File -FilePath $Path -Encoding UTF8 }
  }
}

Write-Host "Collecting Azure environment resources to $OutputDir ..."

Write-Json (Join-Path $OutputDir 'subscription.json') { az account show -o json }
Write-Json (Join-Path $OutputDir 'resource_groups.json') { az group list -o json }
Write-Json (Join-Path $OutputDir 'aks_clusters.json') { az resource list --resource-type Microsoft.ContainerService/managedClusters -o json }
Write-Json (Join-Path $OutputDir 'log_analytics.json') { az monitor log-analytics workspace list -o json }
Write-Json (Join-Path $OutputDir 'managed_grafana.json') { az resource list --resource-type Microsoft.Dashboard/grafana -o json }
Write-Json (Join-Path $OutputDir 'monitor_accounts.json') { az resource list --resource-type Microsoft.Monitor/accounts -o json }
Write-Json (Join-Path $OutputDir 'key_vaults.json') { az keyvault list -o json }
Write-Json (Join-Path $OutputDir 'container_registries.json') { az acr list -o json }

Write-Host "Done. Run scripts/merge-azure-json.ps1 to consolidate."


