# PowerShell Script to Enable Azure AD Authentication via Registry
# Run this as Administrator on the SQL Server machine

param(
    [string]$SqlInstance = "MSSQLSERVER"
)

Write-Host "=== Enabling Azure AD Authentication for SQL Server ===" -ForegroundColor Green
Write-Host "SQL Instance: $SqlInstance" -ForegroundColor Cyan
Write-Host ""

Write-Host "IMPORTANT: This script must be run as Administrator!" -ForegroundColor Red
Write-Host ""

# Check if running as Administrator
$isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole] "Administrator")

if (-not $isAdmin) {
    Write-Host "❌ This script must be run as Administrator!" -ForegroundColor Red
    Write-Host "Please right-click PowerShell and select 'Run as Administrator'" -ForegroundColor Yellow
    exit 1
}

Write-Host "✅ Running as Administrator" -ForegroundColor Green
Write-Host ""

# Registry path for SQL Server 2019
$registryPath = "HKLM:\SOFTWARE\Microsoft\Microsoft SQL Server\MSSQL15.$SqlInstance\MSSQLServer\SuperSocketNetLib"

Write-Host "Registry Path: $registryPath" -ForegroundColor Cyan
Write-Host ""

# Check if the registry path exists
if (-not (Test-Path $registryPath)) {
    Write-Host "❌ Registry path not found!" -ForegroundColor Red
    Write-Host "Please verify the SQL Server instance name: $SqlInstance" -ForegroundColor Yellow
    exit 1
}

Write-Host "✅ Registry path found" -ForegroundColor Green
Write-Host ""

# Enable Azure AD Authentication
Write-Host "Enabling Azure AD Authentication..." -ForegroundColor Yellow
try {
    Set-ItemProperty -Path $registryPath -Name "AzureADAuthentication" -Value 1 -Type DWord
    Write-Host "✅ Azure AD Authentication enabled in registry" -ForegroundColor Green
} catch {
    Write-Host "❌ Failed to enable Azure AD Authentication: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "=== Next Steps ===" -ForegroundColor Yellow
Write-Host "1. Restart the SQL Server service" -ForegroundColor White
Write-Host "2. Test Azure AD authentication" -ForegroundColor White
Write-Host "3. Run the original managed identity SQL script" -ForegroundColor White
Write-Host ""

Write-Host "To restart SQL Server service, run:" -ForegroundColor Cyan
Write-Host "Restart-Service -Name 'MSSQLSERVER' -Force" -ForegroundColor White
Write-Host ""

Write-Host "Press any key to continue..." -ForegroundColor Yellow
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown") 