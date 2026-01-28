import os
import logging
from pathlib import Path
from typing import Optional, Dict, Any, Callable, TypeVar

try:
    # dotenv is optional; used in local/dev
    from dotenv import load_dotenv  # type: ignore
except Exception:  # pragma: no cover

    def load_dotenv(*args, **kwargs):
        return False


# Azure SDK imports are optional at import-time; code handles absence gracefully
try:
    from azure.identity import DefaultAzureCredential, ManagedIdentityCredential  # type: ignore
    from azure.keyvault.secrets import SecretClient  # type: ignore

    AZURE_SDK_AVAILABLE = True
except Exception:
    DefaultAzureCredential = object  # type: ignore
    ManagedIdentityCredential = object  # type: ignore
    SecretClient = object  # type: ignore
    AZURE_SDK_AVAILABLE = False


logger = logging.getLogger(__name__)


_T = TypeVar("_T")


class ConfigManager:
    """Unified configuration manager for environment variables and Azure Key Vault.

    Responsibilities:
    - Loads optional .env from project root for local dev
    - Initializes Azure credentials and Key Vault client (if configured)
    - Provides get_env / get_secret helpers with caching and fallbacks
    - Computes and exposes application settings as attributes
    """

    def __init__(self) -> None:
        self._load_dotenv_from_project_root()

        # Azure Key Vault
        # Support either AZURE_KEY_VAULT_URL or AZURE_KEY_VAULT_NAME
        self.azure_key_vault_url: Optional[str] = os.getenv("AZURE_KEY_VAULT_URL")
        azure_kv_name = os.getenv("AZURE_KEY_VAULT_NAME")
        if not self.azure_key_vault_url and azure_kv_name:
            self.azure_key_vault_url = f"https://{azure_kv_name}.vault.azure.net"
        self._azure_credential: Optional[object] = None
        self._azure_secret_client: Optional[object] = None
        self._secrets_cache: Dict[str, str] = {}

        self._initialize_azure()
        self._load_settings()

    # ---------- Initialization helpers ----------
    def _load_dotenv_from_project_root(self) -> None:
        env_path = Path(__file__).resolve().parent.parent / ".env"
        try:
            if env_path.exists():
                load_dotenv(dotenv_path=env_path)
            else:
                logger.debug(
                    "No .env file found; relying on Key Vault and environment variables"
                )
        except Exception as exc:  # pragma: no cover
            logger.warning(f"Failed to load .env: {exc}")

    def _initialize_azure(self) -> None:
        if not self.azure_key_vault_url:
            logger.info("AZURE_KEY_VAULT_URL not set; Azure Key Vault disabled")
            return

        if not AZURE_SDK_AVAILABLE:
            logger.warning("Azure SDK packages not available; Key Vault disabled")
            return

        # Prefer managed identity if available; fallback to default chain
        try:
            try:
                # Prefer DefaultAzureCredential to support AKS Workload Identity, then fallback
                self._azure_credential = DefaultAzureCredential()
                logger.info("Using DefaultAzureCredential for Azure authentication")
            except Exception as exc:
                logger.debug(f"DefaultAzureCredential not available: {exc}")
                self._azure_credential = ManagedIdentityCredential()
                logger.info("Using ManagedIdentityCredential for Azure authentication")

            self._azure_secret_client = SecretClient(
                vault_url=self.azure_key_vault_url,
                credential=self._azure_credential,  # type: ignore[arg-type]
            )
            logger.info(
                f"Azure Key Vault client initialized: {self.azure_key_vault_url}"
            )
        except Exception as exc:
            logger.error(f"Failed to initialize Azure Key Vault: {exc}")
            self._azure_secret_client = None

    # ---------- Public helpers ----------
    def get_env(
        self,
        name: str,
        default: Optional[_T] = None,
        cast: Optional[Callable[[str], _T]] = None,
    ) -> Optional[_T]:
        value = os.getenv(name)
        if value is None:
            return default
        if cast is None:
            return value  # type: ignore[return-value]
        try:
            return cast(value)
        except Exception:
            logger.warning(f"Failed to cast env var {name}; using default")
            return default

    def clear_secret_cache(self) -> None:
        self._secrets_cache.clear()

    def get_secret(
        self, secret_name: str, default: Optional[str] = None, use_cache: bool = True
    ) -> Optional[str]:
        # Cache
        if use_cache and secret_name in self._secrets_cache:
            return self._secrets_cache[secret_name]

        # Try Key Vault
        if self._azure_secret_client is not None:
            try:
                secret = self._azure_secret_client.get_secret(secret_name)  # type: ignore[attr-defined]
                value = getattr(secret, "value", None)
                if value is not None:
                    if use_cache:
                        self._secrets_cache[secret_name] = value
                    return value
            except Exception as exc:
                logger.warning(
                    f"Key Vault get_secret failed for '{secret_name}': {exc}"
                )

        # Fallback to environment variable
        fallback = os.getenv(secret_name, default)
        if fallback is not None and use_cache:
            self._secrets_cache[secret_name] = fallback
        return fallback

    def set_secret(self, secret_name: str, secret_value: str) -> bool:
        if self._azure_secret_client is None:
            logger.warning("Azure Key Vault not available; cannot set secret")
            return False
        try:
            self._azure_secret_client.set_secret(secret_name, secret_value)  # type: ignore[attr-defined]
            # Update cache
            self._secrets_cache[secret_name] = secret_value
            logger.info(f"Set secret '{secret_name}' in Azure Key Vault")
            return True
        except Exception as exc:
            logger.error(f"Failed to set secret '{secret_name}' in Key Vault: {exc}")
            return False

    def get_azure_environment_config(self) -> Dict[str, Any]:
        return {
            "azure_key_vault_enabled": self._azure_secret_client is not None,
            "azure_key_vault_url": self.azure_key_vault_url,
            "azure_managed_identity_enabled": isinstance(
                self._azure_credential, ManagedIdentityCredential
            ),
        }

    # ---------- Settings loading ----------
    def _load_settings(self) -> None:
        # === SafetyAmp ===
        self.SAFETYAMP_DOMAIN: str = self.get_env("SAFETYAMP_DOMAIN", "https://api.safetyamp.com")  # type: ignore[assignment]
        self.SAFETYAMP_FQDN: str = self.get_env("SAFETYAMP_FQDN", "iius.safetyamp.com")  # type: ignore[assignment]
        self.SAFETYAMP_TOKEN: Optional[str] = self.get_secret("SAFETYAMP-TOKEN")

        # === MS Graph ===
        self.MS_GRAPH_CLIENT_ID: Optional[str] = self.get_secret("MS-GRAPH-CLIENT-ID")
        self.MS_GRAPH_CLIENT_SECRET: Optional[str] = self.get_secret(
            "MS-GRAPH-CLIENT-SECRET"
        )
        self.MS_GRAPH_TENANT_ID: Optional[str] = self.get_secret("MS-GRAPH-TENANT-ID")

        # === Samsara ===
        self.SAMSARA_DOMAIN: str = self.get_env("SAMSARA_DOMAIN", "https://api.samsara.com")  # type: ignore[assignment]
        self.SAMSARA_API_KEY: Optional[str] = self.get_secret("SAMSARA-API-KEY")

        # === SQL Server / Viewpoint ===
        self.SQL_SERVER: Optional[str] = self.get_secret("SQL-SERVER")
        self.SQL_DATABASE: Optional[str] = self.get_secret("SQL-DATABASE")
        self.SQL_DRIVER: str = self.get_env("SQL_DRIVER", "{ODBC Driver 18 for SQL Server}")  # type: ignore[assignment]
        self.SQL_AUTH_MODE: str = (
            self.get_env("SQL_AUTH_MODE", "managed_identity") or "managed_identity"
        ).lower()

        self.VIEWPOINT_CONN_STRING: str = self._build_viewpoint_connection_string()

        # Connection Pool
        self.DB_POOL_SIZE: int = int(self.get_env("DB_POOL_SIZE", "5"))
        self.DB_MAX_OVERFLOW: int = int(self.get_env("DB_MAX_OVERFLOW", "10"))
        self.DB_POOL_TIMEOUT: int = int(self.get_env("DB_POOL_TIMEOUT", "300"))
        self.DB_POOL_RECYCLE: int = int(self.get_env("DB_POOL_RECYCLE", "3600"))

        # Email
        self.ALERT_EMAIL_FROM: Optional[str] = self.get_secret("ALERT-EMAIL-FROM")
        self.ALERT_EMAIL_TO: Optional[str] = self.get_secret("ALERT-EMAIL-TO")
        self.SMTP_SERVER: str = self.get_env("SMTP_SERVER", "smtp.office365.com")  # type: ignore[assignment]
        self.SMTP_PORT: int = int(self.get_env("SMTP_PORT", 587))
        self.SMTP_USERNAME: Optional[str] = self.get_secret("SMTP-USERNAME")
        self.SMTP_PASSWORD: Optional[str] = self.get_secret("SMTP-PASSWORD")

        # Redis
        self.REDIS_HOST: str = self.get_env("REDIS_HOST", "localhost")  # type: ignore[assignment]
        self.REDIS_PORT: int = int(self.get_env("REDIS_PORT", 6379))
        self.REDIS_DB: int = int(self.get_env("REDIS_DB", 0))
        self.REDIS_PASSWORD: Optional[str] = self.get_env(
            "REDIS_PASSWORD", None
        )  # no default password

        # Logging
        self.LOG_LEVEL: str = self.get_env("LOG_LEVEL", "INFO")  # type: ignore[assignment]
        self.LOG_DIR: str = self.get_env("LOG_DIR", "output/logs")  # type: ignore[assignment]
        self.LOG_FORMAT: str = (self.get_env("LOG_FORMAT", "text") or "text").lower()
        self.STRUCTURED_LOGGING_ENABLED: bool = (
            (self.get_env("STRUCTURED_LOGGING_ENABLED", "") or "").lower()
            in ("1", "true", "yes")
        ) or self.LOG_FORMAT == "json"

        # Runtime
        self.SYNC_INTERVAL_MINUTES: int = int(
            self.get_env("SYNC_INTERVAL_MINUTES", "60")
        )
        self.VISTA_REFRESH_MINUTES: int = int(
            self.get_env("VISTA_REFRESH_MINUTES", "30")
        )
        self.PRODUCTION: bool = (
            self.get_env("ENV", "production") or "production"
        ).lower() == "production"

        # Cache / Retry / HTTP
        self.CACHE_TTL_HOURS: int = int(self.get_env("CACHE_TTL_HOURS", "4"))
        self.CACHE_REFRESH_INTERVAL_HOURS: int = int(
            self.get_env("CACHE_REFRESH_INTERVAL_HOURS", "4")
        )
        self.API_RATE_LIMIT_CALLS: int = int(self.get_env("API_RATE_LIMIT_CALLS", "60"))
        self.API_RATE_LIMIT_PERIOD: int = int(
            self.get_env("API_RATE_LIMIT_PERIOD", "61")
        )
        self.MAX_RETRY_ATTEMPTS: int = int(self.get_env("MAX_RETRY_ATTEMPTS", "3"))
        self.RETRY_DELAY_SECONDS: int = int(self.get_env("RETRY_DELAY_SECONDS", "30"))
        self.HTTP_REQUEST_TIMEOUT: int = int(self.get_env("HTTP_REQUEST_TIMEOUT", "15"))

        # Failed Sync Tracker
        self.FAILED_SYNC_TRACKER_ENABLED: bool = (
            self.get_env("FAILED_SYNC_TRACKER_ENABLED", "true") or "true"
        ).lower() in ("1", "true", "yes")
        self.FAILED_SYNC_TTL_DAYS: int = int(self.get_env("FAILED_SYNC_TTL_DAYS", "7"))

    def _build_viewpoint_connection_string(self) -> str:
        if self.SQL_AUTH_MODE == "managed_identity":
            return (
                f"DRIVER={self.SQL_DRIVER};"
                f"SERVER={self.SQL_SERVER};"
                f"DATABASE={self.SQL_DATABASE};"
                "Authentication=ActiveDirectoryMSI;"
                "Encrypt=yes;"
                "TrustServerCertificate=yes;"
                "MultiSubnetFailover=Yes;"
                "Login Timeout=30;"
                "Connection Timeout=30;"
                "Connect Timeout=30;"
                "Command Timeout=60;"
            )
        if self.SQL_AUTH_MODE == "sql_auth":
            sql_username = self.get_secret("SQL-USERNAME")
            sql_password = self.get_secret("VISTA-SQL-PASSWORD")
            return (
                f"DRIVER={self.SQL_DRIVER};"
                f"SERVER={self.SQL_SERVER};"
                f"DATABASE={self.SQL_DATABASE};"
                f"UID={sql_username};"
                f"PWD={sql_password};"
                "Encrypt=yes;"
                "TrustServerCertificate=yes;"
                "MultiSubnetFailover=Yes;"
                "Login Timeout=30;"
                "Connection Timeout=30;"
                "Connect Timeout=30;"
                "Command Timeout=60;"
            )
        raise ValueError(
            f"Invalid SQL_AUTH_MODE: {self.SQL_AUTH_MODE}. Must be 'managed_identity' or 'sql_auth'"
        )

    # ---------- Validation and status ----------
    def validate_required_secrets(self) -> bool:
        """Validate presence of required configuration and secrets.

        Rules:
        - Always require SQL server and database identifiers
        - SAFETYAMP token is required for API access
        - If SQL auth mode, require SQL-USERNAME and VISTA-SQL-PASSWORD
        """
        missing: list[str] = []

        def require(name: str, value: object) -> None:
            if value in (None, "", False):
                missing.append(name)

        require("SQL-SERVER", self.SQL_SERVER)
        require("SQL-DATABASE", self.SQL_DATABASE)
        require("SAFETYAMP-TOKEN", self.SAFETYAMP_TOKEN)

        if self.SQL_AUTH_MODE == "sql_auth":
            require("SQL-USERNAME", self.get_secret("SQL-USERNAME"))
            require("VISTA-SQL-PASSWORD", self.get_secret("VISTA-SQL-PASSWORD"))

        # Email is optional but recommended for notifications
        # Redis password optional; host/port have defaults

        self._last_validation_missing = missing  # type: ignore[attr-defined]
        return len(missing) == 0

    def get_configuration_status(self) -> dict:
        """Return a redacted, structured view of configuration status for logging/health."""

        def mask(value: object) -> object:
            if value is None or value is False:
                return None
            if isinstance(value, str):
                if len(value) <= 4:
                    return "****"
                return value[:2] + "****" + value[-2:]
            return "set"

        validation_ok = self.validate_required_secrets()
        missing = getattr(self, "_last_validation_missing", [])  # type: ignore[attr-defined]

        return {
            "validation": {
                "is_valid": validation_ok,
                "missing": missing,
            },
            "azure": self.get_azure_environment_config(),
            "secrets": {
                "SAFETYAMP_TOKEN": mask(self.SAFETYAMP_TOKEN),
                "MS_GRAPH_CLIENT_ID": mask(self.MS_GRAPH_CLIENT_ID),
                "MS_GRAPH_TENANT_ID": mask(self.MS_GRAPH_TENANT_ID),
                "SAMSARA_API_KEY": mask(self.SAMSARA_API_KEY),
                "SMTP_USERNAME": mask(self.SMTP_USERNAME),
                "SMTP_PASSWORD": mask(self.SMTP_PASSWORD),
            },
            "env": {
                "SQL_SERVER": self.SQL_SERVER,
                "SQL_DATABASE": self.SQL_DATABASE,
                "SQL_AUTH_MODE": self.SQL_AUTH_MODE,
                "REDIS_HOST": self.REDIS_HOST,
                "REDIS_PORT": self.REDIS_PORT,
                "LOG_FORMAT": self.LOG_FORMAT,
                "STRUCTURED_LOGGING_ENABLED": self.STRUCTURED_LOGGING_ENABLED,
                "PRODUCTION": self.PRODUCTION,
            },
        }


