### SafetyAmp Integration Cleanup – Implementation-Ready Plan

This plan describes, in implementation-ready detail, how to consolidate data, events, and configuration into unified managers. It is structured for incremental rollout with clear file changes, codemods, testing, and a backout plan.

## Goals and Outcomes
- **Single DataManager**: Unified caching (Redis/file), Vista in-memory lifecycle, API data caching, and validation utilities.
- **Single EventManager**: Unified error/change tracking and notifications with session management and reporting.
- **Single ConfigManager**: Unified, type-safe configuration with Azure Key Vault integration and fallbacks.
- **Removal of redundant modules**: Eliminate ~15 overlapping files and mixed configuration patterns.

## Preconditions and Environment
- **Branching**: Create a feature branch, e.g., `feat/unified-managers`.
- **Python**: 3.9+.
- **Redis**: Accessible in dev and staging; configure `REDIS_HOST`, `REDIS_PORT`, `REDIS_DB`, `REDIS_PASSWORD` if applicable.
- **Azure**: If using Key Vault, ensure service principal/workload identity with access to required secrets.
- **Telemetry/Email**: SMTP creds or email provider access for notifications; optional OpenTelemetry exporter.

## Required Dependencies (add/verify in requirements.txt)
```
redis>=5.0
azure-identity>=1.16.0
azure-keyvault-secrets>=4.7.0
pydantic>=2.6
python-dotenv>=1.0
tenacity>=8.2  # for retries/backoff
opentelemetry-api>=1.25  # optional
opentelemetry-sdk>=1.25  # optional
``` 

## High-Level Phasing
1. Config foundation (ConfigManager) – safe to land first.
2. Data layer (DataManager) – introduce as façade with adapters.
3. Events (EventManager) – unify logging, change tracking, notifications.
4. Migrate consumers (sync jobs, services) using codemods + manual edits.
5. Delete redundant modules after tests are green and logs are clean.

---

### Phase 0: Pre-flight and Bootstrap
- **Create feature branch**: `git checkout -b feat/unified-managers`.
- **Add dependencies** to `requirements.txt` and install in your environment.
- **Set base env** in `.env` (dev) or copy `.env.example`:
  - `ENV=dev`
  - `REDIS_HOST=localhost`
  - `REDIS_PORT=6379`
  - `SAFETYAMP_TOKEN=...` (dev)
  - `AZURE_KEY_VAULT_NAME=...` (if applicable)
  - SMTP/email settings as needed.
- **CI caches**: Ensure CI can reach Redis or use a local ephemeral Redis service.

Verification: `pip install -r requirements.txt` should succeed.

---

### Phase 1: Standardize Configuration (ConfigManager)

Files to create/modify:
- Create/Replace: `config/__init__.py` (unified `ConfigManager` and exported singleton `config` and alias `settings`). [Implemented]
- Modify: `main.py` (startup config validation/logging). [Implemented]
- Modify: service modules that read configuration to import from `config`. [Implemented: `services/data_manager.py`, `services/viewpoint_api.py`, `services/safetyamp_api.py`, `services/samsara_api.py`, `services/graph_api.py`, `utils/health.py`, `utils/emailer.py`]

Design:
- Precedence: env → Azure Key Vault → .env → defaults.
- Read-only after load; lazy secret resolution with memoization.
- Validation of required keys; never log secret values.

Implementation checklist:
- Create `ConfigManager` with:
  - Typed properties (e.g., `SAFETYAMP_TOKEN: str`, `REDIS_HOST: str`, ...).
  - Methods: `validate_required_secrets()`, `get_configuration_status()`, `get_secret(name, refresh=False)`, `build_sql_connection_string()` if applicable.
  - Azure KV support using `DefaultAzureCredential` with `SecretClient`; fall back to env/.env.
  - Support `AZURE_KEY_VAULT_NAME` to derive URL (`https://{name}.vault.azure.net`) in addition to `AZURE_KEY_VAULT_URL`.
- Export a singleton: `config = ConfigManager()`; keep `settings = config` for compatibility.

