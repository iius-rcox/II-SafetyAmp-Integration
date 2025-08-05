# PowerShell Script to Check Azure AD Authentication Status
# Run this to check if your on-premises SQL Server supports Azure AD authentication

param(
    [string]$SqlServer = "inscolvsql.insulationsinc.local"
)

Write-Host "=== Checking Azure AD Authentication Status ===" -ForegroundColor Green
Write-Host "SQL Server: $SqlServer" -ForegroundColor Cyan
Write-Host ""

Write-Host "Method 1: Check via SQL Server Management Studio (SSMS)" -ForegroundColor Yellow
Write-Host "1. Open SSMS and connect to: $SqlServer" -ForegroundColor White
Write-Host "2. Right-click on the server name in Object Explorer" -ForegroundColor White
Write-Host "3. Select 'Properties'" -ForegroundColor White
Write-Host "4. Go to 'Security' page" -ForegroundColor White
Write-Host "5. Look for 'Azure Active Directory authentication' option" -ForegroundColor White
Write-Host ""

Write-Host "Method 2: Check via SQL Script" -ForegroundColor Yellow
Write-Host "Run the SQL script: check-azure-ad-status.sql" -ForegroundColor White
Write-Host ""

Write-Host "Method 3: Check via Registry" -ForegroundColor Yellow
Write-Host "Check if Azure AD authentication is enabled in registry:" -ForegroundColor White
Write-Host "HKEY_LOCAL_MACHINE\SOFTWARE\Microsoft\Microsoft SQL Server\MSSQL15.MSSQLSERVER\MSSQLServer\SuperSocketNetLib" -ForegroundColor Cyan
Write-Host "Look for: 'AzureADAuthentication' = 1" -ForegroundColor White
Write-Host ""

Write-Host "Method 4: Check via SQL Configuration Manager" -ForegroundColor Yellow
Write-Host "1. Open SQL Server Configuration Manager" -ForegroundColor White
Write-Host "2. Go to SQL Server Network Configuration" -ForegroundColor White
Write-Host "3. Check if Azure AD authentication is listed as an option" -ForegroundColor White
Write-Host ""

Write-Host "Method 5: Check via T-SQL" -ForegroundColor Yellow
Write-Host "Run these queries in SSMS:" -ForegroundColor White
Write-Host ""

Write-Host "Query 1: Check SQL Server version and edition" -ForegroundColor Cyan
Write-Host "SELECT @@VERSION, SERVERPROPERTY('Edition')" -ForegroundColor White
Write-Host ""

Write-Host "Query 2: Check for Azure AD logins" -ForegroundColor Cyan
Write-Host "SELECT name, type_desc FROM sys.server_principals WHERE type_desc = 'EXTERNAL_LOGIN'" -ForegroundColor White
Write-Host ""

Write-Host "Query 3: Test Azure AD login creation" -ForegroundColor Cyan
Write-Host "CREATE LOGIN [test-azure-ad] FROM EXTERNAL PROVIDER;" -ForegroundColor White
Write-Host ""

Write-Host "Expected Results:" -ForegroundColor Yellow
Write-Host "✅ If Azure AD is enabled: Login creation will succeed" -ForegroundColor Green
Write-Host "❌ If Azure AD is NOT enabled: Error about 'EXTERNAL PROVIDER' not supported" -ForegroundColor Red
Write-Host ""

Write-Host "Press any key to continue..." -ForegroundColor Yellow
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown") 