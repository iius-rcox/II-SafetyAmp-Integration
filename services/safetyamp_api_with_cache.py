#!/usr/bin/env python3
"""
SafetyAmp API Service with Smart Caching

This module demonstrates how to integrate smart Redis caching with SafetyAmp API calls
to minimize API requests while keeping data fresh.
"""

from services.safetyamp_api import SafetyAmpAPI
from utils.smart_redis_cache import SmartRedisCache
from utils.logger import get_logger

logger = get_logger("safetyamp_api_cached")

class CachedSafetyAmpAPI(SafetyAmpAPI):
    def __init__(self):
        super().__init__()
        self.cache = SmartRedisCache()
    
    def get_all_employees(self, force_refresh=False):
        """
        Get all employees with intelligent caching
        
        - Uses cache if data is fresh (1 hour TTL)
        - Only calls API if cache is expired or forced
        - Extends cache TTL if data hasn't changed
        """
        def fetch_employees():
            logger.info("Fetching employees from SafetyAmp API")
            return super().get_all_paginated("employees")
        
        return self.cache.get_cached_data(
            cache_name="employees",
            fetch_function=fetch_employees,
            force_refresh=force_refresh,
            check_for_changes=True  # Check if data actually changed
        )
    
    def get_all_departments(self, force_refresh=False):
        """
        Get all departments with long-term caching
        
        - 2 hour TTL since departments rarely change
        - Extends TTL if no changes detected
        """
        def fetch_departments():
            logger.info("Fetching departments from SafetyAmp API")
            return super().get_all_paginated("departments")
        
        return self.cache.get_cached_data(
            cache_name="departments",
            fetch_function=fetch_departments,
            force_refresh=force_refresh,
            check_for_changes=True
        )
    
    def get_all_titles(self, force_refresh=False):
        """
        Get all titles with long-term caching
        
        - 2 hour TTL since titles rarely change
        """
        def fetch_titles():
            logger.info("Fetching titles from SafetyAmp API")
            return super().get_all_paginated("titles")
        
        return self.cache.get_cached_data(
            cache_name="titles",
            fetch_function=fetch_titles,
            force_refresh=force_refresh,
            check_for_changes=True
        )
    
    def get_all_jobs(self, force_refresh=False):
        """
        Get all jobs with moderate caching
        
        - 1 hour TTL for moderate changes
        """
        def fetch_jobs():
            logger.info("Fetching jobs from SafetyAmp API")
            return super().get_all_paginated("jobs")
        
        return self.cache.get_cached_data(
            cache_name="jobs",
            fetch_function=fetch_jobs,
            force_refresh=force_refresh,
            check_for_changes=True
        )
    
    def get_all_vehicles(self, force_refresh=False):
        """
        Get all vehicles with shorter caching
        
        - 30 minute TTL since vehicles change more frequently
        """
        def fetch_vehicles():
            logger.info("Fetching vehicles from SafetyAmp API")
            return super().get_all_paginated("vehicles")
        
        return self.cache.get_cached_data(
            cache_name="vehicles",
            fetch_function=fetch_vehicles,
            force_refresh=force_refresh,
            check_for_changes=True
        )
    
    def get_safety_events(self, force_refresh=False):
        """
        Get safety events with very short caching
        
        - 5 minute TTL since events are very dynamic
        """
        def fetch_events():
            logger.info("Fetching safety events from SafetyAmp API")
            return super().get_all_paginated("safety_events")
        
        return self.cache.get_cached_data(
            cache_name="safety_events",
            fetch_function=fetch_events,
            force_refresh=force_refresh,
            check_for_changes=True
        )
    
    def invalidate_cache(self, cache_type=None):
        """Invalidate specific cache or all caches"""
        self.cache.invalidate_cache(cache_type)
        logger.info(f"Invalidated cache for {cache_type or 'all'}")
    
    def get_cache_stats(self):
        """Get cache statistics for monitoring"""
        return self.cache.get_cache_stats()
    
    def force_refresh_all(self):
        """Force refresh all cached data"""
        logger.info("Force refreshing all cached data")
        self.get_all_employees(force_refresh=True)
        self.get_all_departments(force_refresh=True)
        self.get_all_titles(force_refresh=True)
        self.get_all_jobs(force_refresh=True)
        self.get_all_vehicles(force_refresh=True)
        self.get_safety_events(force_refresh=True)