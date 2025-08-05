# PowerShell Script to Configure SQL Server Managed Identity
# This script helps you configure the Azure Managed Identity on your SQL Server

param(
    [string]$SqlServer = "inscolvsql.insulationsinc.local",
    [string]$Database = "Viewpoint",
    [string]$ManagedIdentityClientId = "a2bcb3ce-a89b-43af-804c-e8029e0bafb4"
)

Write-Host "=== SQL Server Managed Identity Configuration ===" -ForegroundColor Green
Write-Host ""

Write-Host "Configuration Details:" -ForegroundColor Yellow
Write-Host "SQL Server: $SqlServer" -ForegroundColor Cyan
Write-Host "Database: $Database" -ForegroundColor Cyan
Write-Host "Managed Identity Client ID: $ManagedIdentityClientId" -ForegroundColor Cyan
Write-Host ""

Write-Host "IMPORTANT: You need to run the SQL script on your SQL Server." -ForegroundColor Red
Write-Host "This script will help you with the process." -ForegroundColor Yellow
Write-Host ""

# Check if SQL Server is accessible
Write-Host "Step 1: Testing SQL Server connectivity..." -ForegroundColor Yellow
try {
    $connectionString = "Server=$SqlServer;Database=$Database;Integrated Security=true;"
    $connection = New-Object System.Data.SqlClient.SqlConnection($connectionString)
    $connection.Open()
    Write-Host "✅ SQL Server connection successful!" -ForegroundColor Green
    $connection.Close()
} catch {
    Write-Host "❌ SQL Server connection failed: $($_.Exception.Message)" -ForegroundColor Red
    Write-Host "Please ensure you have access to the SQL Server." -ForegroundColor Yellow
    exit 1
}

Write-Host ""
Write-Host "Step 2: SQL Script Location" -ForegroundColor Yellow
Write-Host "The SQL script has been created at: configure-sql-managed-identity.sql" -ForegroundColor Cyan
Write-Host ""

Write-Host "Step 3: Instructions to run the SQL script:" -ForegroundColor Yellow
Write-Host "1. Open SQL Server Management Studio (SSMS)" -ForegroundColor White
Write-Host "2. Connect to: $SqlServer" -ForegroundColor White
Write-Host "3. Open the file: configure-sql-managed-identity.sql" -ForegroundColor White
Write-Host "4. Execute the script" -ForegroundColor White
Write-Host ""

Write-Host "Step 4: Alternative - Using sqlcmd:" -ForegroundColor Yellow
Write-Host "If you have sqlcmd installed, you can run:" -ForegroundColor White
Write-Host "sqlcmd -S $SqlServer -d $Database -i configure-sql-managed-identity.sql" -ForegroundColor Cyan
Write-Host ""

Write-Host "Step 5: After running the SQL script:" -ForegroundColor Yellow
Write-Host "1. Switch back to managed_identity mode in the deployment" -ForegroundColor White
Write-Host "2. Restart the SafetyAmp pods" -ForegroundColor White
Write-Host "3. Test the connectivity again" -ForegroundColor White
Write-Host ""

Write-Host "Step 6: Switch back to managed_identity mode:" -ForegroundColor Yellow
Write-Host "Run this command after SQL configuration:" -ForegroundColor White
Write-Host "kubectl patch configmap safety-amp-config -n safety-amp --type='merge' -p='{\"data\":{\"SQL_AUTH_MODE\":\"managed_identity\"}}'" -ForegroundColor Cyan
Write-Host ""

Write-Host "Step 7: Restart the deployment:" -ForegroundColor Yellow
Write-Host "kubectl rollout restart deployment safety-amp-agent -n safety-amp" -ForegroundColor Cyan
Write-Host ""

Write-Host "=== Next Steps ===" -ForegroundColor Green
Write-Host "1. Run the SQL script on your SQL Server" -ForegroundColor White
Write-Host "2. Switch back to managed_identity mode" -ForegroundColor White
Write-Host "3. Restart the deployment" -ForegroundColor White
Write-Host "4. Test connectivity with: python test-connections.py" -ForegroundColor White
Write-Host ""

Write-Host "Press any key to continue..." -ForegroundColor Yellow
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown") 