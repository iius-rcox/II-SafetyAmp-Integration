#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Configure Grafana Azure Monitor Logs datasource for SafetyAmp monitoring

.DESCRIPTION
    This script configures the Azure Monitor Logs datasource in Grafana to point to the correct
    Log Analytics workspace for SafetyAmp logs and metrics.

.PARAMETER GrafanaUrl
    The Grafana URL (defaults to the one from azure_env.json)

.PARAMETER ApiToken
    The Grafana API token (defaults to GRAFANA-API-TOKEN from Azure Key Vault)

.PARAMETER WorkspaceId
    The Log Analytics workspace ID (defaults to e8f8224e-1030-4fed-952d-bfc0c11fc146)

.EXAMPLE
    .\configure-grafana-datasource.ps1
    .\configure-grafana-datasource.ps1 -GrafanaUrl "https://your-grafana-url" -ApiToken "your-token"
#>

[CmdletBinding()]
param(
    [string]$GrafanaUrl,
    [string]$ApiToken,
    [string]$WorkspaceId = "e8f8224e-1030-4fed-952d-bfc0c11fc146",
    [string]$KeyVaultName = "iius-akv"
)

# Import required modules
Import-Module (Join-Path $PSScriptRoot "modules\Output.psm1") -Force

function Resolve-GrafanaApiToken {
    [CmdletBinding()]
    param(
        [string]$Existing,
        [string]$EnvVarName = 'GRAFANA_API_TOKEN',
        [string]$KeyVaultName,
        [string]$SecretName = 'GRAFANA-API-TOKEN'
    )
    
    # If provided directly, use it
    if ($Existing) {
        Write-Host "Using provided API token" -ForegroundColor Green
        return $Existing
    }
    
    # Check environment variable
    $envToken = [Environment]::GetEnvironmentVariable($EnvVarName)
    if ($envToken) {
        Write-Host "Using API token from environment variable $EnvVarName" -ForegroundColor Green
        return $envToken
    }
    
    # Try Azure Key Vault
    if ($KeyVaultName) {
        try {
            Write-Host "Retrieving API token from Azure Key Vault $KeyVaultName..." -ForegroundColor Yellow
            $token = az keyvault secret show --vault-name $KeyVaultName --name $SecretName --query value -o tsv 2>$null
            if ($token) {
                Write-Host "Using API token from Azure Key Vault" -ForegroundColor Green
                return $token
            }
        }
        catch {
            Write-Warning "Failed to retrieve token from Key Vault: $_"
        }
    }
    
    throw "No Grafana API token found. Please provide -ApiToken parameter or set $EnvVarName environment variable or add GRAFANA-API-TOKEN to Azure Key Vault."
}

function Resolve-GrafanaUrl {
    [CmdletBinding()]
    param(
        [string]$ProvidedUrl,
        [string]$AzureEnvPath = (Join-Path $PSScriptRoot ".." "output" "azure_env.json")
    )
    
    # If provided directly, use it
    if ($ProvidedUrl) {
        return $ProvidedUrl
    }
    
    # Try to get from azure_env.json
    if (Test-Path $AzureEnvPath) {
        try {
            $azureEnv = Get-Content $AzureEnvPath | ConvertFrom-Json
            if ($azureEnv.managedGrafana) {
                $grafanaName = $azureEnv.managedGrafana.name
                $location = $azureEnv.managedGrafana.location
                $url = "https://$grafanaName-hcanhvgkayhwb0hh.scus.grafana.azure.com"
                Write-Host "Using Grafana URL from azure_env.json: $url" -ForegroundColor Green
                return $url
            }
        }
        catch {
            Write-Warning "Failed to parse azure_env.json: $_"
        }
    }
    
    throw "No Grafana URL found. Please provide -GrafanaUrl parameter or ensure azure_env.json is available."
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
        Write-Error "❌ Failed to connect to Grafana: $_"
        return $false
    }
}

function Get-ExistingDatasource {
    [CmdletBinding()]
    param(
        [string]$GrafanaUrl,
        [string]$ApiToken,
        [string]$Name = "Azure Monitor Logs"
    )
    
    try {
        $headers = @{
            "Authorization" = "Bearer $ApiToken"
            "Content-Type" = "application/json"
        }
        
        $datasources = Invoke-RestMethod -Uri "$GrafanaUrl/api/datasources" -Headers $headers -Method Get
        return $datasources | Where-Object { $_.name -eq $Name } | Select-Object -First 1
    }
    catch {
        Write-Warning "Failed to get existing datasources: $_"
        return $null
    }
}

