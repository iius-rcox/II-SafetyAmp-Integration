import os
from pathlib import Path
from dotenv import load_dotenv
from .azure_key_vault import AzureKeyVault
from .azure_settings import get_azure_config

# Load .env from project root (if it exists)
env_path = Path(__file__).resolve().parent.parent / '.env'
if env_path.exists():
    load_dotenv(dotenv_path=env_path)
else:
    # In production, we should rely on Azure Key Vault and environment variables only
    print("No .env file found, using Azure Key Vault and environment variables only")

# Initialize Azure Key Vault and Azure configuration
key_vault = AzureKeyVault()
azure_config = get_azure_config()

# === SafetyAmp ===
SAFETYAMP_DOMAIN = os.getenv("SAFETYAMP_DOMAIN", "https://api.safetyamp.com")
SAFETYAMP_FQDN = os.getenv("SAFETYAMP_FQDN", "iius.safetyamp.com")
SAFETYAMP_TOKEN = key_vault.get_secret("SAFETYAMP-TOKEN")

# === MS Graph API Settings ===
MS_GRAPH_CLIENT_ID = key_vault.get_secret("MS-GRAPH-CLIENT-ID")
MS_GRAPH_CLIENT_SECRET = key_vault.get_secret("MS-GRAPH-CLIENT-SECRET")
MS_GRAPH_TENANT_ID = key_vault.get_secret("MS-GRAPH-TENANT-ID")

# === Samsara ===
SAMSARA_DOMAIN = os.getenv("SAMSARA_DOMAIN", "https://api.samsara.com")
SAMSARA_API_KEY = key_vault.get_secret("SAMSARA-API-KEY")

# === Viewpoint (Vista) SQL Server — Azure Authentication ===
# Fallback to environment variables if Key Vault is not available
SQL_SERVER = key_vault.get_secret("SQL-SERVER") or os.getenv("SQL_SERVER")
SQL_DATABASE = key_vault.get_secret("SQL-DATABASE") or os.getenv("SQL_DATABASE")
SQL_DRIVER = os.getenv("SQL_DRIVER", "{ODBC Driver 18 for SQL Server}")

# Authentication mode: 'managed_identity' or 'sql_auth'
SQL_AUTH_MODE = os.getenv("SQL_AUTH_MODE", "managed_identity")

# Enhanced connection timeout settings
CONNECTION_TIMEOUT = int(os.getenv("CONNECTION_TIMEOUT", "60"))  # Increased from 30
LOGIN_TIMEOUT = int(os.getenv("LOGIN_TIMEOUT", "60"))  # Added login timeout

if SQL_AUTH_MODE == "managed_identity":
    # Use Azure Workload Identity / Managed Identity
    VIEWPOINT_CONN_STRING = (
        f"DRIVER={SQL_DRIVER};"
        f"SERVER={SQL_SERVER};"
        f"DATABASE={SQL_DATABASE};"
        "Authentication=ActiveDirectoryMSI;"
        "Encrypt=yes;"
        "TrustServerCertificate=yes;"
        f"Connection Timeout={CONNECTION_TIMEOUT};"
        f"Login Timeout={LOGIN_TIMEOUT};"
    )
elif SQL_AUTH_MODE == "sql_auth":
    # Fallback to SQL Authentication using secrets
    SQL_USERNAME = key_vault.get_secret("SQL-USERNAME") or os.getenv("SQL_USERNAME")
    SQL_PASSWORD = key_vault.get_secret("VISTA-SQL-PASSWORD") or os.getenv("VISTA_SQL_PASSWORD")
    VIEWPOINT_CONN_STRING = (
        f"DRIVER={SQL_DRIVER};"
        f"SERVER={SQL_SERVER};"
        f"DATABASE={SQL_DATABASE};"
        f"UID={SQL_USERNAME};"
        f"PWD={SQL_PASSWORD};"
        "Encrypt=yes;"
        "TrustServerCertificate=yes;"
        f"Connection Timeout={CONNECTION_TIMEOUT};"
        f"Login Timeout={LOGIN_TIMEOUT};"
    )
else:
    raise ValueError(f"Invalid SQL_AUTH_MODE: {SQL_AUTH_MODE}. Must be 'managed_identity' or 'sql_auth'")

# Validate required connection parameters
if not SQL_SERVER or not SQL_DATABASE:
    import logging
    logger = logging.getLogger(__name__)
    logger.warning(f"Vista connection may fail: SQL_SERVER={SQL_SERVER}, SQL_DATABASE={SQL_DATABASE}")
    if SQL_AUTH_MODE == "sql_auth" and (not SQL_USERNAME or not SQL_PASSWORD):
        logger.warning("SQL authentication selected but username/password not configured")

# Connection Pool Settings - Enhanced for better reliability
DB_POOL_SIZE = int(os.getenv('DB_POOL_SIZE', '3'))  # Reduced from 5 for testing
DB_MAX_OVERFLOW = int(os.getenv('DB_MAX_OVERFLOW', '5'))  # Reduced from 10
DB_POOL_TIMEOUT = int(os.getenv('DB_POOL_TIMEOUT', '60'))  # Increased from 30
DB_POOL_RECYCLE = int(os.getenv('DB_POOL_RECYCLE', '1800'))  # Reduced from 3600

# === Email Settings ===
ALERT_EMAIL_FROM = key_vault.get_secret("ALERT-EMAIL-FROM")
ALERT_EMAIL_TO = key_vault.get_secret("ALERT-EMAIL-TO")
SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.office365.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", 587))
SMTP_USERNAME = key_vault.get_secret("SMTP-USERNAME")
SMTP_PASSWORD = key_vault.get_secret("SMTP-PASSWORD")

# === Redis Cache Settings ===
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
REDIS_DB = int(os.getenv("REDIS_DB", 0))
REDIS_PASSWORD = os.getenv("REDIS_PASSWORD", None)  # No Redis password by default

# === Logging ===
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOG_DIR = os.getenv("LOG_DIR", "output/logs")

# === Runtime Settings ===
SYNC_INTERVAL_MINUTES = int(os.getenv("SYNC_INTERVAL_MINUTES", "60"))
PRODUCTION = os.getenv("ENV", "production").lower() == "production"

# === Cache Settings ===
CACHE_TTL_HOURS = int(os.getenv("CACHE_TTL_HOURS", "1"))
API_RATE_LIMIT_CALLS = int(os.getenv("API_RATE_LIMIT_CALLS", "60"))
API_RATE_LIMIT_PERIOD = int(os.getenv("API_RATE_LIMIT_PERIOD", "61"))
MAX_RETRY_ATTEMPTS = int(os.getenv("MAX_RETRY_ATTEMPTS", "3"))
RETRY_DELAY_SECONDS = int(os.getenv("RETRY_DELAY_SECONDS", "30"))
