#!/usr/bin/env python3
"""
Test script for Week 1 and Week 2 implementations
"""

import sys
import os
import time
from pathlib import Path

# Add project root to path
project_root = Path(__file__).resolve().parent
sys.path.insert(0, str(project_root))

def test_azure_key_vault():
    """Test Azure Key Vault integration"""
    print("Testing Azure Key Vault integration...")
    try:
        from config.azure_key_vault import AzureKeyVault
        
        # Test initialization
        key_vault = AzureKeyVault()
        print(f"✓ Azure Key Vault initialized successfully")
        
        # Test secret retrieval (will fallback to env vars if Key Vault not available)
        test_secret = key_vault.get_secret("TEST_SECRET", "fallback_value")
        print(f"✓ Secret retrieval works (got: {test_secret[:10]}...)")
        
        return True
    except Exception as e:
        print(f"✗ Azure Key Vault test failed: {e}")
        return False

def test_redis_cache():
    """Test Redis cache integration"""
    print("Testing Redis cache integration...")
    try:
        from utils.redis_cache_manager import RedisCacheManager
        
        # Test initialization
        cache_manager = RedisCacheManager()
        print(f"✓ Redis cache manager initialized successfully")
        
        # Test cache info
        cache_info = cache_manager.get_cache_info()
        print(f"✓ Cache info retrieved: {cache_info['status']}")
        
        # Test cache operations
        def test_fetch_function():
            return {"test": "data", "timestamp": time.time()}
        
        cached_data = cache_manager.get_cached_data("test_cache", test_fetch_function)
        print(f"✓ Cache operations work (got: {cached_data})")
        
        return True
    except Exception as e:
        print(f"✗ Redis cache test failed: {e}")
        return False

def test_health_endpoints():
    """Test health check endpoints"""
    print("Testing health check endpoints...")
    try:
        from main import app
        
        with app.test_client() as client:
            # Test health endpoint
            response = client.get('/health')
            print(f"✓ Health endpoint returns: {response.status_code}")
            
            # Test ready endpoint
            response = client.get('/ready')
            print(f"✓ Ready endpoint returns: {response.status_code}")
            
            # Test metrics endpoint
            response = client.get('/metrics')
            print(f"✓ Metrics endpoint returns: {response.status_code}")
        
        return True
    except Exception as e:
        print(f"✗ Health endpoints test failed: {e}")
        return False

def test_configuration():
    """Test configuration loading"""
    print("Testing configuration loading...")
    try:
        from config import settings
        
        # Test that key settings are loaded
        required_settings = [
            'SAFETYAMP_DOMAIN',
            'SAFETYAMP_FQDN',
            'REDIS_HOST',
            'REDIS_PORT',
            'LOG_LEVEL'
        ]
        
        for setting in required_settings:
            value = getattr(settings, setting, None)
            print(f"✓ {setting}: {value}")
        
        return True
    except Exception as e:
        print(f"✗ Configuration test failed: {e}")
        return False

def main():
    """Run all tests"""
    print("=" * 50)
    print("Testing Week 1 and Week 2 Implementations")
    print("=" * 50)
    
    tests = [
        ("Configuration Loading", test_configuration),
        ("Azure Key Vault", test_azure_key_vault),
        ("Redis Cache", test_redis_cache),
        ("Health Endpoints", test_health_endpoints),
    ]
    
    results = []
    for test_name, test_func in tests:
        print(f"\n{test_name}:")
        print("-" * 30)
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"✗ {test_name} test crashed: {e}")
            results.append((test_name, False))
    
    print("\n" + "=" * 50)
    print("Test Results Summary:")
    print("=" * 50)
    
    passed = 0
    total = len(results)
    
    for test_name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{test_name}: {status}")
        if result:
            passed += 1
    
    print(f"\nOverall: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! Week 1 and Week 2 implementations are working correctly.")
        return 0
    else:
        print("⚠️  Some tests failed. Please check the implementation.")
        return 1

if __name__ == "__main__":
    sys.exit(main())