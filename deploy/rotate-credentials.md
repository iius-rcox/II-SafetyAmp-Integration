# 🚨 IMMEDIATE ACTION REQUIRED: Credential Rotation

## Critical Security Issue

The `.env` file in this repository contains **real production secrets** that have been exposed. These credentials must be rotated **immediately**.

## Exposed Credentials to Rotate

### 1. SafetyAmp API Token ✅ **HIGHEST PRIORITY**
- **Token**: `eyJ0eXAiOiJKV1QiLCJhbGciOiJSUzI1NiJ9...` (EXPOSED)
- **Action**: Generate new API token in SafetyAmp dashboard
- **Location**: SafetyAmp admin panel → API Keys

### 2. Microsoft Graph Client Secret ✅ **HIGH PRIORITY**
- **Client ID**: `73b82823-d860-4bf6-938b-74deabeebab7`
- **Secret**: `T~k8Q~jQjVIaJML57NYDZBKph3BXdeEJcDt4vb~c` (EXPOSED)
- **Action**: 
  1. Go to Azure Portal → App Registrations
  2. Find app `73b82823-d860-4bf6-938b-74deabeebab7`
  3. Generate new client secret
  4. Remove old secret

### 3. Samsara API Key ✅ **HIGH PRIORITY**
- **Key**: `samsara_api_8pbhuGqktwraLrf9MyhXWVK3kXaX6v` (EXPOSED)
- **Action**: Generate new API key in Samsara dashboard
- **Location**: Samsara Cloud → Settings → API Tokens

### 4. SMTP Password (if exists)
- **Action**: Reset email service password
- **Location**: Office 365 admin center or email provider

## Immediate Actions (Do Now)

### Step 1: Remove Exposed .env File
```bash
# Remove from repository (if committed)
git rm .env
git commit -m "Remove exposed .env file with secrets"

# Or simply delete locally
rm .env
```

### Step 2: Store Secrets in Azure Key Vault
```bash
# Add rotated secrets to Key Vault
az keyvault secret set --vault-name "your-keyvault" --name "SAFETYAMP-TOKEN" --value "new_token_here"
az keyvault secret set --vault-name "your-keyvault" --name "MS-GRAPH-CLIENT-SECRET" --value "new_secret_here"
az keyvault secret set --vault-name "your-keyvault" --name "SAMSARA-API-KEY" --value "new_key_here"
```

### Step 3: Update Application Configuration
The application is already configured to use Azure Key Vault via the `config/azure_key_vault.py` module.

### Step 4: Test New Credentials
```bash
# Test the application with new credentials
kubectl logs -f deployment/safety-amp-agent -n safety-amp
```

## Key Vault Secret Names

The application expects these secret names in Azure Key Vault:

| Application Variable | Key Vault Secret Name |
|---------------------|----------------------|
| `SAFETYAMP_TOKEN` | `SAFETYAMP-TOKEN` |
| `MS_GRAPH_CLIENT_SECRET` | `MS-GRAPH-CLIENT-SECRET` |
| `MS_GRAPH_CLIENT_ID` | `MS-GRAPH-CLIENT-ID` |
| `MS_GRAPH_TENANT_ID` | `MS-GRAPH-TENANT-ID` |
| `SAMSARA_API_KEY` | `SAMSARA-API-KEY` |
| `SQL_SERVER` | `SQL-SERVER` |
| `SQL_DATABASE` | `SQL-DATABASE` |
| `SQL_USERNAME` | `SQL-USERNAME` (only if using sql_auth mode) |
| `SQL_PASSWORD` | `SQL-PASSWORD` (only if using sql_auth mode) |
| `SMTP_USERNAME` | `SMTP-USERNAME` |
| `SMTP_PASSWORD` | `SMTP-PASSWORD` |
| `ALERT_EMAIL_FROM` | `ALERT-EMAIL-FROM` |
| `ALERT_EMAIL_TO` | `ALERT-EMAIL-TO` |

## Verification Steps

1. **Check Key Vault Access**:
   ```bash
   az keyvault secret list --vault-name "your-keyvault" --query "[].name" -o table
   ```

2. **Test Application Startup**:
   ```bash
   kubectl get pods -n safety-amp
   kubectl logs deployment/safety-amp-agent -n safety-amp
   ```

3. **Verify Health Endpoints**:
   ```bash
   kubectl port-forward svc/safety-amp-service 8080:8080 -n safety-amp
   curl http://localhost:8080/health
   ```

## Security Best Practices Going Forward

1. **Never commit .env files** with real secrets
2. **Use .env.template** for documentation
3. **Store all secrets in Azure Key Vault**
4. **Use Managed Identity** for authentication where possible
5. **Rotate credentials regularly** (quarterly recommended)
6. **Monitor for exposed secrets** using tools like:
   - GitHub secret scanning
   - Azure Security Center
   - SIEM alerts on unusual API usage

## Impact Assessment

### SafetyAmp Token
- **Risk**: Complete access to SafetyAmp data and API
- **Mitigation**: Rotate immediately, monitor for unusual activity

### Microsoft Graph Secret
- **Risk**: Access to Office 365 data and Graph API
- **Mitigation**: Rotate immediately, review audit logs

### Samsara API Key
- **Risk**: Access to fleet/vehicle data
- **Mitigation**: Rotate immediately, check access logs

## Emergency Contacts

If you need immediate assistance:
1. Contact your Azure administrator
2. Contact SafetyAmp support
3. Contact Microsoft Graph API administrator
4. Contact Samsara account manager

---

**⚠️ DO NOT DELAY: These credentials should be rotated within 1 hour of discovery.**