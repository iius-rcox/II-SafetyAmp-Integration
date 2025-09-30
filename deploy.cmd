@echo off
REM Windows batch file to launch PowerShell deployment script
REM Usage: deploy.cmd [dev|staging|prod] [tag]

SET ENVIRONMENT=%1
SET TAG=%2

IF "%ENVIRONMENT%"=="" SET ENVIRONMENT=dev
IF "%TAG%"=="" SET TAG=latest

echo Starting SafetyAmp Integration deployment...
echo Environment: %ENVIRONMENT%
echo Tag: %TAG%

powershell.exe -ExecutionPolicy Bypass -File "%~dp0deploy-to-aks.ps1" -Environment %ENVIRONMENT% -Tag %TAG%

pause