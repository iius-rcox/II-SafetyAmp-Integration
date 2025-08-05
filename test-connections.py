#!/usr/bin/env python3
"""
Test script to check connectivity to SafetyAmp, Samsara, and Viewpoint
"""

import os
import sys
import time
import requests
import pyodbc
from config.settings import *
from services.safetyamp_api import SafetyAmpAPI
from services.samsara_api import SamsaraAPI
from services.viewpoint_api import ViewpointAPI

def test_safetyamp_connection():
    """Test SafetyAmp API connection"""
    print("🔍 Testing SafetyAmp API connection...")
    try:
        api = SafetyAmpAPI()
        # Test a simple API call
        response = api.get_sites()
        if response:
            print(f"✅ SafetyAmp API: Connected successfully! Found {len(response)} sites")
            return True
        else:
            print("❌ SafetyAmp API: No data returned")
            return False
    except Exception as e:
        print(f"❌ SafetyAmp API: Connection failed - {str(e)}")
        return False

def test_samsara_connection():
    """Test Samsara API connection"""
    print("🔍 Testing Samsara API connection...")
    try:
        api = SamsaraAPI()
        # Test a simple API call
        response = api.get_all_vehicles()
        if response:
            print(f"✅ Samsara API: Connected successfully! Found {len(response)} vehicles")
            return True
        else:
            print("❌ Samsara API: No data returned")
            return False
    except Exception as e:
        print(f"❌ Samsara API: Connection failed - {str(e)}")
        return False

def test_viewpoint_connection():
    """Test Viewpoint database connection with enhanced diagnostics"""
    print("🔍 Testing Viewpoint database connection...")
    
    # First, check configuration
    print(f"  📋 Configuration check:")
    print(f"     SQL_SERVER: {SQL_SERVER}")
    print(f"     SQL_DATABASE: {SQL_DATABASE}")
    print(f"     SQL_AUTH_MODE: {SQL_AUTH_MODE}")
    print(f"     CONNECTION_TIMEOUT: {getattr(sys.modules[__name__], 'CONNECTION_TIMEOUT', 'Not set')}")
    print(f"     DB_POOL_TIMEOUT: {DB_POOL_TIMEOUT}")
    
    if not SQL_SERVER or not SQL_DATABASE:
        print("❌ Viewpoint Database: Configuration incomplete - missing SQL_SERVER or SQL_DATABASE")
        return False
    
    try:
        api = ViewpointAPI()
        print("  ✅ ViewpointAPI instance created successfully")
        
        # Test basic connection
        print("  🔄 Testing basic connection...")
        if api.test_connection():
            print("  ✅ Basic connection test successful")
            
            # Test a simple query using the connection context manager
            with api._get_connection() as conn:
                result = api._fetch_query(conn, "SELECT TOP 1 * FROM INFORMATION_SCHEMA.TABLES")
                if result:
                    print(f"✅ Viewpoint Database: Connected successfully! Query returned {len(result)} rows")
                    return True
                else:
                    print("❌ Viewpoint Database: No data returned")
                    return False
        else:
            print("❌ Viewpoint Database: Basic connection test failed")
            return False
            
    except ValueError as ve:
        print(f"❌ Viewpoint Database: Configuration error - {str(ve)}")
        return False
    except Exception as e:
        error_str = str(e)
        print(f"❌ Viewpoint Database: Connection failed - {error_str}")
        
        # Provide specific guidance based on error type
        if "login timeout" in error_str.lower():
            print("  💡 Suggestion: This is a login timeout. Check:")
            print("     - Network connectivity to SQL Server")
            print("     - Azure Managed Identity configuration")
            print("     - SQL Server firewall settings")
            print("     - Consider using SQL authentication as fallback")
        elif "authentication" in error_str.lower():
            print("  💡 Suggestion: Authentication failed. Check:")
            print("     - Azure Managed Identity permissions")
            print("     - SQL Server authentication mode")
            print("     - User permissions on database")
        elif "timeout" in error_str.lower():
            print("  💡 Suggestion: Connection timeout. Check:")
            print("     - Network connectivity")
            print("     - SQL Server is running and accessible")
            print("     - Firewall settings")
        
        return False