Main startup validation (in `main.py`):
```python
from config import config

if not config.validate_required_secrets():
    logger.critical("Configuration validation failed")
    sys.exit(1)

status = config.get_configuration_status()
logger.info(f"Configuration loaded: {status['validation']['is_valid']}")
```

Testing steps:
- Run a small script to print `config.get_configuration_status()`.
- Toggle missing envs and assert validation fails with actionable messages.
- Verify `main.py` respects `ENABLE_UNIFIED_CONFIG` feature flag.

---

### Phase 2: Consolidate Data (DataManager)

Files to create/modify:
- Create/Replace: `services/data_manager.py` (unified façade with adapters).
- Remove later: `utils/cache_manager.py` (after migration), and direct API caching usages.
- Modify: `sync/sync_employees.py`, `sync/sync_jobs.py`, `sync/sync_titles.py`, `sync/sync_vehicles.py`, `services/viewpoint_api.py` to consume `data_manager`.

Architecture:
- Adapters: `RedisCacheAdapter`, `FileCacheAdapter` with fallback order.
- Domain methods: thin legacy convenience wrappers (`get_employees()` etc.).
- Validation bridge: expose `validate_employee_data(...)` via injected validator.
- Cache keys: `app:v{n}:domain:entity:{id}` with metadata `{schema_version, ttl, created_at, source}`.
- Stampede control: distributed locks + jitter; `get-or-populate` primitive.

Minimal public API (façade):
```python
class DataManager:
    def get_cached_data(self, name: str, key: str): ...
    def save_cache(self, name: str, data: Any, ttl_seconds: int | None = None, key: str | None = None, metadata: dict | None = None) -> bool: ...
    def invalidate(self, key_or_pattern: str) -> int: ...
    def get_cached_data_with_fallback(self, name: str, key: str, loader: Callable[[], Any], ttl_seconds: int, lock: bool = True, metadata: dict | None = None) -> Any: ...

    # Legacy domain helpers (optional)
    def get_employees(self) -> list[dict]: ...
    def get_jobs(self) -> list[dict]: ...

    # Validation bridge
    def validate_employee_data(self, payload: dict, employee_id: str, display_name: str) -> tuple[bool, list[str], dict]: ...

# Export singleton
data_manager = DataManager(...)
```

Migration mapping (old → new):

| Old import | Old call | New import | New call |
|---|---|---|---|
| `from utils.cache_manager import CacheManager` | `CacheManager().get_employees()` | `from services.data_manager import data_manager` | `data_manager.get_employees()` |
| `from services.data_manager import data_manager` | `data_manager.save_cache("k", data)` | same | same |
| `from utils.data_validator import validator` | `validator.validate_employee_data(...)` | `from services.data_manager import data_manager` | `data_manager.validate_employee_data(...)` |
| Any direct API caching | ad-hoc | `from services.data_manager import data_manager` | `data_manager.get_cached_data_with_fallback(...)` |

Testing steps:
- Unit test cache get/set with Redis running; verify metadata and TTL.
- Simulate Redis outage: ensure file adapter fallback works.
- Validate stampede control by concurrent get-or-populate.

---

### Phase 3: Unify Events (EventManager)

Files to create/modify:
- Create: `services/event_manager.py` (unified event model and sinks). [Implemented]
- Remove later: `utils/error_manager.py`, `utils/change_tracker.py`, `utils/error_notifier.py`.
- Modify: `sync/sync_employees.py`, `sync/sync_departments.py`, `sync/sync_jobs.py`, `sync/sync_titles.py`, `sync/sync_vehicles.py`, `main.py` to use `event_manager`. [Partially implemented: `main.py`, `sync/sync_employees.py`]
- Modify: `deploy/monitor-changes.ps1`, `deploy/monitor-validation.ps1`, `deploy/test-error-notifications.ps1` if they import old modules.

Design:
- Event schema: `{event_id, timestamp, severity, category, entity_type, entity_id, session_id, attributes, error}`.
- Start/end sessions for sync runs; summarize created/updated/deleted/errors.
- Sinks: logging/audit, metrics, notifier (email/webhook). Non-blocking dispatch with batching.

