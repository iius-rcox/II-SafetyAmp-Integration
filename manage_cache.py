#!/usr/bin/env python3
"""
Cache Management Script

This script helps manage SafetyAmp data caches.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from utils.cache_manager import CacheManager
from services.safetyamp_api import SafetyAmpAPI
from utils.logger import get_logger
import json

logger = get_logger("cache_manager")

def main():
    """Main cache management function"""
    cache_manager = CacheManager()
    api = SafetyAmpAPI()
    
    if len(sys.argv) < 2:
        print("Cache Management Script")
        print("=" * 50)
        print("Usage:")
        print("  python manage_cache.py info                    - Show cache information")
        print("  python manage_cache.py clear [cache_name]      - Clear specific or all caches")
        print("  python manage_cache.py refresh [cache_name]    - Refresh specific or all caches")
        print("  python manage_cache.py list                    - List all available caches")
        print()
        print("Available caches:")
        print("  - safetyamp_users")
        print("  - safetyamp_users_by_id")
        print("  - safetyamp_sites")
        print("  - safetyamp_asset_types")
        print("  - safetyamp_titles")
        print("  - safetyamp_assets")
        print("  - safetyamp_roles")
        return
    
    command = sys.argv[1].lower()
    
    if command == "info":
        show_cache_info(cache_manager)
    elif command == "clear":
        cache_name = sys.argv[2] if len(sys.argv) > 2 else None
        clear_cache(cache_manager, cache_name)
    elif command == "refresh":
        cache_name = sys.argv[2] if len(sys.argv) > 2 else None
        refresh_cache(cache_manager, api, cache_name)
    elif command == "list":
        list_caches(cache_manager)
    else:
        print(f"Unknown command: {command}")

def show_cache_info(cache_manager):
    """Show information about all caches"""
    print("Cache Information")
    print("=" * 50)
    
    cache_info = cache_manager.get_cache_info()
    
    if not cache_info:
        print("No cache files found.")
        return
    
    for filename, info in cache_info.items():
        print(f"\n{filename}:")
        print(f"  Size: {info['size']:,} bytes")
        print(f"  Modified: {info['modified']}")
        
        # Try to get metadata
        cache_name = filename.replace('.json', '')
        metadata_info = cache_manager.get_cache_info(cache_name)
        if metadata_info and 'metadata' in metadata_info:
            metadata = metadata_info['metadata']
            print(f"  Created: {metadata.get('created_at', 'Unknown')}")
            print(f"  Items: {metadata.get('item_count', 'Unknown')}")

def clear_cache(cache_manager, cache_name=None):
    """Clear cache files"""
    if cache_name:
        print(f"Clearing cache: {cache_name}")
        cache_manager.clear_cache(cache_name)
        print(f"✓ Cleared cache: {cache_name}")
    else:
        print("Clearing all caches...")
        cache_manager.clear_cache()
        print("✓ Cleared all caches")

def refresh_cache(cache_manager, api, cache_name=None):
    """Refresh cache files"""
    cache_methods = {
        'safetyamp_users': api.get_users_cached,
        'safetyamp_users_by_id': api.get_users_by_id_cached,
        'safetyamp_sites': api.get_sites_cached,
        'safetyamp_asset_types': api.get_asset_types_cached,
        'safetyamp_titles': api.get_titles_cached,
        'safetyamp_assets': api.get_assets_cached,
        'safetyamp_roles': api.get_roles_cached
    }
    
    if cache_name:
        if cache_name in cache_methods:
            print(f"Refreshing cache: {cache_name}")
            try:
                data = cache_methods[cache_name](force_refresh=True)
                if data:
                    print(f"✓ Refreshed cache: {cache_name} ({len(data)} items)")
                else:
                    print(f"✗ Failed to refresh cache: {cache_name}")
            except Exception as e:
                print(f"✗ Error refreshing cache {cache_name}: {e}")
        else:
            print(f"Unknown cache: {cache_name}")
            print(f"Available caches: {', '.join(cache_methods.keys())}")
    else:
        print("Refreshing all caches...")
        for name, method in cache_methods.items():
            try:
                print(f"  Refreshing {name}...")
                data = method(force_refresh=True)
                if data:
                    print(f"    ✓ {name}: {len(data)} items")
                else:
                    print(f"    ✗ {name}: failed")
            except Exception as e:
                print(f"    ✗ {name}: error - {e}")

def list_caches(cache_manager):
    """List all available caches"""
    print("Available Caches")
    print("=" * 50)
    
    cache_info = cache_manager.get_cache_info()
    
    if not cache_info:
        print("No cache files found.")
        return
    
    for filename in sorted(cache_info.keys()):
        cache_name = filename.replace('.json', '')
        info = cache_info[filename]
        size_mb = info['size'] / (1024 * 1024)
        print(f"  {cache_name}: {size_mb:.2f} MB")

if __name__ == "__main__":
    main() 