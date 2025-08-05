# Vista Connection Issues - Diagnosis and Fix

## Issues Found

### 1. **Missing ODBC Driver** ✅ FIXED
- **Problem**: Microsoft ODBC Driver 18 for SQL Server was not installed
- **Error**: `Can't open lib 'ODBC Driver 18 for SQL Server' : file not found`
- **Solution**: Installed `msodbcsql18` package

### 2. **Azure Key Vault Not Configured** ✅ IDENTIFIED
- **Problem**: `AZURE_KEY_VAULT_URL` environment variable not set
- **Impact**: SQL Server credentials cannot be retrieved from Key Vault
- **Result**: `SQL_SERVER` and `SQL_DATABASE` are `None`

### 3. **Connection Timeout Issues** ✅ FIXED
- **Problem**: Default 30-second timeouts were too short
- **Solution**: Increased timeouts to 60 seconds and added retry logic
- **Enhanced**: Added exponential backoff and better error handling

### 4. **Poor Error Diagnostics** ✅ FIXED
- **Problem**: Generic error messages made troubleshooting difficult
- **Solution**: Added detailed error analysis and configuration validation

## Fixes Implemented

### 1. Enhanced Configuration (`config/settings.py`)
```python
# Fallback to environment variables if Key Vault unavailable
SQL_SERVER = key_vault.get_secret("SQL-SERVER") or os.getenv("SQL_SERVER")
SQL_DATABASE = key_vault.get_secret("SQL-DATABASE") or os.getenv("SQL_DATABASE")

# Enhanced timeout settings
CONNECTION_TIMEOUT = int(os.getenv("CONNECTION_TIMEOUT", "60"))
LOGIN_TIMEOUT = int(os.getenv("LOGIN_TIMEOUT", "60"))

# Better connection pool settings
DB_POOL_SIZE = int(os.getenv('DB_POOL_SIZE', '3'))
DB_POOL_TIMEOUT = int(os.getenv('DB_POOL_TIMEOUT', '60'))
```

### 2. Improved ViewpointAPI (`services/viewpoint_api.py`)
- **Configuration validation**: Checks for missing server/database before attempting connection
- **Retry logic**: 3 attempts with exponential backoff
- **Better error handling**: Distinguishes between timeout, authentication, and network errors
- **Connection testing**: Added `test_connection()` method for diagnostics

### 3. Enhanced Test Script (`test-connections.py`)
- **Configuration diagnostics**: Shows current settings before testing
- **Fallback testing**: Tries SQL authentication if managed identity fails
- **Specific error guidance**: Provides targeted troubleshooting advice
- **Better reporting**: Clear status and recommendations

## How to Fix Vista Connection

### Option 1: Configure Azure Key Vault (Production)
```bash
export AZURE_KEY_VAULT_URL="https://your-keyvault.vault.azure.net/"
```

### Option 2: Use Environment Variables (Development/Testing)
```bash
export SQL_SERVER="your-server.database.windows.net"
export SQL_DATABASE="your-database-name"
export SQL_AUTH_MODE="sql_auth"  # or "managed_identity"
export TEST_SQL_USERNAME="your-username"
export TEST_SQL_PASSWORD="your-password"
```

### Option 3: Use .env File
Create `.env` file with:
```env
SQL_SERVER=your-server.database.windows.net
SQL_DATABASE=your-database-name
SQL_AUTH_MODE=sql_auth
TEST_SQL_USERNAME=your-username
TEST_SQL_PASSWORD=your-password
```

## Testing the Fix

Run the enhanced test script:
```bash
python test-connections.py
```

The script will:
1. Show current configuration
2. Test managed identity authentication
3. Fall back to SQL authentication if available
4. Provide specific troubleshooting guidance

## Connection Flow After Fix

1. **Configuration Check**: Validates SQL_SERVER and SQL_DATABASE are set
2. **Authentication**: Tries configured auth mode (managed identity or SQL auth)
3. **Retry Logic**: 3 attempts with increasing delays (5s, 7.5s, 11.25s)
4. **Error Analysis**: Provides specific guidance based on error type
5. **Fallback Testing**: Tests alternative authentication if primary fails

## Monitoring and Debugging

### Enable Debug Logging
```python
# In viewpoint_api.py, set echo=True for SQL debugging
self.engine = create_engine(sqlalchemy_url, echo=True, ...)
```

### Check Connection Pool Status
```python
from services.viewpoint_api import ViewpointAPI
api = ViewpointAPI()
print(f"Pool size: {api.engine.pool.size()}")
print(f"Checked out: {api.engine.pool.checkedout()}")
```

### Test Individual Components
```python
# Test just the connection
api = ViewpointAPI()
success = api.test_connection()

# Test with specific timeout
with api._get_connection(max_retries=1) as conn:
    result = api._fetch_query(conn, "SELECT 1")
```

## Environment Variables Reference

| Variable | Purpose | Default | Required |
|----------|---------|---------|----------|
| `SQL_SERVER` | SQL Server hostname | None | Yes |
| `SQL_DATABASE` | Database name | None | Yes |
| `SQL_AUTH_MODE` | Authentication mode | managed_identity | No |
| `CONNECTION_TIMEOUT` | Connection timeout (s) | 60 | No |
| `LOGIN_TIMEOUT` | Login timeout (s) | 60 | No |
| `DB_POOL_TIMEOUT` | Pool timeout (s) | 60 | No |
| `DB_POOL_SIZE` | Pool size | 3 | No |
| `AZURE_KEY_VAULT_URL` | Key Vault URL | None | Production |

## Production Checklist

- [ ] Azure Key Vault configured with proper URL
- [ ] SQL Server credentials stored in Key Vault
- [ ] Managed Identity has database access permissions
- [ ] Network connectivity verified (port 1433)
- [ ] SQL Server firewall allows connections
- [ ] Connection pooling settings optimized
- [ ] Monitoring and alerting configured

## Next Steps

1. **Configure credentials**: Set up either Key Vault or environment variables
2. **Test connection**: Run the test script to verify fixes
3. **Monitor performance**: Check connection pool metrics
4. **Optimize settings**: Adjust timeouts and pool sizes based on usage
5. **Set up alerting**: Monitor for connection failures in production