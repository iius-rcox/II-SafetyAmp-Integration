import asyncio
import json
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

import redis

from utils.logger import get_logger
from utils.metrics import metrics
from utils.data_validator import validator
from config import config

logger = get_logger("data_manager")

# Prometheus gauges for cache telemetry (low-cardinality per cache name)
_cache_last_updated_ts = metrics.cache_last_updated_ts
_cache_items_total = metrics.cache_items_total
_cache_ttl_seconds = metrics.cache_ttl_seconds


class DataManager:
    """Unified data manager that handles:
    - Redis/file caching with TTL and metadata
    - In-memory Vista data lifecycle (employees/jobs)
    - Validation utilities bridge
    """

    def __init__(self):
        # Cache config
        self.cache_dir = Path("cache")
        self.cache_dir.mkdir(exist_ok=True)

        self.redis_host = config.REDIS_HOST
        self.redis_port = int(config.REDIS_PORT)
        self.redis_db = int(config.REDIS_DB)
        self.redis_password = config.REDIS_PASSWORD

        self.redis_client = None
        self._init_redis()

        # TTL settings
        self.cache_ttl_hours = int(config.CACHE_TTL_HOURS)
        self.cache_refresh_interval_hours = int(config.CACHE_REFRESH_INTERVAL_HOURS)

        # Vista in-memory lifecycle
        self._employee_data: List[Dict[str, Any]] = []
        self._job_data: List[Dict[str, Any]] = []
        self._last_employee_refresh: Optional[datetime] = None
        self._last_job_refresh: Optional[datetime] = None
        self._refresh_interval = timedelta(minutes=int(config.VISTA_REFRESH_MINUTES))
        self._lock = asyncio.Lock()

    # ===== Redis/File cache =====
    def _init_redis(self):
        try:
            self.redis_client = redis.Redis(
                host=self.redis_host,
                port=self.redis_port,
                db=self.redis_db,
                password=self.redis_password,
                decode_responses=True,
                socket_connect_timeout=5,
                socket_timeout=5,
            )
            self.redis_client.ping()
            logger.info(f"Redis connected successfully to {self.redis_host}:{self.redis_port}")
        except Exception as e:
            logger.warning(f"Redis connection failed: {e}. Falling back to file-based caching.")
            self.redis_client = None

    def _get_cache_key(self, cache_name: str) -> str:
        return f"safetyamp:{cache_name}"

    def _get_metadata_key(self, cache_name: str) -> str:
        return f"safetyamp:{cache_name}:metadata"

    def get_cache_info(self) -> Dict[str, Any]:
        if self.redis_client:
            try:
                keys = self.redis_client.keys("safetyamp:*")
                cache_info: Dict[str, Any] = {
                    "type": "redis",
                    "host": self.redis_host,
                    "port": self.redis_port,
                    "connected": True,
                    "total_keys": len(keys),
                    "caches": {},
                }
                for key in keys:
                    if not key.endswith(":metadata"):
                        cache_name = key.replace("safetyamp:", "")
                        ttl = self.redis_client.ttl(key)
                        size = len(self.redis_client.get(key) or "")
                        cache_info["caches"][cache_name] = {
                            "ttl_seconds": ttl,
                            "size_bytes": size,
                            "expires_in": f"{ttl//3600}h {(ttl%3600)//60}m" if ttl and ttl > 0 else "expired",
                        }
                        try:
                            _cache_items_total.labels(cache=cache_name).set(size)
                            if ttl is not None and ttl >= 0:
                                _cache_ttl_seconds.labels(cache=cache_name).set(ttl)
                        except Exception:
                            pass
                return cache_info
            except Exception as e:
                logger.error(f"Error getting Redis cache info: {e}")

        cache_files = list(self.cache_dir.glob("*.json"))
        return {
            "type": "file",
            "connected": False,
            "total_files": len(cache_files),
            "caches": {f.stem: {"path": str(f), "size": f.stat().st_size} for f in cache_files},
        }

    def get_cached_data(self, cache_name: str) -> Optional[List[Dict[str, Any]]]:
        if self.redis_client:
            try:
                cache_key = self._get_cache_key(cache_name)
                cached_data = self.redis_client.get(cache_key)
                if cached_data:
                    logger.info(f"Using cached data for {cache_name} from Redis")
                    return json.loads(cached_data)
            except Exception as e:
                logger.warning(f"Redis get failed for {cache_name}: {e}")

        cache_file = self.cache_dir / f"{cache_name}.json"
        if cache_file.exists():
            try:
                with open(cache_file, "r") as f:
                    data = json.load(f)
                logger.info(f"Using cached data for {cache_name} from file")
                return data
            except Exception as e:
                logger.error(f"Error reading cache file {cache_file}: {e}")
        return None

    def get_cached_data_with_fallback(
        self,
        cache_name: str,
        fetch_func,
        max_age_hours: int = 1,
        force_refresh: bool = False,
    ) -> Optional[List[Dict[str, Any]]]:
        if not force_refresh:
            cached_data = self.get_cached_data(cache_name)
            if cached_data is not None:
                if self.is_cache_valid(cache_name, max_age_hours):
                    logger.info(f"Using valid cached data for {cache_name}")
                    return cached_data
                else:
                    logger.info(f"Cache for {cache_name} is expired, fetching fresh data")

        try:
            logger.info(f"Fetching fresh data for {cache_name}")
            fresh_data = fetch_func()
            if fresh_data is not None:
                self.save_cache(cache_name, fresh_data)
                logger.info(f"Saved fresh data to cache for {cache_name}: {len(fresh_data)} items")
                return fresh_data
            else:
                logger.warning(f"Fetch function returned None for {cache_name}")
                return self.get_cached_data(cache_name)
        except Exception as e:
            logger.error(f"Error fetching fresh data for {cache_name}: {e}")
            return self.get_cached_data(cache_name)

    def is_cache_valid(self, cache_name: str, max_age_hours: int = 1) -> bool:
        try:
            if self.redis_client:
                metadata_key = self._get_metadata_key(cache_name)
                metadata_json = self.redis_client.get(metadata_key)
                if metadata_json:
                    metadata = json.loads(metadata_json)
                    cache_age_hours = (time.time() - metadata.get("last_updated", 0)) / 3600
                    return cache_age_hours <= max_age_hours
            metadata_file = self.cache_dir / f"{cache_name}_metadata.json"
            if metadata_file.exists():
                with open(metadata_file, "r") as f:
                    metadata = json.load(f)
                cache_age_hours = (time.time() - metadata.get("last_updated", 0)) / 3600
                return cache_age_hours <= max_age_hours
        except Exception as e:
            logger.warning(f"Error checking cache validity for {cache_name}: {e}")
        return False

    def save_cache(self, cache_name: str, data: List[Dict[str, Any]], metadata: Optional[Dict[str, Any]] = None) -> bool:
        success = True
        now_ts = time.time()

        if self.redis_client:
            try:
                cache_key = self._get_cache_key(cache_name)
                metadata_key = self._get_metadata_key(cache_name)
                ttl_seconds = self.cache_ttl_hours * 3600
                self.redis_client.setex(cache_key, ttl_seconds, json.dumps(data))
                if metadata is None:
                    metadata = {"created": now_ts, "items": len(data), "source": "api"}
                metadata["last_updated"] = now_ts
                self.redis_client.setex(metadata_key, ttl_seconds, json.dumps(metadata))
                logger.info(f"Saved {len(data)} items to Redis cache: {cache_name}")
            except Exception as e:
                logger.error(f"Redis save failed for {cache_name}: {e}")
                success = False

        try:
            cache_file = self.cache_dir / f"{cache_name}.json"
            metadata_file = self.cache_dir / f"{cache_name}_metadata.json"
            with open(cache_file, "w") as f:
                json.dump(data, f, indent=2)
            if metadata is None:
                metadata = {"created": now_ts, "items": len(data), "source": "api"}
            metadata["last_updated"] = now_ts
            with open(metadata_file, "w") as f:
                json.dump(metadata, f, indent=2)
            logger.info(f"Saved {len(data)} items to file cache: {cache_name}")
        except Exception as e:
            logger.error(f"File save failed for {cache_name}: {e}")
            success = False

        try:
            _cache_items_total.labels(cache=cache_name).set(len(data))
            _cache_last_updated_ts.labels(cache=cache_name).set(now_ts)
            _cache_ttl_seconds.labels(cache=cache_name).set(self.cache_ttl_hours * 3600)
        except Exception:
            pass
        return success

    def update_cache_directly(self, cache_name: str, data: List[Dict[str, Any]], source: str = "sync") -> bool:
        metadata = {
            "created": time.time(),
            "items": len(data),
            "source": source,
            "sync_timestamp": time.time(),
        }
        success = self.save_cache(cache_name, data, metadata)
        if success:
            logger.info(f"Direct cache update successful for {cache_name}: {len(data)} items from {source}")
        else:
            logger.error(f"Direct cache update failed for {cache_name}")
        return success

    def invalidate_cache(self, cache_name: str) -> bool:
        success = True
        if self.redis_client:
            try:
                cache_key = self._get_cache_key(cache_name)
                metadata_key = self._get_metadata_key(cache_name)
                self.redis_client.delete(cache_key, metadata_key)
                logger.info(f"Invalidated Redis cache: {cache_name}")
            except Exception as e:
                logger.error(f"Redis invalidation failed for {cache_name}: {e}")
                success = False
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
        stats: Dict[str, Any] = {"redis_connected": self.redis_client is not None, "cache_ttl_hours": self.cache_ttl_hours, "caches": {}}
        if self.redis_client:
            try:
                keys = self.redis_client.keys("safetyamp:*")
                for key in keys:
                    if not key.endswith(":metadata"):
                        cache_name = key.replace("safetyamp:", "")
                        ttl = self.redis_client.ttl(key)
                        data = self.redis_client.get(key)
                        size = len(data) if data else 0
                        stats["caches"][cache_name] = {"type": "redis", "ttl_seconds": ttl, "size_bytes": size, "valid": ttl > 0}
            except Exception as e:
                logger.error(f"Error getting Redis stats: {e}")
        cache_files = list(self.cache_dir.glob("*.json"))
        for cache_file in cache_files:
            if not cache_file.name.endswith("_metadata.json"):
                cache_name = cache_file.stem
                if cache_name not in stats["caches"]:
                    file_age = time.time() - cache_file.stat().st_mtime
                    max_age = self.cache_ttl_hours * 3600
                    stats["caches"][cache_name] = {"type": "file", "size_bytes": cache_file.stat().st_size, "age_seconds": file_age, "valid": file_age < max_age}
        return stats

    def should_refresh_cache(self, cache_name: str) -> bool:
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
                    return True
            except Exception as e:
                logger.warning(f"Error checking cache refresh time for {cache_name}: {e}")
                return True
        metadata_file = self.cache_dir / f"{cache_name}_metadata.json"
        if not metadata_file.exists():
            return True
        try:
            with open(metadata_file, "r") as f:
                metadata = json.load(f)
            last_refresh = metadata.get("last_refresh", 0)
            current_time = time.time()
            refresh_interval_seconds = self.cache_refresh_interval_hours * 3600
            return (current_time - last_refresh) >= refresh_interval_seconds
        except Exception as e:
            logger.warning(f"Error checking file cache refresh time for {cache_name}: {e}")
            return True

    def mark_cache_refreshed(self, cache_name: str) -> bool:
        try:
            metadata = {"last_refresh": time.time(), "refresh_interval_hours": self.cache_refresh_interval_hours}
            if self.redis_client:
                metadata_key = self._get_metadata_key(cache_name)
                ttl_seconds = self.cache_ttl_hours * 3600
                self.redis_client.setex(metadata_key, ttl_seconds, json.dumps(metadata))
            metadata_file = self.cache_dir / f"{cache_name}_metadata.json"
            with open(metadata_file, "w") as f:
                json.dump(metadata, f, indent=2)
            logger.info(f"Marked cache {cache_name} as refreshed")
            try:
                _cache_last_updated_ts.labels(cache=cache_name).set(time.time())
            except Exception:
                pass
            return True
        except Exception as e:
            logger.error(f"Error marking cache {cache_name} as refreshed: {e}")
            return False

    # ===== Vista in-memory lifecycle =====
    async def get_employee_data(self) -> List[Dict[str, Any]]:
        async with self._lock:
            if self._should_refresh_employees():
                await self._refresh_employee_data()
            return self._employee_data.copy()

    async def get_job_data(self) -> List[Dict[str, Any]]:
        async with self._lock:
            if self._should_refresh_jobs():
                await self._refresh_job_data()
            return self._job_data.copy()

    def set_employee_data(self, employee_data: List[Dict[str, Any]]):
        self._employee_data = employee_data
        self._last_employee_refresh = datetime.now()
        logger.info(f"Loaded {len(employee_data)} employees into memory")

    def set_job_data(self, job_data: List[Dict[str, Any]]):
        self._job_data = job_data
        self._last_job_refresh = datetime.now()
        logger.info(f"Loaded {len(job_data)} jobs into memory")

    def get_employee_by_id(self, employee_id: int) -> Optional[Dict[str, Any]]:
        return next((emp for emp in self._employee_data if emp.get("Employee") == employee_id), None)

    def get_employees_by_department(self, department: str) -> List[Dict[str, Any]]:
        return [emp for emp in self._employee_data if emp.get("PRDept") == department]

    def search_employees(self, search_term: str) -> List[Dict[str, Any]]:
        search_term_lower = search_term.lower()
        return [
            emp
            for emp in self._employee_data
            if (
                search_term_lower in str(emp.get("FirstName", "")).lower()
                or search_term_lower in str(emp.get("LastName", "")).lower()
                or search_term_lower in str(emp.get("Email", "")).lower()
            )
        ]

    def get_job_by_code(self, job_code: str) -> Optional[Dict[str, Any]]:
        return next((job for job in self._job_data if job.get("Job") == job_code), None)

    def _should_refresh_employees(self) -> bool:
        return not self._employee_data or not self._last_employee_refresh or (datetime.now() - self._last_employee_refresh) > self._refresh_interval

    def _should_refresh_jobs(self) -> bool:
        return not self._job_data or not self._last_job_refresh or (datetime.now() - self._last_job_refresh) > self._refresh_interval

    async def _refresh_employee_data(self):
        logger.info("Employee data refresh requested")

    async def _refresh_job_data(self):
        logger.info("Job data refresh requested")

    # ===== Validation bridge =====
    def validate_employee_data(self, payload: Dict[str, Any], emp_id: str, full_name: str):
        return validator.validate_employee_data(payload, emp_id, full_name)

    def validate_site_data(self, payload: Dict[str, Any], site_id: str):
        return validator.validate_site_data(payload, site_id)

    def validate_vehicle_data(self, payload: Dict[str, Any], asset_id: str):
        return validator.validate_vehicle_data(payload, asset_id)

    def clean_phone(self, phone: Optional[str]) -> Optional[str]:
        return validator.clean_phone(phone)

    def normalize_gender(self, gender_raw: Optional[str]) -> Optional[str]:
        return validator.normalize_gender(gender_raw)

    def format_date(self, val: Optional[str]) -> Optional[str]:
        return validator.format_date(val)


# Global instance for easy access
data_manager = DataManager()