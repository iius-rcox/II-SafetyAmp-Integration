# AKS Deployment for dev-aks Cluster

This repository contains Kubernetes configuration files and deployment scripts for your Azure Kubernetes Service (AKS) cluster `dev-aks`. The setup includes n8n automation platform, SafetyAmp integration, Samsara integration, and supporting infrastructure.

## 🏗 Architecture Overview

### **AKS Cluster: dev-aks**
- **Location:** South Central US
 - **Resource Group:** rg_prod
- **Kubernetes Version:** v1.32.5
- **Network:** Azure CNI Overlay with Cilium
- **Private Cluster:** ✅ Enabled

### **Applications Deployed**
- **n8n:** Low-code/no-code automation platform (accessible via HTTPS)
- **SafetyAmp Agent:** Python-based safety integration service
- **Samsara Integration:** Asset synchronization service with scheduled jobs
- **NGINX Ingress Controller:** Load balancer and SSL termination
- **cert-manager:** Automated SSL certificate management

## 📁 Project Structure

```
├── k8s/
│   ├── namespaces/
│   │   └── namespaces.yaml              # Namespace definitions
│   ├── cert-manager/
│   │   └── cert-manager.yaml            # SSL certificate management
│   ├── ingress/
│   │   └── nginx-ingress-controller.yaml # Ingress controller
│   ├── n8n/
│   │   └── n8n-deployment.yaml          # n8n automation platform
│   ├── safety-amp/
│   │   └── safety-amp-deployment.yaml   # SafetyAmp integration
│   ├── samsara/
│   │   └── samsara-deployment.yaml      # Samsara integration
│   ├── rbac/
│   │   └── service-accounts.yaml        # RBAC and service accounts
│   └── monitoring/
│       └── monitoring.yaml              # Monitoring and logging
├── deploy/
│   └── deploy.sh                        # Deployment script
└── README.md                            # This file
```

## 🚀 Quick Start

### Prerequisites

1. **Azure CLI** installed and authenticated
2. **kubectl** installed and configured
3. **Access to dev-aks cluster**

### Get Cluster Credentials

```bash
az aks get-credentials --resource-group rg_prod --name dev-aks
```

### Deploy Everything

```bash
# Make the deployment script executable
chmod +x deploy/deploy.sh

# Deploy all applications
./deploy/deploy.sh deploy
```

### Check Deployment Status

```bash
./deploy/deploy.sh status
```

## 🔧 Detailed Configuration

### 1. Namespaces

The deployment creates separate namespaces for organization:
- `n8n` - n8n automation platform
- `safety-amp` - SafetyAmp integration
- `samsara` - Samsara integration
- `ingress-nginx` - NGINX Ingress Controller
- `cert-manager` - Certificate management

### 2. n8n Configuration

**Features:**
- Persistent storage (20GB)
- PostgreSQL database connection
- HTTPS access via `n8n.dev.ii-us.com`
- Auto-SSL certificates
- Health checks and monitoring

**Important:** Update the following secrets in `k8s/n8n/n8n-deployment.yaml`:
- Database connection details
- Encryption keys
- JWT secrets

### 3. SafetyAmp Integration

**Features:**
- Python-based agent
- Health and metrics endpoints
- Configurable sync intervals
- Azure AD authentication

**Container Image:** Update `image:` field with your SafetyAmp agent image

### 4. Samsara Integration

**Features:**
- Asset synchronization
- CronJob for scheduled syncs (every 6 hours)
- Rate limiting and retry logic
- Multiple sync types (vehicles, drivers, locations, maintenance)

**Container Image:** Update `image:` field with your Samsara integration image

### 5. Monitoring & Logging

**Prometheus Configuration:**
- Metrics collection from all applications
- Custom alert rules
- Integration with Azure Monitor

**Fluent Bit Logging:**
- Log aggregation to Azure Monitor
- Kubernetes metadata enrichment

## 🔐 Security Configuration

### Service Accounts & RBAC

Each application has dedicated service accounts with minimal required permissions:
- n8n: Can manage pods and access secrets/configmaps
- SafetyAmp: Read-only access to cluster resources
- Samsara: Can create jobs and access secrets

### Azure Workload Identity

Service accounts are configured for Azure Workload Identity integration. Update the annotations with your actual client IDs:

```yaml
annotations:
  azure.workload.identity/client-id: "your-client-id"
  azure.workload.identity/tenant-id: "your-tenant-id"
```

## 🌐 Network & DNS Configuration

### External Access

1. **Get LoadBalancer IP:**
   ```bash
   kubectl get service ingress-nginx -n ingress-nginx
   ```

2. **Update DNS Records:**
   - Create A record: `n8n.dev.ii-us.com` → LoadBalancer IP

