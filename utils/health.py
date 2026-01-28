from typing import Dict, Any
import time
import requests
from sqlalchemy import text
from utils.logger import get_logger
from services.viewpoint_api import ViewpointAPI
from services.safetyamp_api import SafetyAmpAPI
from services.samsara_api import SamsaraAPI
from services.data_manager import data_manager
from utils import failed_sync_tracker
from config import config

logger = get_logger("health")


def check_database() -> Dict[str, Any]:
    start = time.time()
    try:
        vp = ViewpointAPI()
        with vp._get_connection() as conn:
            conn.execute(text("SELECT 1"))
        return {"status": "healthy", "latency_ms": (time.time() - start) * 1000}
    except Exception as e:
        logger.warning(f"Database health check failed: {e}")
        return {
            "status": "unhealthy",
            "error": str(e),
            "latency_ms": (time.time() - start) * 1000,
        }


def check_safetyamp() -> Dict[str, Any]:
    start = time.time()
    try:
        api = SafetyAmpAPI()
        # Minimal request to validate token/access; limit result size
        data = api.get("/api/users", params={"limit": 1})
        ok = isinstance(data, list)
        return {
            "status": "healthy" if ok else "degraded",
            "latency_ms": (time.time() - start) * 1000,
        }
    except Exception as e:
        logger.warning(f"SafetyAmp health check failed: {e}")
        return {
            "status": "degraded",
            "error": str(e),
            "latency_ms": (time.time() - start) * 1000,
        }


def check_samsara() -> Dict[str, Any]:
    start = time.time()
    try:
        # Use direct request to keep it lightweight
        url = f"{config.SAMSARA_DOMAIN.rstrip('/')}/fleet/vehicles"
        headers = {
            "Authorization": f"Bearer {config.SAMSARA_API_KEY}",
            "Accept": "application/json",
        }
        resp = requests.get(url, headers=headers, params={"limit": 1}, timeout=5)
        resp.raise_for_status()
        return {"status": "healthy", "latency_ms": (time.time() - start) * 1000}
    except Exception as e:
        logger.warning(f"Samsara health check failed: {e}")
        return {
            "status": "degraded",
            "error": str(e),
            "latency_ms": (time.time() - start) * 1000,
        }


def check_cache() -> Dict[str, Any]:
    start = time.time()
    try:
        info = data_manager.get_cache_info()
        connected = bool(info.get("connected")) or info.get("type") == "redis"
        return {
            "status": "healthy" if connected else "degraded",
            "info": info,
            "latency_ms": (time.time() - start) * 1000,
        }
    except Exception as e:
        logger.warning(f"Cache health check failed: {e}")
        return {
            "status": "degraded",
            "error": str(e),
            "latency_ms": (time.time() - start) * 1000,
        }


def check_failed_syncs() -> Dict[str, Any]:
    """Check failed sync tracker status"""
    start = time.time()
    try:
        if (
            not failed_sync_tracker.failed_sync_tracker
            or not failed_sync_tracker.failed_sync_tracker.enabled
        ):
            return {"status": "disabled", "latency_ms": (time.time() - start) * 1000}

        stats = failed_sync_tracker.failed_sync_tracker.get_failure_stats()

        return {
            "status": "healthy",
            "total_failures": stats.get("total", 0),
            "by_entity_type": stats.get("by_entity_type", {}),
            "by_reason": stats.get("by_reason", {}),
            "oldest_failure": stats.get("oldest_failure"),
            "latency_ms": (time.time() - start) * 1000,
        }
    except Exception as e:
        logger.warning(f"Failed sync tracker health check failed: {e}")
        return {
            "status": "degraded",
            "error": str(e),
            "latency_ms": (time.time() - start) * 1000,
        }


def run_health_checks() -> Dict[str, Any]:
    checks = {
        "database": check_database(),
        "safetyamp": check_safetyamp(),
        "samsara": check_samsara(),
        "cache": check_cache(),
        "failed_syncs": check_failed_syncs(),
    }

    # Determine overall status
    # Do NOT mark overall unhealthy solely due to database issues to avoid liveness failures.
    # Treat database failures as degraded so the pod stays up, and operators can inspect logs/metrics.
    if any(
        checks[name]["status"] not in ("healthy", "disabled")
        for name in ("database", "safetyamp", "samsara", "cache", "failed_syncs")
    ):
        overall = "degraded"
    else:
        overall = "healthy"

    return {"status": overall, "checks": checks}