Minimal public API:
```python
class EventManager:
    def start_sync(self, name: str, correlation_id: str | None = None) -> str: ...
    def log_creation(self, entity: str, entity_id: str, details: dict | None = None, session_id: str | None = None): ...
    def log_update(self, entity: str, entity_id: str, changes: dict | None = None, session_id: str | None = None): ...
    def log_deletion(self, entity: str, entity_id: str, reason: str | None = None, session_id: str | None = None): ...
    def log_error(self, kind: str, entity: str | None, entity_id: str | None, message: str, exc: BaseException | None = None, session_id: str | None = None): ...
    def end_sync(self, session_id: str | None = None) -> dict: ...
    def send_hourly_notification(self): ...

# Export singleton
event_manager = EventManager(...)
```

Migration mapping (old → new):

| Old import | Old call | New import | New call |
|---|---|---|---|
| `from utils.error_manager import error_manager` | `error_manager.log_error(...)` | `from services.event_manager import event_manager` | `event_manager.log_error(...)` |
| `from utils.change_tracker import ChangeTracker` | `ChangeTracker().log_creation(...)` | same as above | `event_manager.log_creation(...)` |
| `from utils.error_notifier import error_notifier` | `error_notifier.send_hourly_notification()` | same as above | `event_manager.send_hourly_notification()` |

Applied so far:
- `main.py`: switched hourly notifications and error logging to `event_manager`.
- `sync/sync_employees.py`: migrated session lifecycle and all event/error calls to `event_manager`.

Testing steps:
- Start a session, emit creation and error events, end session; assert summary counts.
- Induce notifier failure (e.g., bad SMTP) to confirm non-fatal behavior and backoff.
- Verify structured logs and (optional) OpenTelemetry spans are emitted.

---

### Phase 4: Migrate Consumers and Delete Redundancies

Targets to update imports and calls:
- `sync/sync_employees.py`
- `sync/sync_departments.py`
- `sync/sync_jobs.py`
- `sync/sync_titles.py`
- `sync/sync_vehicles.py`
- `services/viewpoint_api.py`
- `services/safetyamp_api.py`
- `services/samsara_api.py`
- `services/graph_api.py`
- `utils/emailer.py`
- `main.py`
- `deploy/monitor-changes.ps1`
- `deploy/monitor-validation.ps1`
- `deploy/test-error-notifications.ps1`

Temporary compatibility (optional for one release):
- Keep stubs that import the new managers and emit a `DeprecationWarning`. Remove in the next release.

Remove after migration and green tests:
- `utils/cache_manager.py`
- `utils/error_manager.py`
- `utils/change_tracker.py`
- `utils/error_notifier.py`

---

## Codemod and Automation

One-time Python codemod script `tools/codemod_unified_managers.py`:
```python
#!/usr/bin/env python3
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parents[1]
TARGETS = [
    'sync', 'services', 'utils', 'main.py', 'deploy'
]

REPLACEMENTS = [
    # Config
    (r"from\s+config\s+import\s+(settings|SAFETYAMP_TOKEN|SQL_SERVER|[A-Z_]+)", "from config import config"),
    # Cache/Data
    (r"from\s+utils\.cache_manager\s+import\s+CacheManager", "from services.data_manager import data_manager"),
    (r"CacheManager\(\)", "data_manager"),
    (r"validator\.validate_employee_data\(", "data_manager.validate_employee_data("),
    # Events
    (r"from\s+utils\.error_manager\s+import\s+error_manager", "from services.event_manager import event_manager"),
    (r"from\s+utils\.change_tracker\s+import\s+ChangeTracker", "from services.event_manager import event_manager"),
    (r"from\s+utils\.error_notifier\s+import\s+error_notifier", "from services.event_manager import event_manager"),
    (r"error_manager\.", "event_manager."),
    (r"error_notifier\.", "event_manager."),
    (r"ChangeTracker\(\)", "event_manager"),
]

FILE_GLOBS = ["**/*.py", "**/*.ps1"]

for glob in FILE_GLOBS:
    for path in ROOT.glob(glob):
        if any(str(path).startswith(str(ROOT / t)) for t in TARGETS):
            text = path.read_text(encoding='utf-8')
            orig = text
            for pattern, repl in REPLACEMENTS:
                text = re.sub(pattern, repl, text)
            if text != orig:
                path.write_text(text, encoding='utf-8')
                print(f"Updated {path}")
```

