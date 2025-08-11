# AKS Deployment for dev-aks Cluster

This repository contains Kubernetes configuration and deployment assets for n8n, the SafetyAmp Integration, and the Samsara Integration on AKS.

## Start Here
- docs/Getting-Started.md — minimal steps to deploy core components
- docs/Deployment-Operations-Guide.md — single comprehensive guide (deployment + operations)
- docs/Operations-Runbook.md — day-2 operations, debugging, and procedures
- docs/Observability.md — metrics, logs, dashboards, and alerts overview

## Project Structure
```
k8s/               # Kubernetes manifests
services/          # Application services
utils/             # Utilities
deploy/            # Scripts and tooling (kept lean)
docs/              # Centralized documentation (new)
```

## Notes
- Never commit secrets. Use Kubernetes Secrets, Azure Key Vault, or similar.
- Update image references to your container registry before deploying.