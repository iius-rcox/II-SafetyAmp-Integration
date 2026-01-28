# II-SafetyAmp-Integration Architecture Codemap

> **Freshness**: 2026-01-27 | **Type**: Python Backend Integration Service

## Overview

Backend microservice that orchestrates data synchronization between enterprise systems:
- **SafetyAmp** - Field safety management platform (target)
- **Vista/Viewpoint** - Construction ERP database (SQL Server source)
- **Samsara** - Fleet management API (source)
- **Microsoft Graph** - Azure Entra directory (source)

## Directory Structure

```
II-SafetyAmp-Integration/
├── config/              # Configuration management (Azure Key Vault + env vars)
├── services/            # External API clients and data management
├── sync/                # Data synchronization operations
├── utils/               # Utility modules (logging, metrics, health)
├── k8s/                 # Kubernetes manifests (AKS deployment)
├── deploy/              # Terraform modules, Grafana dashboards
├── docs/                # Documentation
├── scripts/             # Helper scripts (PowerShell, Azure)
├── main.py              # Flask app entry point
├── sync_batch.py        # CronJob batch execution wrapper
└── Dockerfile           # Multi-stage container build
```

## Layered Architecture

```
┌─────────────────────────────────────────────────────┐
│  Entry Points: main.py, sync_batch.py               │
├─────────────────────────────────────────────────────┤
│  Sync Operations: sync/*.py                         │
│  (employees, vehicles, departments, jobs, titles)   │
├─────────────────────────────────────────────────────┤
│  Services: services/*.py                            │
│  (API clients, data manager, event manager)         │
├─────────────────────────────────────────────────────┤
│  Utilities: utils/*.py                              │
│  (logger, metrics, health, validation, resilience)  │
├─────────────────────────────────────────────────────┤
│  Configuration: config/__init__.py                  │
│  (ConfigManager with Azure Key Vault integration)   │
└─────────────────────────────────────────────────────┘
```

## Data Flow

```
SOURCES                  SYNC LAYER              TARGET
─────────────────────────────────────────────────────────
Vista SQL Server ──┐
                   ├──► sync_employees.py ──┐
MS Graph API ──────┤    sync_departments.py │
                   │    sync_jobs.py        ├──► SafetyAmp API
                   │    sync_titles.py      │
Samsara API ───────┴──► sync_vehicles.py ───┘

              ┌─────────────────────────────┐
              │  Supporting Infrastructure   │
              ├─────────────────────────────┤
              │  Redis/File Cache           │
              │  Prometheus Metrics         │
              │  Structured Logging         │
              │  Change Tracking Events     │
              │  Error Notification         │
              └─────────────────────────────┘
```

## Key Patterns

| Pattern | Location | Purpose |
|---------|----------|---------|
| Singleton | config, services, utils | Global instances for shared state |
| Base Class | sync/base_sync.py | Common sync operation behavior |
| Context Manager | viewpoint_api.py | Database connection handling |
| Decorator | safetyamp_api.py | Rate limiting, retry logic |
| Circuit Breaker | utils/circuit_breaker.py | Fault tolerance |

## Module Dependencies

```
main.py
  └── sync/*
        ├── services/safetyamp_api.py
        ├── services/viewpoint_api.py
        ├── services/graph_api.py
        ├── services/samsara_api.py
        ├── services/data_manager.py
        ├── services/event_manager.py
        └── utils/*
              └── config/*
```

## Deployment

- **Container**: Docker multi-stage build (python:3.11-slim-bullseye)
- **Orchestration**: Kubernetes on Azure AKS
- **Authentication**: Workload Identity (Managed Identity)
- **Secrets**: Azure Key Vault
- **Monitoring**: Prometheus + Grafana + Fluent Bit
