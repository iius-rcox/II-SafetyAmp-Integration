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
    """Test Viewpoint database connection"""
    print("🔍 Testing Viewpoint database connection...")
    try:
        api = ViewpointAPI()
        # Test a simple query using the connection context manager
        with api._get_connection() as conn:
            result = api._fetch_query(conn, "SELECT TOP 1 * FROM INFORMATION_SCHEMA.TABLES")
            if result:
                print(f"✅ Viewpoint Database: Connected successfully! Query returned {len(result)} rows")
                return True
            else:
                print("❌ Viewpoint Database: No data returned")
                return False
    except Exception as e:
        print(f"❌ Viewpoint Database: Connection failed - {str(e)}")
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
    print()
    
    # Summary
    print("=" * 50)
    print("📊 CONNECTIVITY TEST SUMMARY:")
    print("=" * 50)
    
    for service, status in results.items():
        status_icon = "✅" if status else "❌"
        status_text = "CONNECTED" if status else "FAILED"
        print(f"{status_icon} {service.upper()}: {status_text}")
    
    all_connected = all(results.values())
    if all_connected:
        print("\n🎉 All services are connected successfully!")
        return 0
    else:
        print("\n⚠️  Some services failed to connect. Check the errors above.")
        return 1

if __name__ == "__main__":
    sys.exit(main()) 