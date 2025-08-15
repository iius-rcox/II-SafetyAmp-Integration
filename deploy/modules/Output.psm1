# Output helper functions for SafetyAmp deployment scripts

Set-StrictMode -Version Latest

function Write-SectionHeader {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory=$true)][string]$Title
    )
    Write-Host "" 
    Write-Host "🔍 $Title" -ForegroundColor Yellow
    Write-Host ("=" * (4 + $Title.Length)) -ForegroundColor Yellow
}

function Write-Status {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory=$true)][string]$Message,
        [Parameter(Mandatory=$true)][bool]$Success
    )
    $icon = if ($Success) { "✅" } else { "❌" }
    $color = if ($Success) { "Green" } else { "Red" }
    Write-Host "$icon $Message" -ForegroundColor $color
}

function Write-ColorOutput {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory=$true)][string]$Message,
        [ValidateSet('Green','Yellow','Red','Cyan','Magenta','White','Gray')][string]$Color = 'White'
    )
    Write-Host $Message -ForegroundColor $Color
}

function Format-LogEntry {
    [CmdletBinding()]
    param([Parameter(Mandatory=$true)][string]$Line)

    if ($Line -match "\[(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\] \[(\w+)\] \[(\w+)\]: (.+)") {
        $timestamp = $matches[1]
        $level = $matches[2]
        $module = $matches[3]
        $message = $matches[4]

        $color = switch ($level) {
            'ERROR' { 'Red' }
            'WARNING' { 'Yellow' }
            'INFO' { 'Green' }
            default { 'White' }
        }

        Write-Host "[$timestamp] " -NoNewline -ForegroundColor Gray
        Write-Host "[$level] " -NoNewline -ForegroundColor $color
        Write-Host "[$module] " -NoNewline -ForegroundColor Cyan
        Write-Host $message -ForegroundColor White
        return
    }

    if ($Line -match "(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}) - - \[(.+)\] `"(.+?)`" (\d{3})") {
        $ip = $matches[1]
        $timestamp = $matches[2]
        $request = $matches[3]
        $status = $matches[4]

        $statusColor = if ($status -eq '200') { 'Green' } else { 'Red' }

        Write-Host "[$timestamp] " -NoNewline -ForegroundColor Gray
        Write-Host "$ip " -NoNewline -ForegroundColor Blue
        Write-Host "$request " -NoNewline -ForegroundColor White
        Write-Host $status -ForegroundColor $statusColor
        return
    }

    Write-Host $Line -ForegroundColor Gray
}

Export-ModuleMember -Function Write-SectionHeader,Write-Status,Write-ColorOutput,Format-LogEntry


