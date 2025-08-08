# Security & Governance

## NetworkPolicy (metrics)
- Allow scrape to `:9090` only from monitoring namespace (Managed Prometheus agents)
- Deny other cross-namespace ingress by default

## RBAC
- Grafana: Azure AD SSO; readers vs admins
- Log Analytics: workspace access limited to ops/eng; read-only dashboards for stakeholders

## Data retention & cost
- Log Analytics retention: 30–90 days
- Limit Fluent Bit inputs to essential files; avoid high-volume logs
- Prefer metrics for high-frequency observability

## Secrets
- Store Log Analytics workspace ID/key in Kubernetes Secret
- Use Azure Workload Identity for app → Key Vault
