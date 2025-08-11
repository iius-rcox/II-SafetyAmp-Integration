# Getting Started

This project deploys n8n, the SafetyAmp Integration, and supporting services to AKS.

## Prerequisites
- Azure CLI and kubectl installed
- Access to target AKS cluster and ACR

## One-time setup
```bash
az aks get-credentials --resource-group rg_prod --name dev-aks
```

## Deploy core components
```bash
kubectl apply -f k8s/namespaces/namespaces.yaml
kubectl apply -f k8s/cert-manager/cert-manager.yaml
kubectl apply -f k8s/ingress/nginx-ingress-controller.yaml
kubectl apply -f k8s/n8n/n8n-deployment.yaml
kubectl apply -f k8s/safety-amp/safety-amp-deployment.yaml
kubectl apply -f k8s/samsara/samsara-deployment.yaml
```

## Verify
```bash
kubectl get pods --all-namespaces
kubectl get ingress --all-namespaces
```

## Next
- Read the full Deployment and Operations Guide: docs/Deployment-Operations-Guide.md
- See the Runbook for day-2 operations: docs/Operations-Runbook.md
- Observability setup overview: docs/Observability.md