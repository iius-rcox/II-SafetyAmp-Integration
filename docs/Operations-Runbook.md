# Operations Runbook

## Daily Checks
- Deployment availability and replica readiness
- Error rates and resource usage below targets
- Last sync time within schedule; no sustained backlogs

## Monitoring
```powershell
# Unified monitoring entrypoint
./deploy/monitor.ps1 -Feature dashboard -Hours 24

# Focused views
./deploy/monitor.ps1 -Feature logs -Hours 6
./deploy/monitor.ps1 -Feature validation -Hours 24
./deploy/monitor.ps1 -Feature changes -Hours 24
./deploy/monitor.ps1 -Feature sync -Hours 1

# Raw kubectl when needed
kubectl logs -f deployment/safety-amp-agent -n safety-amp
kubectl top pods -n safety-amp
kubectl port-forward -n safety-amp svc/safety-amp-service 9090:9090  # /metrics
```

## Common Issues
- Pod CrashLoop:
  - Check events and container logs
  - Validate secrets and env vars
- Ingress unreachable:
  - Verify LB IP, DNS A record, and TLS certs
- 422 validation errors:
  - Ensure required fields (first_name, last_name, email) exist
  - Resolve duplicate emails/phones at source

## Debugging Commands
```bash
kubectl describe pod <pod> -n <ns>
kubectl get events -n <ns> --sort-by=.lastTimestamp | tail -n 50
kubectl get jobs,cronjobs -n safety-amp -o wide
```

## Secrets & Config Updates
```bash
kubectl create secret generic n8n-secrets \
  --from-literal=N8N_ENCRYPTION_KEY="<key>" \
  --from-literal=DB_POSTGRESDB_PASSWORD="<pwd>" \
  -n n8n --dry-run=client -o yaml | kubectl apply -f -
```

## Scaling
```bash
kubectl scale deployment safety-amp-agent --replicas=2 -n safety-amp
```

## Rollback
```bash
kubectl rollout undo deployment/safety-amp-agent -n safety-amp
```

## Success Metrics
- Throughput: ~5000 records/hour
- Error rate: < 5% (excluding 429s)
- CPU < 70%, Memory < 80%

## Alert Response
- Rate limit (429): expected bursts; monitor patterns
- High error rate: check upstream API health
- Backlog: inspect DB connectivity and resources
- Pod crashes: examine logs and resource limits