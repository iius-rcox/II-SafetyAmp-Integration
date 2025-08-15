#!/usr/bin/env pwsh
param(
    [string]$Filter = "all",
    [int]$Lines = 50,
    [switch]$Follow,
    [switch]$Summary
)

Write-Host "⚠️  'monitor-sync-logs.ps1' is deprecated. Use 'monitor.ps1 -Feature sync' instead." -ForegroundColor Yellow
& "$PSScriptRoot/monitor.ps1" -Feature sync -Hours 1