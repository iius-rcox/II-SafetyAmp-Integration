# 🚀 Quick Start: Azure AKS Migration

## Prerequisites Check

Before starting, ensure you have:

- [Azure CLI](https://docs.microsoft.com/en-us/cli/azure/install-azure-cli) installed
- [kubectl](https://kubernetes.io/docs/tasks/tools/install-kubectl/) installed
- [Docker](https://docs.docker.com/get-docker/) installed
- Active Azure subscription

## 🎯 Quick Migration Steps

### 1. Login to Azure
```bash
az login
az account show  # Verify your subscription
```

### 2. Run the Migration Script
```bash
# On Windows (PowerShell) - Use the PowerShell script
.\deploy\azure-aks-setup.ps1 setup

# On Linux/Mac - Use the bash script
chmod +x deploy/azure-aks-setup.sh
./deploy/azure-aks-setup.sh setup
```

### 3. Add Your Secrets
```bash
# Replace with your actual values
az keyvault secret set --vault-name safetyamp-kv --name "safetyamp-api-key" --value "your-api-key"
az keyvault secret set --vault-name safetyamp-kv --name "samsara-api-key" --value "your-api-key"
az keyvault secret set --vault-name safetyamp-kv --name "viewpoint-connection-string" --value "your-connection-string"
```

### 4. Test the Deployment
```bash
# Check if everything is running
kubectl get pods -n safety-amp

# Test the application
kubectl port-forward service/safety-amp-service 8080:8080 -n safety-amp
# Then visit: http://localhost:8080/health
```

## 📋 What Gets Created

The script automatically creates:

- **Resource Group**: `safetyamp-rg`
- **AKS Cluster**: `safetyamp-aks` (3 nodes, Standard_D4s_v3)
- **Azure Container Registry**: `safetyampacr`
- **Azure Key Vault**: `safetyamp-kv`
- **Managed Identity**: For secure authentication
- **Workload Identity**: For pod-level Azure access

## 🔧 Key Features

✅ **Production Ready**: 2 replicas, auto-scaling, health checks  
✅ **Azure Native**: Key Vault integration, managed identity  
✅ **Monitoring**: Prometheus metrics, Azure Monitor  
✅ **Security**: Workload identity, network policies  
✅ **Performance**: Optimized for 5000 records/hour  

## 🚨 Troubleshooting

### Common Issues

1. **Permission Errors**
   ```bash
   # Ensure you have Contributor role
   az role assignment list --assignee $(az account show --query user.name -o tsv)
   ```

2. **Image Pull Errors**
   ```bash
   # Login to ACR
   az acr login --name safetyampacr
   ```

3. **Pod Startup Issues**
   ```bash
   # Check logs
   kubectl logs -f deployment/safety-amp-agent -n safety-amp
   ```

### Health Checks

Test these endpoints:
- `/health` - Basic health check
- `/ready` - Readiness with dependencies
- `/metrics` - Prometheus metrics
- `/health/detailed` - Comprehensive status

## 📊 Monitoring

### Access Grafana
```bash
kubectl port-forward service/prometheus-grafana 3000:80 -n monitoring
# Visit: http://localhost:3000 (admin/prom-operator)
```

### View Logs
```bash
# Application logs
kubectl logs -f deployment/safety-amp-agent -n safety-amp

# Azure Monitor (in Azure Portal)
az aks browse --resource-group safetyamp-rg --name safetyamp-aks
```

## 🔄 Updates

### Update Application
```bash
# Build and push new image
./deploy/azure-aks-setup.sh build

# Update deployment
kubectl set image deployment/safety-amp-agent safety-amp-agent=safetyampacr.azurecr.io/safety-amp-agent:latest -n safety-amp
```

### Scale Application
```bash
# Scale manually
kubectl scale deployment safety-amp-agent --replicas=3 -n safety-amp

# Check HPA
kubectl get hpa -n safety-amp
```

## 🧹 Cleanup

To remove everything:
```bash
az group delete --name safetyamp-rg --yes --no-wait
```

## 📞 Need Help?

1. Check the full migration guide: `deploy/AZURE_MIGRATION_GUIDE.md`
2. Review application logs: `kubectl logs -f deployment/safety-amp-agent -n safety-amp`
3. Check health endpoints for detailed status

## 🎉 Success!

Your SafetyAmp Integration is now running on Azure Kubernetes Service with enterprise-grade security, monitoring, and scalability! 