def test_viewpoint_with_sql_auth():
    """Test Viewpoint with SQL authentication as fallback"""
    print("\n🔄 Testing Viewpoint with SQL authentication fallback...")
    
    # Temporarily switch to SQL auth mode for testing
    original_auth_mode = os.environ.get('SQL_AUTH_MODE', 'managed_identity')
    os.environ['SQL_AUTH_MODE'] = 'sql_auth'
    
    # Set test credentials if available
    test_username = os.environ.get('TEST_SQL_USERNAME')
    test_password = os.environ.get('TEST_SQL_PASSWORD')
    
    if not test_username or not test_password:
        print("❌ SQL Auth test skipped: TEST_SQL_USERNAME or TEST_SQL_PASSWORD not set")
        os.environ['SQL_AUTH_MODE'] = original_auth_mode
        return False
    
    os.environ['SQL_USERNAME'] = test_username
    os.environ['VISTA_SQL_PASSWORD'] = test_password
    
    try:
        # Reload settings with new auth mode
        import importlib
        import config.settings
        importlib.reload(config.settings)
        
        api = ViewpointAPI()
        if api.test_connection():
            print("✅ SQL Authentication: Connection successful!")
            os.environ['SQL_AUTH_MODE'] = original_auth_mode
            return True
        else:
            print("❌ SQL Authentication: Connection failed")
            os.environ['SQL_AUTH_MODE'] = original_auth_mode
            return False
    except Exception as e:
        print(f"❌ SQL Authentication: Connection failed - {str(e)}")
        os.environ['SQL_AUTH_MODE'] = original_auth_mode
        return False

def test_key_vault_access():
    """Test Azure Key Vault access"""
    print("🔍 Testing Azure Key Vault access...")
    try:
        from config.azure_key_vault import AzureKeyVault
        
        # Use the same initialization as in settings.py
        key_vault = AzureKeyVault()
        
        # Test retrieving a secret
        test_secret = key_vault.get_secret("SAFETYAMP-TOKEN")
        if test_secret:
            print("✅ Azure Key Vault: Access successful!")
            return True
        else:
            print("❌ Azure Key Vault: No secret retrieved")
            print("  💡 Set AZURE_KEY_VAULT_URL environment variable for Azure Key Vault access")
            return False
    except Exception as e:
        print(f"❌ Azure Key Vault: Access failed - {str(e)}")
        return False

def main():
    """Main test function"""
    print("🚀 Starting connectivity tests...")
    print("=" * 50)
    
    results = {}
    
    # Test Key Vault first (needed for other tests)
    results['key_vault'] = test_key_vault_access()
    print()
    
    # Test external services
    results['safetyamp'] = test_safetyamp_connection()
    print()
    
    results['samsara'] = test_samsara_connection()
    print()
    
    results['viewpoint'] = test_viewpoint_connection()
    
    # If Viewpoint failed with managed identity, try SQL auth
    if not results['viewpoint']:
        results['viewpoint_sql_auth'] = test_viewpoint_with_sql_auth()
    
    print()
    
    # Summary
    print("=" * 50)
    print("📊 CONNECTIVITY TEST SUMMARY:")
    print("=" * 50)
    
    for service, status in results.items():
        status_icon = "✅" if status else "❌"
        status_text = "CONNECTED" if status else "FAILED"
        print(f"{status_icon} {service.upper()}: {status_text}")
    
    # Vista-specific recommendations
    if not results.get('viewpoint', False):
        print("\n🔧 VISTA CONNECTION TROUBLESHOOTING:")
        print("=" * 50)
        print("1. Verify SQL Server connectivity:")
        print("   - Check if SQL Server is accessible from this environment")
        print("   - Verify firewall rules allow connections on port 1433")
        print("2. Authentication setup:")
        print("   - For Managed Identity: Ensure the identity has access to the database")
        print("   - For SQL Auth: Set TEST_SQL_USERNAME and TEST_SQL_PASSWORD environment variables")
        print("3. Environment variables:")
        print("   - Set SQL_SERVER and SQL_DATABASE environment variables")
        print("   - Set AZURE_KEY_VAULT_URL for production credential management")
    
    vista_connected = results.get('viewpoint', False) or results.get('viewpoint_sql_auth', False)
    all_connected = all([results.get('key_vault', False), vista_connected])
    
    if vista_connected:
        print("\n🎉 Vista connection working!")
        return 0
    else:
        print("\n⚠️  Vista connection failed. Check the errors above.")
        return 1

if __name__ == "__main__":
    sys.exit(main()) 