# Test Managed Identity Connection to SQL Server
# Run this after configuring the managed identity on SQL Server

param(
    [string]$SqlServer = "inscolvsql.insulationsinc.local",
    [string]$Database = "Viewpoint"
)

Write-Host "=== Testing Managed Identity Connection ===" -ForegroundColor Green
Write-Host ""

Write-Host "This script tests if the managed identity can connect to SQL Server." -ForegroundColor Yellow
Write-Host "Run this after you've configured the managed identity on SQL Server." -ForegroundColor Yellow
Write-Host ""

Write-Host "Configuration:" -ForegroundColor Cyan
Write-Host "SQL Server: $SqlServer" -ForegroundColor White
Write-Host "Database: $Database" -ForegroundColor White
Write-Host ""

Write-Host "Testing connection using Azure CLI..." -ForegroundColor Yellow

try {
    # Test connection using Azure CLI with managed identity
    $result = az sql db query --server $SqlServer --name $Database --query "SELECT 'Managed Identity Connection Test' as TestResult" 2>$null
    
    if ($result) {
        Write-Host "✅ Managed Identity connection successful!" -ForegroundColor Green
        Write-Host "Result: $result" -ForegroundColor Cyan
    } else {
        Write-Host "❌ Managed Identity connection failed" -ForegroundColor Red
    }
} catch {
    Write-Host "❌ Error testing managed identity connection: $($_.Exception.Message)" -ForegroundColor Red
}

Write-Host ""
Write-Host "If the test fails, ensure:" -ForegroundColor Yellow
Write-Host "1. The SQL script was executed successfully" -ForegroundColor White
Write-Host "2. The managed identity has the correct permissions" -ForegroundColor White
Write-Host "3. The SQL Server allows Azure AD authentication" -ForegroundColor White
Write-Host ""

Write-Host "Press any key to continue..." -ForegroundColor Yellow
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown") 