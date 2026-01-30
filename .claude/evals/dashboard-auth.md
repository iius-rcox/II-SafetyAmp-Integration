## EVAL: dashboard-auth
Created: 2026-01-30
Last Check: 2026-01-30T17:07:00Z
Status: READY

### Capability Evals

#### Token Configuration
- [x] DASHBOARD_API_TOKEN is set in Kubernetes secret `safety-amp-secrets`
- [x] Token is injected into safety-amp-agent pod as environment variable
- [x] Token is injected into ops-dashboard pod as environment variable
- [x] Nginx template substitutes token at container startup
- [x] Both pods have matching token values

#### Nginx Proxy Authentication
- [x] Nginx config includes `proxy_set_header X-Dashboard-Token`
- [x] Token is substituted via envsubst in `/etc/nginx/conf.d/default.conf`
- [x] All `/api/` requests include the token header automatically
- [x] Frontend code doesn't need to manage token (nginx handles it)

#### Backend Authentication Decorator
- [x] `require_dashboard_auth` decorator protects all dashboard endpoints
- [x] Decorator reads token from `X-Dashboard-Token` header
- [x] Decorator uses `secrets.compare_digest` for timing-safe comparison
- [x] Returns 401 when token is missing
- [x] Returns 403 when token is invalid
- [x] Returns 503 when DASHBOARD_API_TOKEN not configured (fail closed)

#### Protected Endpoints
- [x] GET `/api/dashboard/cache-stats` requires auth
- [x] GET `/api/dashboard/sync-metrics` requires auth
- [x] GET `/api/dashboard/error-suggestions` requires auth
- [x] GET `/api/dashboard/live-status` requires auth
- [x] GET `/api/dashboard/entity-counts` requires auth
- [x] GET `/api/dashboard/dependency-health` requires auth
- [x] POST `/api/dashboard/sync-pause` requires auth
- [x] POST `/api/dashboard/trigger-sync` requires auth
- [x] POST `/api/dashboard/cache/invalidate/*` requires auth
- [x] GET `/api/dashboard/audit-log` requires auth

#### Dashboard UI Authentication Flow
- [x] Dashboard loads without showing 403 errors
- [x] All API calls succeed when token is configured correctly
- [x] Sync status indicator shows actual status (not "unavailable")
- [x] Cache Monitor shows "Redis Connected" when authenticated

### Regression Evals

#### Security Requirements
- [x] Token is never logged in application logs
- [x] Token is never exposed in API responses
- [x] Token is not passed via query parameters (header only)
- [x] Failed auth attempts are logged with warning level

#### Fail-Closed Behavior
- [x] Missing DASHBOARD_API_TOKEN returns 503, not 200
- [x] Empty token is treated as missing
- [x] Whitespace-only token is treated as missing

#### Kubernetes Secret Management
- [x] Secret is of type Opaque
- [x] Secret value is base64 encoded
- [x] Pods restart picks up updated secret values
- [x] No hardcoded tokens in deployment manifests (uses secretKeyRef)

#### No Breaking Changes
- [x] Unauthenticated health endpoints still work (`/health`, `/live`, `/ready`)
- [x] Prometheus metrics endpoint still accessible (`/metrics`)
- [x] Sync batch job doesn't require dashboard auth

### Success Criteria
- pass@3 > 90% for capability evals ✅ (100%)
- pass^3 = 100% for regression evals ✅ (100%)

### Test Commands

```bash
# Check secret exists
kubectl get secret -n safety-amp-dev safety-amp-secrets -o jsonpath='{.data.DASHBOARD_API_TOKEN}' | base64 -d

# Check token in safety-amp-agent pod
kubectl exec -n safety-amp-dev deploy/safety-amp-agent -c safety-amp-agent -- env | grep DASHBOARD_API_TOKEN

# Check token in ops-dashboard pod
kubectl exec -n safety-amp-dev deploy/ops-dashboard -- env | grep DASHBOARD_API_TOKEN

# Check nginx config substitution
kubectl exec -n safety-amp-dev deploy/ops-dashboard -- cat /etc/nginx/conf.d/default.conf | grep Dashboard-Token

# Test auth - no token (should return 401)
curl -s https://ops-dashboard.ii-us.com/api/dashboard/cache-stats | jq

# Test auth - wrong token (should return 403)
curl -s -H "X-Dashboard-Token: wrong" https://ops-dashboard.ii-us.com/api/dashboard/cache-stats | jq

# Test auth - correct token (should return 200)
curl -s -H "X-Dashboard-Token: $TOKEN" https://ops-dashboard.ii-us.com/api/dashboard/cache-stats | jq

# Verify health endpoints don't require auth
curl -s https://ops-dashboard.ii-us.com/api/health | jq '.status'
```

### Files Involved
- `routes/dashboard.py` - `require_dashboard_auth` decorator and `_get_dashboard_token()`
- `dashboard/nginx.conf` - Nginx proxy configuration with token injection
- `dashboard/Dockerfile` - Template file setup for envsubst
- `k8s/base/dashboard-deployment.yaml` - DASHBOARD_API_TOKEN env var from secret
- `k8s/base/safety-amp-complete.yaml` - DASHBOARD_API_TOKEN env var from secret
- `k8s/overlays/dev/azure-identity-patch.yaml` - Secret definition with token

### Known Issues Fixed
- 2026-01-30: Token mismatch between ops-dashboard and safety-amp-agent
  - Cause: Pods were started with different secret values
  - Fix: Restart deployments to pick up current secret value
  - Prevention: Ensure both deployments reference same secret key

### Notes
- Nginx's alpine image natively supports `/etc/nginx/templates/*.template` files
- Template files are processed with envsubst at container startup
- The `require_dashboard_auth` decorator fails closed (denies if token not configured)
- Token comparison uses constant-time algorithm to prevent timing attacks
