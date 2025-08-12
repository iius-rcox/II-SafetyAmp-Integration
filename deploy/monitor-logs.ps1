#!/usr/bin/env pwsh
param(
    [string]$Mode = "realtime",
    [string]$Pod = "",
    [int]$Hours = 4,
    [switch]$SaveErrors
)

Write-Host "⚠️  'monitor-logs.ps1' is deprecated. Use 'monitor.ps1 -Feature logs' instead." -ForegroundColor Yellow
& "$PSScriptRoot/monitor.ps1" -Feature logs -Mode $Mode -Pod $Pod -Hours $Hours -SaveErrors:$SaveErrors