#!/usr/bin/env pwsh
# Fix Cache Manager Method Signature Issue
# This script deploys the updated cache manager and restarts pods

Write-Host "🔧 Fixing Cache Manager Method Signature Issue" -ForegroundColor Cyan
Write-Host "=============================================" -ForegroundColor Cyan

# Step 1: Check current pod status
Write-Host "`n📋 Step 1: Checking current pod status..." -ForegroundColor Yellow
kubectl get pods -n safety-amp

# Step 2: Restart SafetyAmp pods to pick up the updated code
Write-Host "`n🔄 Step 2: Restarting SafetyAmp pods to pick up cache manager fixes..." -ForegroundColor Yellow
kubectl rollout restart deployment/safety-amp-agent -n safety-amp

# Step 3: Wait for SafetyAmp pods to be ready
Write-Host "`n⏳ Step 3: Waiting for SafetyAmp pods to be ready..." -ForegroundColor Yellow
kubectl wait --for=condition=ready pod -l app=safety-amp -n safety-amp --timeout=300s

# Step 4: Check pod status after restart
Write-Host "`n📊 Step 4: Checking pod status after restart..." -ForegroundColor Yellow
kubectl get pods -n safety-amp

# Step 5: Check SafetyAmp logs for cache manager errors
Write-Host "`n🔍 Step 5: Checking SafetyAmp logs for cache manager errors..." -ForegroundColor Yellow
$safetyAmpPod = kubectl get pods -n safety-amp -l app=safety-amp-agent -o jsonpath='{.items[0].metadata.name}' 2>$null
if ($safetyAmpPod) {
    Write-Host "Recent SafetyAmp logs (filtered for cache/error):" -ForegroundColor Green
    kubectl logs $safetyAmpPod -n safety-amp --tail=30 | Select-String -Pattern "cache|Cache|ERROR|Error|TypeError"
} else {
    Write-Host "❌ SafetyAmp pod not found" -ForegroundColor Red
}

# Step 6: Test cache functionality
Write-Host "`n🧪 Step 6: Testing cache functionality..." -ForegroundColor Yellow
Write-Host "Monitoring logs for cache operations..." -ForegroundColor Green
kubectl logs -f deployment/safety-amp-agent -n safety-amp --tail=50 | Select-String -Pattern "cache|Cache|Using cached|Fetching fresh" -Context 2

Write-Host "`n✅ Cache manager fix completed!" -ForegroundColor Green
Write-Host "`n💡 Next steps:" -ForegroundColor Cyan
Write-Host "  - Monitor logs: .\deploy\monitor-sync-logs.ps1 -Filter cache" -ForegroundColor Gray
Write-Host "  - Check health: kubectl get pods -n safety-amp" -ForegroundColor Gray
Write-Host "  - View detailed logs: kubectl logs -f deployment/safety-amp-agent -n safety-amp" -ForegroundColor Gray
Write-Host "  - Test sync: .\deploy\monitor-sync-logs.ps1 -Filter sync" -ForegroundColor Gray