# Singleton config instance
config = ConfigManager()
# Back-compat alias: allow 'from config import settings'
settings = config


# Backward-compatible module-level constants to minimize code changes elsewhere
# These mirror the names previously defined in config.settings
SAFETYAMP_DOMAIN = config.SAFETYAMP_DOMAIN
SAFETYAMP_FQDN = config.SAFETYAMP_FQDN
SAFETYAMP_TOKEN = config.SAFETYAMP_TOKEN

MS_GRAPH_CLIENT_ID = config.MS_GRAPH_CLIENT_ID
MS_GRAPH_CLIENT_SECRET = config.MS_GRAPH_CLIENT_SECRET
MS_GRAPH_TENANT_ID = config.MS_GRAPH_TENANT_ID

SAMSARA_DOMAIN = config.SAMSARA_DOMAIN
SAMSARA_API_KEY = config.SAMSARA_API_KEY

SQL_SERVER = config.SQL_SERVER
SQL_DATABASE = config.SQL_DATABASE
SQL_DRIVER = config.SQL_DRIVER
SQL_AUTH_MODE = config.SQL_AUTH_MODE
VIEWPOINT_CONN_STRING = config.VIEWPOINT_CONN_STRING

DB_POOL_SIZE = config.DB_POOL_SIZE
DB_MAX_OVERFLOW = config.DB_MAX_OVERFLOW
DB_POOL_TIMEOUT = config.DB_POOL_TIMEOUT
DB_POOL_RECYCLE = config.DB_POOL_RECYCLE

