# Frontend Structure Codemap

> **Freshness**: 2026-01-27 | **Status**: N/A - Backend-Only Service

## Overview

This project is a **backend-only integration service** with no frontend components.

## User Interfaces

The service exposes only API endpoints for:

### Health/Observability Endpoints
```
GET /health  - Comprehensive health status (JSON)
GET /ready   - Kubernetes readiness probe
GET /live    - Kubernetes liveness probe
GET /metrics - Prometheus metrics (text/plain)
```

### Monitoring Dashboards (External)

Grafana dashboards are defined in `deploy/grafana/` and deployed separately:
- Sync operation metrics
- Error rates and latency
- Database connection pool status
- Cache hit/miss ratios

### Log Aggregation (External)

- Fluent Bit collects container logs
- Azure Log Analytics for centralized logging
- JSON structured format for query capabilities

## No Web UI

This service operates as a background worker:
1. Runs sync operations on configured intervals
2. Exposes metrics for Prometheus scraping
3. Sends error notifications via email
4. Outputs change logs to file system

Administrative operations are performed via:
- Kubernetes kubectl commands
- Azure CLI / Portal
- Grafana dashboards
- Log queries
