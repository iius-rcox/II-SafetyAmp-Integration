#!/usr/bin/env python3
"""
Smart Redis Cache Manager

This module provides intelligent caching functionality for SafetyAmp data
that minimizes API calls while keeping data fresh and relevant.
"""

import os
import json
import time
import hashlib
from datetime import datetime, timedelta
from typing import Optional, Any, Callable, Dict, List
import redis
from utils.logger import get_logger

logger = get_logger("smart_redis_cache")

class SmartRedisCache:
    def __init__(self, host=None, port=6379, db=0):
        self.host = host or os.getenv('REDIS_HOST', 'localhost')
        self.port = port or int(os.getenv('REDIS_PORT', 6379))
        self.db = db
        self.client = None
        self._connect()
        
        # Cache configuration
        self.default_ttl = {
            'employees': 3600,      # 1 hour - changes rarely
            'departments': 7200,    # 2 hours - very stable
            'titles': 7200,         # 2 hours - very stable
            'jobs': 3600,           # 1 hour - moderate changes
            'vehicles': 1800,       # 30 minutes - more dynamic
            'safety_events': 300,   # 5 minutes - very dynamic
        }
    
    def _connect(self):
        """Establish Redis connection with fallback"""
        try:
            self.client = redis.Redis(
                host=self.host,
                port=self.port,
                db=self.db,
                decode_responses=True,
                socket_connect_timeout=5,
                socket_timeout=5,
                retry_on_timeout=True,
                health_check_interval=30
            )
            self.client.ping()
            logger.info(f"Connected to Redis at {self.host}:{self.port}")
        except Exception as e:
            logger.warning(f"Failed to connect to Redis: {e}. Using fallback mode.")
            self.client = None
    
    def _get_cache_key(self, cache_name: str, version: str = None) -> str:
        """Generate cache key with optional versioning"""
        base_key = f"safetyamp:{cache_name}"
        if version:
            return f"{base_key}:v{version}"
        return base_key
    
    def _get_metadata_key(self, cache_name: str) -> str:
        """Generate metadata key for cache info"""
        return f"safetyamp:{cache_name}:metadata"
    
    def _calculate_data_hash(self, data: Any) -> str:
        """Calculate hash of data for change detection"""
        if isinstance(data, (dict, list)):
            # Sort for consistent hashing
            data_str = json.dumps(data, sort_keys=True, default=str)
        else:
            data_str = str(data)
        return hashlib.md5(data_str.encode()).hexdigest()
    
    def get_cached_data(
        self, 
        cache_name: str, 
        fetch_function: Callable, 
        max_age_hours: int = None,
        force_refresh: bool = False,
        check_for_changes: bool = True
    ) -> Any:
        """
        Get cached data with intelligent refresh logic
        
        Args:
            cache_name: Name of the cache
            fetch_function: Function to fetch fresh data
            max_age_hours: Maximum age in hours (overrides default)
            force_refresh: Force refresh regardless of cache state
            check_for_changes: Check if data has actually changed
        """
        if not self.client:
            logger.warning("Redis unavailable, fetching fresh data")
            return fetch_function()
        
        # Use default TTL if not specified
        if max_age_hours is None:
            max_age_hours = self.default_ttl.get(cache_name, 3600) // 3600
        
        cache_key = self._get_cache_key(cache_name)
        metadata_key = self._get_metadata_key(cache_name)
        
        try:
            # Check if we should use cache
            if not force_refresh:
                cached_data = self._try_get_cache(cache_key, metadata_key, max_age_hours)
                if cached_data is not None:
                    logger.info(f"Using cached data for {cache_name} ({len(cached_data)} items)")
                    return cached_data
            
            # Fetch fresh data
            logger.info(f"Fetching fresh data for {cache_name}")
            fresh_data = fetch_function()
            
            if fresh_data is None:
                logger.warning(f"Fetch function returned None for {cache_name}")
                # Try to return cached data as fallback
                cached_data = self._try_get_cache(cache_key, metadata_key, max_age_hours * 2)
                return cached_data
            
            # Check if data has actually changed
            if check_for_changes and not force_refresh:
                cached_data = self._try_get_cache(cache_key, metadata_key, max_age_hours * 2)
                if cached_data is not None:
                    fresh_hash = self._calculate_data_hash(fresh_data)
                    cached_hash = self._calculate_data_hash(cached_data)
                    
                    if fresh_hash == cached_hash:
                        logger.info(f"Data for {cache_name} hasn't changed, extending cache TTL")
                        # Extend cache TTL since data is still valid
                        self._extend_cache_ttl(cache_key, metadata_key, max_age_hours)
                        return cached_data
            
            # Cache the fresh data
            self._save_cache(cache_key, metadata_key, fresh_data, max_age_hours)
            logger.info(f"Cached fresh data for {cache_name} ({len(fresh_data)} items)")
            
            return fresh_data
            
        except Exception as e:
            logger.error(f"Error in get_cached_data for {cache_name}: {e}")
            # Fallback to fetch function
            return fetch_function()
    
    def _try_get_cache(self, cache_key: str, metadata_key: str, max_age_hours: int) -> Optional[Any]:
        """Try to get valid cached data"""
        try:
            # Check metadata first
            metadata = self.client.get(metadata_key)
            if not metadata:
                return None
            
            metadata = json.loads(metadata)
            created_at = datetime.fromisoformat(metadata['created_at'])
            max_age = timedelta(hours=max_age_hours)
            
            if datetime.now() - created_at > max_age:
                logger.debug(f"Cache expired for {cache_key}")
                return None
            
            # Get cached data
            cached_data = self.client.get(cache_key)
            if cached_data:
                return json.loads(cached_data)
            
        except Exception as e:
            logger.error(f"Error reading cache {cache_key}: {e}")
        
        return None
    
    def _save_cache(self, cache_key: str, metadata_key: str, data: Any, max_age_hours: int):
        """Save data to cache with metadata"""
        try:
            # Save data
            ttl_seconds = max_age_hours * 3600
            self.client.setex(cache_key, ttl_seconds, json.dumps(data, default=str))
            
            # Save metadata
            metadata = {
                'created_at': datetime.now().isoformat(),
                'item_count': len(data) if isinstance(data, (list, dict)) else 0,
                'ttl_hours': max_age_hours,
                'data_hash': self._calculate_data_hash(data)
            }
            self.client.setex(metadata_key, ttl_seconds, json.dumps(metadata))
            
        except Exception as e:
            logger.error(f"Error saving cache {cache_key}: {e}")
    
    def _extend_cache_ttl(self, cache_key: str, metadata_key: str, max_age_hours: int):
        """Extend cache TTL when data hasn't changed"""
        try:
            ttl_seconds = max_age_hours * 3600
            self.client.expire(cache_key, ttl_seconds)
            self.client.expire(metadata_key, ttl_seconds)
            logger.debug(f"Extended TTL for {cache_key}")
        except Exception as e:
            logger.error(f"Error extending TTL for {cache_key}: {e}")
    
    def invalidate_cache(self, cache_name: str = None):
        """Invalidate specific cache or all caches"""
        if not self.client:
            return
        
        try:
            if cache_name:
                pattern = f"safetyamp:{cache_name}*"
            else:
                pattern = "safetyamp:*"
            
            keys = self.client.keys(pattern)
            if keys:
                self.client.delete(*keys)
                logger.info(f"Invalidated {len(keys)} cache entries for {cache_name or 'all'}")
        except Exception as e:
            logger.error(f"Error invalidating cache: {e}")
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        if not self.client:
            return {"error": "Redis not available"}
        
        try:
            stats = {}
            for cache_name in self.default_ttl.keys():
                cache_key = self._get_cache_key(cache_name)
                metadata_key = self._get_metadata_key(cache_name)
                
                # Check if cache exists
                exists = self.client.exists(cache_key)
                if exists:
                    ttl = self.client.ttl(cache_key)
                    metadata = self.client.get(metadata_key)
                    if metadata:
                        metadata = json.loads(metadata)
                        stats[cache_name] = {
                            'exists': True,
                            'ttl_seconds': ttl,
                            'created_at': metadata.get('created_at'),
                            'item_count': metadata.get('item_count', 0)
                        }
                    else:
                        stats[cache_name] = {'exists': True, 'ttl_seconds': ttl}
                else:
                    stats[cache_name] = {'exists': False}
            
            return stats
        except Exception as e:
            logger.error(f"Error getting cache stats: {e}")
            return {"error": str(e)}
    
    def set_cache_ttl(self, cache_name: str, hours: int):
        """Set custom TTL for a specific cache type"""
        self.default_ttl[cache_name] = hours * 3600
        logger.info(f"Set TTL for {cache_name} to {hours} hours")
    
    def health_check(self) -> bool:
        """Check Redis connection health"""
        if not self.client:
            return False
        
        try:
            self.client.ping()
            return True
        except Exception:
            return False