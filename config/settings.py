import os
from pathlib import Path
from dotenv import load_dotenv
from .azure_key_vault import AzureKeyVault

# Load .env from project root
env_path = Path(__file__).resolve().parent.parent / '.env'
load_dotenv(dotenv_path=env_path)

# Initialize Azure Key Vault
key_vault = AzureKeyVault()

# === SafetyAmp ===
SAFETYAMP_DOMAIN = os.getenv("SAFETYAMP_DOMAIN", "https://api.safetyamp.com")
SAFETYAMP_FQDN = os.getenv("SAFETYAMP_FQDN", "iius.safetyamp.com")
SAFETYAMP_TOKEN = key_vault.get_secret("SAFETYAMP_TOKEN")

# === MS Graph API Settings ===
MS_GRAPH_CLIENT_ID = key_vault.get_secret("MS_GRAPH_CLIENT_ID")
MS_GRAPH_CLIENT_SECRET = key_vault.get_secret("MS_GRAPH_CLIENT_SECRET")
MS_GRAPH_TENANT_ID = key_vault.get_secret("MS_GRAPH_TENANT_ID")

# === Samsara ===
SAMSARA_DOMAIN = os.getenv("SAMSARA_DOMAIN", "https://api.samsara.com")
SAMSARA_API_KEY = key_vault.get_secret("SAMSARA_API_KEY")

# === Viewpoint (Vista) SQL Server — using Trusted Connection ===
SQL_SERVER = key_vault.get_secret("SQL_SERVER")
SQL_DATABASE = key_vault.get_secret("SQL_DATABASE")
SQL_DRIVER = os.getenv("SQL_DRIVER", "{ODBC Driver 18 for SQL Server}")
VIEWPOINT_CONN_STRING = (
    f"DRIVER={SQL_DRIVER};"
    f"SERVER={SQL_SERVER};"
    f"DATABASE={SQL_DATABASE};"
    "Trusted_Connection=yes;"
    f"Encrypt=no;"
)

# === Email Settings ===
ALERT_EMAIL_FROM = key_vault.get_secret("ALERT_EMAIL_FROM")
ALERT_EMAIL_TO = key_vault.get_secret("ALERT_EMAIL_TO")
SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.office365.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", 587))
SMTP_USERNAME = key_vault.get_secret("SMTP_USERNAME", "donotreply@ii-us.com")
SMTP_PASSWORD = key_vault.get_secret("SMTP_PASSWORD")

# === Redis Cache Settings ===
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
REDIS_DB = int(os.getenv("REDIS_DB", 0))
REDIS_PASSWORD = key_vault.get_secret("REDIS_PASSWORD")

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
