#!/usr/bin/env pwsh
param(
  [Parameter(Mandatory=$true)][string]$GrafanaUrl,
  [Parameter(Mandatory=$true)][string]$ApiToken,
  [string]$DeveloperEmail = "",
  [string]$ContactPointName = "cp-dev-email"
)

$ErrorActionPreference = 'Stop'

# Resolve developer email
if (-not $DeveloperEmail) {
  if ($env:ALERT_EMAIL_TO) { $DeveloperEmail = $env:ALERT_EMAIL_TO }
  else { throw "Provide -DeveloperEmail or set ALERT_EMAIL_TO env" }
}

$headers = @{ Authorization = "Bearer $ApiToken"; 'Content-Type' = 'application/json' }

# 1) Ensure contact point exists/updated
Write-Host "🔧 Ensuring Grafana contact point '$ContactPointName' -> $DeveloperEmail"
$cpList = Invoke-RestMethod -Method GET -Headers $headers -Uri "$GrafanaUrl/api/v1/provisioning/contact-points"
$cp = $cpList | Where-Object { $_.name -eq $ContactPointName }

$cpPayload = @{ name = $ContactPointName; type = 'email'; settings = @{ addresses = $DeveloperEmail } }
if ($null -eq $cp) {
  Invoke-RestMethod -Method POST -Headers $headers -Uri "$GrafanaUrl/api/v1/provisioning/contact-points" -Body ($cpPayload | ConvertTo-Json -Depth 5) | Out-Null
  Write-Host "✅ Created contact point: $ContactPointName"
} else {
  $uid = $cp.uid
  Invoke-RestMethod -Method PUT -Headers $headers -Uri "$GrafanaUrl/api/v1/provisioning/contact-points/$uid" -Body ($cpPayload | ConvertTo-Json -Depth 5) | Out-Null
  Write-Host "✅ Updated contact point: $ContactPointName"
}

# 2) Ensure notification policy routes severity=critical -> contact point
Write-Host "🔧 Ensuring notification policy for severity=critical routes to '$ContactPointName'"
$policy = Invoke-RestMethod -Method GET -Headers $headers -Uri "$GrafanaUrl/api/v1/provisioning/policies"

if (-not $policy.receiver) { $policy.receiver = $ContactPointName }
if (-not $policy.routes) { $policy | Add-Member -NotePropertyName routes -NotePropertyValue @() }

$hasCriticalRoute = $false
foreach ($r in $policy.routes) {
  $matchers = @($r.object_matchers)
  foreach ($m in $matchers) {
    if ($m.Count -ge 3 -and $m[0] -eq 'severity' -and $m[1] -eq '=' -and $m[2] -eq 'critical') {
      $hasCriticalRoute = $true
      $r.receiver = $ContactPointName
    }
  }
}

if (-not $hasCriticalRoute) {
  $newRoute = @{ receiver = $ContactPointName; object_matchers = @(@('severity', '=', 'critical')) }
  $policy.routes = ,$newRoute + $policy.routes
}

Invoke-RestMethod -Method PUT -Headers $headers -Uri "$GrafanaUrl/api/v1/provisioning/policies" -Body ($policy | ConvertTo-Json -Depth 8) | Out-Null
Write-Host "✅ Notification policy updated"

Write-Host "🎉 Grafana alert routing configured: severity=critical → $DeveloperEmail"
