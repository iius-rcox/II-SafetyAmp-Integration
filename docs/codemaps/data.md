# Data Models and Schemas Codemap

> **Freshness**: 2026-01-27 | **Scope**: Data sources, transformations, caching

## Data Sources

### Vista/Viewpoint (SQL Server)
```
Source: Construction ERP Database
Connection: ODBC via SQLAlchemy
Auth: SQL Auth or Azure Managed Identity

Tables/Views accessed:
├── Employees (PREH table)
│   ├── PRCo, Employee, FirstName, LastName
│   ├── Email, JobTitle, Department
│   ├── ActiveYN, HireDate, TermDate
│   └── Supervisor, DefaultCrew
├── Departments (HQCO/JCJM related)
├── Jobs (JCJM table)
└── Titles (custom views)
```

### Microsoft Graph (Entra ID)
```
Source: Azure Active Directory
Connection: MSAL OAuth
Endpoint: /v1.0/users

Fields retrieved:
├── id, userPrincipalName
├── displayName, givenName, surname
├── mail, jobTitle, department
├── accountEnabled
└── employeeId (custom attribute)
```

### Samsara API
```
Source: Fleet Management Platform
Connection: REST API with API key

Endpoints:
├── /fleet/vehicles
│   ├── id, name, vin
│   ├── make, model, year
│   ├── licensePlate
│   └── externalIds
└── /fleet/drivers (if needed)
```

### SafetyAmp API (Target)
```
Target: Field Safety Management Platform
Connection: REST API with API key

Entities managed:
├── Users (employees)
├── Assets (vehicles/equipment)
├── Sites (locations/projects)
├── Departments
├── Jobs
└── Titles
```

## Data Transformations

### Employee Sync Mapping
```
Vista/Graph → SafetyAmp User
─────────────────────────────────────────
Vista.Employee    → SafetyAmp.external_id
Vista.FirstName   → SafetyAmp.first_name
Vista.LastName    → SafetyAmp.last_name
Graph.mail        → SafetyAmp.email (preferred)
Vista.Email       → SafetyAmp.email (fallback)
Vista.JobTitle    → SafetyAmp.title_id (via title_map)
Vista.Department  → SafetyAmp.department_id (via dept_map)
Vista.PRCo        → SafetyAmp.cluster (via cluster_map)
Vista.ActiveYN    → SafetyAmp.status
Vista.Supervisor  → SafetyAmp.supervisor_id
```

### Vehicle Sync Mapping
```
Samsara → SafetyAmp Asset
─────────────────────────────────────────
Samsara.id           → SafetyAmp.external_id
Samsara.name         → SafetyAmp.name
Samsara.vin          → SafetyAmp.vin
Samsara.make         → SafetyAmp.make
Samsara.model        → SafetyAmp.model
Samsara.year         → SafetyAmp.year
Samsara.licensePlate → SafetyAmp.license_plate
Samsara.status       → SafetyAmp.status (regulated/unregulated)
```

### Mapping Dictionaries
```python
# In sync_employees.py
cluster_map = {
    1: "cluster_id_1",   # PRCo → SafetyAmp cluster
    2: "cluster_id_2",
    ...
}

role_map = {
    "ADMIN": "admin_role_id",
    "USER": "user_role_id",
    ...
}

title_map = {
    "Project Manager": "title_id_pm",
    "Superintendent": "title_id_super",
    ...
}
```

## Caching Layer

### DataManager Cache Structure
```
Redis Keys (or file-based JSON):
├── vista:employees        → List[EmployeeDict]
├── vista:departments      → List[DepartmentDict]
├── vista:jobs            → List[JobDict]
├── vista:titles          → List[TitleDict]
├── graph:users           → List[GraphUserDict]
├── samsara:vehicles      → List[VehicleDict]
├── safetyamp:users       → List[SafetyAmpUserDict]
├── safetyamp:assets      → List[SafetyAmpAssetDict]
└── safetyamp:sites       → List[SafetyAmpSiteDict]

TTL: 4 hours (configurable)
Format: JSON serialized
```

### FailedSyncTracker Storage
```
Redis Keys (or file-based JSON):
├── failed_sync:{entity_type}:{external_id}
│   ├── external_id
│   ├── entity_type
│   ├── failed_fields: List[str]
│   ├── field_hashes: Dict[str, str]  # SHA-256
│   ├── last_error: str
│   ├── last_attempt: ISO timestamp
│   ├── retry_count: int
│   └── created_at: ISO timestamp

TTL: 7 days (configurable)
Cleanup: On successful sync or TTL expiry
```

## Event/Change Tracking

### EventManager Output
```
File: output/changes/{session_id}.json

Structure:
{
  "session_id": "uuid",
  "started_at": "ISO timestamp",
  "completed_at": "ISO timestamp",
  "sync_type": "employees|vehicles|...",
  "summary": {
    "created": 10,
    "updated": 25,
    "deleted": 2,
    "skipped": 5,
    "errors": 1
  },
  "records": {
    "created": [...],
    "updated": [...],
    "deleted": [...],
    "skipped": [...],
    "errors": [...]
  }
}
```

## Validation Rules

### DataValidator Schemas
```python
Employee Validation:
├── email: RFC 5322 format (optional)
├── phone: E.164 format (optional)
├── first_name: required, non-empty
├── last_name: required, non-empty
├── external_id: required, non-empty
└── skip_record: if validation fails (no placeholders)

Vehicle Validation:
├── external_id: required
├── name: required, non-empty
├── vin: optional, 17 chars if present
└── status: enum (active, inactive)

Site Validation:
├── external_id: required
├── name: required, non-empty
└── cluster_id: required
```

## Database Connection Pooling

### SQLAlchemy Configuration
```python
# viewpoint_api.py
create_engine(
    connection_string,
    pool_size=5,
    max_overflow=10,
    pool_timeout=30,
    pool_recycle=1800,
    pool_pre_ping=True
)
```

## Prometheus Metrics Schema

```
# Counters
sync_operations_total{operation, status}
records_processed_total{sync_type, action}
failed_sync_records_total{entity_type, error_type}

# Histograms
sync_duration_seconds{operation}
health_check_duration_seconds{check_type}

# Gauges
database_connections_active
cache_items_total{cache_type}
cache_ttl_seconds{cache_type}
cache_last_updated_timestamp{cache_type}
```
