from azure.keyvault.secrets import SecretClient
from azure.identity import DefaultAzureCredential
import os
from utils.logger import get_logger

logger = get_logger("azure_key_vault")

class AzureKeyVault:
    def __init__(self, vault_url=None):
        self.vault_url = vault_url or os.getenv('AZURE_KEY_VAULT_URL')
        if self.vault_url:
            try:
                self.credential = DefaultAzureCredential()
                self.client = SecretClient(vault_url=self.vault_url, credential=self.credential)
                logger.info(f"Successfully connected to Azure Key Vault: {self.vault_url}")
            except Exception as e:
                logger.warning(f"Failed to connect to Azure Key Vault: {e}")
                self.client = None
        else:
            logger.info("No Azure Key Vault URL provided, using environment variables only")
            self.client = None
    
    def get_secret(self, secret_name, default=None):
        """Get secret from Azure Key Vault or environment variable"""
        if self.client:
            try:
                secret_value = self.client.get_secret(secret_name).value
                logger.debug(f"Retrieved secret '{secret_name}' from Azure Key Vault")
                return secret_value
            except Exception as e:
                logger.warning(f"Failed to get secret '{secret_name}' from Azure Key Vault: {e}")
                # Fallback to environment variable
                return os.getenv(secret_name, default)
        else:
            # Use environment variable directly
            return os.getenv(secret_name, default)
    
    def set_secret(self, secret_name, secret_value):
        """Set secret in Azure Key Vault"""
        if self.client:
            try:
                self.client.set_secret(secret_name, secret_value)
                logger.info(f"Successfully set secret '{secret_name}' in Azure Key Vault")
                return True
            except Exception as e:
                logger.error(f"Failed to set secret '{secret_name}' in Azure Key Vault: {e}")
                return False
        else:
            logger.warning("Azure Key Vault not available, cannot set secret")
            return False