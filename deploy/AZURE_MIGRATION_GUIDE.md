# Azure Kubernetes Service (AKS) Migration Guide

## 🎯 Overview

This guide provides step-by-step instructions for migrating the SafetyAmp Integration application to Azure Kubernetes Service (AKS) with Azure-native services for security, monitoring, and scalability.

## 📋 Prerequisites

### Required Tools
- [Azure CLI](https://docs.microsoft.com/en-us/cli/azure/install-azure-cli) (latest version)
- [kubectl](https://kubernetes.io/docs/tasks/tools/install-kubectl/)
- [Helm](https://helm.sh/docs/intro/install/) (v3.x)
- [Docker](https://docs.docker.com/get-docker/)
- [Git](https://git-scm.com/downloads)

### Azure Requirements
- Active Azure subscription with sufficient quota
- Contributor or Owner role on the subscription
- Domain name for SSL certificates (optional but recommended)

## 🏗️ Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                    Azure Kubernetes Service                 │
├─────────────────────────────────────────────────────────────┤
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐         │
│  │   NGINX     │  │ cert-manager│  │ Prometheus  │         │
│  │  Ingress    │  │             │  │   Stack     │         │
│  └─────────────┘  └─────────────┘  └─────────────┘         │
├─────────────────────────────────────────────────────────────┤
│  ┌─────────────────────────────────────────────────────────┐ │
│  │              SafetyAmp Integration Pods                │ │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐     │ │
│  │  │   Agent     │  │   Sync      │  │   Monitor   │     │ │
│  │  │  (2 replicas)│  │  CronJob   │  │   Service   │     │ │
│  │  └─────────────┘  └─────────────┘  └─────────────┘     │ │
│  └─────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    Azure Services                           │
├─────────────────────────────────────────────────────────────┤
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐         │
│  │ Azure Key   │  │ Azure       │  │ Azure       │         │
│  │   Vault     │  │ Container   │  │ Monitor     │         │
│  │             │  │ Registry    │  │             │         │
│  └─────────────┘  └─────────────┘  └─────────────┘         │
└─────────────────────────────────────────────────────────────┘
```

## 🚀 Step-by-Step Migration

### Step 1: Azure Authentication and Setup

```bash
# Login to Azure
az login

# Set your subscription (if you have multiple)
az account set --subscription "your-subscription-id"

# Verify your account
az account show
```

### Step 2: Run the Azure AKS Setup Script

```bash
# Make the script executable
chmod +x deploy/azure-aks-setup.sh

# Run the complete setup
./deploy/azure-aks-setup.sh setup
```

This script will:
- Create a resource group
- Create Azure Container Registry (ACR)
- Create Azure Key Vault
- Create AKS cluster with workload identity
- Configure managed identity and permissions
- Install cluster add-ons (NGINX, cert-manager, Prometheus)
- Build and push Docker image
- Deploy the application

### Step 3: Configure Secrets in Azure Key Vault

After the setup completes, add your secrets to Azure Key Vault:

```bash
# Get your Key Vault name from the setup output
KEY_VAULT_NAME="safetyamp-kv"

# Add SafetyAmp API key
az keyvault secret set \
  --vault-name $KEY_VAULT_NAME \
  --name "safetyamp-api-key" \
  --value "your-safetyamp-api-key"

# Add Samsara API key
az keyvault secret set \
  --vault-name $KEY_VAULT_NAME \
  --name "samsara-api-key" \
  --value "your-samsara-api-key"

# Add Viewpoint connection string
az keyvault secret set \
  --vault-name $KEY_VAULT_NAME \
  --name "viewpoint-connection-string" \
  --value "your-viewpoint-connection-string"

# Add Redis password
az keyvault secret set \
  --vault-name $KEY_VAULT_NAME \
  --name "redis-password" \
  --value "your-redis-password"
```

### Step 4: Configure DNS and SSL (Optional)

If you have a domain name:

1. **Get the LoadBalancer IP:**
   ```bash
   kubectl get service ingress-nginx -n ingress-nginx -o jsonpath='{.status.loadBalancer.ingress[0].ip}'
   ```

2. **Update your DNS records** to point your domain to the LoadBalancer IP

3. **Update the ingress configuration:**
   ```bash
   # Edit the ingress file
   kubectl edit ingress safety-amp-ingress -n safety-amp
   ```
   
   Replace `safetyamp.yourdomain.com` with your actual domain.

4. **Apply the updated ingress:**
   ```bash
   kubectl apply -f k8s/ingress/safety-amp-ingress.yaml
   ```

### Step 5: Verify Deployment

```bash
# Check cluster status
kubectl get nodes

# Check pods
kubectl get pods -n safety-amp

# Check services
kubectl get services -n safety-amp

# Check ingress
kubectl get ingress -n safety-amp

# Check certificates
kubectl get certificates -n safety-amp
```

### Step 6: Test the Application

```bash
# Port forward to test locally
kubectl port-forward service/safety-amp-service 8080:8080 -n safety-amp

# Test health endpoint
curl http://localhost:8080/health

# Test metrics endpoint
curl http://localhost:8080/metrics

# Test detailed health
curl http://localhost:8080/health/detailed
```

## 🔧 Configuration Details

### Azure-Specific Settings

The application now includes Azure-specific configuration in `config/azure_settings.py`:

- **Azure Key Vault Integration**: Automatic secret retrieval
- **Managed Identity**: Secure authentication without secrets
- **Workload Identity**: Pod-level identity for Azure services

### Environment Variables

Key environment variables for Azure deployment:

```bash
# Azure Configuration
AZURE_KEY_VAULT_URL=https://your-keyvault.vault.azure.net/
SQL_AUTH_MODE=managed_identity

# Application Configuration
SYNC_INTERVAL=900  # 15 minutes
BATCH_SIZE=125     # Optimal for 5000 records/hour
DB_POOL_SIZE=8     # Increased for production
DB_MAX_OVERFLOW=15 # More overflow connections
```

### Resource Requirements

The deployment is configured for production workloads:

- **Memory**: 768Mi requests, 1.5Gi limits
- **CPU**: 300m requests, 1500m limits
- **Replicas**: 2 for high availability
- **Database Pool**: 8 connections + 15 overflow

## 📊 Monitoring and Observability

### Prometheus Metrics

The application exposes Prometheus metrics at `/metrics`:

- `safetyamp_sync_operations_total`: Total sync operations by status
- `safetyamp_sync_duration_seconds`: Sync operation duration
- `safetyamp_records_processed_total`: Total records processed
- `safetyamp_current_sync_operations`: Current ongoing sync operations
- `safetyamp_database_connections_active`: Active database connections

### Azure Monitor Integration

The AKS cluster includes Azure Monitor for containers:

```bash
# View logs in Azure Portal
az aks browse --resource-group safetyamp-rg --name safetyamp-aks

# Or use kubectl
kubectl logs -f deployment/safety-amp-agent -n safety-amp
```

### Grafana Dashboard

Access Grafana for monitoring:

```bash
# Port forward Grafana
kubectl port-forward service/prometheus-grafana 3000:80 -n monitoring

# Default credentials: admin / prom-operator
```

## 🔒 Security Features

### Workload Identity

The application uses Azure Workload Identity for secure authentication:

- No secrets stored in Kubernetes
- Automatic token rotation
- Fine-grained permissions

### Network Policies

Network policies restrict pod-to-pod communication:

```bash
# Apply network policies
kubectl apply -f k8s/safety-amp/networkpolicy.yaml
```

### RBAC Configuration

Role-based access control is configured:

```bash
# Apply RBAC
kubectl apply -f k8s/rbac/service-accounts.yaml
```

## 🚨 Troubleshooting

### Common Issues

1. **Image Pull Errors**
   ```bash
   # Check ACR authentication
   az acr login --name safetyampacr
   
   # Verify image exists
   az acr repository list --name safetyampacr
   ```

2. **Key Vault Access Issues**
   ```bash
   # Check managed identity permissions
   az keyvault show --name safetyamp-kv --query properties.accessPolicies
   ```

3. **Pod Startup Issues**
   ```bash
   # Check pod events
   kubectl describe pod <pod-name> -n safety-amp
   
   # Check logs
   kubectl logs <pod-name> -n safety-amp
   ```

4. **Database Connection Issues**
   ```bash
   # Test database connectivity
   kubectl exec -it <pod-name> -n safety-amp -- python -c "
   from config.settings import VIEWPOINT_CONN_STRING
   print('Connection string configured:', bool(VIEWPOINT_CONN_STRING))
   "
   ```

### Health Check Endpoints

Use these endpoints to diagnose issues:

- `/health`: Basic liveness probe
- `/ready`: Readiness probe with dependency checks
- `/health/detailed`: Comprehensive health status
- `/metrics`: Prometheus metrics

## 🔄 Scaling and Updates

### Horizontal Pod Autoscaler

The deployment includes HPA for automatic scaling:

```bash
# Check HPA status
kubectl get hpa -n safety-amp

# Scale manually if needed
kubectl scale deployment safety-amp-agent --replicas=3 -n safety-amp
```

### Rolling Updates

Update the application:

```bash
# Build and push new image
./deploy/azure-aks-setup.sh build

# Update deployment
kubectl set image deployment/safety-amp-agent \
  safety-amp-agent=safetyampacr.azurecr.io/safety-amp-agent:latest \
  -n safety-amp
```

### Configuration Updates

Update configuration:

```bash
# Update ConfigMap
kubectl apply -f k8s/safety-amp/safety-amp-deployment.yaml

# Restart deployment to pick up changes
kubectl rollout restart deployment/safety-amp-agent -n safety-amp
```

## 💰 Cost Optimization

### Resource Optimization

- **Node Pool**: Use Spot instances for non-critical workloads
- **Autoscaling**: Enable cluster autoscaler
- **Resource Limits**: Set appropriate CPU/memory limits

### Monitoring Costs

```bash
# Check resource usage
kubectl top pods -n safety-amp
kubectl top nodes

# Monitor Azure costs in the portal
az consumption usage list --query "[?contains(instanceName, 'safetyamp')]"
```

## 🧹 Cleanup

To remove all resources:

```bash
# Delete the resource group (this removes everything)
az group delete --name safetyamp-rg --yes --no-wait

# Or use the cleanup script
./deploy/azure-aks-setup.sh cleanup
```

## 📞 Support

For issues or questions:

1. Check the troubleshooting section above
2. Review application logs: `kubectl logs -f deployment/safety-amp-agent -n safety-amp`
3. Check Azure Monitor for detailed metrics
4. Review the application's health endpoints

## 🎉 Migration Complete!

Your SafetyAmp Integration is now running on Azure Kubernetes Service with:

✅ **Production-ready infrastructure**  
✅ **Azure-native security** (Key Vault, Managed Identity)  
✅ **Automatic scaling** (HPA, Cluster Autoscaler)  
✅ **Comprehensive monitoring** (Prometheus, Azure Monitor)  
✅ **High availability** (Multi-replica deployment)  
✅ **SSL/TLS termination** (cert-manager)  
✅ **Load balancing** (NGINX Ingress)  

The application is configured to process **5000 records/hour** with optimal resource utilization and reliability. 