# SafetyAmp Integration Resource Optimization

## Current Resource Configuration Analysis

### Main Deployment (`safety-amp-agent`)

**Current Settings:**
```yaml
resources:
  requests:
    memory: "512Mi"
    cpu: "200m"
  limits:
    memory: "1Gi"
    cpu: "1000m"
```

**Analysis:**
- ✅ **Memory requests**: 512Mi is reasonable for connection pooling and caching
- ⚠️ **CPU requests**: 200m might be low for sync operations
- ⚠️ **Memory limits**: 1Gi could be excessive for steady-state operation
- ⚠️ **CPU limits**: 1000m (1 full core) may be high for most operations

### CronJob (`safety-amp-sync-job`)

**Current Settings:**
```yaml
resources:
  requests:
    memory: "256Mi"
    cpu: "100m"
  limits:
    memory: "512Mi"
    cpu: "500m"
```

**Analysis:**
- ✅ **Settings**: Appropriate for batch operations
- ✅ **Lower than main deployment**: Correct approach

## Recommended Optimizations

### 1. Environment-Based Resource Profiles

#### Development/Staging Environment
```yaml
# Main deployment
resources:
  requests:
    memory: "256Mi"
    cpu: "100m"
  limits:
    memory: "512Mi"
    cpu: "500m"

# CronJob
resources:
  requests:
    memory: "128Mi"
    cpu: "50m"
  limits:
    memory: "256Mi"
    cpu: "200m"
```

#### Production Environment
```yaml
# Main deployment
resources:
  requests:
    memory: "512Mi"
    cpu: "250m"
  limits:
    memory: "1Gi"
    cpu: "750m"

# CronJob  
resources:
  requests:
    memory: "256Mi"
    cpu: "100m"
  limits:
    memory: "512Mi"
    cpu: "400m"
```

#### High-Load Production Environment
```yaml
# Main deployment
resources:
  requests:
    memory: "768Mi"
    cpu: "500m"
  limits:
    memory: "1.5Gi"
    cpu: "1000m"

# CronJob
resources:
  requests:
    memory: "512Mi"
    cpu: "200m"
  limits:
    memory: "1Gi"
    cpu: "600m"
```

### 2. Dynamic Resource Scaling

#### Horizontal Pod Autoscaler (HPA)
```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: safety-amp-agent-hpa
  namespace: safety-amp
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: safety-amp-agent
  minReplicas: 1
  maxReplicas: 3
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
  - type: Resource
    resource:
      name: memory
      target:
        type: Utilization
        averageUtilization: 80
  behavior:
    scaleDown:
      stabilizationWindowSeconds: 300
      policies:
      - type: Percent
        value: 50
        periodSeconds: 60
    scaleUp:
      stabilizationWindowSeconds: 60
      policies:
      - type: Percent
        value: 100
        periodSeconds: 30
```

#### Vertical Pod Autoscaler (VPA) - Recommendation Mode
```yaml
apiVersion: autoscaling.k8s.io/v1
kind: VerticalPodAutoscaler
metadata:
  name: safety-amp-agent-vpa
  namespace: safety-amp
spec:
  targetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: safety-amp-agent
  updatePolicy:
    updateMode: "Off"  # Recommendation only
  resourcePolicy:
    containerPolicies:
    - containerName: safety-amp-agent
      minAllowed:
        cpu: 50m
        memory: 128Mi
      maxAllowed:
        cpu: 2
        memory: 2Gi
      controlledResources: ["cpu", "memory"]
```

### 3. Connection Pool Optimization

#### Current Pool Settings
```yaml
DB_POOL_SIZE: "5"
DB_MAX_OVERFLOW: "10"
DB_POOL_TIMEOUT: "30"
DB_POOL_RECYCLE: "3600"
```

#### Optimized Pool Settings by Environment

**Development:**
```yaml
DB_POOL_SIZE: "2"
DB_MAX_OVERFLOW: "3"
DB_POOL_TIMEOUT: "15"
DB_POOL_RECYCLE: "1800"
```

**Production (Low Load):**
```yaml
DB_POOL_SIZE: "5"
DB_MAX_OVERFLOW: "10"
DB_POOL_TIMEOUT: "30"
DB_POOL_RECYCLE: "3600"
```

**Production (High Load):**
```yaml
DB_POOL_SIZE: "10"
DB_MAX_OVERFLOW: "20"
DB_POOL_TIMEOUT: "45"
DB_POOL_RECYCLE: "7200"
```

### 4. Memory Usage Patterns