ALERT_EMAIL_FROM = config.ALERT_EMAIL_FROM
ALERT_EMAIL_TO = config.ALERT_EMAIL_TO
SMTP_SERVER = config.SMTP_SERVER
SMTP_PORT = config.SMTP_PORT
SMTP_USERNAME = config.SMTP_USERNAME
SMTP_PASSWORD = config.SMTP_PASSWORD

REDIS_HOST = config.REDIS_HOST
REDIS_PORT = config.REDIS_PORT
REDIS_DB = config.REDIS_DB
REDIS_PASSWORD = config.REDIS_PASSWORD

LOG_LEVEL = config.LOG_LEVEL
LOG_DIR = config.LOG_DIR
LOG_FORMAT = config.LOG_FORMAT
STRUCTURED_LOGGING_ENABLED = config.STRUCTURED_LOGGING_ENABLED

SYNC_INTERVAL_MINUTES = config.SYNC_INTERVAL_MINUTES
PRODUCTION = config.PRODUCTION

CACHE_TTL_HOURS = config.CACHE_TTL_HOURS
CACHE_REFRESH_INTERVAL_HOURS = config.CACHE_REFRESH_INTERVAL_HOURS
API_RATE_LIMIT_CALLS = config.API_RATE_LIMIT_CALLS
API_RATE_LIMIT_PERIOD = config.API_RATE_LIMIT_PERIOD
MAX_RETRY_ATTEMPTS = config.MAX_RETRY_ATTEMPTS
RETRY_DELAY_SECONDS = config.RETRY_DELAY_SECONDS
HTTP_REQUEST_TIMEOUT = config.HTTP_REQUEST_TIMEOUT


def get_config() -> ConfigManager:
    return config
