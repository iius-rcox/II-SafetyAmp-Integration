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

## Local Development

1. Use Python 3.9+.
2. Install dependencies: `pip install -r requirements.txt`.
3. Copy `.env.example` to `.env` and customize for your environment (do not commit real secrets).
4. Optionally configure Azure Key Vault via `AZURE_KEY_VAULT_NAME` or `AZURE_KEY_VAULT_URL`.