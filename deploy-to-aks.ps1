#!/usr/bin/env pwsh
<#
.SYNOPSIS
    One-click deployment script for SafetyAmp Integration to AKS
.DESCRIPTION
    Automates Docker build & push, Kubernetes manifest deployment, and health verification.
.PARAMETER Environment
    Target environment: dev, staging, or prod (default: dev).
.PARAMETER Tag
    Docker image tag (default: latest).
.PARAMETER SkipBuild
    Skip Docker build and push steps.
.PARAMETER SkipInfra
    Skip infrastructure deployment steps.
.PARAMETER DryRun
    Output the planned actions without making changes.
.PARAMETER ResourceGroup
    Override the Azure resource group for the AKS cluster.
.PARAMETER ClusterName
    Override the AKS cluster name.
#>

param(
    [Parameter(Mandatory=$false)]
    [ValidateSet('dev', 'staging', 'prod')]
    [string]$Environment = 'dev',

    [Parameter(Mandatory=$false)]
    [string]$Tag = 'latest',

    [Parameter(Mandatory=$false)]
    [switch]$SkipBuild,

    [Parameter(Mandatory=$false)]
    [switch]$SkipInfra,

    [Parameter(Mandatory=$false)]
    [switch]$DryRun,

    [Parameter(Mandatory=$false)]
    [string]$ResourceGroup,

    [Parameter(Mandatory=$false)]
    [string]$ClusterName
)

$defaultConfig = @{
    dev = @{
        ResourceGroup = 'rg_prod'
        ClusterName   = 'dev-aks'
        ACRName       = 'iiusacr'
        Namespace     = 'safety-amp'
        Replicas      = 1
    }
    staging = @{
        ResourceGroup = 'rg_prod'
        ClusterName   = 'dev-aks'
        ACRName       = 'iiusacr'
        Namespace     = 'safety-amp'
        Replicas      = 2
    }
    prod = @{
        ResourceGroup = 'rg_prod'
        ClusterName   = 'dev-aks'
        ACRName       = 'iiusacr'
        Namespace     = 'safety-amp'
        Replicas      = 2
    }
}

$envDefaults = $defaultConfig[$Environment]
if (-not $envDefaults) {
    throw "Unsupported environment: $Environment"
}

$envConfig = @{}
foreach ($key in $envDefaults.Keys) {
    $envConfig[$key] = $envDefaults[$key]
}

if ($PSBoundParameters.ContainsKey('ResourceGroup')) {
    $envConfig.ResourceGroup = $ResourceGroup
}

if ($PSBoundParameters.ContainsKey('ClusterName')) {
    $envConfig.ClusterName = $ClusterName
}

$imageName = "{0}.azurecr.io/safetyamp-integration:{1}" -f $envConfig.ACRName, $Tag
$script:ClusterEndpoint = $null

function Write-Step {
    param([string]$Message)
    Write-Host "`n==> $Message" -ForegroundColor Cyan
}

function Write-Success {
    param([string]$Message)
    Write-Host "[OK] $Message" -ForegroundColor Green
}

function Write-ErrorMessage {
    param([string]$Message)
    Write-Host "[ERROR] $Message" -ForegroundColor Red
}

function Write-Info {
    param([string]$Message)
    Write-Host "[INFO] $Message" -ForegroundColor Yellow
}

function Get-KubectlFailureMessage {
    param(
        [string]$Action,
        [string]$RawOutput
    )

    if ($null -ne $RawOutput -and $RawOutput -match 'no such host|i/o timeout|context deadline exceeded') {
        if ($script:ClusterEndpoint) {
            return "$Action failed: unable to reach cluster endpoint '$script:ClusterEndpoint'. Ensure VPN/private DNS connectivity, then retry."
        }
        return "$Action failed: unable to reach the AKS API endpoint. Ensure VPN/private DNS connectivity, then retry."
    }

    if ([string]::IsNullOrWhiteSpace($RawOutput)) {
        return "$Action failed. kubectl returned a non-zero exit code without output."
    }

    return "$Action failed. kubectl reported:`n$RawOutput"
}

