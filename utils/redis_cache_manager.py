import redis
import json
import time
import os
from datetime import datetime, timedelta
from utils.logger import get_logger
from config import settings

logger = get_logger("redis_cache")

class RedisCacheManager:
    def __init__(self, host=None, port=None, db=None, password=None):
        self.host = host or settings.REDIS_HOST
        self.port = port or settings.REDIS_PORT
        self.db = db or settings.REDIS_DB
        self.password = password or settings.REDIS_PASSWORD
        self.client = None
        self._connect()
    
    def _connect(self):
        """Establish Redis connection"""
        try:
            connection_kwargs = {
                'host': self.host,
                'port': self.port,
                'db': self.db,
                'decode_responses': True,
                'socket_connect_timeout': 5,
                'socket_timeout': 5
            }
            
            if self.password:
                connection_kwargs['password'] = self.password
            
            self.client = redis.Redis(**connection_kwargs)
            self.client.ping()
            logger.info(f"Connected to Redis at {self.host}:{self.port}")
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
            self.client = None
    
    def get_cached_data(self, cache_name, fetch_function, max_age_hours=None, force_refresh=False):
        """Get cached data from Redis with intelligent fallback"""
        if not self.client:
            # Fallback to fetch function if Redis unavailable
            logger.warning("Redis unavailable, fetching fresh data")
            return fetch_function()
        
        max_age_hours = max_age_hours or settings.CACHE_TTL_HOURS
        cache_key = f"safetyamp:{cache_name}"
        
        try:
            if not force_refresh:
                # Try to get from cache
                cached_data = self.client.get(cache_key)
                if cached_data:
                    data = json.loads(cached_data)
                    logger.info(f"Using cached data for {cache_name}")
                    return data
            
            # Fetch fresh data
            logger.info(f"Fetching fresh data for {cache_name}")
            data = fetch_function()
            
            if data is not None:
                # Cache the data
                self.client.setex(
                    cache_key,
                    timedelta(hours=max_age_hours),
                    json.dumps(data, default=str)
                )
                logger.info(f"Cached {cache_name} with {len(data) if isinstance(data, list) else 'data'}")
            
            return data
            
        except Exception as e:
            logger.error(f"Redis cache error for {cache_name}: {e}")
            # Fallback to fetch function
            return fetch_function()
    
    def set_cache(self, cache_name, data, max_age_hours=None):
        """Manually set cache data"""
        if not self.client:
            logger.warning("Redis unavailable, cannot set cache")
            return False
        
        max_age_hours = max_age_hours or settings.CACHE_TTL_HOURS
        cache_key = f"safetyamp:{cache_name}"
        
        try:
            self.client.setex(
                cache_key,
                timedelta(hours=max_age_hours),
                json.dumps(data, default=str)
            )
            logger.info(f"Manually cached {cache_name}")
            return True
        except Exception as e:
            logger.error(f"Error setting cache for {cache_name}: {e}")
            return False
    
    def get_cache(self, cache_name):
        """Get cached data without fallback"""
        if not self.client:
            return None
        
        cache_key = f"safetyamp:{cache_name}"
        
        try:
            cached_data = self.client.get(cache_key)
            if cached_data:
                return json.loads(cached_data)
            return None
        except Exception as e:
            logger.error(f"Error getting cache for {cache_name}: {e}")
            return None
    
    def clear_cache(self, cache_name=None):
        """Clear cache entries"""
        if not self.client:
            logger.warning("Redis unavailable, cannot clear cache")
            return False
        
        try:
            if cache_name:
                pattern = f"safetyamp:{cache_name}"
            else:
                pattern = "safetyamp:*"
            
            keys = self.client.keys(pattern)
            if keys:
                self.client.delete(*keys)
                logger.info(f"Cleared {len(keys)} cache entries")
                return True
            return False
        except Exception as e:
            logger.error(f"Error clearing cache: {e}")
            return False
    
    def get_cache_info(self):
        """Get cache statistics"""
        if not self.client:
            return {"status": "unavailable"}
        
        try:
            info = self.client.info()
            keys = self.client.keys("safetyamp:*")
            return {
                "status": "connected",
                "host": self.host,
                "port": self.port,
                "db": self.db,
                "connected_clients": info.get("connected_clients", 0),
                "used_memory_human": info.get("used_memory_human", "0B"),
                "cache_keys": len(keys),
                "cache_patterns": list(set([key.split(":")[1] for key in keys if ":" in key]))
            }
        except Exception as e:
            logger.error(f"Error getting cache info: {e}")
            return {"status": "error", "error": str(e)}
    
    def is_available(self):
        """Check if Redis is available"""
        if not self.client:
            return False
        
        try:
            self.client.ping()
            return True
        except Exception:
            return False