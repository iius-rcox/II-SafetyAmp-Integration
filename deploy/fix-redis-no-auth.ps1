#!/usr/bin/env pwsh
# Fix Redis Authentication Issue - No Auth Option
# This script removes Redis authentication for a simpler setup

Write-Host "🔧 Fixing Redis Authentication Issue (No Auth)" -ForegroundColor Cyan
Write-Host "===============================================" -ForegroundColor Cyan

# Step 1: Update SafetyAmp secrets to remove Redis password
Write-Host "`n📋 Step 1: Updating SafetyAmp secrets to remove Redis password..." -ForegroundColor Yellow

# Create a temporary secret file
$secretYaml = @"
apiVersion: v1
kind: Secret
metadata:
  name: safety-amp-secrets
  namespace: safety-amp
  labels:
    app: safety-amp
type: Opaque
stringData:
  # These will be populated from Azure Key Vault
  AZURE_KEY_VAULT_URL: "https://iius-akv.vault.azure.net/"
  REDIS_HOST: "redis-service"
  REDIS_PORT: "6379"
  # REDIS_PASSWORD removed - no authentication required
"@

$secretYaml | kubectl apply -f -

# Step 2: Update Redis deployment to remove authentication
Write-Host "`n📋 Step 2: Updating Redis deployment to remove authentication..." -ForegroundColor Yellow

# Create a temporary Redis config without authentication
$redisConfigYaml = @"
apiVersion: v1
kind: ConfigMap
metadata:
  name: redis-config
  namespace: safety-amp
  labels:
    app: redis
data:
  redis.conf: |
    # Redis configuration for SafetyAmp integration (no auth)
    bind 0.0.0.0
    port 6379
    timeout 0
    tcp-keepalive 300
    daemonize no
    supervised no
    pidfile /var/run/redis_6379.pid
    loglevel notice
    logfile ""
    databases 16
    save 900 1
    save 300 10
    save 60 10000
    stop-writes-on-bgsave-error yes
    rdbcompression yes
    rdbchecksum yes
    dbfilename dump.rdb
    dir /data
    maxmemory 200mb
    maxmemory-policy allkeys-lru
    appendonly yes
    appendfilename "appendonly.aof"
    appendfsync everysec
    no-appendfsync-on-rewrite no
    auto-aof-rewrite-percentage 100
    auto-aof-rewrite-min-size 64mb
    aof-load-truncated yes
    aof-use-rdb-preamble yes
    # No authentication required
---
apiVersion: v1
kind: Service
metadata:
  name: redis-service
  namespace: safety-amp
  labels:
    app: redis
spec:
  type: ClusterIP
  ports:
  - port: 6379
    targetPort: 6379
    protocol: TCP
    name: redis
  selector:
    app: redis
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: redis
  namespace: safety-amp
  labels:
    app: redis
spec:
  replicas: 1
  selector:
    matchLabels:
      app: redis
  template:
    metadata:
      labels:
        app: redis
    spec:
      containers:
      - name: redis
        image: redis:7-alpine
        command: ["redis-server", "/etc/redis/redis.conf"]
        ports:
        - containerPort: 6379
          name: redis
        resources:
          requests:
            memory: "128Mi"
            cpu: "100m"
          limits:
            memory: "256Mi"
            cpu: "200m"
        livenessProbe:
          tcpSocket:
            port: 6379
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          tcpSocket:
            port: 6379
          initialDelaySeconds: 5
          periodSeconds: 5
        volumeMounts:
        - name: redis-data
          mountPath: /data
        - name: redis-config
          mountPath: /etc/redis
      volumes:
      - name: redis-data
        emptyDir: {}
      - name: redis-config
        configMap:
          name: redis-config
"@

$redisConfigYaml | kubectl apply -f -

# Step 3: Update SafetyAmp deployment to remove REDIS_PASSWORD environment variable
Write-Host "`n📋 Step 3: Updating SafetyAmp deployment..." -ForegroundColor Yellow

# Get the current deployment and remove REDIS_PASSWORD
$deployment = kubectl get deployment safety-amp-agent -n safety-amp -o yaml
$deployment = $deployment -replace "        - name: REDIS_PASSWORD`n          valueFrom:`n            secretKeyRef:`n              name: safety-amp-secrets`n              key: REDIS_PASSWORD", ""
$deployment | kubectl apply -f -

# Step 4: Wait for Redis pod to be ready
Write-Host "`n⏳ Step 4: Waiting for Redis pod to be ready..." -ForegroundColor Yellow
kubectl wait --for=condition=ready pod -l app=redis -n safety-amp --timeout=120s

# Step 5: Restart SafetyAmp pods
Write-Host "`n🔄 Step 5: Restarting SafetyAmp pods..." -ForegroundColor Yellow
kubectl rollout restart deployment/safety-amp-agent -n safety-amp

# Step 6: Wait for SafetyAmp pods to be ready
Write-Host "`n⏳ Step 6: Waiting for SafetyAmp pods to be ready..." -ForegroundColor Yellow
kubectl wait --for=condition=ready pod -l app=safety-amp -n safety-amp --timeout=300s

# Step 7: Verify Redis connection
Write-Host "`n🔍 Step 7: Verifying Redis connection..." -ForegroundColor Yellow
$redisPod = kubectl get pods -n safety-amp -l app=redis -o jsonpath='{.items[0].metadata.name}' 2>$null
if ($redisPod) {
    Write-Host "Testing Redis connection (no auth)..." -ForegroundColor Green
    kubectl exec $redisPod -n safety-amp -- redis-cli ping
} else {
    Write-Host "❌ Redis pod not found" -ForegroundColor Red
}

# Step 8: Check SafetyAmp logs
Write-Host "`n📊 Step 8: Checking SafetyAmp logs for Redis connection..." -ForegroundColor Yellow
$safetyAmpPod = kubectl get pods -n safety-amp -l app=safety-amp-agent -o jsonpath='{.items[0].metadata.name}' 2>$null
if ($safetyAmpPod) {
    Write-Host "Recent SafetyAmp logs (filtered for Redis):" -ForegroundColor Green
    kubectl logs $safetyAmpPod -n safety-amp --tail=20 | Select-String -Pattern "Redis|redis|cache"
} else {
    Write-Host "❌ SafetyAmp pod not found" -ForegroundColor Red
}

Write-Host "`n✅ Redis authentication fix completed (No Auth)!" -ForegroundColor Green
Write-Host "`n💡 Next steps:" -ForegroundColor Cyan
Write-Host "  - Monitor logs: .\deploy\monitor-sync-logs.ps1 -Filter cache" -ForegroundColor Gray
Write-Host "  - Check health: kubectl get pods -n safety-amp" -ForegroundColor Gray
Write-Host "  - View detailed logs: kubectl logs -f deployment/safety-amp-agent -n safety-amp" -ForegroundColor Gray