#### Expected Memory Usage
- **Base application**: ~100-150MB
- **SQLAlchemy connection pool**: ~50-100MB per connection
- **Redis cache client**: ~20-50MB
- **HTTP client libraries**: ~30-50MB
- **Azure SDK libraries**: ~50-100MB

#### Memory Calculation Formula
```
Total Memory = Base + (Pool_Size × 75MB) + Cache_Overhead + Buffer
             = 150MB + (5 × 75MB) + 70MB + 100MB
             = 695MB ≈ 700MB
```

**Recommendation**: Set requests to 75% of calculated need, limits to 150%
- **Requests**: 512MB (safe for pooled connections)
- **Limits**: 1GB (allows for spikes during large syncs)

### 5. Monitoring and Alerts

#### Resource Monitoring Queries
```promql
# CPU utilization
rate(container_cpu_usage_seconds_total{pod=~"safety-amp-agent-.*"}[5m]) * 100

# Memory utilization  
container_memory_working_set_bytes{pod=~"safety-amp-agent-.*"} / container_spec_memory_limit_bytes * 100

# Database connection pool usage
db_connection_pool_active_connections / db_connection_pool_size * 100
```

#### Recommended Alerts
```yaml
# High CPU utilization
- alert: SafetyAmpHighCPU
  expr: rate(container_cpu_usage_seconds_total{pod=~"safety-amp-agent-.*"}[5m]) > 0.8
  for: 5m
  
# High memory utilization
- alert: SafetyAmpHighMemory
  expr: container_memory_working_set_bytes{pod=~"safety-amp-agent-.*"} / container_spec_memory_limit_bytes > 0.9
  for: 2m

# Connection pool exhaustion
- alert: SafetyAmpPoolExhaustion
  expr: db_connection_pool_active_connections / db_connection_pool_size > 0.9
  for: 1m
```

### 6. Performance Tuning Recommendations

#### Application-Level Optimizations
1. **Enable connection pooling validation**:
   ```python
   pool_pre_ping=True  # Already enabled
   ```

2. **Optimize cache TTL based on data change frequency**:
   ```yaml
   CACHE_TTL_HOURS: "4"  # Increase if data changes infrequently
   ```

3. **Use async operations where possible**:
   ```python
   # Consider asyncio for concurrent API calls
   ```

#### Infrastructure Optimizations
1. **Node affinity for database proximity**:
   ```yaml
   nodeAffinity:
     preferredDuringSchedulingIgnoredDuringExecution:
     - weight: 100
       preference:
         matchExpressions:
         - key: topology.azure.com/zone
           operator: In
           values: ["zone-with-sql-server"]
   ```

2. **Pod topology spread constraints**:
   ```yaml
   topologySpreadConstraints:
   - maxSkew: 1
     topologyKey: topology.kubernetes.io/zone
     whenUnsatisfiable: DoNotSchedule
     labelSelector:
       matchLabels:
         app: safety-amp
   ```

### 7. Cost Optimization

#### Current Monthly Cost Estimate (Azure AKS)
- **3 nodes × Standard_D2s_v3**: ~$140/month
- **Storage**: ~$10/month
- **Load Balancer**: ~$20/month
- **Total**: ~$170/month

#### Optimized Cost (Right-sized)
- **2 nodes × Standard_B2s**: ~$60/month
- **Storage**: ~$10/month
- **Load Balancer**: ~$20/month
- **Total**: ~$90/month
- **Savings**: ~47%

### 8. Implementation Strategy

#### Phase 1: Monitoring (Week 1)
1. Deploy VPA in recommendation mode
2. Enable detailed metrics collection
3. Monitor for 1 week to establish baseline

#### Phase 2: Gradual Optimization (Week 2)
1. Implement environment-specific resource configs
2. Adjust connection pool settings
3. Deploy HPA for automatic scaling

#### Phase 3: Fine-tuning (Week 3-4)
1. Apply VPA recommendations
2. Optimize based on real usage patterns
3. Implement cost optimizations

#### Phase 4: Production Deployment (Week 4)
1. Apply optimized configurations to production
2. Monitor performance closely
3. Document final settings

## Testing Resource Changes

```bash
# Apply changes gradually
kubectl patch deployment safety-amp-agent -n safety-amp -p '{"spec":{"template":{"spec":{"containers":[{"name":"safety-amp-agent","resources":{"requests":{"memory":"256Mi","cpu":"100m"}}}]}}}}'

# Monitor impact
kubectl top pods -n safety-amp
kubectl get hpa -n safety-amp

# Check performance
kubectl port-forward svc/safety-amp-service 8080:8080 -n safety-amp
curl http://localhost:8080/metrics
```

This optimization plan will reduce costs while maintaining performance and reliability.