function Deploy-SafetyAmpIntegration {
    try {
        Write-Host
        Write-Host '============================================================' -ForegroundColor Magenta
        Write-Host ' SafetyAmp Integration - One-Click Deployment' -ForegroundColor Magenta
        Write-Host " Environment : $Environment" -ForegroundColor Magenta
        Write-Host " Cluster     : $($envConfig.ClusterName)" -ForegroundColor Magenta
        Write-Host " ResourceGrp : $($envConfig.ResourceGroup)" -ForegroundColor Magenta
        Write-Host " Image Tag   : $Tag" -ForegroundColor Magenta
        Write-Host '============================================================' -ForegroundColor Magenta

        if ($DryRun) {
            Write-Info 'DRY RUN MODE - No changes will be made.'
        }

        Write-Step 'Checking Azure authentication...'
        $accountJson = az account show 2>$null
        if ($LASTEXITCODE -eq 0 -and $accountJson) {
            $account = $accountJson | ConvertFrom-Json
            Write-Success "Authenticated as: $($account.user.name)"
        } else {
            Write-Info 'Not logged in to Azure. Initiating login...'
            if (-not $DryRun) {
                az login | Out-Null
                if ($LASTEXITCODE -ne 0) {
                    throw 'Azure login failed.'
                }
            } else {
                Write-Info 'Dry run: skipping az login.'
            }
        }

        Write-Step 'Validating AKS cluster...'
        $clusterDetails = $null
        if (-not $DryRun) {
            $clusterRaw = az aks show --resource-group $envConfig.ResourceGroup --name $envConfig.ClusterName 2>$null
            if ($LASTEXITCODE -ne 0 -or -not $clusterRaw) {
                throw "AKS cluster '$($envConfig.ClusterName)' was not found in resource group '$($envConfig.ResourceGroup)'."
            }
            $clusterDetails = $clusterRaw | ConvertFrom-Json
            $script:ClusterEndpoint = if ($clusterDetails.fqdn) { $clusterDetails.fqdn } elseif ($clusterDetails.privateFqdn) { $clusterDetails.privateFqdn } else { $null }
            if ($script:ClusterEndpoint) {
                try {
                    [System.Net.Dns]::GetHostAddresses($script:ClusterEndpoint) | Out-Null
                } catch {
                    Write-Info "DNS lookup for $script:ClusterEndpoint failed. Connect to the private network or ensure DNS forwarding is configured before proceeding."
                }
            }
        } else {
            Write-Info 'Dry run: skipping AKS cluster validation.'
        }
        Write-Success "Cluster confirmed: $($envConfig.ClusterName)"

        Write-Step 'Getting AKS cluster credentials...'
        if (-not $DryRun) {
            az aks get-credentials `
                --resource-group $envConfig.ResourceGroup `
                --name $envConfig.ClusterName `
                --overwrite-existing | Out-Null
            if ($LASTEXITCODE -ne 0) {
                throw 'Failed to get AKS credentials.'
            }
        } else {
            Write-Info 'Dry run: skipping az aks get-credentials.'
        }
        Write-Success "Cluster context ready: $($envConfig.ClusterName)"

        if (-not $SkipBuild) {
            Write-Step 'Verifying Docker daemon...'
            if (-not $DryRun) {
                $dockerInfo = & docker info 2>&1
                if ($LASTEXITCODE -ne 0) {
                    $details = ($dockerInfo | Out-String).Trim()
                    if (-not [string]::IsNullOrWhiteSpace($details)) {
                        Write-ErrorMessage $details
                    }
                    throw 'Docker daemon is unreachable. Start Docker Desktop or rerun with -SkipBuild.'
                }
            } else {
                Write-Info 'Dry run: skipping docker info check.'
            }
            Write-Step 'Building Docker image...'
            if (-not $DryRun) {
                docker build -t $imageName . | Out-Null
                if ($LASTEXITCODE -ne 0) {
                    throw 'Docker build failed.'
                }
            } else {
                Write-Info 'Dry run: skipping docker build.'
            }
            Write-Success "Docker image prepared: $imageName"

            Write-Step 'Logging in to Azure Container Registry...'
            if (-not $DryRun) {
                az acr login --name $envConfig.ACRName | Out-Null
                if ($LASTEXITCODE -ne 0) {
                    throw 'ACR login failed.'
                }
            } else {
                Write-Info 'Dry run: skipping az acr login.'
            }
            Write-Success 'ACR login step complete.'

            Write-Step 'Pushing Docker image...'
            if (-not $DryRun) {
                docker push $imageName | Out-Null
                if ($LASTEXITCODE -ne 0) {
                    throw 'Docker push failed.'
                }
            } else {
                Write-Info 'Dry run: skipping docker push.'
            }
            Write-Success 'Docker image push step complete.'
        } else {
            Write-Info 'Skipping Docker build and push (SkipBuild flag set).'
        }

        if (-not $SkipInfra) {
            Write-Step 'Deploying infrastructure components...'
            $infraFiles = @(
                'k8s/namespaces/namespaces.yaml',
                'k8s/cert-manager/cert-manager.yaml',
                'k8s/ingress/nginx-ingress-controller.yaml'
            )

            foreach ($file in $infraFiles) {
                if (Test-Path $file) {
                    if (-not $DryRun) {
                        $infraOutput = & kubectl apply -f $file 2>&1
                        if ($LASTEXITCODE -ne 0) {
                            $message = ($infraOutput | Out-String).Trim()
                            Write-Info (Get-KubectlFailureMessage -Action "kubectl apply -f $file" -RawOutput $message)
                        }
                    } else {
                        Write-Info "Dry run: would apply $file"
                    }
                }
            }
            Write-Success 'Infrastructure components processed.'
        } else {
            Write-Info 'Skipping infrastructure deployment (SkipInfra flag set).'
        }

        Write-Step 'Deploying SafetyAmp Integration...'
        $deploymentFile = 'k8s/safety-amp/safety-amp-complete.yaml'
        if (Test-Path $deploymentFile) {
            if (-not $DryRun) {
                $content = Get-Content -Path $deploymentFile -Raw
                $updated = $content -replace 'image:\s*.+/safetyamp-integration:[^\n]+', "image: $imageName"
                $tempFile = [System.IO.Path]::GetTempFileName()
                Set-Content -Path $tempFile -Value $updated -Encoding UTF8
                $applyOutput = & kubectl apply -f $tempFile 2>&1
                $applyExit = $LASTEXITCODE
                Remove-Item $tempFile -ErrorAction SilentlyContinue
                if ($applyExit -ne 0) {
                    $message = ($applyOutput | Out-String).Trim()
                    throw (Get-KubectlFailureMessage -Action 'Application deployment' -RawOutput $message)
                }
            } else {
                Write-Info "Dry run: would update image to $imageName in $deploymentFile"
            }
            Write-Success 'SafetyAmp deployment applied.'
        } else {
            Write-Info "Deployment manifest not found at $deploymentFile"
        }

        Write-Step 'Applying environment overlays...'
        $overlayPath = "k8s/overlays/$Environment"
        if (Test-Path $overlayPath) {
            if (-not $DryRun) {
                $overlayOutput = & kubectl apply -k $overlayPath 2>&1
                if ($LASTEXITCODE -ne 0) {
                    $message = ($overlayOutput | Out-String).Trim()
                    Write-Info (Get-KubectlFailureMessage -Action "Overlay apply" -RawOutput $message)
                }
            } else {
                Write-Info "Dry run: would apply overlay at $overlayPath"
            }
            Write-Success 'Environment overlays applied.'
        } else {
            Write-Info "No overlays found at $overlayPath"
        }

        Write-Step 'Deploying monitoring stack...'
        $monitoringFiles = @(
            'k8s/monitoring/monitoring-stack.yaml',
            'k8s/monitoring/grafana/datasource-azuremonitor.yaml'
        )

        foreach ($file in $monitoringFiles) {
            if (Test-Path $file) {
                if (-not $DryRun) {
                    $monitorOutput = & kubectl apply -f $file 2>&1
                    if ($LASTEXITCODE -ne 0) {
                        $message = ($monitorOutput | Out-String).Trim()
                        Write-Info (Get-KubectlFailureMessage -Action "kubectl apply -f $file" -RawOutput $message)
                    }
                } else {
                    Write-Info "Dry run: would apply $file"
                }
            }
        }
        Write-Success 'Monitoring stack processed.'

        Write-Step 'Waiting for deployment rollout...'
        $rolloutSucceeded = $true
        if (-not $DryRun) {
            $rolloutOutput = & kubectl rollout status deployment/safety-amp-agent -n $envConfig.Namespace --timeout=300s 2>&1
            if ($LASTEXITCODE -ne 0) {
                $message = ($rolloutOutput | Out-String).Trim()
                Write-ErrorMessage (Get-KubectlFailureMessage -Action 'Rollout status' -RawOutput $message)
                Write-Info 'Checking pod status...'
                & kubectl get pods -n $envConfig.Namespace 2>$null
                $rolloutSucceeded = $false
            }
        } else {
            Write-Info 'Dry run: skipping rollout status check.'
        }

        if ($rolloutSucceeded) {
            Write-Success 'Deployment rollout completed.'
        }

        Write-Step 'Verifying deployment health...'
        if (-not $DryRun) {
            $podsJsonOutput = & kubectl get pods -n $envConfig.Namespace -o json 2>&1
            if ($LASTEXITCODE -eq 0 -and $podsJsonOutput) {
                $pods = ($podsJsonOutput | Out-String | ConvertFrom-Json)
                $runningPods = @($pods.items | Where-Object { $_.status.phase -eq 'Running' })
                if ($runningPods.Count -gt 0) {
                    Write-Success "$($runningPods.Count) pod(s) running."
                    Write-Info 'Testing health endpoint via port-forward...'
                    $job = Start-Job -ScriptBlock {
                        param($ns)
                        kubectl port-forward -n $ns svc/safety-amp-service 8080:8080 | Out-Null
                    } -ArgumentList $envConfig.Namespace
                    Start-Sleep -Seconds 5
                    try {
                        $health = Invoke-RestMethod -Uri 'http://localhost:8080/health' -Method Get -TimeoutSec 10
                        if ($health -and $health.status) {
                            Write-Success "Health check passed: $($health.status)"
                        } else {
                            Write-Success 'Health endpoint responded.'
                        }
                    } catch {
                        Write-Info 'Health check failed or timed out (port-forward may be blocked).'
                    } finally {
                        Stop-Job $job -ErrorAction SilentlyContinue | Out-Null
                        Remove-Job $job -ErrorAction SilentlyContinue
                    }
                } else {
                    Write-ErrorMessage "No running pods found in namespace $($envConfig.Namespace)."
                }
            } else {
                $message = ($podsJsonOutput | Out-String).Trim()
                Write-ErrorMessage (Get-KubectlFailureMessage -Action 'Pod status retrieval' -RawOutput $message)
            }
        } else {
            Write-Info 'Dry run: skipping health verification.'
        }

        Write-Host
        Write-Host '============================================================' -ForegroundColor Green
        Write-Host ' Deployment completed successfully.' -ForegroundColor Green
        Write-Host '------------------------------------------------------------' -ForegroundColor Green
        Write-Host ' Next steps:' -ForegroundColor Green
        Write-Host "  1. kubectl get pods -n $($envConfig.Namespace)" -ForegroundColor Green
        Write-Host "  2. kubectl logs -f deployment/safety-amp-agent -n $($envConfig.Namespace)" -ForegroundColor Green
        Write-Host "  3. kubectl port-forward -n $($envConfig.Namespace) svc/safety-amp-service 9090:9090" -ForegroundColor Green
        Write-Host "  4. .\\deploy\\monitor.ps1 -Feature dashboard -Hours 24" -ForegroundColor Green
        Write-Host '============================================================' -ForegroundColor Green

    } catch {
        Write-ErrorMessage "Deployment failed: $_"
        Write-Host
        Write-Host 'Troubleshooting tips:' -ForegroundColor Yellow
        Write-Host '  1. az account show' -ForegroundColor Yellow
        Write-Host "  2. kubectl cluster-info" -ForegroundColor Yellow
        Write-Host "  3. kubectl get pods -n $($envConfig.Namespace)" -ForegroundColor Yellow
        Write-Host "  4. kubectl logs -n $($envConfig.Namespace) <pod-name>" -ForegroundColor Yellow
        exit 1
    }
}

Deploy-SafetyAmpIntegration

