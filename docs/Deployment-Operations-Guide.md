# Deployment and Operations Guide (AKS)

This single guide consolidates the prior README, DEPLOYMENT_SUMMARY, DEPLOYMENT_STATUS, and DEPLOYMENT_GUIDE into one source of truth for deploying and operating the SafetyAmp Integration and associated services on AKS.

## Scope
- Environments: Dev, Staging, Production
- Cluster: AKS (private), Azure CNI Overlay with Cilium
- Apps: n8n, SafetyAmp Integration, Samsara Integration, Ingress, cert-manager

## Prerequisites
- Azure CLI authenticated to the subscription
- kubectl configured for the target AKS cluster
- Access to ACR for container images
- Ability to update DNS and certificates

## Architecture Summary
- Namespaces: `n8n`, `safety-amp`, `samsara`, `ingress-nginx`, `cert-manager`
- External access via NGINX Ingress Controller
- SSL with cert-manager (Let’s Encrypt)
- Observability: Managed Prometheus + Managed Grafana + Azure Monitor (optional sidecar for custom JSON logs)

## Quick Start
1) Get cluster credentials
```bash
az aks get-credentials --resource-group rg_prod --name dev-aks
```

2) Deploy core components
```bash
kubectl apply -f k8s/namespaces/namespaces.yaml
kubectl apply -f k8s/cert-manager/cert-manager.yaml
kubectl apply -f k8s/ingress/nginx-ingress-controller.yaml
kubectl apply -f k8s/n8n/n8n-deployment.yaml
kubectl apply -f k8s/safety-amp/safety-amp-deployment.yaml
kubectl apply -f k8s/samsara/samsara-deployment.yaml
```

3) Check status
```bash
kubectl get pods --all-namespaces
kubectl get ingress --all-namespaces
```

## Configuration and Security
- Update container images to your registry
- Provide secrets via Kubernetes Secrets (never commit secrets)
- Azure Workload Identity annotations on service accounts

Example annotations:
```yaml
annotations:
  azure.workload.identity/client-id: "<client-id>"
  azure.workload.identity/tenant-id: "<tenant-id>"
```

## Deployment Phases (Production)

Phase 1: Infrastructure
```bash
# Build and push image
docker build -t <acr>/safetyamp-integration:<tag> .
docker push <acr>/safetyamp-integration:<tag>

# Apply infra
kubectl apply -f k8s/namespaces/namespaces.yaml
kubectl apply -f k8s/rbac/service-accounts.yaml
```

Phase 2: Secrets & Config
- Verify Key Vault or secret source
- Ensure env vars for sync intervals, batch size, DB pool are set

Phase 3: Test & Validate
```bash
# Tail logs and validate health
kubectl logs -f deployment/safety-amp-agent -n safety-amp
kubectl port-forward -n safety-amp svc/safety-amp-service 8080:8080
curl http://localhost:8080/health
```

Phase 4: Rollout
```bash
# Update the image and wait for rollout
kubectl set image deployment/safety-amp-agent \
  safety-amp-agent=<acr>/safetyamp-integration:<tag> -n safety-amp
kubectl rollout status deployment/safety-amp-agent -n safety-amp
```

## Recommended Production Settings
Environment variables:
```bash
SYNC_INTERVAL=900        # 15 minutes
BATCH_SIZE=125           # per-sync target
DB_POOL_SIZE=8
DB_MAX_OVERFLOW=15
CIRCUIT_BREAKER_FAILURE_THRESHOLD=5
```

Kubernetes deployment knobs:
- Requests/Limits: memory 768Mi/1.5Gi, CPU 300m/1500m (tune with baselines)
- Replicas: 2+ for HA

## Monitoring and Validation

Metrics (Prometheus):
- safetyamp_sync_operations_total, safetyamp_sync_duration_seconds
- safetyamp_records_processed_total
- Optional/Recommended: cache gauges, change/error counters, sync state gauges

Key validation commands:
```bash
kubectl logs -f deployment/safety-amp-agent -n safety-amp
kubectl top pods -n safety-amp
kubectl port-forward -n safety-amp svc/safety-amp-service 9090:9090  # /metrics
```

Success targets:
- Throughput: ~5000 records/hour
- Error rate: < 5% (excluding rate limit 429s)
- Resource usage: CPU < 70%, Memory < 80%

## Troubleshooting

Common issues and checks:
- Pods not starting: describe pod and inspect events
```bash
kubectl describe pod <pod> -n <ns>
kubectl logs <pod> -n <ns>
```
- Ingress issues: describe ingress and check ingress controller logs
```bash
kubectl describe ingress <name> -n <ns>
kubectl logs -n ingress-nginx deployment/nginx-ingress-controller
```
- Certificates: inspect certs and issuers
```bash
kubectl describe certificate <name> -n <ns>
kubectl describe clusterissuer letsencrypt-prod
```

Data validation and quick fixes:
- Ensure required fields exist (first_name, last_name, email)
- Resolve duplicate emails or phones at source
- Add missing site mappings

## Rollback

Automated (if backup exists):
```bash
kubectl rollout undo deployment/safety-amp-agent -n safety-amp
```

Manual image pin:
```bash
kubectl set image deployment/safety-amp-agent \
  safety-amp-agent=<acr>/safetyamp-integration:<previous-tag> -n safety-amp
```

## Operations

Secrets update example:
```bash
kubectl create secret generic n8n-secrets \
  --from-literal=N8N_ENCRYPTION_KEY="<key>" \
  --from-literal=DB_POSTGRESDB_PASSWORD="<pwd>" \
  -n n8n --dry-run=client -o yaml | kubectl apply -f -
```

Scaling:
```bash
kubectl scale deployment safety-amp-agent --replicas=2 -n safety-amp
```

Daily checks:
- Deployment available and healthy
- Error rates and resource usage within targets
- Recent syncs completed; last sync time reasonable

## Checklists

Pre-deploy
- Security fixes and secrets in place
- Images built and pushed
- Config/Env validated

Post-deploy
- Rollout healthy
- Health endpoints pass
- Metrics and logs flowing
- Alerts configured

## Links
- Kubernetes docs: https://kubernetes.io/docs/
- AKS docs: https://learn.microsoft.com/azure/aks/
- cert-manager: https://cert-manager.io/docs/
- n8n docs: https://docs.n8n.io/