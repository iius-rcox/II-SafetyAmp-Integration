# Cost Guardrails

- Prefer metrics for frequent/aggregate signals; logs for details/audit only
- Limit Fluent Bit tail patterns to essential JSON files
- Set Log Analytics retention to 30–90 days
- Consider sampling or dropping verbose lines if needed
- Review ingestion costs weekly during rollout; adapt patterns