Run:
```bash
python tools/codemod_unified_managers.py
```

Sanity checks:
- Grep for forbidden imports:
```bash
grep -R "utils/cache_manager\|utils/error_manager\|utils/change_tracker\|utils/error_notifier" -n || true

Note: For modules still needing direct `ChangeTracker` instances, keep imports temporarily; migrate to `event_manager` where possible.
```

---

## Testing Strategy

Unit tests (add under `tests/`):
- ConfigManager: precedence, validation, Key Vault fallback, secret masking in status.
- DataManager: key schema/versioning, TTL behavior, metadata, file fallback when Redis is down.
- EventManager: session lifecycle, counters, notifier failure isolation.

Integration tests:
- With Redis running: `docker run -p 6379:6379 -d redis:7`.
- Key Vault (if available): use a dev vault or a local mock that mirrors the API.

Concurrency/resilience tests:
- Simulate parallel `get-or-populate` calls; ensure single loader execution and others read cached value.
- Simulate Redis timeout and ensure fallback path is used and recorded in metrics/logs.

Observability assertions:
- Metrics: cache hit/miss, load latency, error rates.
- Logs: structured events with redaction applied; no secrets present.

Smoke tests:
- Run `main.py` with config validation enabled; ensure startup success.
- Trigger a sample sync session with `event_manager` and verify summary.

---

## CI/CD Updates
- Ensure `pip install -r requirements.txt` is part of CI.
- Add a CI step to fail on forbidden imports after codemod:
```bash
grep -R "utils/cache_manager\|utils/error_manager\|utils/change_tracker\|utils/error_notifier" -n && echo "Forbidden import found" && exit 1 || true
```
- Cache Redis in CI or spin a Redis service for integration tests.
- Publish artifacts/logs for early rollout monitoring.

---

## Rollout Plan and Backout

Incremental rollout flags:
- Feature flag per manager (env-driven): `ENABLE_UNIFIED_CONFIG`, `ENABLE_UNIFIED_DATA`, `ENABLE_UNIFIED_EVENTS`.
- Gradually enable per sync job to limit blast radius.

Backout plan:
- Keep old modules behind flags for one release window; switch flags off to revert.
- If critical issues arise, revert the feature branch or toggle flags to old path.

Deprecation timeline:
- Release N: Unified managers default on; deprecation warnings for old imports.
- Release N+1: Remove deprecated modules and warnings; enforce CI import checks.

---

## Security and Compliance
- Redact PII in logs and events; centralize redaction rules in EventManager.
- Encrypt file cache if storing sensitive data; prefer Redis over disk for PII.
- Never log secret values; `get_configuration_status()` must mask secrets.
- Apply least-privilege to Key Vault access; monitor secret access logs.

---

## Acceptance Criteria (Definition of Done)
- ConfigManager: unified, validated at startup; all modules import from `config`. [Implemented: module exists; startup validation wired in `main.py`]
- DataManager: caching + validation unified; no direct cache manager usages; API caching routed via `get_cached_data_with_fallback()`.
- EventManager: unified logging/change tracking/notifications; sessions produce summaries. [Implemented: `services/event_manager.py`; `main.py` + `sync/sync_employees.py` migrated]
- All targeted files updated; redundant modules deleted.
- Unit/integration tests green; CI import check passes; no legacy imports remain.
- Observability: metrics and structured logs for cache and events present.

---

## Detailed Task Checklist

General
- [ ] Create feature branch `feat/unified-managers`
- [ ] Update `requirements.txt` and install

ConfigManager
- [ ] Implement `config/__init__.py` with `ConfigManager` and `config` singleton
- [ ] Add Azure Key Vault integration and fallbacks
- [ ] Add `validate_required_secrets()` and `get_configuration_status()`
- [ ] Update `main.py` startup validation
- [ ] Update services to import from `config`

