# Dead Code Analysis Report

**Generated:** 2026-01-27
**Tool:** vulture (Python dead code finder)
**Confidence Threshold:** 60%+

## Summary

| Category | Count | Action |
|----------|-------|--------|
| Unused Imports | 2 | SAFE to remove |
| Unused Variables | 7 | Review needed |
| Unused Functions/Methods | 45+ | Mostly FALSE POSITIVES |
| Unused Dependencies | 4 | Review needed |

## Findings by Severity

### 🟢 SAFE: High Confidence (90-100%)

These are definitely unused and safe to remove:

| File | Line | Issue | Confidence |
|------|------|-------|------------|
| `main.py` | 289 | `frame` - unused signal handler arg | 100% |
| `services/viewpoint_api.py` | 2 | `import pyodbc` - SQLAlchemy handles it | 90% |
| `services/viewpoint_api.py` | 7 | `import Engine` - unused type hint | 90% |

### 🟡 CAUTION: False Positives (60%)

These are flagged but are actually USED - vulture can't detect:
- Flask route decorators (`@app.route`)
- Dynamic method calls
- Methods called through base class

**Flask Routes (NOT dead code):**
- `main.py:88` - `health()` - used by `/health` route
- `main.py:118` - `ready()` - used by `/ready` route
- `main.py:136` - `live()` - used by `/live` route
- `main.py:146` - `metrics_endpoint()` - used by `/metrics` route

**API Client Methods (likely used dynamically):**
- `services/safetyamp_api.py` - convenience methods like `get_sites()`, `get_users()`
- `services/data_manager.py` - cache methods for flexible data access

**Base Class Methods (inherited):**
- `sync/base_sync.py` - methods designed for subclass use

### 🔴 DANGER: Do Not Delete

- `config/__init__.py:393` - `get_config()` - public API for config access
- `utils/logger.py:11` - `format()` - logging.Formatter override

## Unused Dependencies

These packages are in `requirements.txt` but not imported:

| Package | Status | Recommendation |
|---------|--------|----------------|
| `pydantic` | Not imported | **REMOVE** - not used |
| `tenacity` | Not imported | **REMOVE** - not used |
| `opentelemetry-api` | Not imported | **KEEP** - marked optional |
| `opentelemetry-sdk` | Not imported | **KEEP** - marked optional |
| `black` | Dev tool | **KEEP** - linting |
| `flake8` | Dev tool | **KEEP** - linting |

## Recommended Actions

### Phase 1: Safe Removals (No Risk)

1. **Remove unused import in viewpoint_api.py**
   ```python
   # Line 2: Remove direct pyodbc import (SQLAlchemy handles connection)
   import pyodbc  # DELETE THIS LINE
   ```

2. **Remove unused Engine import**
   ```python
   # Line 7: Not used for type hints
   from sqlalchemy.engine import Engine  # DELETE THIS LINE
   ```

3. **Fix signal handler signature**
   ```python
   # Line 289: Use _ for unused argument
   def signal_handler(signum, frame):  # Change to: def signal_handler(signum, _):
   ```

### Phase 2: Dependency Cleanup

1. **Remove from requirements.txt:**
   - `pydantic>=2.6` - Not imported anywhere
   - `tenacity>=8.2` - Not imported anywhere

### Phase 3: Review for Future Cleanup

These methods appear unused but may be:
- Part of public API
- Called dynamically
- Planned for future use

Consider adding `# noqa: vulture` comments or actually removing if confirmed unused:

- `utils/data_validator.py:203` - `_generate_email()` - helper not called
- `utils/circuit_breaker.py:36` - `SmartRateLimiter` class - appears unused
- `utils/notification_manager.py:9` - entire `NotificationManager` class

## Test Verification Required

Before any deletion:
```bash
# Run full test suite
python3 -m pytest tests/ -v

# Run with coverage to verify impact
python3 -m pytest tests/ --cov=. --cov-report=term-missing
```

## Files to Skip

These files were excluded from analysis:
- `tests/` - Test code
- `output/` - Generated output
- `deploy/` - Deployment scripts
- `k8s/` - Kubernetes manifests
