import os
import logging
from pathlib import Path
from typing import Optional, Dict, Any

try:
    from dotenv import load_dotenv
except Exception:  # pragma: no cover
    def load_dotenv(*args, **kwargs):
        return False

# Azure SDK imports
try:
    from azure.identity import DefaultAzureCredential, ManagedIdentityCredential
    from azure.keyvault.secrets import SecretClient
    from azure.core.exceptions import AzureError
except Exception:  # pragma: no cover - allow running without Azure libs in some environments
    DefaultAzureCredential = None  # type: ignore
    ManagedIdentityCredential = None  # type: ignore
    SecretClient = None  # type: ignore
    AzureError = Exception  # type: ignore


class ConfigManager:
    """Unified configuration manager for environment variables and Azure Key Vault."""

    def __init__(self) -> None:
        self._logger = logging.getLogger(__name__)
        self._secrets_cache: Dict[str, str] = {}

        # Initialize environment
        self._initialize_environment()

        # Initialize Azure Key Vault
        self.key_vault_url: Optional[str] = None
        self.credential: Optional[Any] = None
        self.secret_client: Optional[Any] = None
        self._initialize_azure()

        # Load all settings
        self._load_settings()

    # ---------- Initialization ----------
    def _initialize_environment(self) -> None:
        """Load .env from project root if it exists."""
        env_path = Path(__file__).resolve().parent.parent / '.env'
        if env_path.exists():
            load_dotenv(dotenv_path=env_path)
        else:
            self._logger.info("No .env file found, using Azure Key Vault and environment variables only")

    def _initialize_azure(self) -> None:
        """Initialize Azure Key Vault client if AZURE_KEY_VAULT_URL is set."""
        try:
            self.key_vault_url = os.getenv('AZURE_KEY_VAULT_URL')
            if not self.key_vault_url:
                self._logger.info("AZURE_KEY_VAULT_URL not set, Azure Key Vault integration disabled")
                return

            if ManagedIdentityCredential is not None:
                try:
                    # Prefer Managed Identity in Azure
                    self.credential = ManagedIdentityCredential()
                    self._logger.info("Using ManagedIdentityCredential for Azure authentication")
                except Exception as managed_identity_error:  # noqa: F841
                    # Fallback to DefaultAzureCredential
                    if DefaultAzureCredential is not None:
                        self.credential = DefaultAzureCredential()
                        self._logger.info("Using DefaultAzureCredential for Azure authentication")
                    else:
                        self.credential = None
            elif DefaultAzureCredential is not None:
                self.credential = DefaultAzureCredential()
                self._logger.info("Using DefaultAzureCredential for Azure authentication")

            if self.credential is not None and SecretClient is not None:
                self.secret_client = SecretClient(vault_url=self.key_vault_url, credential=self.credential)
                self._logger.info(f"Azure Key Vault client initialized: {self.key_vault_url}")
            else:
                self.secret_client = None
                self._logger.warning("Azure credentials or SecretClient unavailable; Key Vault disabled")

        except Exception as e:
            self._logger.error(f"Failed to initialize Azure configuration: {e}")
            self.secret_client = None

    # ---------- Secret access ----------
    def get_secret(self, secret_name: str, default: Optional[str] = None, use_cache: bool = True) -> Optional[str]:
        """Get secret from Azure Key Vault, with fallback to environment variable.

        Args:
            secret_name: Key Vault secret name (or env var name for fallback)
            default: Default value if not found anywhere
            use_cache: Use in-memory cache for secrets
        """
        if use_cache and secret_name in self._secrets_cache:
            return self._secrets_cache[secret_name]

        # Try Azure Key Vault first
        if self.secret_client is not None:
            try:
                secret = self.secret_client.get_secret(secret_name)
                secret_value = secret.value
                if use_cache and secret_value is not None:
                    self._secrets_cache[secret_name] = secret_value
                self._logger.debug(f"Retrieved secret from Key Vault: {secret_name}")
                return secret_value
            except AzureError as e:  # type: ignore[misc]
                self._logger.warning(f"Failed to retrieve secret '{secret_name}' from Key Vault: {e}")
            except Exception as e:
                self._logger.warning(f"Unexpected error retrieving secret '{secret_name}': {e}")

        # Fallback to environment variables
        env_value = os.getenv(secret_name, default)
        if env_value is not None and use_cache:
            self._secrets_cache[secret_name] = env_value
        return env_value

    def set_secret(self, secret_name: str, secret_value: str) -> bool:
        """Set secret in Azure Key Vault if available."""
        if self.secret_client is None:
            self._logger.warning("Azure Key Vault not available, cannot set secret")
            return False
        try:
            self.secret_client.set_secret(secret_name, secret_value)
            # Update cache
            self._secrets_cache[secret_name] = secret_value
            self._logger.info(f"Successfully set secret '{secret_name}' in Azure Key Vault")
            return True
        except Exception as e:
            self._logger.error(f"Failed to set secret '{secret_name}' in Azure Key Vault: {e}")
            return False

    def clear_cache(self) -> None:
        self._secrets_cache.clear()
        self._logger.debug("Secrets cache cleared")

    # ---------- Settings population ----------
    def _load_settings(self) -> None:
        # === SafetyAmp ===
        self.SAFETYAMP_DOMAIN = os.getenv("SAFETYAMP_DOMAIN", "https://api.safetyamp.com")
        self.SAFETYAMP_FQDN = os.getenv("SAFETYAMP_FQDN", "iius.safetyamp.com")
        self.SAFETYAMP_TOKEN = self.get_secret("SAFETYAMP-TOKEN")

        # === MS Graph API Settings ===
        self.MS_GRAPH_CLIENT_ID = self.get_secret("MS-GRAPH-CLIENT-ID")
        self.MS_GRAPH_CLIENT_SECRET = self.get_secret("MS-GRAPH-CLIENT-SECRET")
        self.MS_GRAPH_TENANT_ID = self.get_secret("MS-GRAPH-TENANT-ID")

        # === Samsara ===
        self.SAMSARA_DOMAIN = os.getenv("SAMSARA_DOMAIN", "https://api.samsara.com")
        self.SAMSARA_API_KEY = self.get_secret("SAMSARA-API-KEY")

        # === Viewpoint (Vista) SQL Server — Azure Authentication ===
        self.SQL_SERVER = self.get_secret("SQL-SERVER")
        self.SQL_DATABASE = self.get_secret("SQL-DATABASE")
        self.SQL_DRIVER = os.getenv("SQL_DRIVER", "{ODBC Driver 18 for SQL Server}")

        # Authentication mode: 'managed_identity' or 'sql_auth'
        self.SQL_AUTH_MODE = os.getenv("SQL_AUTH_MODE", "managed_identity")

        if self.SQL_AUTH_MODE == "managed_identity":
            self.VIEWPOINT_CONN_STRING = (
                f"DRIVER={self.SQL_DRIVER};"
                f"SERVER={self.SQL_SERVER};"
                f"DATABASE={self.SQL_DATABASE};"
                "Authentication=ActiveDirectoryMSI;"
                "Encrypt=yes;"
                "TrustServerCertificate=yes;"
                "Connection Timeout=300;"
                "Command Timeout=300;"
                "Connect Timeout=300;"
            )
        elif self.SQL_AUTH_MODE == "sql_auth":
            self.SQL_USERNAME = self.get_secret("SQL-USERNAME")
            self.SQL_PASSWORD = self.get_secret("VISTA-SQL-PASSWORD")
            self.VIEWPOINT_CONN_STRING = (
                f"DRIVER={self.SQL_DRIVER};"
                f"SERVER={self.SQL_SERVER};"
                f"DATABASE={self.SQL_DATABASE};"
                f"UID={self.SQL_USERNAME};"
                f"PWD={self.SQL_PASSWORD};"
                "Encrypt=yes;"
                "TrustServerCertificate=yes;"
                "Connection Timeout=300;"
                "Command Timeout=300;"
                "Connect Timeout=300;"
            )
        else:
            raise ValueError(f"Invalid SQL_AUTH_MODE: {self.SQL_AUTH_MODE}. Must be 'managed_identity' or 'sql_auth'")

        # Connection Pool Settings
        self.DB_POOL_SIZE = int(os.getenv('DB_POOL_SIZE', '5'))
        self.DB_MAX_OVERFLOW = int(os.getenv('DB_MAX_OVERFLOW', '10'))
        self.DB_POOL_TIMEOUT = int(os.getenv('DB_POOL_TIMEOUT', '300'))
        self.DB_POOL_RECYCLE = int(os.getenv('DB_POOL_RECYCLE', '3600'))

        # === Email Settings ===
        self.ALERT_EMAIL_FROM = self.get_secret("ALERT-EMAIL-FROM")
        self.ALERT_EMAIL_TO = self.get_secret("ALERT-EMAIL-TO")
        self.SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.office365.com")
        self.SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
        self.SMTP_USERNAME = self.get_secret("SMTP-USERNAME")
        self.SMTP_PASSWORD = self.get_secret("SMTP-PASSWORD")

        # === Redis Cache Settings ===
        self.REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
        self.REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
        self.REDIS_DB = int(os.getenv("REDIS_DB", "0"))
        # Prefer Key Vault, fallback to env var for compatibility
        self.REDIS_PASSWORD = self.get_secret("REDIS-PASSWORD", default=os.getenv("REDIS_PASSWORD"))

        # === Logging ===
        self.LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
        self.LOG_DIR = os.getenv("LOG_DIR", "output/logs")
        self.LOG_FORMAT = os.getenv("LOG_FORMAT", "text").lower()  # 'text' or 'json'
        self.STRUCTURED_LOGGING_ENABLED = (
            os.getenv("STRUCTURED_LOGGING_ENABLED", "").lower() in ("1", "true", "yes")
            or self.LOG_FORMAT == "json"
        )

        # === Runtime Settings ===
        self.SYNC_INTERVAL_MINUTES = int(os.getenv("SYNC_INTERVAL_MINUTES", "60"))
        self.PRODUCTION = os.getenv("ENV", "production").lower() == "production"

        # === Cache Settings ===
        self.CACHE_TTL_HOURS = int(os.getenv("CACHE_TTL_HOURS", "4"))
        self.CACHE_REFRESH_INTERVAL_HOURS = int(os.getenv("CACHE_REFRESH_INTERVAL_HOURS", "4"))
        self.API_RATE_LIMIT_CALLS = int(os.getenv("API_RATE_LIMIT_CALLS", "60"))
        self.API_RATE_LIMIT_PERIOD = int(os.getenv("API_RATE_LIMIT_PERIOD", "61"))
        self.MAX_RETRY_ATTEMPTS = int(os.getenv("MAX_RETRY_ATTEMPTS", "3"))
        self.RETRY_DELAY_SECONDS = int(os.getenv("RETRY_DELAY_SECONDS", "30"))

    # ---------- Azure environment diagnostics ----------
    def get_azure_environment_config(self) -> Dict[str, Any]:
        """Return diagnostic information about Azure configuration (no secret values)."""
        config: Dict[str, Any] = {
            'azure_key_vault_enabled': self.secret_client is not None,
            'azure_key_vault_url': self.key_vault_url,
            'azure_managed_identity_enabled': isinstance(self.credential, ManagedIdentityCredential) if ManagedIdentityCredential is not None else False,  # type: ignore[arg-type]
        }
        # Do not enumerate secrets to avoid permissions and latency; optionally check for a few expected ones
        try:
            expected_secrets = [
                'SAFETYAMP-TOKEN',
                'SAMSARA-API-KEY',
                'SQL-SERVER',
                'SQL-DATABASE',
                'SMTP-USERNAME',
            ]
            available_secrets = []
            for secret_name in expected_secrets:
                if self.get_secret(secret_name, use_cache=False) is not None:
                    available_secrets.append(secret_name)
            config['available_secrets'] = available_secrets
        except Exception:
            config['available_secrets'] = []
        return config

    # ---------- Utilities ----------
    def reload(self) -> None:
        """Reload environment and secrets and recompute settings."""
        self.clear_cache()
        self._initialize_environment()
        # Do not reinitialize Azure client unless URL changed
        current_url = os.getenv('AZURE_KEY_VAULT_URL')
        if current_url != self.key_vault_url:
            self._initialize_azure()
        self._load_settings()


# Public instance to preserve `from config import settings` usage
settings = ConfigManager()


# Backward-compat convenience functions (if needed)

def get_config() -> ConfigManager:
    return settings


def get_secret_from_azure(secret_name: str) -> Optional[str]:
    return settings.get_secret(secret_name)


def get_connection_string_from_azure(connection_name: str) -> Optional[str]:
    return settings.get_secret(connection_name)


def get_api_key_from_azure(api_name: str) -> Optional[str]:
    return settings.get_secret(api_name)