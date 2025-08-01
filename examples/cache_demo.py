#!/usr/bin/env python3
"""
Cache Demo: Demonstrating API Call Reduction

This script shows how smart Redis caching dramatically reduces SafetyAmp API calls
while keeping data fresh and relevant.
"""

import time
from services.safetyamp_api_with_cache import CachedSafetyAmpAPI
from utils.logger import get_logger

logger = get_logger("cache_demo")

def demo_without_cache():
    """Demo showing current behavior (no caching)"""
    print("\n=== DEMO: WITHOUT CACHE ===")
    print("This simulates the current file-based cache approach")
    
    api = CachedSafetyAmpAPI()
    
    # Simulate multiple requests (like multiple pod restarts or instances)
    for i in range(5):
        print(f"\nRequest {i+1}:")
        start_time = time.time()
        
        # Each request hits the API
        employees = api.get_all_employees(force_refresh=True)
        departments = api.get_all_departments(force_refresh=True)
        titles = api.get_all_titles(force_refresh=True)
        
        duration = time.time() - start_time
        print(f"  - Fetched {len(employees)} employees")
        print(f"  - Fetched {len(departments)} departments") 
        print(f"  - Fetched {len(titles)} titles")
        print(f"  - Duration: {duration:.2f} seconds")
        print(f"  - API calls made: 3")
        
        time.sleep(1)  # Simulate processing time

def demo_with_smart_cache():
    """Demo showing smart caching behavior"""
    print("\n=== DEMO: WITH SMART CACHE ===")
    print("This shows the Redis caching approach")
    
    api = CachedSafetyAmpAPI()
    
    # First request - populates cache
    print("\nRequest 1 (Initial - populates cache):")
    start_time = time.time()
    
    employees = api.get_all_employees()
    departments = api.get_all_departments()
    titles = api.get_all_titles()
    
    duration = time.time() - start_time
    print(f"  - Fetched {len(employees)} employees")
    print(f"  - Fetched {len(departments)} departments")
    print(f"  - Fetched {len(titles)} titles")
    print(f"  - Duration: {duration:.2f} seconds")
    print(f"  - API calls made: 3 (cache miss)")
    
    # Subsequent requests - use cache
    for i in range(4):
        print(f"\nRequest {i+2} (Cache hit):")
        start_time = time.time()
        
        employees = api.get_all_employees()
        departments = api.get_all_departments()
        titles = api.get_all_titles()
        
        duration = time.time() - start_time
        print(f"  - Fetched {len(employees)} employees")
        print(f"  - Fetched {len(departments)} departments")
        print(f"  - Fetched {len(titles)} titles")
        print(f"  - Duration: {duration:.2f} seconds")
        print(f"  - API calls made: 0 (cache hit)")
        
        time.sleep(1)
    
    # Show cache stats
    print("\nCache Statistics:")
    stats = api.get_cache_stats()
    for cache_name, info in stats.items():
        if info.get('exists'):
            ttl_minutes = info.get('ttl_seconds', 0) // 60
            print(f"  - {cache_name}: {info.get('item_count', 0)} items, TTL: {ttl_minutes} minutes")

def demo_change_detection():
    """Demo showing change detection and TTL extension"""
    print("\n=== DEMO: CHANGE DETECTION ===")
    print("This shows how the cache extends TTL when data hasn't changed")
    
    api = CachedSafetyAmpAPI()
    
    # First request
    print("\nRequest 1:")
    employees = api.get_all_employees()
    print(f"  - Fetched {len(employees)} employees")
    
    # Second request (within TTL, but checks for changes)
    print("\nRequest 2 (checking for changes):")
    employees = api.get_all_employees()
    print(f"  - Fetched {len(employees)} employees")
    print(f"  - If data unchanged: TTL extended, no API call")
    print(f"  - If data changed: New API call, cache updated")

def demo_cache_invalidation():
    """Demo showing cache invalidation"""
    print("\n=== DEMO: CACHE INVALIDATION ===")
    print("This shows how to force refresh when needed")
    
    api = CachedSafetyAmpAPI()
    
    # Normal request (uses cache)
    print("\nNormal request (uses cache):")
    employees = api.get_all_employees()
    print(f"  - Fetched {len(employees)} employees")
    
    # Force refresh
    print("\nForce refresh (ignores cache):")
    employees = api.get_all_employees(force_refresh=True)
    print(f"  - Fetched {len(employees)} employees")
    print(f"  - API call made regardless of cache state")
    
    # Invalidate specific cache
    print("\nInvalidating employee cache:")
    api.invalidate_cache("employees")
    print(f"  - Employee cache cleared")
    
    # Next request will hit API
    print("\nNext request (cache miss):")
    employees = api.get_all_employees()
    print(f"  - Fetched {len(employees)} employees")
    print(f"  - API call made due to cache invalidation")

def main():
    """Run all demos"""
    print("SafetyAmp API Caching Demo")
    print("=" * 50)
    
    try:
        # Run demos
        demo_without_cache()
        demo_with_smart_cache()
        demo_change_detection()
        demo_cache_invalidation()
        
        print("\n" + "=" * 50)
        print("SUMMARY:")
        print("- Without cache: Every request hits the API")
        print("- With smart cache: API calls only when needed")
        print("- Change detection: Extends cache TTL when data unchanged")
        print("- Force refresh: Available when immediate updates needed")
        print("- Cache invalidation: Manual control over cache state")
        
    except Exception as e:
        logger.error(f"Demo failed: {e}")
        print(f"\nDemo failed: {e}")
        print("Make sure Redis is running and SafetyAmp API is accessible")

if __name__ == "__main__":
    main()