### SSL Certificates

cert-manager automatically provisions Let's Encrypt certificates for:
- `n8n.dev.ii-us.com`

## 📊 Monitoring & Alerting

### Built-in Alerts

- **Application Down:** Alerts when services are unavailable
- **High CPU/Memory Usage:** Resource utilization alerts
- **Pod Crash Looping:** Application stability alerts
- **Deployment Issues:** Kubernetes deployment problems

### Accessing Metrics

```bash
# Port forward to access metrics
kubectl port-forward -n n8n svc/n8n-service 5678:5678
kubectl port-forward -n safety-amp svc/safety-amp-service 9090:9090
kubectl port-forward -n samsara svc/samsara-service 9090:9090
```

## 🔄 GitOps Workflow

### Recommended Workflow

1. **Development:**
   - Make changes in feature branches
   - Test locally or in dev environment

2. **Staging:**
   - Create pull request to `main` branch
   - Review and approve changes

3. **Production:**
   - Merge to `main` triggers deployment
   - Monitor deployment status

### Manual Deployment Commands

```bash
# Deploy specific components
kubectl apply -f k8s/namespaces/namespaces.yaml
kubectl apply -f k8s/cert-manager/cert-manager.yaml
kubectl apply -f k8s/ingress/nginx-ingress-controller.yaml
kubectl apply -f k8s/n8n/n8n-deployment.yaml
kubectl apply -f k8s/safety-amp/safety-amp-deployment.yaml
kubectl apply -f k8s/samsara/samsara-deployment.yaml
```

## 🛠 Maintenance & Operations

### Updating Secrets

```bash
# Update n8n secrets
kubectl create secret generic n8n-secrets \
  --from-literal=N8N_ENCRYPTION_KEY="your-key" \
  --from-literal=DB_POSTGRESDB_PASSWORD="your-password" \
  -n n8n --dry-run=client -o yaml | kubectl apply -f -

# Restart deployment to pick up new secrets
kubectl rollout restart deployment/n8n -n n8n
```

### Scaling Applications

```bash
# Scale n8n
kubectl scale deployment n8n --replicas=2 -n n8n

# Scale SafetyAmp
kubectl scale deployment safety-amp-agent --replicas=2 -n safety-amp
```

### Backup & Recovery

```bash
# Backup persistent volumes
kubectl get pvc -n n8n
# Use Azure Backup or Velero for PVC backups

# Export configurations
kubectl get all -n n8n -o yaml > n8n-backup.yaml
```

## 🔍 Troubleshooting

### Common Issues

1. **Pods not starting:**
   ```bash
   kubectl describe pod <pod-name> -n <namespace>
   kubectl logs <pod-name> -n <namespace>
   ```

2. **Ingress not working:**
   ```bash
   kubectl describe ingress n8n-ingress -n n8n
   kubectl logs -n ingress-nginx deployment/nginx-ingress-controller
   ```

3. **Certificate issues:**
   ```bash
   kubectl describe certificate n8n-tls -n n8n
   kubectl describe clusterissuer letsencrypt-prod
   ```

### Debugging Commands

```bash
# Check cluster status
kubectl cluster-info
kubectl get nodes

# Check application status
kubectl get pods --all-namespaces
kubectl get services --all-namespaces
kubectl get ingress --all-namespaces

# Check resource usage
kubectl top nodes
kubectl top pods --all-namespaces
```

## 📝 Required Actions

### Before Deployment

1. **Update Secrets:** Replace placeholder values in all secret configurations
2. **Container Images:** Update image references to your actual container registry
3. **DNS Configuration:** Ensure you can update DNS records for your domain
4. **Azure Monitor:** Get Log Analytics workspace credentials

### After Deployment

1. **DNS Records:** Point `n8n.dev.ii-us.com` to LoadBalancer IP
2. **SSL Verification:** Verify certificates are issued correctly
3. **Application Testing:** Test each application functionality
4. **Monitoring Setup:** Verify metrics and logs are flowing

## 📞 Support

### Useful Commands

```bash
# Get deployment status
./deploy/deploy.sh status

# Clean up all deployments
./deploy/deploy.sh cleanup

# Get help
./deploy/deploy.sh help
```

### Links

- [n8n Documentation](https://docs.n8n.io/)
- [Azure AKS Documentation](https://docs.microsoft.com/en-us/azure/aks/)
- [Kubernetes Documentation](https://kubernetes.io/docs/)
- [cert-manager Documentation](https://cert-manager.io/docs/)

---

**⚠️ Security Notice:** Never commit secrets or sensitive configuration to version control. Use Azure Key Vault or similar solutions for production secrets management.