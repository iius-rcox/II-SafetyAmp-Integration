#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Run SafetyAmp application locally for testing

.DESCRIPTION
    Sets up and runs the SafetyAmp application locally with proper environment
    configuration for testing and development.

.PARAMETER Mode
    The run mode:
    - "dev": Development mode with debug logging
    - "test": Test mode with minimal logging
    - "sync": Run sync operations only (no web server)

.EXAMPLE
    .\run-local.ps1
    .\run-local.ps1 -Mode "dev"
    .\run-local.ps1 -Mode "sync"
#>

param(
    [string]$Mode = "dev"
)

Write-Host "🚀 SafetyAmp Local Development Setup" -ForegroundColor Cyan
Write-Host "=====================================" -ForegroundColor Cyan

# Check if Python is installed
try {
    $pythonVersion = python --version 2>&1
    Write-Host "✅ Python found: $pythonVersion" -ForegroundColor Green
} catch {
    Write-Host "❌ Python not found! Please install Python 3.11+" -ForegroundColor Red
    exit 1
}

# Check if virtual environment exists
if (-not (Test-Path "venv")) {
    Write-Host "📦 Creating virtual environment..." -ForegroundColor Yellow
    python -m venv venv
}

# Activate virtual environment
Write-Host "🔧 Activating virtual environment..." -ForegroundColor Yellow
& "venv\Scripts\Activate.ps1"

# Install dependencies
Write-Host "📚 Installing dependencies..." -ForegroundColor Yellow
pip install -r requirements.txt

# Set environment variables for local development
Write-Host "⚙️  Setting up environment variables..." -ForegroundColor Yellow

# Create .env file for local development
$envContent = @"
# Local Development Environment Variables
# These will be overridden by Azure Key Vault in production

# Azure Key Vault Configuration
AZURE_TENANT_ID=your-tenant-id
AZURE_CLIENT_ID=your-client-id
AZURE_CLIENT_SECRET=your-client-secret
AZURE_KEY_VAULT_URL=https://iius-akv.vault.azure.net/

# Application Settings
LOG_LEVEL=DEBUG
SYNC_INTERVAL=300
BATCH_SIZE=100
SQL_AUTH_MODE=sql_auth

# Redis Configuration (local)
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_PASSWORD=

# External API Configuration
SAFETYAMP_BASE_URL=https://api.safetyamp.com
SAMSARA_BASE_URL=https://api.samsara.com
VIEWPOINT_SERVER=inscolvsql.insulationsinc.local
VIEWPOINT_DATABASE=Viewpoint

# Note: In production, these secrets are stored in Azure Key Vault
# For local testing, you may need to set them manually or use Azure CLI
"@

$envContent | Out-File -FilePath ".env" -Encoding UTF8

Write-Host "📝 Created .env file for local development" -ForegroundColor Green
Write-Host "⚠️  Please update the .env file with your actual credentials" -ForegroundColor Yellow

# Run the application based on mode
switch ($Mode.ToLower()) {
    "dev" {
        Write-Host "🔧 Starting in development mode..." -ForegroundColor Green
        Write-Host "🌐 Web server will be available at: http://localhost:8080" -ForegroundColor Cyan
        Write-Host "📊 Health check: http://localhost:8080/health" -ForegroundColor Cyan
        Write-Host "📈 Metrics: http://localhost:8080/metrics" -ForegroundColor Cyan
        Write-Host "Press Ctrl+C to stop" -ForegroundColor Yellow
        Write-Host ""
        
        $env:FLASK_ENV = "development"
        $env:LOG_LEVEL = "DEBUG"
        python main.py
    }
    "test" {
        Write-Host "🧪 Starting in test mode..." -ForegroundColor Green
        Write-Host "📊 Running connectivity tests..." -ForegroundColor Cyan
        Write-Host ""
        
        python test-connections.py
    }
    "sync" {
        Write-Host "🔄 Running sync operations only..." -ForegroundColor Green
        Write-Host ""
        
        # Import and run sync directly
        python -c "
import sys
sys.path.append('.')
from sync.sync_employees import EmployeeSyncer
from services.safetyamp_api import SafetyAmpAPI
from services.samsara_api import SamsaraAPI
from services.viewpoint_api import ViewpointAPI

print('Starting sync operations...')
syncer = EmployeeSyncer()
result = syncer.sync()
print(f'Sync completed: {result}')
"
    }
    default {
        Write-Host "❌ Unknown mode: $Mode" -ForegroundColor Red
        Write-Host "Available modes: dev, test, sync" -ForegroundColor Yellow
        exit 1
    }
} 