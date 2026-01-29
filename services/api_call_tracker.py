"""
API Call Tracker for monitoring dashboard.

Tracks API calls to external services (SafetyAmp, Samsara, MS Graph, Viewpoint)
using a Redis ring buffer for efficient storage and retrieval.
"""

import json
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import redis

from utils.logger import get_logger

logger = get_logger("api_call_tracker")

# Redis key for the API calls list
REDIS_KEY = "safetyamp:api_calls"


class ApiCallTracker:
    """
    Tracks API calls to external services using a Redis ring buffer.

    Features:
    - Stores last N API calls (configurable max_entries)
    - Supports filtering by service, method, status, correlation_id
    - Provides statistics and aggregations
    - Gracefully handles Redis unavailability
    """

    def __init__(
        self,
        redis_host: str = "localhost",
        redis_port: int = 6379,
        redis_db: int = 0,
        redis_password: Optional[str] = None,
        max_entries: int = 100,
    ):
        """
        Initialize the API call tracker.

        Args:
            redis_host: Redis server hostname
            redis_port: Redis server port
            redis_db: Redis database number
            redis_password: Optional Redis password
            max_entries: Maximum number of entries to keep in ring buffer
        """
        self.redis_host = redis_host
        self.redis_port = redis_port
        self.redis_db = redis_db
        self.redis_password = redis_password
        self.max_entries = max_entries
        self.redis_client: Optional[redis.Redis] = None

        self._init_redis()

    def _init_redis(self) -> None:
        """Initialize Redis connection."""
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
            logger.info(
                f"API Call Tracker connected to Redis at {self.redis_host}:{self.redis_port}"
            )
        except Exception as e:
            logger.warning(
                f"API Call Tracker Redis connection failed: {e}. "
                "Call tracking will be disabled."
            )
            self.redis_client = None

    def record_call(
        self,
        service: str,
        method: str,
        endpoint: str,
        status_code: int,
        duration_ms: int,
        error_message: Optional[str] = None,
        correlation_id: Optional[str] = None,
        request_payload: Optional[Dict[str, Any]] = None,
        response_summary: Optional[str] = None,
    ) -> Optional[str]:
        """
        Record an API call to the ring buffer.

        Args:
            service: Service name (safetyamp, samsara, msgraph, viewpoint)
            method: HTTP method (GET, POST, PUT, PATCH, DELETE)
            endpoint: API endpoint path
            status_code: HTTP response status code
            duration_ms: Request duration in milliseconds
            error_message: Optional error message for failed calls
            correlation_id: Optional correlation ID for sync session tracking
            request_payload: Optional summary of request payload
            response_summary: Optional summary of response

        Returns:
            The unique ID of the recorded call, or None if recording failed
        """
        if not self.redis_client:
            return None

        call_id = str(uuid.uuid4())
        timestamp = datetime.now(timezone.utc).isoformat()

        call_record = {
            "id": call_id,
            "timestamp": timestamp,
            "service": service,
            "method": method.upper(),
            "endpoint": endpoint,
            "status_code": status_code,
            "duration_ms": duration_ms,
            "error_message": error_message,
            "correlation_id": correlation_id,
        }

        # Optionally include payload/response summaries (truncated for storage)
        if request_payload:
            call_record["request_summary"] = str(request_payload)[:200]
        if response_summary:
            call_record["response_summary"] = str(response_summary)[:200]

        try:
            # Push to head of list (newest first)
            self.redis_client.lpush(REDIS_KEY, json.dumps(call_record))

            # Trim to maintain ring buffer size
            self.redis_client.ltrim(REDIS_KEY, 0, self.max_entries - 1)

            logger.debug(
                f"Recorded API call: {service} {method} {endpoint} -> {status_code}"
            )
            return call_id

        except Exception as e:
            logger.error(f"Failed to record API call: {e}")
            return None

    def get_recent_calls(
        self,
        limit: int = 100,
        service: Optional[str] = None,
        method: Optional[str] = None,
        errors_only: bool = False,
        correlation_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Retrieve recent API calls with optional filtering.

        Args:
            limit: Maximum number of calls to return
            service: Filter by service name
            method: Filter by HTTP method
            errors_only: If True, only return calls with status >= 400
            correlation_id: Filter by correlation ID

        Returns:
            List of API call records, newest first
        """
        if not self.redis_client:
            return []

        try:
            # Fetch more than limit to account for filtering
            fetch_limit = min(limit * 3, self.max_entries)
            raw_calls = self.redis_client.lrange(REDIS_KEY, 0, fetch_limit - 1)

            calls = []
            for raw_call in raw_calls:
                try:
                    call = json.loads(raw_call)

                    # Apply filters
                    if service and call.get("service") != service:
                        continue
                    if method and call.get("method") != method.upper():
                        continue
                    if errors_only and call.get("status_code", 0) < 400:
                        continue
                    if correlation_id and call.get("correlation_id") != correlation_id:
                        continue

                    calls.append(call)

                    if len(calls) >= limit:
                        break

                except json.JSONDecodeError:
                    logger.warning(f"Invalid JSON in API call log: {raw_call[:50]}...")
                    continue

            return calls

        except Exception as e:
            logger.error(f"Failed to get recent API calls: {e}")
            return []

    def get_call_stats(
        self,
        service: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Get aggregated statistics about API calls.

        Args:
            service: Optional filter by service name

        Returns:
            Dictionary with statistics including:
            - total_calls: Total number of calls
            - by_service: Breakdown by service
            - error_count: Number of errors (status >= 400)
            - success_rate: Percentage of successful calls
            - avg_duration_ms: Average call duration
        """
        calls = self.get_recent_calls(limit=self.max_entries, service=service)

        if not calls:
            return {
                "total_calls": 0,
                "by_service": {},
                "error_count": 0,
                "success_rate": 100.0,
                "avg_duration_ms": 0,
            }

        by_service: Dict[str, int] = {}
        error_count = 0
        total_duration = 0

        for call in calls:
            # Count by service
            svc = call.get("service", "unknown")
            by_service[svc] = by_service.get(svc, 0) + 1

            # Count errors
            if call.get("status_code", 0) >= 400:
                error_count += 1

            # Sum durations
            total_duration += call.get("duration_ms", 0)

        total_calls = len(calls)
        success_count = total_calls - error_count
        success_rate = (success_count / total_calls * 100) if total_calls > 0 else 100.0
        avg_duration = total_duration / total_calls if total_calls > 0 else 0

        return {
            "total_calls": total_calls,
            "by_service": by_service,
            "error_count": error_count,
            "success_rate": round(success_rate, 1),
            "avg_duration_ms": round(avg_duration, 1),
        }

    def clear_all(self) -> bool:
        """
        Clear all recorded API calls.

        Returns:
            True if successful, False otherwise
        """
        if not self.redis_client:
            return False

        try:
            self.redis_client.delete(REDIS_KEY)
            logger.info("Cleared all API call records")
            return True
        except Exception as e:
            logger.error(f"Failed to clear API calls: {e}")
            return False

    def get_calls_count(self) -> int:
        """
        Get the total number of recorded calls.

        Returns:
            Number of calls in the buffer
        """
        if not self.redis_client:
            return 0

        try:
            return self.redis_client.llen(REDIS_KEY)
        except Exception as e:
            logger.error(f"Failed to get call count: {e}")
            return 0


# Global singleton instance - will be initialized when needed
_api_call_tracker: Optional[ApiCallTracker] = None


def get_api_call_tracker() -> Optional[ApiCallTracker]:
    """Get the global API call tracker instance."""
    return _api_call_tracker


def initialize_api_call_tracker(
    redis_host: str = "localhost",
    redis_port: int = 6379,
    redis_db: int = 0,
    redis_password: Optional[str] = None,
    max_entries: int = 100,
) -> ApiCallTracker:
    """
    Initialize the global API call tracker.

    Args:
        redis_host: Redis server hostname
        redis_port: Redis server port
        redis_db: Redis database number
        redis_password: Optional Redis password
        max_entries: Maximum number of entries to keep

    Returns:
        The initialized ApiCallTracker instance
    """
    global _api_call_tracker
    _api_call_tracker = ApiCallTracker(
        redis_host=redis_host,
        redis_port=redis_port,
        redis_db=redis_db,
        redis_password=redis_password,
        max_entries=max_entries,
    )
    return _api_call_tracker
