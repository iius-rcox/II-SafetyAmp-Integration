# SQL Server Windows Firewall Configuration

## Issue
AKS pods (running on systempool nodes) can resolve DNS for `inscolvsql.insulationsinc.local` but cannot connect to port 1433 because the Windows Firewall on the SQL Server VM blocks the AKS pod network.

## Solution
Add a Windows Firewall rule on INSCOLVSQL (10.0.0.5) to allow inbound TCP port 1433 from the AKS pod network.

### Option 1: PowerShell (on INSCOLVSQL VM)
```powershell
New-NetFirewallRule -DisplayName "Allow SQL from AKS Pods" `
  -Direction Inbound `
  -Protocol TCP `
  -LocalPort 1433 `
  -RemoteAddress 10.244.0.0/16 `
  -Action Allow `
  -Profile Any `
  -Enabled True
```

### Option 2: Windows Firewall GUI (on INSCOLVSQL VM)
1. Open Windows Firewall with Advanced Security
2. Click "Inbound Rules" → "New Rule"
3. Rule Type: Port
4. Protocol: TCP, Specific local ports: 1433
5. Action: Allow the connection
6. Profile: All
7. Name: "Allow SQL from AKS Pods"
8. In "Scope" tab, add Remote IP: 10.244.0.0/16

### Verification
After adding the rule, test from AKS pod:
```bash
kubectl exec -n safety-amp <pod-name> -c safety-amp-agent -- python -c "import socket; s = socket.socket(); s.settimeout(5); result = s.connect_ex(('10.0.0.5', 1433)); print('Connected' if result == 0 else f'Failed: {result}'); s.close()"
```

## Why This is Needed
- AKS Automatic cluster uses Azure CNI Overlay mode
- Pods get IPs from 10.244.0.0/16 (overlay network)
- Cannot change pod subnet in AKS Automatic clusters
- Azure NSG already allows port 1433 from any source
- Windows Firewall is the blocking layer

## Current Configuration
- **Cluster**: AKS Automatic SKU with Karpenter
- **Nodes**: systempool (10.0.0.x) with CriticalAddonsOnly taint
- **Pods**: Overlay network (10.244.x.x)
- **SQL Server**: INSCOLVSQL at 10.0.0.5 on default subnet
- **DNS**: ✅ Working (inscolvsql.insulationsinc.local → 10.0.0.5)
- **TCP 1433**: ❌ Blocked by Windows Firewall
