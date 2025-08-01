#!/usr/bin/env python3
"""
Cache Manager

This module provides caching functionality for SafetyAmp data to avoid
repeated API calls and improve performance.
"""

import os
import json
import time
from datetime import datetime, timedelta
from utils.logger import get_logger

logger = get_logger("cache_manager")

class CacheManager:
    def __init__(self, cache_dir="cache"):
        self.cache_dir = cache_dir
        self._ensure_cache_dir()
    
    def _ensure_cache_dir(self):
        """Ensure the cache directory exists"""
        if not os.path.exists(self.cache_dir):
            os.makedirs(self.cache_dir)
            logger.info(f"Created cache directory: {self.cache_dir}")
    
    def _get_cache_file_path(self, cache_name):
        """Get the full path for a cache file"""
        return os.path.join(self.cache_dir, f"{cache_name}.json")
    
    def _get_metadata_file_path(self, cache_name):
        """Get the full path for a cache metadata file"""
        return os.path.join(self.cache_dir, f"{cache_name}_metadata.json")
    
    def is_cache_valid(self, cache_name, max_age_hours=1):
        """Check if cache is still valid (not older than max_age_hours)"""
        metadata_path = self._get_metadata_file_path(cache_name)
        
        if not os.path.exists(metadata_path):
            logger.debug(f"Cache metadata not found for {cache_name}")
            return False
        
        try:
            with open(metadata_path, 'r') as f:
                metadata = json.load(f)
            
            cache_time = datetime.fromisoformat(metadata.get('created_at', ''))
            max_age = timedelta(hours=max_age_hours)
            
            if datetime.now() - cache_time > max_age:
                logger.debug(f"Cache {cache_name} is expired (age: {datetime.now() - cache_time})")
                return False
            
            logger.debug(f"Cache {cache_name} is valid (age: {datetime.now() - cache_time})")
            return True
            
        except Exception as e:
            logger.error(f"Error checking cache validity for {cache_name}: {e}")
            return False
    
    def load_cache(self, cache_name):
        """Load data from cache file"""
        cache_path = self._get_cache_file_path(cache_name)
        
        if not os.path.exists(cache_path):
            logger.debug(f"Cache file not found: {cache_path}")
            return None
        
        try:
            with open(cache_path, 'r') as f:
                data = json.load(f)
            logger.debug(f"Loaded cache {cache_name} with {len(data)} items")
            return data
            
        except Exception as e:
            logger.error(f"Error loading cache {cache_name}: {e}")
            return None
    
    def save_cache(self, cache_name, data):
        """Save data to cache file with metadata"""
        cache_path = self._get_cache_file_path(cache_name)
        metadata_path = self._get_metadata_file_path(cache_name)
        
        try:
            # Save the data
            with open(cache_path, 'w') as f:
                json.dump(data, f, indent=2, default=str)
            
            # Save metadata
            metadata = {
                'created_at': datetime.now().isoformat(),
                'item_count': len(data) if isinstance(data, dict) else len(data) if isinstance(data, list) else 0,
                'cache_name': cache_name
            }
            
            with open(metadata_path, 'w') as f:
                json.dump(metadata, f, indent=2)
            
            logger.info(f"Saved cache {cache_name} with {len(data)} items")
            
        except Exception as e:
            logger.error(f"Error saving cache {cache_name}: {e}")
    
    def get_cached_data(self, cache_name, fetch_function, max_age_hours=1, force_refresh=False):
        """
        Get cached data, refreshing if needed
        
        Args:
            cache_name: Name of the cache
            fetch_function: Function to call to fetch fresh data
            max_age_hours: Maximum age of cache in hours
            force_refresh: Force refresh even if cache is valid
        
        Returns:
            The cached or freshly fetched data
        """
        # Check if we need to refresh the cache
        if force_refresh or not self.is_cache_valid(cache_name, max_age_hours):
            logger.info(f"Fetching fresh data for {cache_name}")
            try:
                data = fetch_function()
                if data is not None:
                    self.save_cache(cache_name, data)
                    return data
                else:
                    logger.warning(f"Fetch function returned None for {cache_name}")
            except Exception as e:
                logger.error(f"Error fetching fresh data for {cache_name}: {e}")
        
        # Try to load from cache
        cached_data = self.load_cache(cache_name)
        if cached_data is not None:
            logger.info(f"Using cached data for {cache_name}")
            return cached_data
        
        # If cache loading failed, try fetching fresh data
        logger.warning(f"Cache loading failed for {cache_name}, fetching fresh data")
        try:
            data = fetch_function()
            if data is not None:
                self.save_cache(cache_name, data)
            return data
        except Exception as e:
            logger.error(f"Error fetching fresh data for {cache_name}: {e}")
            return None
    
    def clear_cache(self, cache_name=None):
        """Clear cache files"""
        if cache_name:
            # Clear specific cache
            cache_path = self._get_cache_file_path(cache_name)
            metadata_path = self._get_metadata_file_path(cache_name)
            
            for path in [cache_path, metadata_path]:
                if os.path.exists(path):
                    os.remove(path)
                    logger.info(f"Removed cache file: {path}")
        else:
            # Clear all caches
            for filename in os.listdir(self.cache_dir):
                file_path = os.path.join(self.cache_dir, filename)
                if os.path.isfile(file_path):
                    os.remove(file_path)
                    logger.info(f"Removed cache file: {file_path}")
    
    def get_cache_info(self, cache_name=None):
        """Get information about cache files"""
        if cache_name:
            # Get info for specific cache
            cache_path = self._get_cache_file_path(cache_name)
            metadata_path = self._get_metadata_file_path(cache_name)
            
            info = {}
            if os.path.exists(cache_path):
                info['cache_file'] = {
                    'path': cache_path,
                    'size': os.path.getsize(cache_path),
                    'modified': datetime.fromtimestamp(os.path.getmtime(cache_path)).isoformat()
                }
            
            if os.path.exists(metadata_path):
                try:
                    with open(metadata_path, 'r') as f:
                        metadata = json.load(f)
                    info['metadata'] = metadata
                except Exception as e:
                    info['metadata_error'] = str(e)
            
            return info
        else:
            # Get info for all caches
            cache_files = {}
            for filename in os.listdir(self.cache_dir):
                if filename.endswith('.json'):
                    file_path = os.path.join(self.cache_dir, filename)
                    cache_files[filename] = {
                        'path': file_path,
                        'size': os.path.getsize(file_path),
                        'modified': datetime.fromtimestamp(os.path.getmtime(file_path)).isoformat()
                    }
            return cache_files 