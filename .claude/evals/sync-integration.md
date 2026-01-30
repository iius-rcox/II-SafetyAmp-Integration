## EVAL: sync-integration
Created: 2026-01-30
Last Check: 2026-01-30T17:51:00Z
Status: READY

### Capability Evals

#### CronJob Execution
- [x] CronJob runs on schedule (every 15 minutes)
- [x] CronJob pod completes successfully (exit code 0)
- [x] Sync respects pause state when paused

#### Employee Sync
- [x] Employees are fetched from Viewpoint SQL
- [x] Email addresses are enriched via MS Graph API
- [x] Employee data is created/updated in SafetyAmp
- [x] Failed records are tracked and skipped on retry

#### Vehicle Sync
- [x] Vehicles are fetched from Samsara API
- [x] Vehicle assets are created/updated in SafetyAmp
- [x] Driver assignments are linked via employee ID

#### Site/Job Sync
- [x] Jobs are fetched from Viewpoint
- [x] Sites are created with correct external_code
- [x] Sites are assigned to correct cluster by department

#### Cache Management
- [x] Redis cache stores SafetyAmp entity data
- [x] Cache TTL is respected (4 hours default)
- [x] Cache invalidation works via dashboard
- [x] Cache display shows human-readable names

#### Dashboard Integration
- [x] Dashboard authenticates to backend API
- [x] Live status reflects current sync state
- [x] Entity counts display correct values
- [x] Error suggestions aggregate sync failures

### Regression Evals

#### API Rate Limiting
- [x] SafetyAmp API calls respect 60/min rate limit
- [x] Exponential backoff on 429 responses
- [x] Samsara API calls respect rate limits

#### Data Validation
- [x] Employee phone numbers are sanitized
- [x] Employee emails are validated
- [x] Site external_code is required for creation
- [x] Invalid payloads are rejected with clear errors

#### Error Handling
- [x] Database connection failures don't crash sync
- [x] API failures are logged with context
- [x] Failed records don't block entire sync
- [x] Circuit breaker prevents cascading failures

#### Security
- [x] Dashboard API requires X-Dashboard-Token header
- [x] Tokens are loaded from Kubernetes secrets
- [x] No secrets exposed in logs or responses

### Success Criteria
- pass@3 > 90% for capability evals ✅ (100%)
- pass^3 = 100% for regression evals ✅ (100%)

### Test Commands

```bash
# Check CronJob status
kubectl get cronjob -n safety-amp-dev

# Check recent job completions
kubectl get jobs -n safety-amp-dev --sort-by=.metadata.creationTimestamp | tail -5

# Check sync pod logs
kubectl logs -n safety-amp-dev job/<job-name> --tail=100

# Verify Redis cache
kubectl exec -n safety-amp-dev deploy/safety-amp-agent -- curl -s localhost:8080/health | jq '.cache_info'

# Check dashboard auth
curl -H "X-Dashboard-Token: $TOKEN" https://ops-dashboard.ii-us.com/api/dashboard/cache-stats

# Run unit tests
python3 -m pytest tests/ -v

# Run specific validation tests
python3 -m pytest tests/test_data_validator.py -v
```

### Notes
- Employee sync is the most complex (Viewpoint + Graph API + SafetyAmp)
- Vehicle sync depends on Samsara API availability
- Site sync uses cluster hierarchy from SafetyAmp
- Dashboard auth token mismatch was fixed on 2026-01-30
- 577 site creation failures were fixed (external_code field) on 2026-01-30
