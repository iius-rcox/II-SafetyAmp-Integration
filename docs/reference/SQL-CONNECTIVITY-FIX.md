# SQL Server Connectivity Fix - Root Cause Analysis

## Summary
Database connectivity failures were caused by **Kubernetes NetworkPolicy blocking egress traffic to port 1433**.

## Root Cause
The NetworkPolicy `safety-amp-integration-netpol` had egress rules allowing:
- ✅ Port 53 (DNS)
- ✅ Port 443 (HTTPS) 
- ✅ Port 80 (HTTP)
- ✅ Port 6379 (Redis)
- ❌ **Port 1433 (SQL Server) - MISSING**

## The Fix
Added single egress rule to NetworkPolicy:
```yaml
- to: []
  ports:
  - protocol: TCP
    port: 1433
```

## What Was NOT the Issue
- ❌ Azure NSG (already allowed 1433 from any source)
- ❌ Windows Firewall on SQL Server
- ❌ Karpenter node overlay networking (all nodes use same overlay)
- ❌ DNS resolution (was working via port 53)
- ❌ Node placement (both systempool and Karpenter nodes work)

## Results
- ✅ SQL Server connectivity working from all nodes
- ✅ First successful sync: **25 created, 7 updated, 1336 skipped**
- ✅ Database queries executing normally
- ✅ No additional node selectors or tolerations needed

## Files Changed
- `k8s/safety-amp/safety-amp-complete.yaml` - Added port 1433 egress rule
- No other infrastructure changes required

## Lesson Learned
Always check Kubernetes NetworkPolicies when troubleshooting connectivity issues. 
They operate at a different layer than Azure NSGs and can silently block traffic.