DataManager
- [ ] Implement `services/data_manager.py` with adapters and façade
- [ ] Implement `get_cached_data_with_fallback()` with locking and jitter
- [ ] Bridge validator methods (e.g., `validate_employee_data`)
- [ ] Update sync modules and `services/viewpoint_api.py`

EventManager
- [ ] Implement `services/event_manager.py` with session lifecycle and sinks
- [ ] Update sync modules and `main.py` to use `event_manager`
- [ ] Update deploy scripts if importing old modules

Migration & Cleanup
- [ ] Run codemod script and manual fixes
- [ ] Add CI step to forbid legacy imports
- [ ] Delete `utils/cache_manager.py`, `utils/error_manager.py`, `utils/change_tracker.py`, `utils/error_notifier.py`

Testing
- [ ] Add unit tests for each manager
- [ ] Run integration tests with Redis and optional Key Vault
- [ ] Perform smoke test for a full sync session

Rollout
- [ ] Add feature flags for staged rollout
- [ ] Monitor metrics/logs and validate stability

---

## Example Usage Snippets (Post-Migration)

Configuration:
```python
from config import config
if not config.validate_required_secrets():
    raise SystemExit("Missing required secrets")
```

Data:
```python
from services.data_manager import data_manager

employees = data_manager.get_employees()
project = data_manager.get_cached_data_with_fallback(
    name="viewpoint_projects",
    key="v1:all",
    loader=lambda: viewpoint_api.get_all_projects(),
    ttl_seconds=3600,
)
```

Events:
```python
from services.event_manager import event_manager

sid = event_manager.start_sync("sync_employees")
event_manager.log_creation("employee", "123", {"name": "Jane"}, sid)
try:
    ...
except Exception as exc:
    event_manager.log_error("sync_failure", "employee", "123", str(exc), exc, sid)
summary = event_manager.end_sync(sid)
```

---

## Time and Effort Estimate (guidance)
- ConfigManager: 0.5–1 day including validation and Key Vault integration.
- DataManager: 1–2 days including adapters, stampede control, and tests.
- EventManager: 1–1.5 days including notifier integration and summaries.
- Migration + cleanup: 0.5–1 day including codemods and CI updates.
- Total: ~3–5 days depending on test coverage and integrations.

---

## Notes and Pitfalls
- Avoid god-object creep: keep adapters and sinks modular; façade thin.
- Don’t mix sync/async paths; choose consistently per code path.
- Define TTLs per domain; avoid stale critical data.
- Surface degraded modes explicitly via logs/metrics; do not fail silently.
- Mask secrets and PII everywhere; validate redaction in tests.

References (best practices):
- Config in env, not code (.env only for dev): 12-Factor App — Config (https://12factor.net/config)
- Azure auth and Key Vault usage with DefaultAzureCredential: Microsoft Docs (https://learn.microsoft.com/azure/developer/python/sdk/authentication-overview)
- Key Vault URI format: Microsoft Docs (https://learn.microsoft.com/azure/key-vault/general/about-keys-secrets-certificates#key-vault-uris)
- Do not log secrets; redact: OWASP Logging Cheat Sheet (https://cheatsheetseries.owasp.org/cheatsheets/Logging_Cheat_Sheet.html)
- Fail-fast/health monitoring: Health Endpoint Monitoring pattern (https://learn.microsoft.com/azure/architecture/patterns/health-endpoint-monitoring)
- Structured logging guidance: 12-Factor — Logs (https://12factor.net/logs)
- Prometheus instrumentation: Best Practices (https://prometheus.io/docs/practices/instrumentation/)
- Graceful shutdown for k8s: Pod termination (https://kubernetes.io/docs/concepts/workloads/pods/pod-lifecycle/#pod-termination)
- Monitoring principles: Google SRE — Monitoring Distributed Systems (https://sre.google/sre-book/monitoring-distributed-systems/)
- Avoid thundering herd with jitter/backoff: AWS Builders’ Library (https://aws.amazon.com/builders-library/timeouts-retries-and-backoff-with-jitter/)
