#!/usr/bin/env pwsh
param(
    [string]$Action = "validation-summary",
    [int]$Hours = 24
)

Write-Host "⚠️  'monitor-validation.ps1' is deprecated. Use 'monitor.ps1 -Feature validation' instead." -ForegroundColor Yellow
& "$PSScriptRoot/monitor.ps1" -Feature validation -Hours $Hours
