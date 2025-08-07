#!/usr/bin/env pwsh
# Fix Redis Authentication Issue
# This script updates Redis configuration and restarts pods to resolve authentication errors

Write-Host "🔧 Fixing Redis Authentication Issue" -ForegroundColor Cyan
Write-Host "=====================================" -ForegroundColor Cyan

# Step 1: Apply the updated Redis configuration
Write-Host "`n📋 Step 1: Applying updated Redis configuration..." -ForegroundColor Yellow
kubectl apply -f k8s/redis/redis-deployment.yaml -n safety-amp

# Step 2: Wait for Redis pod to be ready
Write-Host "`n⏳ Step 2: Waiting for Redis pod to be ready..." -ForegroundColor Yellow
kubectl wait --for=condition=ready pod -l app=redis -n safety-amp --timeout=120s

# Step 3: Restart SafetyAmp pods to pick up the new Redis configuration
Write-Host "`n🔄 Step 3: Restarting SafetyAmp pods..." -ForegroundColor Yellow
kubectl rollout restart deployment/safety-amp-agent -n safety-amp

# Step 4: Wait for SafetyAmp pods to be ready
Write-Host "`n⏳ Step 4: Waiting for SafetyAmp pods to be ready..." -ForegroundColor Yellow
kubectl wait --for=condition=ready pod -l app=safety-amp -n safety-amp --timeout=300s

# Step 5: Verify Redis connection
Write-Host "`n🔍 Step 5: Verifying Redis connection..." -ForegroundColor Yellow
$redisPod = kubectl get pods -n safety-amp -l app=redis -o jsonpath='{.items[0].metadata.name}' 2>$null
if ($redisPod) {
    Write-Host "Testing Redis authentication..." -ForegroundColor Green
    kubectl exec $redisPod -n safety-amp -- redis-cli -a your-redis-password ping
} else {
    Write-Host "❌ Redis pod not found" -ForegroundColor Red
}

# Step 6: Check SafetyAmp logs for Redis connection status
Write-Host "`n📊 Step 6: Checking SafetyAmp logs for Redis connection..." -ForegroundColor Yellow
$safetyAmpPod = kubectl get pods -n safety-amp -l app=safety-amp-agent -o jsonpath='{.items[0].metadata.name}' 2>$null
if ($safetyAmpPod) {
    Write-Host "Recent SafetyAmp logs (filtered for Redis):" -ForegroundColor Green
    kubectl logs $safetyAmpPod -n safety-amp --tail=20 | Select-String -Pattern "Redis|redis|cache"
} else {
    Write-Host "❌ SafetyAmp pod not found" -ForegroundColor Red
}

Write-Host "`n✅ Redis authentication fix completed!" -ForegroundColor Green
Write-Host "`n💡 Next steps:" -ForegroundColor Cyan
Write-Host "  - Monitor logs: .\deploy\monitor-sync-logs.ps1 -Filter cache" -ForegroundColor Gray
Write-Host "  - Check health: kubectl get pods -n safety-amp" -ForegroundColor Gray
Write-Host "  - View detailed logs: kubectl logs -f deployment/safety-amp-agent -n safety-amp" -ForegroundColor Gray

