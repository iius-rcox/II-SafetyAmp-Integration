using module ./Output.psm1
using module ./Kube.psm1
# Monitoring helpers consolidating common logic used by monitor-*.ps1

Set-StrictMode -Version Latest

function Show-ErrorSummary {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory=$true)][string]$PodName,
        [Parameter(Mandatory=$true)][int]$Hours,
        [string]$Namespace = 'safety-amp'
    )
    Write-Host "📊 Error Summary (Last $Hours hours)" -ForegroundColor Cyan
    Write-Host "=========================================" -ForegroundColor Cyan

    $logs = Get-LogsSince -PodName $PodName -Hours $Hours -Namespace $Namespace
    if (-not $logs) { Write-Status 'No logs retrieved' $false; return }

    $errorLines = $logs | Select-String -Pattern "ERROR|Exception|Error|Failed|Failed to|Connection failed"
    if (-not $errorLines) { Write-Status "No errors found in the last $Hours hours" $true; return }

    $recent = $logs | Select-String -Pattern "ERROR|Exception|Error|Failed" | Select-Object -Last 5
    if ($recent) {
        Write-Host "`n🕒 Recent Errors:" -ForegroundColor Cyan
        $recent | ForEach-Object { Write-Host "  $($_.Line)" -ForegroundColor Red }
    }
}

function Start-PodLogStream {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory=$true)][string]$PodName,
        [string]$Namespace = 'safety-amp'
    )
    Write-Host "📺 Following logs in real-time..." -ForegroundColor Green
    Write-Host "Press Ctrl+C to stop" -ForegroundColor Yellow
    kubectl logs -f -n $Namespace $PodName | ForEach-Object { Format-LogEntry -Line $_ }
}

Export-ModuleMember -Function Show-ErrorSummary,Start-PodLogStream


