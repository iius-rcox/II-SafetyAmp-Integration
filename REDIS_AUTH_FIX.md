# Redis Authentication Issue Fix

## Problem
The SafetyAmp integration is experiencing Redis connection failures with the error:
```
Redis connection failed: AUTH <password> called without any password configured for the default user. Are you sure your configuration is correct?
```

## Root Cause
- The Redis deployment was running without authentication configured
- The SafetyAmp application was trying to connect with a password (`REDIS_PASSWORD: "your-redis-password"`)
- Redis rejected the AUTH command because no password was configured

## Additional Issue: Cache Manager Method Signature
After fixing Redis authentication, a new error appeared:
```
TypeError: CacheManager.get_cached_data() got an unexpected keyword argument 'max_age_hours'
```

**Root Cause:**
- The SafetyAmp API client was calling `get_cached_data()` with advanced parameters
- The cache manager only supported basic caching functionality
- Missing method signature for advanced caching with validation and refresh logic

## Solutions

### Option 1: Enable Redis Authentication (Recommended for Production)
This option configures Redis with proper authentication for better security.

**Files Updated:**
- `k8s/redis/redis-deployment.yaml` - Added Redis configuration with authentication
- `deploy/fix-redis-auth.ps1` - Script to apply the fix

**To apply:**
```powershell
.\deploy\fix-redis-auth.ps1
```

**What it does:**
1. Creates a Redis ConfigMap with authentication enabled (`requirepass your-redis-password`)
2. Updates Redis deployment to use the configuration file
3. Restarts SafetyAmp pods to pick up the new configuration
4. Verifies the connection works

### Option 2: Remove Redis Authentication (Simpler Setup)
This option removes authentication entirely for a simpler development setup.

**Files Updated:**
- `k8s/redis/redis-deployment.yaml` - Updated to remove authentication
- `deploy/fix-redis-no-auth.ps1` - Script to apply the fix

**To apply:**
```powershell
.\deploy\fix-redis-no-auth.ps1
```

**What it does:**
1. Removes `REDIS_PASSWORD` from SafetyAmp secrets
2. Updates Redis configuration to run without authentication
3. Removes `REDIS_PASSWORD` environment variable from SafetyAmp deployment
4. Restarts all pods and verifies connection

### Fix 3: Cache Manager Method Signature
This fix adds the missing advanced caching functionality.

**Files Updated:**
- `utils/cache_manager.py` - Added `get_cached_data_with_fallback()` method
- `services/safetyamp_api.py` - Updated to use new method
- `deploy/fix-cache-manager.ps1` - Script to apply the fix

**To apply:**
```powershell
.\deploy\fix-cache-manager.ps1
```

**What it does:**
1. Adds advanced caching method with validation and refresh logic
2. Updates API client to use the correct method signature
3. Restarts pods to pick up the updated code
4. Verifies cache operations work correctly

## Complete Fix Sequence

To resolve all issues, run the fixes in this order:

```powershell
# 1. Fix Redis authentication (choose one)
.\deploy\fix-redis-auth.ps1
# OR
.\deploy\fix-redis-no-auth.ps1

# 2. Fix cache manager method signature
.\deploy\fix-cache-manager.ps1
```

## Verification

After applying all fixes, verify the solution worked:

```powershell
# Check pod status
kubectl get pods -n safety-amp

# Monitor logs for Redis connection
.\deploy\monitor-sync-logs.ps1 -Filter cache

# Check specific Redis logs
kubectl logs -f deployment/safety-amp-agent -n safety-amp | Select-String -Pattern "Redis|redis|cache"

# Test sync operations
.\deploy\monitor-sync-logs.ps1 -Filter sync
```

## Expected Results

**Successful Redis Connection:**
```
[INFO] [cache_manager]: Redis connected successfully to redis-service:6379
```

**Successful Cache Operations:**
```
[INFO] [cache_manager]: Using valid cached data for safetyamp_sites
[INFO] [cache_manager]: Fetching fresh data for safetyamp_sites
[INFO] [cache_manager]: Saved fresh data to cache for safetyamp_sites: 25 items
```

**No More Errors:**
- No more "AUTH <password> called without any password configured" errors
- No more "TypeError: CacheManager.get_cached_data() got an unexpected keyword argument" errors
- Cache operations should work normally
- Sync operations should complete successfully

## Security Considerations

- **Option 1 (With Auth)**: More secure, recommended for production environments
- **Option 2 (No Auth)**: Simpler setup, suitable for development or internal networks

## Troubleshooting

If issues persist:

1. **Check Redis pod status:**
   ```powershell
   kubectl get pods -n safety-amp -l app=redis
   ```

2. **Check Redis logs:**
   ```powershell
   kubectl logs -f deployment/redis -n safety-amp
   ```

3. **Test Redis connection manually:**
   ```powershell
   kubectl exec -it <redis-pod-name> -n safety-amp -- redis-cli ping
   ```

4. **Verify environment variables:**
   ```powershell
   kubectl exec -it <safetyamp-pod-name> -n safety-amp -- env | grep REDIS
   ```

5. **Check cache manager logs:**
   ```powershell
   kubectl logs -f deployment/safety-amp-agent -n safety-amp | Select-String -Pattern "cache|Cache"
   ```
