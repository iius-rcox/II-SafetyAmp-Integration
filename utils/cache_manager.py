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

logger = get_logger("cache_manager")

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
    
    def save_cache(self, cache_name: str, data: List[Dict[str, Any]], 
                   metadata: Optional[Dict[str, Any]] = None) -> bool:
        """Save data to both Redis and file cache"""
        success = True
        
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
                        "created": time.time(),
                        "items": len(data),
                        "source": "api"
                    }
                metadata["last_updated"] = time.time()
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
                    "created": time.time(),
                    "items": len(data),
                    "source": "api"
                }
            metadata["last_updated"] = time.time()
            
            with open(metadata_file, 'w') as f:
                json.dump(metadata, f, indent=2)
                
            logger.info(f"Saved {len(data)} items to file cache: {cache_name}")
        except Exception as e:
            logger.error(f"File save failed for {cache_name}: {e}")
            success = False
        
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
    
    def is_cache_valid(self, cache_name: str) -> bool:
        """Check if cache is still valid (not expired)"""
        if self.redis_client:
            try:
                cache_key = self._get_cache_key(cache_name)
                return self.redis_client.exists(cache_key) > 0
            except Exception as e:
                logger.warning(f"Redis cache validation failed for {cache_name}: {e}")
        
        # Fallback to file-based validation
        cache_file = self.cache_dir / f"{cache_name}.json"
        if not cache_file.exists():
            return False
        
        # Check file age
        file_age = time.time() - cache_file.stat().st_mtime
        max_age = self.cache_ttl_hours * 3600
        
        return file_age < max_age
    
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
            return True
        except Exception as e:
            logger.error(f"Error marking cache {cache_name} as refreshed: {e}")
            return False 