# Backend Structure Codemap

> **Freshness**: 2026-01-27 | **Scope**: Python services, sync operations, utilities

## Entry Points

### main.py (Flask Application)
```
main.py (364 lines)
├── Flask app initialization
├── Health endpoints: /health, /ready, /live
├── Metrics endpoint: /metrics
├── Background sync worker thread
├── Connection pooling management
└── Graceful shutdown handling
```

### sync_batch.py (Batch Execution)
```
sync_batch.py
├── One-off batch sync for Kubernetes CronJobs
├── Runs all sync operations once
└── Exits after completion
```

## Configuration Layer (config/)

### config/__init__.py - ConfigManager
```python
ConfigManager (singleton: config)
├── Environment variable loading (.env)
├── Azure Key Vault integration (managed identity)
├── SQL Server auth modes (managed_identity | sql_auth)
├── Settings caching and validation
└── Graceful degradation when Azure SDK unavailable

Key Settings:
├── SAFETYAMP_API_KEY, SAFETYAMP_BASE_URL
├── VIEWPOINT_* (SQL Server connection)
├── GRAPH_* (Microsoft Graph OAuth)
├── SAMSARA_API_KEY
├── REDIS_* (cache configuration)
└── SYNC_* (intervals, batch sizes)
```

## Services Layer (services/)

### safetyamp_api.py - SafetyAmpAPI
```python
SafetyAmpAPI
├── @limits(calls=60, period=61) - Rate limiting
├── @sleep_and_retry - Exponential backoff
├── CRUD: get/create/update users, assets, sites, etc.
├── Payload validation before sending
├── 422 validation error handling with callbacks
└── Session-based HTTP connection pooling
```

### viewpoint_api.py - ViewpointAPI
```python
ViewpointAPI
├── SQLAlchemy connection pooling (QueuePool)
├── ODBC driver for SQL Server
├── Context manager: _get_connection()
├── Query methods: employees, departments, jobs, titles
└── Supports Azure Managed Identity auth
```

### graph_api.py - MSGraphAPI
```python
MSGraphAPI
├── MSAL OAuth authentication
├── Token caching and refresh
├── Pagination for user fetching
└── Active Entra users retrieval
```

### samsara_api.py - SamsaraAPI
```python
SamsaraAPI
├── Vehicle/fleet data ingestion
├── Pagination support
└── Asset format conversion for SafetyAmp
```

### data_manager.py - DataManager
```python
DataManager (singleton: data_manager)
├── Redis primary, file fallback
├── TTL management (4-hour default)
├── In-memory lifecycle for Vista data
├── JSON serialization for caching
└── Cache invalidation methods
```

### event_manager.py - EventManager
```python
EventManager (singleton: event_manager)
├── Change tracking: created/updated/deleted/skipped/error
├── JSON output to output/changes/
├── Session-based tracking with timestamps
└── Summary statistics generation
```

## Sync Operations Layer (sync/)

### base_sync.py - BaseSyncOperation
```python
BaseSyncOperation (abstract base class)
├── Error tracking (consecutive error counter)
├── Safety stop threshold (10 errors)
├── HTTP error handling (422 specialized)
├── Change tracking integration
├── Metrics recording
└── Abstract: run(), _sync_record()
```

### sync_employees.py - SyncEmployees
```python
SyncEmployees extends BaseSyncOperation
├── Most complex sync (30K+ LOC)
├── Bidirectional: Vista ↔ SafetyAmp
├── MS Graph Entra user integration
├── Field mapping: cluster_map, role_map, title_map
├── Deactivation/reactivation logic
├── Supervisor hierarchy handling
└── Custom field mapping for SafetyAmp
```

### sync_vehicles.py - SyncVehicles
```python
SyncVehicles extends BaseSyncOperation
├── Samsara → SafetyAmp
├── Asset type mapping per site
├── Status mapping (regulated/unregulated)
└── VIN-based matching
```

### sync_departments.py, sync_jobs.py, sync_titles.py
```python
Similar pattern:
├── Vista → SafetyAmp
├── Code-based matching
├── Create/update logic
└── Change tracking
```

## Utilities Layer (utils/)

### logger.py - Structured Logging
```python
Logger
├── Text and JSON formats (switchable)
├── File + console output
├── Extra fields: sync_type, session_id, operation
├── Output: output/logs/safetyamp_sync.log
└── Log level configuration
```

### metrics.py - MetricsCollector
```python
MetricsCollector (singleton: metrics)
├── sync_operations_total (counter)
├── sync_duration_seconds (histogram)
├── records_processed_total (counter)
├── health_check_duration (histogram)
├── database_connections_active (gauge)
├── cache_* metrics
└── failed_sync_* metrics
```

### health.py - HealthCheck
```python
HealthCheck
├── Database connectivity (ViewpointAPI)
├── SafetyAmp API status
├── Samsara API status
├── Failed sync tracker health
└── Composite health score
```

### data_validator.py - DataValidator
```python
DataValidator (singleton: validator)
├── Email format validation
├── Phone E.164 format validation
├── Required field checks
├── Entity-specific validation rules
└── No placeholder substitution (skip invalid)
```

### failed_sync_tracker.py - FailedSyncTracker
```python
FailedSyncTracker (singleton: _tracker)
├── Field-level change detection (SHA-256)
├── Only retry if problematic fields changed
├── TTL cleanup (7 days default)
├── Redis or file-backed storage
└── Retry attempt tracking
```

### error_notifier.py - ErrorNotifier
```python
ErrorNotifier
├── Error aggregation (hourly batches)
├── Email notifications via SMTP
├── Error categorization by type
└── Rate limiting for notifications
```

### circuit_breaker.py - CircuitBreaker
```python
CircuitBreaker
├── Failure threshold configuration
├── Recovery timeout
├── Half-open state for testing
└── Prevents cascading failures
```

## Global Singletons

```python
# Instantiated at module import
config = ConfigManager()           # config/__init__.py
data_manager = DataManager()       # services/data_manager.py
event_manager = EventManager()     # services/event_manager.py
metrics = MetricsCollector()       # utils/metrics.py
validator = DataValidator()        # utils/data_validator.py
_tracker = FailedSyncTracker()     # utils/failed_sync_tracker.py
```

## External Dependencies

```
Core: Flask, Gunicorn, Requests, Python-dotenv
Database: PyODBC, SQLAlchemy
APIs: MSAL (Graph OAuth), Ratelimit
Cache: Redis, hiredis
Azure: azure-identity, azure-keyvault-secrets
Monitoring: prometheus-client, structlog
Resilience: tenacity, circuitbreaker, pydantic
```
