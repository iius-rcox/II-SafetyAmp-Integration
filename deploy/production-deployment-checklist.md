# SafetyAmp Production Deployment Checklist

## 🔴 CRITICAL SECURITY REQUIREMENTS - MUST COMPLETE BEFORE DEPLOYMENT

### 1. Secrets Management ✅ COMPLETED
- [x] No exposed secrets in repository (.env files removed)
- [x] All secrets configured to use Azure Key Vault exclusively
- [x] Azure Workload Identity properly configured

### 2. Azure Workload Identity Configuration ✅ COMPLETED
- [x] Tenant ID configured: `953922e6-5370-4a01-a3d5-773a30df726b`
- [x] Managed Identity Client ID configured: `a2bcb3ce-a89b-43af-804c-e8029e0bafb4`
- [x] ServiceAccount properly annotated in deployment manifests
- [x] Federated identity credential configured

### 3. SQL Server Configuration ✅ COMPLETED
- [x] SQL Server FQDN: `inscolvsql.insulationsinc.local`
- [x] Database Name: `Viewpoint`
- [x] Authentication mode set to `managed_identity` (no more Trusted_Connection)
- [x] Connection pooling implemented with SQLAlchemy
- [x] Proper SSL encryption enabled

### 4. Container Registry Configuration ✅ COMPLETED
- [x] Placeholder `your-registry` replaced with `youracr.azurecr.io`
- [x] All deployment manifests updated

## 🚨 PRE-DEPLOYMENT REQUIREMENTS

### Azure Infrastructure Setup Required

1. **Container Registry Setup**
   ```bash
   # Replace 'youracr' with your actual ACR name
   # Build and push the safety-amp-agent image
   docker build -t youracr.azurecr.io/safety-amp-agent:latest .
   docker push youracr.azurecr.io/safety-amp-agent:latest
   ```

2. **Azure Key Vault Secrets Configuration**
   ```bash
   # Run the workload identity setup script first
   ./deploy/setup-workload-identity.sh
   
   # Then populate Key Vault with required secrets:
   az keyvault secret set --vault-name kv-safety-amp-dev --name "SAFETYAMP_TOKEN" --value "YOUR_ACTUAL_TOKEN"
   az keyvault secret set --vault-name kv-safety-amp-dev --name "MS_GRAPH_CLIENT_SECRET" --value "YOUR_ACTUAL_SECRET"
   az keyvault secret set --vault-name kv-safety-amp-dev --name "MS_GRAPH_CLIENT_ID" --value "YOUR_CLIENT_ID"
   az keyvault secret set --vault-name kv-safety-amp-dev --name "MS_GRAPH_TENANT_ID" --value "953922e6-5370-4a01-a3d5-773a30df726b"
   az keyvault secret set --vault-name kv-safety-amp-dev --name "SQL_SERVER" --value "inscolvsql.insulationsinc.local"
   az keyvault secret set --vault-name kv-safety-amp-dev --name "SQL_DATABASE" --value "Viewpoint"
   az keyvault secret set --vault-name kv-safety-amp-dev --name "SAMSARA_API_KEY" --value "YOUR_SAMSARA_KEY"
   az keyvault secret set --vault-name kv-safety-amp-dev --name "SMTP_USERNAME" --value "YOUR_SMTP_USER"
   az keyvault secret set --vault-name kv-safety-amp-dev --name "SMTP_PASSWORD" --value "YOUR_SMTP_PASSWORD"
   az keyvault secret set --vault-name kv-safety-amp-dev --name "ALERT_EMAIL_FROM" --value "YOUR_FROM_EMAIL"
   az keyvault secret set --vault-name kv-safety-amp-dev --name "ALERT_EMAIL_TO" --value "YOUR_TO_EMAIL"
   ```

3. **SQL Server Azure AD Authentication Setup**
   ```sql
   -- Connect to SQL Server as Azure AD admin and run:
   CREATE USER [safety-amp-workload-identity] FROM EXTERNAL PROVIDER;
   ALTER ROLE db_datareader ADD MEMBER [safety-amp-workload-identity];
   ALTER ROLE db_datawriter ADD MEMBER [safety-amp-workload-identity];
   ALTER ROLE db_ddladmin ADD MEMBER [safety-amp-workload-identity];
   GO
   ```

