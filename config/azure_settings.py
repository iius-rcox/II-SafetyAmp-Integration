"""
Azure-specific configuration for SafetyAmp Integration
Handles Azure Key Vault integration, managed identity, and Azure-specific settings
"""

import os
import logging
from typing import Optional, Dict, Any
from azure.identity import DefaultAzureCredential, ManagedIdentityCredential
from azure.keyvault.secrets import SecretClient
from azure.core.exceptions import AzureError

logger = logging.getLogger(__name__)

class AzureConfig:
    """Azure-specific configuration manager"""
    
    def __init__(self):
        self.key_vault_url: Optional[str] = None
        self.secret_client: Optional[SecretClient] = None
        self.credential: Optional[DefaultAzureCredential] = None
        self._secrets_cache: Dict[str, str] = {}
        
        # Initialize Azure configuration
        self._initialize_azure_config()
    
    def _initialize_azure_config(self):
        """Initialize Azure configuration and credentials"""
        try:
            # Get Key Vault URL from environment
            self.key_vault_url = os.getenv('AZURE_KEY_VAULT_URL')
            
            if not self.key_vault_url:
                logger.warning("AZURE_KEY_VAULT_URL not set, Azure Key Vault integration disabled")
                return
            
            # Initialize Azure credentials
            # Try managed identity first, then fall back to default credential
            try:
                self.credential = ManagedIdentityCredential()
                logger.info("Using managed identity for Azure authentication")
            except Exception as e:
                logger.warning(f"Managed identity not available: {e}")
                self.credential = DefaultAzureCredential()
                logger.info("Using default Azure credential")
            
            # Initialize Key Vault client
            self.secret_client = SecretClient(
                vault_url=self.key_vault_url,
                credential=self.credential
            )
            
            logger.info(f"Azure Key Vault client initialized: {self.key_vault_url}")
            
        except Exception as e:
            logger.error(f"Failed to initialize Azure configuration: {e}")
            self.secret_client = None
    
    def get_secret(self, secret_name: str, use_cache: bool = True) -> Optional[str]:
        """
        Get a secret from Azure Key Vault
        
        Args:
            secret_name: Name of the secret in Key Vault
            use_cache: Whether to use cached value (default: True)
            
        Returns:
            Secret value or None if not found
        """
        if not self.secret_client:
            logger.warning("Azure Key Vault client not initialized")
            return None
        
        # Check cache first
        if use_cache and secret_name in self._secrets_cache:
            return self._secrets_cache[secret_name]
        
        try:
            # Get secret from Key Vault
            secret = self.secret_client.get_secret(secret_name)
            secret_value = secret.value
            
            # Cache the secret
            if use_cache:
                self._secrets_cache[secret_name] = secret_value
            
            logger.debug(f"Retrieved secret from Key Vault: {secret_name}")
            return secret_value
            
        except AzureError as e:
            logger.error(f"Failed to retrieve secret '{secret_name}' from Key Vault: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error retrieving secret '{secret_name}': {e}")
            return None
    
    def get_connection_string(self, connection_name: str) -> Optional[str]:
        """
        Get a database connection string from Key Vault
        
        Args:
            connection_name: Name of the connection string secret
            
        Returns:
            Connection string or None if not found
        """
        return self.get_secret(connection_name)
    
    def get_api_key(self, api_name: str) -> Optional[str]:
        """
        Get an API key from Key Vault
        
        Args:
            api_name: Name of the API key secret (e.g., 'safetyamp-api-key')
            
        Returns:
            API key or None if not found
        """
        return self.get_secret(api_name)
    
    def clear_cache(self):
        """Clear the secrets cache"""
        self._secrets_cache.clear()
        logger.debug("Azure secrets cache cleared")
    
    def get_azure_environment_config(self) -> Dict[str, Any]:
        """
        Get Azure-specific environment configuration
        
        Returns:
            Dictionary of Azure-specific configuration
        """
        config = {
            'azure_key_vault_enabled': self.secret_client is not None,
            'azure_key_vault_url': self.key_vault_url,
            'azure_managed_identity_enabled': isinstance(self.credential, ManagedIdentityCredential),
        }
        
        # Add available secrets (without values for security)
        if self.secret_client:
            try:
                # List available secrets (this is a simplified approach)
                # In production, you might want to maintain a list of expected secrets
                expected_secrets = [
                    'safetyamp-api-key',
                    'samsara-api-key', 
                    'viewpoint-connection-string',
                    'redis-password'
                ]
                
                available_secrets = []
                for secret_name in expected_secrets:
                    if self.get_secret(secret_name, use_cache=False):
                        available_secrets.append(secret_name)
                
                config['available_secrets'] = available_secrets
                
            except Exception as e:
                logger.warning(f"Could not enumerate available secrets: {e}")
                config['available_secrets'] = []
        
        return config

# Global Azure configuration instance
azure_config = AzureConfig()

def get_azure_config() -> AzureConfig:
    """Get the global Azure configuration instance"""
    return azure_config

def get_secret_from_azure(secret_name: str) -> Optional[str]:
    """
    Convenience function to get a secret from Azure Key Vault
    
    Args:
        secret_name: Name of the secret
        
    Returns:
        Secret value or None if not found
    """
    return azure_config.get_secret(secret_name)

def get_connection_string_from_azure(connection_name: str) -> Optional[str]:
    """
    Convenience function to get a connection string from Azure Key Vault
    
    Args:
        connection_name: Name of the connection string secret
        
    Returns:
        Connection string or None if not found
    """
    return azure_config.get_connection_string(connection_name)

def get_api_key_from_azure(api_name: str) -> Optional[str]:
    """
    Convenience function to get an API key from Azure Key Vault
    
    Args:
        api_name: Name of the API key secret
        
    Returns:
        API key or None if not found
    """
    return azure_config.get_api_key(api_name) 