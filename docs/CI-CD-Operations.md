# CI/CD Operations Guide

This document describes the CI/CD pipeline for the SafetyAmp Integration Service, including GitHub Actions workflows and ArgoCD GitOps deployment.

## Architecture Overview

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│  GitHub Repo    │────▶│  GitHub Actions │────▶│  Azure ACR      │
│  (Source)       │     │  (CI/CD)        │     │  (Registry)     │
└─────────────────┘     └─────────────────┘     └─────────────────┘
        │                                                │
        │                                                │
        ▼                                                ▼
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│  k8s/overlays/  │◀────│  ArgoCD         │◀────│  AKS Cluster    │
│  (Manifests)    │     │  (GitOps)       │     │  (Runtime)      │
└─────────────────┘     └─────────────────┘     └─────────────────┘
```

## GitHub Actions Workflows

### 1. CI Workflow (`ci.yaml`)

**Trigger:** Pull requests to `main`, pushes to `main`

**Jobs:**
- **lint**: Code formatting (black) and syntax checking (flake8)
- **test**: Unit tests with pytest and coverage reporting
- **build**: Docker image build validation (no push)
- **security-scan**: Trivy vulnerability scanning

### 2. Build and Deploy (`build-deploy.yaml`)

**Trigger:** Pushes to `main` branch

**Jobs:**
- **build-and-push**:
  - Builds Docker image
  - Pushes to Azure Container Registry with tags:
    - `sha-<commit>` (e.g., `sha-abc1234`)
    - `dev` (rolling tag)
  - Runs Trivy security scan
  - Uploads SARIF results to GitHub Security tab

- **update-manifests**:
  - Updates `k8s/overlays/dev/kustomization.yaml` with new image tag
  - Commits and pushes manifest changes
  - ArgoCD detects change and syncs automatically

### 3. Release Workflow (`release.yaml`)

**Trigger:** Manual (workflow_dispatch)

**Inputs:**
- `source_tag`: Image tag to promote (e.g., `sha-abc1234`)
- `target_environment`: `staging` or `prod`
- `release_version`: Required for prod (e.g., `v1.2.3`)

**Jobs:**
- **validate**: Input validation
- **promote**:
  - Re-tags image in ACR
  - Updates target environment's kustomization.yaml
  - Creates Git tag for prod releases
- **notify**: Success/failure notification

## ArgoCD Configuration

### Project (`k8s/argocd/project.yaml`)

Defines the SafetyAmp Integration project with:
- Allowed source repositories
- Destination namespaces (safety-amp-dev, safety-amp-staging, safety-amp-prod)
- Resource whitelists
- Role-based access control

### Applications

| Environment | File | Sync Policy | Namespace |
|-------------|------|-------------|-----------|
| Dev | `applications/dev.yaml` | Automated + Self-heal | safety-amp-dev |
| Staging | `applications/staging.yaml` | Automated + Self-heal | safety-amp-staging |
| Prod | `applications/prod.yaml` | **Manual** | safety-amp-prod |

## Deployment Procedures

### Deploy to Dev (Automatic)

1. Merge PR to `main` branch
2. CI workflow validates code
3. Build-deploy workflow:
   - Builds and pushes image
   - Updates dev kustomization.yaml
4. ArgoCD automatically syncs to dev namespace

### Promote to Staging

```bash
# Via GitHub Actions UI:
# 1. Go to Actions > "Release and Promote"
# 2. Click "Run workflow"
# 3. Enter source_tag (e.g., sha-abc1234)
# 4. Select target_environment: staging
# 5. Click "Run workflow"
```

### Deploy to Production

```bash
# Via GitHub Actions UI:
# 1. Go to Actions > "Release and Promote"
# 2. Click "Run workflow"
# 3. Enter source_tag (e.g., sha-abc1234)
# 4. Select target_environment: prod
# 5. Enter release_version (e.g., v1.2.3)
# 6. Click "Run workflow"

# Then in ArgoCD:
# 1. Navigate to safetyamp-integration-prod application
# 2. Review changes
# 3. Click "Sync" to deploy
```

## Rollback Procedures

### Automatic Rollback (ArgoCD)

For dev/staging with self-heal enabled:
1. Revert the commit in `k8s/overlays/<env>/kustomization.yaml`
2. Push to main
3. ArgoCD automatically syncs the previous image

### Manual Rollback

```bash
# Find previous image tag
git log --oneline k8s/overlays/prod/kustomization.yaml

# Option 1: Revert the kustomization change
git revert <commit-sha>
git push

# Option 2: Run release workflow with previous tag
# Use previous sha-XXXXXXX tag as source_tag
```

### Emergency Rollback via ArgoCD

```bash
# Using ArgoCD CLI
argocd app history safetyamp-integration-prod
argocd app rollback safetyamp-integration-prod <revision>

# Or via UI:
# 1. Go to Application > History
# 2. Select previous revision
# 3. Click "Rollback"
```

## Required Secrets

Configure these in GitHub repository settings (Settings > Secrets > Actions):

| Secret | Description |
|--------|-------------|
| `ACR_USERNAME` | Azure Container Registry username |
| `ACR_PASSWORD` | Azure Container Registry password/token |
| `GITHUB_TOKEN` | Auto-provided by GitHub Actions |

## Monitoring

### GitHub Actions

- View workflow runs: Repository > Actions tab
- Security scan results: Repository > Security > Code scanning

### ArgoCD

```bash
# Port forward to ArgoCD UI
kubectl port-forward svc/argocd-server -n argocd 8080:443

# Open https://localhost:8080

# Or use CLI
argocd app list
argocd app get safetyamp-integration-dev
argocd app sync safetyamp-integration-dev
```

### Application Health

```bash
# Check pod status
kubectl get pods -n safety-amp-dev

# View logs
kubectl logs -f deployment/safety-amp-agent -n safety-amp-dev

# Health endpoints
curl http://<service-ip>:8080/health
curl http://<service-ip>:8080/ready
curl http://<service-ip>:8080/live
```

## Troubleshooting

### Build Failures

1. Check GitHub Actions logs
2. Verify Dockerfile builds locally: `docker build -t test .`
3. Check for dependency issues in requirements.txt

### Sync Failures

```bash
# Check ArgoCD app status
argocd app get safetyamp-integration-dev

# View sync errors
argocd app sync safetyamp-integration-dev --dry-run

# Check Kubernetes events
kubectl get events -n safety-amp-dev --sort-by='.lastTimestamp'
```

### Image Pull Errors

1. Verify ACR credentials in GitHub secrets
2. Check image exists in ACR: `az acr repository show-tags --name iiusacr --repository safetyamp-integration`
3. Verify AKS has ACR pull permissions

## Initial Setup

### 1. Install ArgoCD

```bash
./scripts/install-argocd.sh
```

### 2. Update Repository URL

Edit the ArgoCD application manifests to use your repository:

```bash
# Replace YOUR_ORG with your GitHub organization/username
sed -i 's/YOUR_ORG/your-actual-org/g' k8s/argocd/applications/*.yaml
```

### 3. Configure Repository Access

```bash
# Add repository to ArgoCD
argocd repo add https://github.com/YOUR_ORG/II-SafetyAmp-Integration.git \
  --username <github-user> \
  --password <github-token>
```

### 4. Configure GitHub Secrets

1. Go to Repository > Settings > Secrets and variables > Actions
2. Add `ACR_USERNAME` and `ACR_PASSWORD`
