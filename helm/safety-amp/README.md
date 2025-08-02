# SafetyAmp Integration Helm Chart

A Helm chart for deploying the SafetyAmp Integration service that synchronizes employee, vehicle, and job data between Viewpoint, Samsara, and SafetyAmp systems.

## Overview

This chart deploys a production-ready SafetyAmp integration capable of processing **5000 records/hour** with:
- Optimized batch processing (125 records per 15-minute sync)
- Intelligent rate limiting for API compliance
- Circuit breaker patterns for resilience
- Comprehensive monitoring and alerting
- Multi-environment support (development, staging, production)

## Prerequisites

- Kubernetes 1.19+
- Helm 3.2.0+
- Azure CLI (for Key Vault integration)
- Container registry access (Azure Container Registry)

## Installation

### Quick Start

```bash
# Install in production
./deploy/helm-deploy.sh -e production install

# Install in development
./deploy/helm-deploy.sh -e development install

# Install with custom image
./deploy/helm-deploy.sh -e production -i v1.1.0 install
```

### Manual Installation

```bash
# Add the chart repository (if using remote)
helm repo add safety-amp https://your-charts.example.com
helm repo update

# Install with default values
helm install safety-amp-production ./helm/safety-amp \
  --namespace safety-amp \
  --create-namespace \
  --values ./helm/safety-amp/values-production.yaml

# Install with custom values
helm install safety-amp-production ./helm/safety-amp \
  --namespace safety-amp \
  --create-namespace \
  --set image.tag=v1.1.0 \
  --set keyVault.name=your-key-vault
```

## Configuration

### Environment-Specific Configurations

The chart includes pre-configured values for different environments:

| Environment | File | Description |
|-------------|------|-------------|
| Development | `values-development.yaml` | Small batches, debug logging, minimal resources |
| Staging | `values-staging.yaml` | Medium batches, validation setup, moderate resources |
| Production | `values-production.yaml` | Optimized for 5000 records/hour, full monitoring |

### Key Configuration Options

#### Performance Tuning (5000 Records/Hour)

```yaml
config:
  syncInterval: 900    # 15 minutes (4 times per hour)
  batchSize: 125       # 125 records per sync (5000 ÷ 4)
  cacheTtlHours: 4     # Longer cache for stable data
  
  database:
    poolSize: 8        # Optimized connection pool
    maxOverflow: 15    # Additional connections for spikes
```

#### Resource Allocation

```yaml
resources:
  requests:
    memory: "768Mi"    # Base memory for processing
    cpu: "300m"        # Base CPU for operations
  limits:
    memory: "1.5Gi"    # Maximum memory for spikes
    cpu: "1500m"       # Maximum CPU for 5000 records/hour
```

#### Rate Limiting

```yaml
config:
  apiRateLimit:
    calls: 60          # SafetyAmp: 60 requests/minute
    period: 61         # With 1-second buffer
```

#### High Availability

```yaml
replicaCount: 2        # Multiple instances

autoscaling:
  enabled: true
  minReplicas: 2
  maxReplicas: 5
  targetCPUUtilizationPercentage: 70

podDisruptionBudget:
  enabled: true
  minAvailable: 1
```

### Required Secrets

The following secrets must be configured in Azure Key Vault:

| Secret Name | Description |
|-------------|-------------|
| `SAFETYAMP-TOKEN` | SafetyAmp API authentication token |
| `MS-GRAPH-CLIENT-SECRET` | Microsoft Graph API client secret |
| `SAMSARA-API-KEY` | Samsara API key |
| `SQL-SERVER` | Viewpoint SQL Server connection string |
| `SQL-DATABASE` | Viewpoint database name |

```bash
# Set secrets in Azure Key Vault
az keyvault secret set --vault-name kv-safety-amp-prod --name "SAFETYAMP-TOKEN" --value "your-token"
az keyvault secret set --vault-name kv-safety-amp-prod --name "SAMSARA-API-KEY" --value "your-key"
# ... etc
```

## Usage Examples

### Development Environment

```bash
# Install development environment
./deploy/helm-deploy.sh -e development install

# Check status
./deploy/helm-deploy.sh -e development status

# View logs
kubectl logs -f deployment/safety-amp-development-agent -n safety-amp
```

### Staging Environment

```bash
# Install staging environment
./deploy/helm-deploy.sh -e staging install

# Test with specific image
./deploy/helm-deploy.sh -e staging -i v1.1.0-beta upgrade

# Run tests
./deploy/helm-deploy.sh -e staging test
```

### Production Environment

```bash
# Install production environment
./deploy/helm-deploy.sh -e production install

# Upgrade to new version
./deploy/helm-deploy.sh -e production -i v1.2.0 upgrade

# Check processing metrics
kubectl port-forward svc/safety-amp-production-service 8080:8080 -n safety-amp
curl http://localhost:8080/health/detailed
```

### Template Generation and Validation

```bash
# Generate templates for review
./deploy/helm-deploy.sh -e production template > production-manifests.yaml

# Lint the chart
./deploy/helm-deploy.sh -e production lint

# Dry-run upgrade
./deploy/helm-deploy.sh -e production -i v1.1.0 -d upgrade
```

