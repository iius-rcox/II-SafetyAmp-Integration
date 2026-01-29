"""
Dashboard Data module for aggregating and formatting data for the monitoring dashboard.

Provides helper functions to:
- Aggregate sync metrics over time
- Get entity counts
- Calculate error rates
- Format data for charts
"""

from collections import defaultdict
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

from utils.logger import get_logger

logger = get_logger("dashboard_data")


class DashboardData:
    """
    Aggregates and formats data from various sources for the monitoring dashboard.

    Features:
    - Sync metrics aggregation
    - Entity counts
    - Cache statistics
    - Duration trends
    - Error rate calculations
    """

    def __init__(
        self,
        event_manager=None,
        data_manager=None,
    ):
        """
        Initialize the dashboard data aggregator.

        Args:
            event_manager: EventManager instance for sync history
            data_manager: DataManager instance for cache and entity data
        """
        self.event_manager = event_manager
        self.data_manager = data_manager

    def get_sync_metrics(self, hours: int = 24) -> Dict[str, Any]:
        """
        Get aggregated sync metrics for the specified time period.

        Args:
            hours: Time window in hours (default: 24)

        Returns:
            Dictionary with sync metrics
        """
        if not self.event_manager:
            return self._empty_metrics()

        try:
            summary = self.event_manager.change_tracker.get_summary_report(hours)

            sessions = summary.get("recent_sessions", [])
            by_operation = summary.get("by_operation", {})

            total_syncs = len(sessions)
            total_processed = sum(s.get("total_processed", 0) for s in sessions)
            total_created = sum(s.get("total_created", 0) for s in sessions)
            total_updated = sum(s.get("total_updated", 0) for s in sessions)
            total_errors = sum(s.get("total_errors", 0) for s in sessions)
            total_skipped = sum(s.get("total_skipped", 0) for s in sessions)

            # Calculate success rate
            success_rate = self._calculate_success_rate(total_processed, total_errors)

            # Calculate average duration
            durations = [
                s.get("duration_seconds", 0)
                for s in sessions
                if s.get("duration_seconds")
            ]
            avg_duration = sum(durations) / len(durations) if durations else 0

            return {
                "total_syncs": total_syncs,
                "successful_syncs": total_syncs
                - len([s for s in sessions if s.get("total_errors", 0) > 0]),
                "failed_syncs": len(
                    [s for s in sessions if s.get("total_errors", 0) > 0]
                ),
                "total_records_processed": total_processed,
                "total_created": total_created,
                "total_updated": total_updated,
                "total_errors": total_errors,
                "total_skipped": total_skipped,
                "success_rate": success_rate,
                "avg_duration_seconds": round(avg_duration, 2),
                "by_operation": by_operation,
                "by_entity_type": summary.get("by_entity_type", {}),
            }

        except Exception as e:
            logger.error(f"Error getting sync metrics: {e}")
            return self._empty_metrics()

    def _empty_metrics(self) -> Dict[str, Any]:
        """Return empty metrics structure."""
        return {
            "total_syncs": 0,
            "successful_syncs": 0,
            "failed_syncs": 0,
            "total_records_processed": 0,
            "total_created": 0,
            "total_updated": 0,
            "total_errors": 0,
            "total_skipped": 0,
            "success_rate": 100.0,
            "avg_duration_seconds": 0,
            "by_operation": {},
            "by_entity_type": {},
        }

    def get_sync_history(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get recent sync session history.

        Args:
            limit: Maximum number of sessions to return

        Returns:
            List of sync session records
        """
        if not self.event_manager:
            return []

        try:
            summary = self.event_manager.change_tracker.get_summary_report(
                hours=168
            )  # 7 days
            sessions = summary.get("recent_sessions", [])
            return sessions[:limit]

        except Exception as e:
            logger.error(f"Error getting sync history: {e}")
            return []

    def get_entity_counts(self) -> Dict[str, int]:
        """
        Get current entity counts from in-memory data.

        Returns:
            Dictionary mapping entity type to count
        """
        counts = {
            "employees": 0,
            "jobs": 0,
            "departments": 0,
            "vehicles": 0,
            "titles": 0,
        }

        if not self.data_manager:
            return counts

        try:
            # Get counts from data manager's in-memory data
            if hasattr(self.data_manager, "_employee_data"):
                counts["employees"] = len(self.data_manager._employee_data)

            if hasattr(self.data_manager, "_job_data"):
                counts["jobs"] = len(self.data_manager._job_data)

        except Exception as e:
            logger.error(f"Error getting entity counts: {e}")

        return counts

    def get_cache_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics.

        Returns:
            Dictionary with cache statistics
        """
        if not self.data_manager:
            return {
                "redis_connected": False,
                "cache_ttl_hours": 0,
                "caches": {},
            }

        try:
            return self.data_manager.get_cache_stats()
        except Exception as e:
            logger.error(f"Error getting cache stats: {e}")
            return {
                "redis_connected": False,
                "cache_ttl_hours": 0,
                "caches": {},
            }

    def get_sync_duration_trends(self, hours: int = 24) -> List[Dict[str, Any]]:
        """
        Get sync duration data over time for trend analysis.

        Args:
            hours: Time window in hours

        Returns:
            List of duration data points with timestamps
        """
        if not self.event_manager:
            return []

        try:
            summary = self.event_manager.change_tracker.get_summary_report(hours)
            sessions = summary.get("recent_sessions", [])

            trends = []
            for session in sessions:
                duration = session.get("duration_seconds", 0)
                start_time = session.get("start_time")

                if start_time:
                    trends.append(
                        {
                            "timestamp": start_time,
                            "duration_seconds": duration,
                            "session_id": session.get("session_id"),
                            "sync_type": session.get("sync_type"),
                        }
                    )

            # Sort by timestamp descending
            trends.sort(key=lambda x: x["timestamp"], reverse=True)
            return trends

        except Exception as e:
            logger.error(f"Error getting sync duration trends: {e}")
            return []

    def get_error_rate_over_time(self, hours: int = 24) -> List[Dict[str, Any]]:
        """
        Get error rate data over time.

        Args:
            hours: Time window in hours

        Returns:
            List of error rate data points
        """
        if not self.event_manager:
            return []

        try:
            summary = self.event_manager.change_tracker.get_summary_report(hours)
            sessions = summary.get("recent_sessions", [])

            error_rates = []
            for session in sessions:
                total = session.get("total_processed", 0)
                errors = session.get("total_errors", 0)
                rate = (errors / total * 100) if total > 0 else 0

                start_time = session.get("start_time")
                if start_time:
                    error_rates.append(
                        {
                            "timestamp": start_time,
                            "error_rate": round(rate, 2),
                            "total_processed": total,
                            "total_errors": errors,
                        }
                    )

            return error_rates

        except Exception as e:
            logger.error(f"Error getting error rate data: {e}")
            return []

    def get_records_by_time_range(self, time_range: str = "1d") -> Dict[str, Any]:
        """
        Get record counts aggregated by time range.

        Args:
            time_range: Time range string (1d, 7d, 30d, 6mo)

        Returns:
            Dictionary with time range data
        """
        hours_map = {
            "1d": 24,
            "7d": 168,
            "30d": 720,
            "6mo": 4320,
        }

        hours = hours_map.get(time_range, 24)

        if not self.event_manager:
            return {
                "time_range": time_range,
                "hours": hours,
                "total_records": 0,
                "by_entity_type": {},
                "data_points": [],
            }

        try:
            summary = self.event_manager.change_tracker.get_summary_report(hours)

            return {
                "time_range": time_range,
                "hours": hours,
                "total_records": summary.get("total_changes", 0),
                "by_entity_type": summary.get("by_entity_type", {}),
                "data_points": [],  # Would be populated with aggregated time series data
            }

        except Exception as e:
            logger.error(f"Error getting records by time range: {e}")
            return {
                "time_range": time_range,
                "hours": hours,
                "total_records": 0,
                "by_entity_type": {},
                "data_points": [],
            }

    def get_live_sync_status(self) -> Dict[str, Any]:
        """
        Get current live sync status.

        Returns:
            Dictionary with current sync state
        """
        return {
            "sync_in_progress": False,
            "last_sync_time": None,
            "current_operation": None,
            "progress_percent": 0,
        }

    def get_dependency_health(self) -> Dict[str, Any]:
        """
        Get health status of external dependencies.

        Returns:
            Dictionary with dependency health information
        """
        return {
            "database": {
                "status": "unknown",
                "latency_ms": 0,
            },
            "redis": {
                "status": "unknown",
                "latency_ms": 0,
            },
            "services": {
                "safetyamp": {"status": "unknown"},
                "samsara": {"status": "unknown"},
                "msgraph": {"status": "unknown"},
            },
        }

    def _calculate_success_rate(self, total: int, errors: int) -> float:
        """
        Calculate success rate percentage.

        Args:
            total: Total number of operations
            errors: Number of errors

        Returns:
            Success rate as percentage (0-100)
        """
        if total == 0:
            return 100.0

        success = total - errors
        return round((success / total) * 100, 1)

    def _aggregate_by_hour(
        self, data_points: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Aggregate data points by hour.

        Args:
            data_points: List of data points with timestamps

        Returns:
            Aggregated data points by hour
        """
        hourly = defaultdict(list)

        for point in data_points:
            timestamp_str = point.get("timestamp", "")
            try:
                timestamp = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
                hour_key = timestamp.replace(minute=0, second=0, microsecond=0)
                hourly[hour_key].append(point)
            except (ValueError, TypeError):
                continue

        aggregated = []
        for hour, points in sorted(hourly.items()):
            # Calculate aggregate for this hour
            values = [p.get("value", 0) for p in points]
            aggregated.append(
                {
                    "timestamp": hour.isoformat(),
                    "count": len(points),
                    "total": sum(values),
                    "avg": sum(values) / len(values) if values else 0,
                }
            )

        return aggregated

    def get_entity_diff(self, entity_type: str, entity_id: str) -> Dict[str, Any]:
        """
        Get diff between source and target data for an entity.

        Args:
            entity_type: Type of entity (employee, vehicle, etc.)
            entity_id: ID of the entity

        Returns:
            Dictionary with source_data, target_data, and diff
        """
        try:
            # Get source data from cache or fetch
            source_data = None
            target_data = None

            if self.data_manager:
                # Try to get from cached source data
                if entity_type == "employee":
                    source_data = self.data_manager.get_employee_by_id(entity_id)
                elif entity_type == "vehicle":
                    source_data = self.data_manager.get_vehicle_by_id(entity_id)
                elif entity_type == "department":
                    source_data = self.data_manager.get_department_by_id(entity_id)
                elif entity_type == "job":
                    source_data = self.data_manager.get_job_by_id(entity_id)

                # Try to get SafetyAmp data
                target_data = self.data_manager.get_safetyamp_entity(
                    entity_type, entity_id
                )

            # Compute diff
            diff = self._compute_diff(source_data, target_data)

            return {
                "entity_type": entity_type,
                "entity_id": entity_id,
                "source_data": source_data,
                "target_data": target_data,
                "diff": diff,
                "has_differences": len(diff.get("changed_fields", [])) > 0,
            }

        except Exception as e:
            logger.error(f"Error getting entity diff: {e}")
            return {
                "entity_type": entity_type,
                "entity_id": entity_id,
                "error": str(e),
            }

    def _compute_diff(
        self, source: Optional[Dict], target: Optional[Dict]
    ) -> Dict[str, Any]:
        """
        Compute differences between source and target data.

        Args:
            source: Source data dictionary
            target: Target data dictionary

        Returns:
            Dictionary describing the differences
        """
        if not source and not target:
            return {"status": "both_missing", "changed_fields": []}

        if not source:
            return {
                "status": "source_missing",
                "changed_fields": [],
                "target_only": True,
            }

        if not target:
            return {
                "status": "target_missing",
                "changed_fields": [],
                "source_only": True,
            }

        changed_fields = []
        all_keys = set(source.keys()) | set(target.keys())

        for key in all_keys:
            source_val = source.get(key)
            target_val = target.get(key)

            if source_val != target_val:
                changed_fields.append(
                    {
                        "field": key,
                        "source_value": source_val,
                        "target_value": target_val,
                    }
                )

        return {
            "status": "different" if changed_fields else "in_sync",
            "changed_fields": changed_fields,
            "total_fields": len(all_keys),
        }

    def get_manual_sync_status(self) -> Dict[str, Any]:
        """
        Get status of any pending or running manual sync.

        Returns:
            Dictionary with sync status
        """
        try:
            # This would integrate with the sync worker status
            # For now, return a basic structure
            return {
                "pending": False,
                "running": False,
                "last_manual_sync": None,
                "queued_syncs": [],
            }

        except Exception as e:
            logger.error(f"Error getting manual sync status: {e}")
            return {
                "pending": False,
                "running": False,
                "error": str(e),
            }

    def _format_duration(self, seconds: float) -> str:
        """
        Format duration in human-readable form.

        Args:
            seconds: Duration in seconds

        Returns:
            Formatted duration string
        """
        if seconds < 60:
            return f"{int(seconds)}s"
        elif seconds < 3600:
            minutes = int(seconds / 60)
            remaining_seconds = int(seconds % 60)
            return f"{minutes}m {remaining_seconds}s"
        else:
            hours = int(seconds / 3600)
            remaining_minutes = int((seconds % 3600) / 60)
            return f"{hours}h {remaining_minutes}m"

    def _format_bytes(self, bytes_value: int) -> str:
        """
        Format bytes in human-readable form.

        Args:
            bytes_value: Size in bytes

        Returns:
            Formatted size string
        """
        for unit in ["B", "KB", "MB", "GB"]:
            if bytes_value < 1024:
                return f"{bytes_value:.1f} {unit}"
            bytes_value /= 1024

        return f"{bytes_value:.1f} TB"


# Global singleton instance
_dashboard_data: Optional[DashboardData] = None


def get_dashboard_data() -> Optional[DashboardData]:
    """Get the global dashboard data instance."""
    return _dashboard_data


def initialize_dashboard_data(
    event_manager=None,
    data_manager=None,
) -> DashboardData:
    """
    Initialize the global dashboard data instance.

    Args:
        event_manager: EventManager instance
        data_manager: DataManager instance

    Returns:
        The initialized DashboardData instance
    """
    global _dashboard_data
    _dashboard_data = DashboardData(
        event_manager=event_manager,
        data_manager=data_manager,
    )
    logger.info("Dashboard data initialized")
    return _dashboard_data
