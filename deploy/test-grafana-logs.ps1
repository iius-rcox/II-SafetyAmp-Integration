#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Test and verify that SafetyAmp logs are appearing in Grafana

.DESCRIPTION
    This script helps verify that the SafetyAmp application logs are properly
    flowing to Azure Monitor Logs and can be queried by Grafana.

.PARAMETER WorkspaceId
    The Log Analytics workspace ID (defaults to e8f8224e-1030-4fed-952d-bfc0c11fc146)

.EXAMPLE
    .\test-grafana-logs.ps1
#>

[CmdletBinding()]
param(
    [string]$WorkspaceId = "e8f8224e-1030-4fed-952d-bfc0c11fc146"
)

function Test-LogAnalyticsQuery {
    [CmdletBinding()]
    param(
        [string]$WorkspaceId,
        [string]$Query,
        [string]$Description
    )
    
    try {
        Write-Host "🔍 Testing: $Description" -ForegroundColor Cyan
        Write-Host "Query: $Query" -ForegroundColor Gray
        
        $result = az monitor log-analytics query --workspace $WorkspaceId --analytics-query $Query --output table 2>$null
        
        if ($result -and $result -notmatch "No data returned") {
            Write-Host "✅ Found data!" -ForegroundColor Green
            Write-Host $result -ForegroundColor Yellow
        } else {
            Write-Host "❌ No data found" -ForegroundColor Red
        }
        Write-Host ""
    }
    catch {
        Write-Host "❌ Query failed: $_" -ForegroundColor Red
        Write-Host ""
    }
}

function Test-GrafanaConnection {
    [CmdletBinding()]
    param(
        [string]$GrafanaUrl,
        [string]$ApiToken
    )
    
    try {
        $headers = @{
            "Authorization" = "Bearer $ApiToken"
            "Content-Type" = "application/json"
        }
        
        $response = Invoke-RestMethod -Uri "$GrafanaUrl/api/health" -Headers $headers -Method Get
        Write-Host "✅ Grafana connection successful" -ForegroundColor Green
        return $true
    }
    catch {
        Write-Host "❌ Failed to connect to Grafana: $_" -ForegroundColor Red
        return $false
    }
}

function Get-GrafanaApiToken {
    [CmdletBinding()]
    param(
        [string]$KeyVaultName = "iius-akv"
    )
    
    try {
        $token = az keyvault secret show --vault-name $KeyVaultName --name "GRAFANA-API-TOKEN" --query value -o tsv 2>$null
        if ($token) {
            return $token
        }
    }
    catch {
        Write-Warning "Failed to retrieve token from Key Vault: $_"
    }
    
    return $null
}

function Resolve-GrafanaUrl {
    [CmdletBinding()]
    param(
        [string]$AzureEnvPath = (Join-Path $PSScriptRoot ".." "output" "azure_env.json")
    )
    
    if (Test-Path $AzureEnvPath) {
        try {
            $azureEnv = Get-Content $AzureEnvPath | ConvertFrom-Json
            if ($azureEnv.managedGrafana) {
                $grafanaName = $azureEnv.managedGrafana.name
                $location = $azureEnv.managedGrafana.location
                $url = "https://$grafanaName-hcanhvgkayhwb0hh.scus.grafana.azure.com"
                return $url
            }
        }
        catch {
            Write-Warning "Failed to parse azure_env.json: $_"
        }
    }
    
    return $null
}

# Main execution
try {
    Write-Host "🔍 Testing SafetyAmp Logs in Grafana" -ForegroundColor Cyan
    Write-Host "=====================================" -ForegroundColor Cyan
    Write-Host ""
    
    # Test 1: Check if logs are in Log Analytics
    Write-Host "📊 Testing Log Analytics Queries" -ForegroundColor Yellow
    Write-Host "--------------------------------" -ForegroundColor Yellow
    
    # Test for recent container logs
    Test-LogAnalyticsQuery -WorkspaceId $WorkspaceId -Description "Recent container logs from safety-amp namespace" -Query "union isfuzzy=true ContainerLogV2, ContainerLog | where TimeGenerated > ago(1h) | where Namespace == 'safety-amp' | take 5"
    
    # Test for specific test logs
    Test-LogAnalyticsQuery -WorkspaceId $WorkspaceId -Description "Test log entries" -Query "union isfuzzy=true ContainerLogV2, ContainerLog | where TimeGenerated > ago(1h) | where Message has 'TEST LOG' or Message has 'TEST ERROR' | take 5"
    
    # Test for error logs
    Test-LogAnalyticsQuery -WorkspaceId $WorkspaceId -Description "Error logs from safety-amp" -Query "union isfuzzy=true ContainerLogV2, ContainerLog | where TimeGenerated > ago(1h) | where Namespace == 'safety-amp' | where Message has 'ERROR' or Message has 'Exception' or Message has 'Failed' | take 5"
    
    # Test for application startup logs
    Test-LogAnalyticsQuery -WorkspaceId $WorkspaceId -Description "Application startup logs" -Query "union isfuzzy=true ContainerLogV2, ContainerLog | where TimeGenerated > ago(1h) | where Namespace == 'safety-amp' | where Message has 'Starting' or Message has 'Redis connected' | take 5"
    
    Write-Host ""
    Write-Host "🎯 Grafana Dashboard Verification" -ForegroundColor Yellow
    Write-Host "--------------------------------" -ForegroundColor Yellow
    
    # Test Grafana connection
    $grafanaUrl = Resolve-GrafanaUrl
    $apiToken = Get-GrafanaApiToken
    
    if ($grafanaUrl -and $apiToken) {
        if (Test-GrafanaConnection -GrafanaUrl $grafanaUrl -ApiToken $apiToken) {
            Write-Host "✅ Grafana is accessible" -ForegroundColor Green
            Write-Host "🌐 Grafana URL: $grafanaUrl" -ForegroundColor Cyan
            Write-Host ""
            Write-Host "📋 Manual Verification Steps:" -ForegroundColor Yellow
            Write-Host "1. Open Grafana: $grafanaUrl" -ForegroundColor White
            Write-Host "2. Go to Dashboards → SafetyAmp Status" -ForegroundColor White
            Write-Host "3. Check the 'Recent Errors' and 'Recent Changes' panels" -ForegroundColor White
            Write-Host "4. Go to Explore → Azure Monitor Logs" -ForegroundColor White
            Write-Host "5. Run this query: union isfuzzy=true ContainerLogV2, ContainerLog | where Namespace == 'safety-amp' | take 10" -ForegroundColor White
            Write-Host ""
            Write-Host "🔍 Expected Results:" -ForegroundColor Yellow
            Write-Host "- You should see logs from the safety-amp namespace" -ForegroundColor White
            Write-Host "- Recent test logs with 'TEST LOG' and 'TEST ERROR' messages" -ForegroundColor White
            Write-Host "- Application startup messages and Redis connection logs" -ForegroundColor White
        }
    } else {
        Write-Host "❌ Cannot access Grafana - missing URL or API token" -ForegroundColor Red
    }
    
    Write-Host ""
    Write-Host "🎉 Log verification completed!" -ForegroundColor Green
    Write-Host "If you see data in the Log Analytics queries above, your logs are flowing correctly." -ForegroundColor Green
    Write-Host "If Grafana shows 'No data', check the datasource configuration and permissions." -ForegroundColor Yellow
    
} catch {
    Write-Error "❌ Verification failed: $_"
    exit 1
}
