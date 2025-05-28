import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env from project root
env_path = Path(__file__).resolve().parent.parent / '.env'
load_dotenv(dotenv_path=env_path)

# === SafetyAmp ===
SAFETYAMP_DOMAIN = os.getenv("SAFETYAMP_DOMAIN", "https://api.safetyamp.com")
SAFETYAMP_FQDN = os.getenv("SAFETYAMP_FQDN", "iius.safetyamp.com")
SAFETYAMP_TOKEN = os.getenv("SAFETYAMP_TOKEN")


# === MS Graph API Settings ===
MS_GRAPH_CLIENT_ID = os.getenv("MS_GRAPH_CLIENT_ID")
MS_GRAPH_CLIENT_SECRET = os.getenv("MS_GRAPH_CLIENT_SECRET")
MS_GRAPH_TENANT_ID = os.getenv("MS_GRAPH_TENANT_ID")

# === Samsara ===
SAMSARA_DOMAIN = os.getenv("SAMSARA_DOMAIN", "https://api.samsara.com")
SAMSARA_API_KEY = os.getenv("SAMSARA_API_KEY")

# === Viewpoint (Vista) SQL Server — using Trusted Connection ===
SQL_SERVER = os.getenv("SQL_SERVER")
SQL_DATABASE = os.getenv("SQL_DATABASE")
SQL_DRIVER = os.getenv("SQL_DRIVER", "{ODBC Driver 18 for SQL Server}")
VIEWPOINT_CONN_STRING = (
    f"DRIVER={SQL_DRIVER};"
    f"SERVER={SQL_SERVER};"
    f"DATABASE={SQL_DATABASE};"
    "Trusted_Connection=yes;"
    f"Encrypt=no;"
)

# === Email Settings ===
ALERT_EMAIL_FROM = os.getenv("ALERT_EMAIL_FROM")
ALERT_EMAIL_TO = os.getenv("ALERT_EMAIL_TO")
SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.office365.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", 587))
SMTP_USERNAME = os.getenv("SMTP_USERNAME", "donotreply@ii-us.com")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")

# === Logging ===
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOG_DIR = os.getenv("LOG_DIR", "output/logs")

# === Runtime Settings ===
SYNC_INTERVAL_MINUTES = int(os.getenv("SYNC_INTERVAL_MINUTES", "60"))
PRODUCTION = os.getenv("ENV", "production").lower() == "production"
