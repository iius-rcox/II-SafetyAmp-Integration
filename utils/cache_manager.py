#!/usr/bin/env python3
"""
Cache Manager

This module provides caching functionality for SafetyAmp data to avoid
repeated API calls and improve performance.
"""

import json
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
from utils.logger import get_logger
import redis
from utils.metrics import metrics

logger = get_logger("cache_manager")

# Prometheus gauges for cache telemetry (low-cardinality per cache name)
_cache_last_updated_ts = metrics.cache_last_updated_ts
_cache_items_total = metrics.cache_items_total
_cache_ttl_seconds = metrics.cache_ttl_seconds

class CacheManager:
    """Enhanced cache manager with Redis support and direct update capabilities"""
    
    def __init__(self):
        self.cache_dir = Path("cache")
        self.cache_dir.mkdir(exist_ok=True)
        
        # Redis configuration
        self.redis_host = os.getenv("REDIS_HOST", "localhost")
        self.redis_port = int(os.getenv("REDIS_PORT", 6379))
        self.redis_db = int(os.getenv("REDIS_DB", 0))
        self.redis_password = os.getenv("REDIS_PASSWORD")
        
        # Initialize Redis connection
        self.redis_client = None
        self._init_redis()
        
        # Cache TTL in hours
        self.cache_ttl_hours = int(os.getenv("CACHE_TTL_HOURS", "4"))
        
        # Cache refresh interval in hours
        self.cache_refresh_interval_hours = int(os.getenv("CACHE_REFRESH_INTERVAL_HOURS", "4"))
        
    def _init_redis(self):
        """Initialize Redis connection"""
        try:
            self.redis_client = redis.Redis(
                host=self.redis_host,
                port=self.redis_port,
                db=self.redis_db,
                password=self.redis_password,
                decode_responses=True,
                socket_connect_timeout=5,
                socket_timeout=5
            )
            # Test connection
            self.redis_client.ping()
            logger.info(f"Redis connected successfully to {self.redis_host}:{self.redis_port}")
        except Exception as e:
            logger.warning(f"Redis connection failed: {e}. Falling back to file-based caching.")
            self.redis_client = None
    
    def _get_cache_key(self, cache_name: str) -> str:
        """Generate Redis cache key"""
        return f"safetyamp:{cache_name}"
    
    def _get_metadata_key(self, cache_name: str) -> str:
        """Generate Redis metadata key"""
        return f"safetyamp:{cache_name}:metadata"
    
    def get_cache_info(self) -> Dict[str, Any]:
        """Get cache status and information"""
        if self.redis_client:
            try:
                keys = self.redis_client.keys("safetyamp:*")
                cache_info = {
                    "type": "redis",
                    "host": self.redis_host,
                    "port": self.redis_port,
                    "connected": True,
                    "total_keys": len(keys),
                    "caches": {}
                }
                
                for key in keys:
                    if not key.endswith(":metadata"):
                        cache_name = key.replace("safetyamp:", "")
                        ttl = self.redis_client.ttl(key)
                        size = len(self.redis_client.get(key) or "")
                        cache_info["caches"][cache_name] = {
                            "ttl_seconds": ttl,
                            "size_bytes": size,
                            "expires_in": f"{ttl//3600}h {(ttl%3600)//60}m" if ttl > 0 else "expired"
                        }
                        # Update gauges opportunistically
                        try:
                            _cache_items_total.labels(cache=cache_name).set(size)
                            if ttl is not None and ttl >= 0:
                                _cache_ttl_seconds.labels(cache=cache_name).set(ttl)
                        except Exception:
                            pass
                
                return cache_info
            except Exception as e:
                logger.error(f"Error getting Redis cache info: {e}")
        
        # Fallback to file-based info
        cache_files = list(self.cache_dir.glob("*.json"))
        return {
            "type": "file",
            "connected": False,
            "total_files": len(cache_files),
            "caches": {f.stem: {"path": str(f), "size": f.stat().st_size} for f in cache_files}
        }
    
    def get_cached_data(self, cache_name: str) -> Optional[List[Dict[str, Any]]]:
        """Get cached data from Redis or file"""
        if self.redis_client:
            try:
                cache_key = self._get_cache_key(cache_name)
                cached_data = self.redis_client.get(cache_key)
                if cached_data:
                    logger.info(f"Using cached data for {cache_name} from Redis")
                    return json.loads(cached_data)
            except Exception as e:
                logger.warning(f"Redis get failed for {cache_name}: {e}")
        
        # Fallback to file-based cache
        cache_file = self.cache_dir / f"{cache_name}.json"
        if cache_file.exists():
            try:
                with open(cache_file, 'r') as f:
                    data = json.load(f)
                logger.info(f"Using cached data for {cache_name} from file")
                return data
            except Exception as e:
                logger.error(f"Error reading cache file {cache_file}: {e}")
        
        return None
    
    def get_cached_data_with_fallback(self, cache_name: str, fetch_func, 
                                     max_age_hours: int = 1, 
                                     force_refresh: bool = False) -> Optional[List[Dict[str, Any]]]:
        """
        Get cached data with fallback to fetch function if cache is invalid or missing
        
        Args:
            cache_name: Name of the cache
            fetch_func: Function to call if cache is invalid/missing
            max_age_hours: Maximum age of cache in hours
            force_refresh: Force refresh the cache
            
        Returns:
            Cached data or freshly fetched data
        """
        # Check if we should use cached data
        if not force_refresh:
            cached_data = self.get_cached_data(cache_name)
            if cached_data is not None:
                # Check if cache is still valid
                if self.is_cache_valid(cache_name, max_age_hours):
                    logger.info(f"Using valid cached data for {cache_name}")
                    return cached_data
                else:
                    logger.info(f"Cache for {cache_name} is expired, fetching fresh data")
        
        # Fetch fresh data
        try:
            logger.info(f"Fetching fresh data for {cache_name}")
            fresh_data = fetch_func()
            
            if fresh_data is not None:
                # Save to cache
                self.save_cache(cache_name, fresh_data)
                logger.info(f"Saved fresh data to cache for {cache_name}: {len(fresh_data)} items")
                return fresh_data
            else:
                logger.warning(f"Fetch function returned None for {cache_name}")
                # Return cached data even if expired as fallback
                return self.get_cached_data(cache_name)
                
        except Exception as e:
            logger.error(f"Error fetching fresh data for {cache_name}: {e}")
            # Return cached data even if expired as fallback
            return self.get_cached_data(cache_name)
    
    def is_cache_valid(self, cache_name: str, max_age_hours: int = 1) -> bool:
        """
        Check if cache is still valid based on age
        
        Args:
            cache_name: Name of the cache
            max_age_hours: Maximum age in hours
            
        Returns:
            True if cache is valid, False otherwise
        """
        try:
            # Check Redis metadata first
            if self.redis_client:
                metadata_key = self._get_metadata_key(cache_name)
                metadata_json = self.redis_client.get(metadata_key)
                if metadata_json:
                    metadata = json.loads(metadata_json)
                    cache_age_hours = (time.time() - metadata.get("last_updated", 0)) / 3600
                    return cache_age_hours <= max_age_hours
            
            # Fallback to file-based metadata
            metadata_file = self.cache_dir / f"{cache_name}_metadata.json"
            if metadata_file.exists():
                with open(metadata_file, 'r') as f:
                    metadata = json.load(f)
                cache_age_hours = (time.time() - metadata.get("last_updated", 0)) / 3600
                return cache_age_hours <= max_age_hours
                
        except Exception as e:
            logger.warning(f"Error checking cache validity for {cache_name}: {e}")
        
        # If we can't determine validity, assume invalid
        return False
    
    def save_cache(self, cache_name: str, data: List[Dict[str, Any]], 
                   metadata: Optional[Dict[str, Any]] = None) -> bool:
        """Save data to both Redis and file cache"""
        success = True
        now_ts = time.time()
        
        # Save to Redis
        if self.redis_client:
            try:
                cache_key = self._get_cache_key(cache_name)
                metadata_key = self._get_metadata_key(cache_name)
                
                # Save data with TTL
                ttl_seconds = self.cache_ttl_hours * 3600
                self.redis_client.setex(cache_key, ttl_seconds, json.dumps(data))
                
                # Save metadata
                if metadata is None:
                    metadata = {
                        "created": now_ts,
                        "items": len(data),
                        "source": "api"
                    }
                metadata["last_updated"] = now_ts
                self.redis_client.setex(metadata_key, ttl_seconds, json.dumps(metadata))
                
                logger.info(f"Saved {len(data)} items to Redis cache: {cache_name}")
            except Exception as e:
                logger.error(f"Redis save failed for {cache_name}: {e}")
                success = False
        
        # Save to file (backup)
        try:
            cache_file = self.cache_dir / f"{cache_name}.json"
            metadata_file = self.cache_dir / f"{cache_name}_metadata.json"
            
            with open(cache_file, 'w') as f:
                json.dump(data, f, indent=2)
            
            if metadata is None:
                metadata = {
                    "created": now_ts,
                    "items": len(data),
                    "source": "api"
                }
            metadata["last_updated"] = now_ts
            
            with open(metadata_file, 'w') as f:
                json.dump(metadata, f, indent=2)
                
            logger.info(f"Saved {len(data)} items to file cache: {cache_name}")
        except Exception as e:
            logger.error(f"File save failed for {cache_name}: {e}")
            success = False
        
        # Update Prometheus gauges
        try:
            _cache_items_total.labels(cache=cache_name).set(len(data))
            _cache_last_updated_ts.labels(cache=cache_name).set(now_ts)
            # Use full TTL horizon for visibility
            _cache_ttl_seconds.labels(cache=cache_name).set(self.cache_ttl_hours * 3600)
        except Exception:
            pass

        return success
    
    def update_cache_directly(self, cache_name: str, data: List[Dict[str, Any]], 
                             source: str = "sync") -> bool:
        """Direct cache update during sync operations (Option 2 implementation)"""
        metadata = {
            "created": time.time(),
            "items": len(data),
            "source": source,
            "sync_timestamp": time.time()
        }
        
        success = self.save_cache(cache_name, data, metadata)
        
        if success:
            logger.info(f"Direct cache update successful for {cache_name}: {len(data)} items from {source}")
        else:
            logger.error(f"Direct cache update failed for {cache_name}")
        
        return success
    
    def invalidate_cache(self, cache_name: str) -> bool:
        """Invalidate cache entries"""
        success = True
        
        # Invalidate Redis cache
        if self.redis_client:
            try:
                cache_key = self._get_cache_key(cache_name)
                metadata_key = self._get_metadata_key(cache_name)
                self.redis_client.delete(cache_key, metadata_key)
                logger.info(f"Invalidated Redis cache: {cache_name}")
            except Exception as e:
                logger.error(f"Redis invalidation failed for {cache_name}: {e}")
                success = False
        
        # Invalidate file cache
        try:
            cache_file = self.cache_dir / f"{cache_name}.json"
            metadata_file = self.cache_dir / f"{cache_name}_metadata.json"
            
            if cache_file.exists():
                cache_file.unlink()
            if metadata_file.exists():
                metadata_file.unlink()
                
            logger.info(f"Invalidated file cache: {cache_name}")
        except Exception as e:
            logger.error(f"File invalidation failed for {cache_name}: {e}")
            success = False
        
        return success
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get comprehensive cache statistics"""
        stats = {
            "redis_connected": self.redis_client is not None,
            "cache_ttl_hours": self.cache_ttl_hours,
            "caches": {}
        }
        
        if self.redis_client:
            try:
                keys = self.redis_client.keys("safetyamp:*")
                for key in keys:
                    if not key.endswith(":metadata"):
                        cache_name = key.replace("safetyamp:", "")
                        ttl = self.redis_client.ttl(key)
                        data = self.redis_client.get(key)
                        size = len(data) if data else 0
                        
                        stats["caches"][cache_name] = {
                            "type": "redis",
                            "ttl_seconds": ttl,
                            "size_bytes": size,
                            "valid": ttl > 0
                        }
            except Exception as e:
                logger.error(f"Error getting Redis stats: {e}")
        
        # Add file-based cache stats
        cache_files = list(self.cache_dir.glob("*.json"))
        for cache_file in cache_files:
            if not cache_file.name.endswith("_metadata.json"):
                cache_name = cache_file.stem
                if cache_name not in stats["caches"]:
                    file_age = time.time() - cache_file.stat().st_mtime
                    max_age = self.cache_ttl_hours * 3600
                    
                    stats["caches"][cache_name] = {
                        "type": "file",
                        "size_bytes": cache_file.stat().st_size,
                        "age_seconds": file_age,
                        "valid": file_age < max_age
                    }
        
        return stats
    
    def should_refresh_cache(self, cache_name: str) -> bool:
        """Check if it's time for a full cache refresh based on the refresh interval"""
        if self.redis_client:
            try:
                metadata_key = self._get_metadata_key(cache_name)
                metadata_json = self.redis_client.get(metadata_key)
                
                if metadata_json:
                    metadata = json.loads(metadata_json)
                    last_refresh = metadata.get("last_refresh", 0)
                    current_time = time.time()
                    refresh_interval_seconds = self.cache_refresh_interval_hours * 3600
                    
                    return (current_time - last_refresh) >= refresh_interval_seconds
                else:
                    # No metadata, need refresh
                    return True
            except Exception as e:
                logger.warning(f"Error checking cache refresh time for {cache_name}: {e}")
                return True
        
        # Fallback to file-based check
        metadata_file = self.cache_dir / f"{cache_name}_metadata.json"
        if not metadata_file.exists():
            return True
        
        try:
            with open(metadata_file, 'r') as f:
                metadata = json.load(f)
            
            last_refresh = metadata.get("last_refresh", 0)
            current_time = time.time()
            refresh_interval_seconds = self.cache_refresh_interval_hours * 3600
            
            return (current_time - last_refresh) >= refresh_interval_seconds
        except Exception as e:
            logger.warning(f"Error checking file cache refresh time for {cache_name}: {e}")
            return True
    
    def mark_cache_refreshed(self, cache_name: str) -> bool:
        """Mark cache as refreshed with current timestamp"""
        try:
            metadata = {
                "last_refresh": time.time(),
                "refresh_interval_hours": self.cache_refresh_interval_hours
            }
            
            # Update Redis metadata
            if self.redis_client:
                metadata_key = self._get_metadata_key(cache_name)
                ttl_seconds = self.cache_ttl_hours * 3600
                self.redis_client.setex(metadata_key, ttl_seconds, json.dumps(metadata))
            
            # Update file metadata
            metadata_file = self.cache_dir / f"{cache_name}_metadata.json"
            with open(metadata_file, 'w') as f:
                json.dump(metadata, f, indent=2)
            
            logger.info(f"Marked cache {cache_name} as refreshed")
            # Also bump last updated timestamp gauge (no item count change)
            try:
                _cache_last_updated_ts.labels(cache=cache_name).set(time.time())
            except Exception:
                pass
            return True
        except Exception as e:
            logger.error(f"Error marking cache {cache_name} as refreshed: {e}")
            return False 