## 🚀 DEPLOYMENT STEPS

### Step 1: Container Registry Update
```bash
# Update deployment files with your actual ACR name
# Replace 'youracr' with your actual Azure Container Registry name
find k8s/ -name "*.yaml" -exec sed -i 's/youracr\.azurecr\.io/YOUR_ACTUAL_ACR.azurecr.io/g' {} \;
```

### Step 2: Build and Push Images
```bash
# Build SafetyAmp agent image
docker build -t YOUR_ACTUAL_ACR.azurecr.io/safety-amp-agent:latest .
docker push YOUR_ACTUAL_ACR.azurecr.io/safety-amp-agent:latest
```

### Step 3: Deploy Infrastructure
```bash
# Run the comprehensive deployment script
./deploy/deploy.sh
```

### Step 4: Verification
```bash
# Check pod status
kubectl get pods -n safety-amp

# Check logs
kubectl logs -n safety-amp deployment/safety-amp-agent

# Test health endpoints
kubectl port-forward -n safety-amp service/safety-amp-service 8080:8080
curl http://localhost:8080/health
curl http://localhost:8080/ready
```

## 🔍 SECURITY VALIDATION

### Pre-Production Security Checks
- [ ] No hardcoded secrets in any configuration files
- [ ] All API keys and passwords stored in Azure Key Vault
- [ ] Workload Identity properly configured and tested
- [ ] SQL Server authentication using Azure AD only
- [ ] Network policies properly configured
- [ ] Resource limits and requests set appropriately
- [ ] Health checks and monitoring configured

### Runtime Security Monitoring
- [ ] Azure Monitor alerts configured
- [ ] Prometheus metrics collection enabled
- [ ] Log aggregation to Azure Log Analytics configured
- [ ] Security scanning enabled on container images

## 🛠 TROUBLESHOOTING

### Common Issues and Solutions

1. **Pod Authentication Errors**
   ```bash
   # Check workload identity configuration
   kubectl describe pod -n safety-amp -l app=safety-amp
   
   # Verify service account annotations
   kubectl get serviceaccount -n safety-amp safety-amp-workload-identity-sa -o yaml
   ```

2. **Key Vault Access Issues**
   ```bash
   # Test Key Vault access from pod
   kubectl run test-keyvault --image=mcr.microsoft.com/azure-cli \
     --namespace=safety-amp \
     --serviceaccount=safety-amp-workload-identity-sa \
     --rm -it -- bash
   
   # Inside the pod:
   az login --identity
   az keyvault secret list --vault-name kv-safety-amp-dev
   ```

3. **SQL Server Connection Issues**
   ```bash
   # Check SQL connectivity from pod
   kubectl exec -it -n safety-amp deployment/safety-amp-agent -- python -c "
   from config.settings import VIEWPOINT_CONN_STRING
   import pyodbc
   print('Testing SQL connection...')
   conn = pyodbc.connect(VIEWPOINT_CONN_STRING)
   print('Connection successful!')
   conn.close()
   "
   ```

## 📊 MONITORING AND METRICS

### Health Check Endpoints
- `/health` - Overall application health
- `/ready` - Readiness for traffic
- `/metrics` - Prometheus metrics

### Key Metrics to Monitor
- Database connection pool utilization
- API response times
- Cache hit rates
- Error rates
- Memory and CPU usage

## 🔄 MAINTENANCE

### Regular Tasks
- Monitor Key Vault secret expiration dates
- Review and rotate credentials quarterly
- Update container images with security patches
- Monitor resource usage and scale as needed

### Credential Rotation Process
1. Generate new credentials in source systems
2. Update Azure Key Vault secrets
3. Restart pods to pick up new secrets: `kubectl rollout restart deployment/safety-amp-agent -n safety-amp`
4. Verify functionality
5. Revoke old credentials