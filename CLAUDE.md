# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a **SafetyAmp Integration Service** that synchronizes data between:
- **Viewpoint ERP** (Microsoft SQL Server) - Source of HR data (employees, departments, jobs, titles)
- **Samsara Fleet Management** - Source of vehicle/asset data
- **Microsoft Entra ID (Graph API)** - Source of user email addresses
- **SafetyAmp** - Target SaaS platform for safety management

The application runs as a Flask service on AKS (Azure Kubernetes Service) with a background sync worker that runs on a configurable interval.

## Build and Run Commands

```bash
# Install dependencies
pip install -r requirements.txt

# Run the Flask service with background sync worker
python main.py

# Run a one-time batch sync (for CronJob usage)
python sync_batch.py

# Test database connectivity
python test-db-connection.py

# Lint code
black --check .
flake8 .

# Run tests
python3 -m pytest tests/ -v

# Run tests with coverage
python3 -m pytest tests/ --cov=utils --cov-report=term-missing

# Run a single test file
python3 -m pytest tests/test_data_validator.py -v

# Run tests matching a pattern
python3 -m pytest tests/ -k "phone" -v
```

### Docker

```bash
# Build image
docker build -t safetyamp-integration .

# The image runs on port 8080 (Flask) and 9090 (Prometheus metrics)
```

### Kubernetes Deployment

```bash
# Get AKS credentials
az aks get-credentials --resource-group rg_prod --name dev-aks

# Deploy (order matters)
kubectl apply -f k8s/namespaces/namespaces.yaml
kubectl apply -f k8s/safety-amp/safety-amp-complete.yaml

# Environment overlays use Kustomize
kubectl apply -k k8s/overlays/dev/
kubectl apply -k k8s/overlays/staging/
kubectl apply -k k8s/overlays/prod/
```

## Architecture

### Entry Points

| File | Purpose |
|------|---------|
| `main.py` | Flask app with `/health`, `/ready`, `/live`, `/metrics` endpoints + background sync worker thread |
| `sync_batch.py` | One-shot sync for Kubernetes CronJobs |

### Data Flow

```
Viewpoint SQL ─┐
               ├─► EmployeeSyncer ─► SafetyAmp API
MS Graph API ──┘       │
                       ├─► EventManager (change tracking + error logging)
Samsara API ──────► VehicleSync ─► SafetyAmp API
```

### Core Modules

**`config/__init__.py`** - Singleton `ConfigManager` that:
- Loads `.env` for local dev
- Connects to Azure Key Vault for secrets (using `DefaultAzureCredential`)
- Exposes all settings as attributes (e.g., `config.SQL_SERVER`, `config.SAFETYAMP_TOKEN`)
- Provides `get_secret()` for on-demand secret retrieval with caching

**`services/`** - External API clients:
- `safetyamp_api.py` - Rate-limited REST client with payload validation
- `viewpoint_api.py` - SQLAlchemy connection pool to Viewpoint SQL Server
- `samsara_api.py` - Rate-limited Samsara fleet API client
- `graph_api.py` - Microsoft Graph client for Entra ID user lookup
- `event_manager.py` - Session-based change tracking and error aggregation
- `data_manager.py` - In-memory + Redis caching layer

**`sync/`** - Sync operation implementations:
- `base_sync.py` - Base class with error backoff, validation, change tracking
- `sync_employees.py` - Viewpoint + Graph → SafetyAmp user sync
- `sync_vehicles.py` - Samsara → SafetyAmp asset sync
- `sync_departments.py`, `sync_jobs.py`, `sync_titles.py` - Reference data sync

**`utils/`** - Supporting utilities:
- `metrics.py` - Prometheus metrics singleton (`metrics.sync_operations_total`, etc.)
- `logger.py` - Structured JSON logging (controlled by `LOG_FORMAT=json`)
- `data_validator.py` - Entity-specific validation with phone/email sanitization
- `failed_sync_tracker.py` - Redis-backed tracker to skip retrying unchanged failed records
- `health.py` - Dependency health checks (DB, SafetyAmp, Samsara)
- `circuit_breaker.py` - Circuit breaker for external dependencies

### Configuration

Secrets are loaded from Azure Key Vault (production) or environment variables (local). Key settings:

| Setting | Description |
|---------|-------------|
| `SAFETYAMP_TOKEN` | Bearer token for SafetyAmp API |
| `SQL_SERVER`, `SQL_DATABASE` | Viewpoint connection |
| `SQL_AUTH_MODE` | `managed_identity` (AKS) or `sql_auth` (local) |
| `SAMSARA_API_KEY` | Samsara fleet API key |
| `MS_GRAPH_*` | Microsoft Graph client credentials |
| `SYNC_INTERVAL_MINUTES` | Background sync interval (default: 60) |

## Key Patterns

### Rate Limiting

All API clients use `@sleep_and_retry` + `@limits()` decorators from the `ratelimit` package, plus exponential backoff on 429 responses.

### Change Tracking

The `EventManager` tracks all sync operations in a session:
```python
event_manager.start_sync("employees")
# ... do work, call log_creation/log_update/log_error ...
summary = event_manager.end_sync()
```

Changes are written to JSON files in `output/changes/` and `output/errors/`.

### Failed Sync Tracker

Records that fail API validation (422) are tracked in Redis. On subsequent syncs, if the problematic fields haven't changed, the record is skipped to avoid repeated failures.

### Kubernetes Health Model

- `/live` - Returns 200 if process is alive (liveness probe)
- `/ready` - Returns 200 only if database is healthy (readiness probe)
- `/health` - Comprehensive status including all dependency checks

## File Locations

- `output/logs/` - Application logs
- `output/changes/` - JSON change logs per sync session
- `output/errors/` - JSON error logs
- `k8s/` - Kubernetes manifests with Kustomize overlays
- `deploy/` - PowerShell deployment scripts and Grafana dashboards
- `deploy/backups/` - Legacy deployment backup YAMLs
- `docs/` - Operational documentation
- `docs/codemaps/` - Architecture and module codemaps
- `docs/reference/` - Ad-hoc notes, analyses, and reference data
- `scripts/` - Utility scripts (e.g. `update-log-analytics-secret.sh`)
