#!/usr/bin/env pwsh
param(
  [string]$ResourceGroup,
  [string]$ActionGroupName = "ag-safetyamp-dev",
  [string]$DeveloperEmail = ""
)

if (-not $ResourceGroup) { Write-Error "Provide -ResourceGroup"; exit 2 }

if (-not $DeveloperEmail) {
  if ($env:ALERT_EMAIL_TO) { $DeveloperEmail = $env:ALERT_EMAIL_TO }
  else { Write-Error "Provide -DeveloperEmail or set ALERT_EMAIL_TO env"; exit 2 }
}

$exists = az monitor action-group show -g $ResourceGroup -n $ActionGroupName 2>$null
if ($LASTEXITCODE -ne 0) {
  Write-Host "Creating Action Group '$ActionGroupName' in RG '$ResourceGroup' with email '$DeveloperEmail'"
  az monitor action-group create -g $ResourceGroup -n $ActionGroupName --short-name safetyamp \
    --action email devEmail $DeveloperEmail | Out-Null
} else {
  Write-Host "Updating Action Group '$ActionGroupName' email receivers to '$DeveloperEmail'"
  az monitor action-group update -g $ResourceGroup -n $ActionGroupName --add-action email devEmail $DeveloperEmail | Out-Null
}

Write-Host "Action Group ready: $ActionGroupName"