## Monitoring and Observability

### Health Endpoints

| Endpoint | Description |
|----------|-------------|
| `/health` | Basic liveness check |
| `/ready` | Readiness check with external dependencies |
| `/health/detailed` | Comprehensive health status with metrics |
| `/metrics` | Prometheus metrics |

### Prometheus Metrics

```bash
# Port forward to metrics endpoint
kubectl port-forward svc/safety-amp-production-service 9090:9090 -n safety-amp

# Key metrics available:
# - safetyamp_sync_operations_total
# - safetyamp_records_processed_total  
# - safetyamp_sync_duration_seconds
# - safetyamp_database_connections_active
```

### Alerts

The chart includes pre-configured alerts for:
- **Critical**: Sync backlog > 1 hour
- **Warning**: Error rate > 10%
- **Info**: Rate limit hits (expected operational constraint)
- **Warning**: High memory/CPU usage
- **Critical**: Pod crash loops

## Troubleshooting

### Common Issues

#### 1. Secrets Not Found

```bash
# Check Key Vault secrets
az keyvault secret list --vault-name kv-safety-amp-prod

# Verify service account permissions
kubectl describe serviceaccount safety-amp-production-workload-identity-sa -n safety-amp
```

#### 2. Rate Limit Errors

Rate limits are expected operational constraints. Check:

```bash
# View rate limit status
curl http://localhost:8080/health/detailed | jq '.rate_limit_status'

# Check logs for 429 responses
kubectl logs deployment/safety-amp-production-agent -n safety-amp | grep "429"
```

#### 3. High Memory Usage

```bash
# Check resource usage
kubectl top pods -n safety-amp

# Adjust batch size if needed
helm upgrade safety-amp-production ./helm/safety-amp \
  --set config.batchSize=100 \
  --reuse-values
```

#### 4. Sync Failures

```bash
# Check CronJob status
kubectl get cronjobs -n safety-amp
kubectl get jobs -n safety-amp

# View detailed logs
kubectl logs job/safety-amp-production-sync-job-xxx -n safety-amp
```

### Debugging Commands

```bash
# Comprehensive status check
./deploy/helm-deploy.sh -e production status

# View all computed values
./deploy/helm-deploy.sh -e production values

# Check pod events
kubectl describe pod -l app.kubernetes.io/name=safety-amp -n safety-amp

# Test database connectivity
kubectl exec -it deployment/safety-amp-production-agent -n safety-amp -- python -c "
from services.viewpoint_api import ViewpointAPI
api = ViewpointAPI()
print('Database connection test...')
"
```

## Performance Optimization

### 5000 Records/Hour Configuration

The production configuration is optimized for 5000 records/hour:

```yaml
# Sync every 15 minutes = 4 times per hour
config.syncInterval: 900

# Process 125 records per sync = 500 records per hour per sync type
# With 10 sync types = 5000 records/hour total
config.batchSize: 125

# Adequate resources for processing load
resources:
  requests:
    memory: "768Mi"
    cpu: "300m"
  limits:
    memory: "1.5Gi" 
    cpu: "1500m"

# Scale to handle peak loads
autoscaling:
  minReplicas: 2
  maxReplicas: 5
```

### Scaling Considerations

- **Higher throughput**: Increase `replicaCount` and `batchSize`
- **Lower latency**: Decrease `syncInterval` (mind rate limits)
- **More resilience**: Enable `autoscaling` and set appropriate `affinity` rules

## Security

### Security Contexts

```yaml
# Pod security
podSecurityContext:
  runAsNonRoot: true
  runAsUser: 1000
  fsGroup: 1000

# Container security  
securityContext:
  allowPrivilegeEscalation: false
  capabilities:
    drop: [ALL]
  readOnlyRootFilesystem: false
  runAsNonRoot: true
```

### Azure Workload Identity

The chart uses Azure Workload Identity for secure access to Key Vault:

```yaml
serviceAccount:
  annotations:
    azure.workload.identity/client-id: "your-client-id"
    azure.workload.identity/tenant-id: "your-tenant-id"
```

## Contributing

1. Make changes to the chart
2. Update version in `Chart.yaml`
3. Test with different environments:
   ```bash
   ./deploy/helm-deploy.sh -e development lint
   ./deploy/helm-deploy.sh -e staging template
   ./deploy/helm-deploy.sh -e production -d install
   ```
4. Update documentation

## Values Reference

For a complete list of configurable values, see:
- [`values.yaml`](values.yaml) - Default values and documentation
- [`values-development.yaml`](values-development.yaml) - Development overrides
- [`values-staging.yaml`](values-staging.yaml) - Staging overrides  
- [`values-production.yaml`](values-production.yaml) - Production overrides

## Support

- **Chart Issues**: Check the troubleshooting section above
- **Application Issues**: Check logs and health endpoints
- **Performance Issues**: Review resource usage and scaling configuration
- **Security Issues**: Verify service account and Key Vault permissions

## License

This chart is part of the SafetyAmp Integration project.