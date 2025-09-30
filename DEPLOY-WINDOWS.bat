@echo off
setlocal enabledelayedexpansion
color 0A
title SafetyAmp Production Deployment

rem Update these defaults to match the live AKS cluster.
set "ENVIRONMENT=prod"
set "CLUSTER=dev-aks"
set "RESOURCE_GROUP=rg_prod"
set "NAMESPACE=safety-amp"

echo.
echo ===================================================
echo   SafetyAmp Integration - Production Deployment

echo   Target Environment : %ENVIRONMENT%
echo   AKS Cluster        : %CLUSTER%
echo   Resource Group     : %RESOURCE_GROUP%
echo ===================================================
echo.

echo [1/3] Checking prerequisites...
echo.

set "MISSING_TOOLS=0"

where az >nul 2>&1
if errorlevel 1 (
    echo   [X] Azure CLI is not installed.
    echo       Download: https://aka.ms/installazurecliwindows
    set "MISSING_TOOLS=1"
) else (
    echo   [OK] Azure CLI found.
)

where docker >nul 2>&1
if errorlevel 1 (
    echo   [X] Docker CLI is not installed.
    echo       Install Docker Desktop: https://www.docker.com/products/docker-desktop
    set "MISSING_TOOLS=1"
) else (
    echo   [OK] Docker CLI found.
    docker info >nul 2>&1
    if errorlevel 1 (
        echo   [X] Docker daemon is not running. Start Docker Desktop and rerun.
        set "MISSING_TOOLS=1"
    ) else (
        echo   [OK] Docker daemon responding.
    )
)

where kubectl >nul 2>&1
if errorlevel 1 (
    echo   [X] kubectl is not installed.
    echo       Install instructions: https://kubernetes.io/docs/tasks/tools/
    set "MISSING_TOOLS=1"
) else (
    echo   [OK] kubectl found.
)

if "%MISSING_TOOLS%"=="1" (
    echo.
    echo Missing required tools. Resolve the items above and run again.
    echo.
    pause
    exit /b 1
)

echo.
echo [2/3] Configure deployment options.
echo.

set "SKIP_BUILD=false"
set "BUILD_LABEL=Yes"
set /p ANSWER="Skip Docker build and push? (y/N): "
if /i "%ANSWER%"=="Y" (
    set "SKIP_BUILD=true"
    set "BUILD_LABEL=No"
)

set "SKIP_INFRA=false"
set "INFRA_LABEL=Yes"
set /p ANSWER="Apply infrastructure components (namespaces, monitoring)? (Y/n): "
if /i "%ANSWER%"=="N" (
    set "SKIP_INFRA=true"
    set "INFRA_LABEL=No"
)

echo.
set /p TAG="Enter image tag (default 'latest'): "
if "%TAG%"=="" set "TAG=latest"

echo.
echo [3/3] Deployment summary

echo   Environment       : %ENVIRONMENT%
echo   AKS Cluster        : %CLUSTER%
echo   Docker Image Tag   : %TAG%
echo   Docker Build Step  : %BUILD_LABEL%
echo   Infra Updates      : %INFRA_LABEL%
echo.
pause

echo.
echo Starting deployment...
echo.

set "PS_ARGS=-ResourceGroup %RESOURCE_GROUP% -AksName %CLUSTER% -Tag %TAG%"

if /i "%SKIP_BUILD%"=="false" (
    REM Build is included by default, no flag needed
) else (
    REM Skip build by not including Docker build steps - handled by script
)

if /i "%SKIP_INFRA%"=="false" (
    REM Apply Kubernetes resources (default behavior)
) else (
    set "PS_ARGS=%PS_ARGS% -SkipKustomizeApply"
)

REM Check if Deploy-SafetyAmp.ps1 exists
if not exist "%~dp0deploy\Deploy-SafetyAmp.ps1" (
    echo ERROR: Deploy-SafetyAmp.ps1 not found in deploy folder!
    echo Expected location: %~dp0deploy\Deploy-SafetyAmp.ps1
    pause
    exit /b 1
)

powershell.exe -ExecutionPolicy Bypass -File "%~dp0deploy\Deploy-SafetyAmp.ps1" %PS_ARGS%

set "RESULT=%ERRORLEVEL%"

if not "%RESULT%"=="0" (
    echo.
    echo Deployment failed. Review the errors above.
) else (
    echo.
    echo Deployment completed successfully.
    echo Recommended follow-up commands:
    echo   kubectl get pods -n %NAMESPACE%
    echo   kubectl logs -f deployment/safety-amp-agent -n %NAMESPACE%
)

echo.
pause
exit /b %RESULT%

