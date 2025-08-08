#!/usr/bin/env pwsh
param(
  [string]$KeyVaultName = "",
  [string]$SecretName = "ALERT-EMAIL-TO"
)

# Try env first (e.g., injected by pipeline)
if ($env:ALERT_EMAIL_TO) {
  Write-Host "Resolved developer email from env: $($env:ALERT_EMAIL_TO)"; exit 0
}

if (-not $KeyVaultName) {
  Write-Error "KeyVaultName not provided and ALERT_EMAIL_TO env not set. Provide -KeyVaultName or set env var."; exit 2
}

try {
  $email = az keyvault secret show --vault-name $KeyVaultName --name $SecretName --query value -o tsv 2>$null
  if ([string]::IsNullOrWhiteSpace($email)) { throw "Empty value" }
  Write-Host "Resolved developer email from Key Vault: $email"
} catch {
  Write-Error "Failed to resolve developer email from Key Vault: $($_.Exception.Message)"; exit 1
}