function New-AzureMonitorLogsDatasource {
    [CmdletBinding()]
    param(
        [string]$GrafanaUrl,
        [string]$ApiToken,
        [string]$WorkspaceId,
        [string]$Name = "Azure Monitor Logs"
    )
    
    $datasourceConfig = @{
        name = $Name
        type = "grafana-azure-monitor-datasource"
        access = "proxy"
        isDefault = $false
        jsonData = @{
            cloudName = "azuremonitor"
            azureLogAnalyticsSameAs = $true
            azureAuthType = "msi"
            tenantId = "953922e6-5370-4a01-a3d5-773a30df726b"
            subscriptionId = "a78954fe-f6fe-4279-8be0-2c748be2f266"
            logAnalyticsDefaultWorkspace = $WorkspaceId
            logAnalyticsTenantId = "953922e6-5370-4a01-a3d5-773a30df726b"
            logAnalyticsSubscriptionId = "a78954fe-f6fe-4279-8be0-2c748be2f266"
        }
        secureJsonData = @{}
    }
    
    try {
        $headers = @{
            "Authorization" = "Bearer $ApiToken"
            "Content-Type" = "application/json"
        }
        
        $body = $datasourceConfig | ConvertTo-Json -Depth 10
        Write-Host "Creating Azure Monitor Logs datasource..." -ForegroundColor Yellow
        Write-Host "Workspace ID: $WorkspaceId" -ForegroundColor Cyan
        
        $response = Invoke-RestMethod -Uri "$GrafanaUrl/api/datasources" -Headers $headers -Method Post -Body $body
        Write-Host "✅ Azure Monitor Logs datasource created successfully (ID: $($response.id))" -ForegroundColor Green
        return $response
    }
    catch {
        Write-Error "❌ Failed to create datasource: $_"
        return $null
    }
}

function Update-AzureMonitorLogsDatasource {
    [CmdletBinding()]
    param(
        [string]$GrafanaUrl,
        [string]$ApiToken,
        [object]$ExistingDatasource,
        [string]$WorkspaceId,
        [string]$Name = "Azure Monitor Logs"
    )
    
    $datasourceConfig = @{
        name = $Name
        type = "grafana-azure-monitor-datasource"
        access = "proxy"
        isDefault = $false
        jsonData = @{
            cloudName = "azuremonitor"
            azureLogAnalyticsSameAs = $true
            azureAuthType = "msi"
            tenantId = "953922e6-5370-4a01-a3d5-773a30df726b"
            subscriptionId = "a78954fe-f6fe-4279-8be0-2c748be2f266"
            logAnalyticsDefaultWorkspace = $WorkspaceId
            logAnalyticsTenantId = "953922e6-5370-4a01-a3d5-773a30df726b"
            logAnalyticsSubscriptionId = "a78954fe-f6fe-4279-8be0-2c748be2f266"
        }
        secureJsonData = @{}
    }
    
    try {
        $headers = @{
            "Authorization" = "Bearer $ApiToken"
            "Content-Type" = "application/json"
        }
        
        $body = $datasourceConfig | ConvertTo-Json -Depth 10
        Write-Host "Updating Azure Monitor Logs datasource (ID: $($ExistingDatasource.id))..." -ForegroundColor Yellow
        Write-Host "Workspace ID: $WorkspaceId" -ForegroundColor Cyan
        
        $response = Invoke-RestMethod -Uri "$GrafanaUrl/api/datasources/$($ExistingDatasource.id)" -Headers $headers -Method Put -Body $body
        Write-Host "✅ Azure Monitor Logs datasource updated successfully" -ForegroundColor Green
        return $response
    }
    catch {
        Write-Error "❌ Failed to update datasource: $_"
        return $null
    }
}

# Main execution
try {
    Write-Host "🔧 Configuring Grafana Azure Monitor Logs Datasource" -ForegroundColor Cyan
    Write-Host "==================================================" -ForegroundColor Cyan
    
    # Resolve Grafana URL and API token
    $grafanaUrl = Resolve-GrafanaUrl -ProvidedUrl $GrafanaUrl
    $apiToken = Resolve-GrafanaApiToken -Existing $ApiToken -KeyVaultName $KeyVaultName
    
    Write-Host "Grafana URL: $grafanaUrl" -ForegroundColor Yellow
    Write-Host "Workspace ID: $WorkspaceId" -ForegroundColor Yellow
    
    # Test connection
    if (-not (Test-GrafanaConnection -GrafanaUrl $grafanaUrl -ApiToken $apiToken)) {
        exit 1
    }
    
    # Check for existing datasource
    $existingDatasource = Get-ExistingDatasource -GrafanaUrl $grafanaUrl -ApiToken $apiToken
    
    if ($existingDatasource) {
        Write-Host "Found existing Azure Monitor Logs datasource (ID: $($existingDatasource.id))" -ForegroundColor Yellow
        
        # Always update the datasource to ensure correct configuration
        Write-Host "Updating Azure Monitor Logs datasource configuration..." -ForegroundColor Yellow
        Update-AzureMonitorLogsDatasource -GrafanaUrl $grafanaUrl -ApiToken $apiToken -ExistingDatasource $existingDatasource -WorkspaceId $WorkspaceId
    } else {
        Write-Host "No existing Azure Monitor Logs datasource found, creating new one..." -ForegroundColor Yellow
        New-AzureMonitorLogsDatasource -GrafanaUrl $grafanaUrl -ApiToken $apiToken -WorkspaceId $WorkspaceId
    }
    
    Write-Host "`n🎉 Grafana datasource configuration completed!" -ForegroundColor Green
    Write-Host "You can now access your SafetyAmp logs in Grafana dashboards." -ForegroundColor Green
    
} catch {
    Write-Error "❌ Configuration failed: $_"
    exit 1
}
