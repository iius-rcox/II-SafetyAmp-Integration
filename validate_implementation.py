#!/usr/bin/env python3
"""
Simple validation script for Week 1 and Week 2 implementations
Checks file structure and basic syntax without external dependencies
"""

import os
import sys
from pathlib import Path

def check_file_exists(file_path, description):
    """Check if a file exists"""
    if os.path.exists(file_path):
        print(f"✅ {description}: {file_path}")
        return True
    else:
        print(f"❌ {description}: {file_path} - MISSING")
        return False

def check_file_content(file_path, required_content, description):
    """Check if file contains required content"""
    if not os.path.exists(file_path):
        print(f"❌ {description}: File not found")
        return False
    
    try:
        with open(file_path, 'r') as f:
            content = f.read()
        
        for item in required_content:
            if item in content:
                print(f"✅ {description}: Contains '{item}'")
            else:
                print(f"❌ {description}: Missing '{item}'")
                return False
        return True
    except Exception as e:
        print(f"❌ {description}: Error reading file - {e}")
        return False

def validate_week1():
    """Validate Week 1 implementation"""
    print("\n" + "="*50)
    print("Week 1: Critical Infrastructure Validation")
    print("="*50)
    
    results = []
    
    # Check Dockerfile
    results.append(check_file_exists("Dockerfile", "Dockerfile"))
    results.append(check_file_content("Dockerfile", [
        "FROM python:3.11-slim",
        "HEALTHCHECK",
        "USER appuser",
        "EXPOSE 8080"
    ], "Dockerfile content"))
    
    # Check main.py updates
    results.append(check_file_exists("main.py", "Updated main.py"))
    results.append(check_file_content("main.py", [
        "Flask",
        "/health",
        "/ready",
        "/metrics",
        "signal_handler",
        "run_sync_worker"
    ], "main.py health endpoints"))
    
    # Check requirements.txt
    results.append(check_file_exists("requirements.txt", "requirements.txt"))
    results.append(check_file_content("requirements.txt", [
        "Flask",
        "azure-identity",
        "redis",
        "prometheus-client"
    ], "requirements.txt dependencies"))
    
    return all(results)

def validate_week2():
    """Validate Week 2 implementation"""
    print("\n" + "="*50)
    print("Week 2: Security & Configuration Validation")
    print("="*50)
    
    results = []
    
    # Check Azure Key Vault integration
    results.append(check_file_exists("config/azure_key_vault.py", "Azure Key Vault module"))
    results.append(check_file_content("config/azure_key_vault.py", [
        "SecretClient",
        "DefaultAzureCredential",
        "get_secret",
        "set_secret"
    ], "Azure Key Vault functionality"))
    
    # Check Redis cache manager
    results.append(check_file_exists("utils/redis_cache_manager.py", "Redis cache manager"))
    results.append(check_file_content("utils/redis_cache_manager.py", [
        "RedisCacheManager",
        "get_cached_data",
        "set_cache",
        "clear_cache"
    ], "Redis cache functionality"))
    
    # Check updated settings
    results.append(check_file_exists("config/settings.py", "Updated settings.py"))
    results.append(check_file_content("config/settings.py", [
        "AzureKeyVault",
        "REDIS_HOST",
        "REDIS_PORT",
        "CACHE_TTL_HOURS"
    ], "Settings integration"))
    
    # Check Kubernetes configuration
    results.append(check_file_exists("k8s/safety-amp/safety-amp-deployment.yaml", "K8s deployment"))
    results.append(check_file_content("k8s/safety-amp/safety-amp-deployment.yaml", [
        "AZURE_KEY_VAULT_URL",
        "REDIS_HOST",
        "CACHE_TTL_HOURS",
        "livenessProbe",
        "readinessProbe"
    ], "K8s configuration"))
    
    return all(results)

def validate_structure():
    """Validate overall project structure"""
    print("\n" + "="*50)
    print("Project Structure Validation")
    print("="*50)
    
    required_dirs = [
        "config",
        "utils", 
        "sync",
        "k8s/safety-amp"
    ]
    
    results = []
    for dir_path in required_dirs:
        if os.path.exists(dir_path):
            print(f"✅ Directory: {dir_path}")
            results.append(True)
        else:
            print(f"❌ Directory: {dir_path} - MISSING")
            results.append(False)
    
    return all(results)

def main():
    """Run all validations"""
    print("SafetyAmp Integration System - Implementation Validation")
    print("="*60)
    
    # Validate structure
    structure_ok = validate_structure()
    
    # Validate Week 1
    week1_ok = validate_week1()
    
    # Validate Week 2  
    week2_ok = validate_week2()
    
    # Summary
    print("\n" + "="*60)
    print("VALIDATION SUMMARY")
    print("="*60)
    
    print(f"Project Structure: {'✅ PASS' if structure_ok else '❌ FAIL'}")
    print(f"Week 1 (Infrastructure): {'✅ PASS' if week1_ok else '❌ FAIL'}")
    print(f"Week 2 (Security & Config): {'✅ PASS' if week2_ok else '❌ FAIL'}")
    
    overall_success = structure_ok and week1_ok and week2_ok
    
    if overall_success:
        print("\n🎉 All validations passed!")
        print("The Week 1 and Week 2 implementations are correctly structured.")
        print("\nNext steps:")
        print("1. Install dependencies: pip install -r requirements.txt")
        print("2. Set up environment variables or Azure Key Vault")
        print("3. Run the application: python main.py")
        print("4. Test with: python test_implementation.py")
        return 0
    else:
        print("\n⚠️  Some validations failed.")
        print("Please check the implementation and fix any issues.")
        return 1

if __name__ == "__main__":
    sys.exit(main())