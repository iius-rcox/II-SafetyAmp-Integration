"""
Dashboard API Routes Flask Blueprint.

Provides REST API endpoints for the monitoring dashboard including:
- Sync metrics and history
- API call tracking
- Error suggestions
- Entity counts
- Cache statistics
- Dependency health
- Failed records queue management
- Configuration status
- Export/download reports
- Manual sync triggers
- Audit logging

Security features:
- API key authentication via X-Dashboard-Token header
- Rate limiting via Flask-Limiter
- Input validation with bounds checking
"""

import csv
import io
import json
import os
import time
from datetime import datetime, timezone
from functools import wraps
from flask import Blueprint, jsonify, request, Response
from typing import Optional, Callable, List, Dict, Any

from utils.logger import get_logger

logger = get_logger("dashboard_routes")

# Rate limiting configuration
RATE_LIMIT_DEFAULT = "60/minute"
RATE_LIMIT_HEAVY = "10/minute"  # For expensive operations

# Parameter bounds
MAX_HOURS = 4320  # 6 months in hours
MAX_LIMIT = 1000  # Max records to return
MAX_AUDIT_LOG_ENTRIES = 1000  # Max audit log entries to keep

# In-memory audit log (use Redis in production)
_audit_log: List[Dict[str, Any]] = []


def _log_audit_event(
    action: str,
    resource: str,
    details: Optional[Dict[str, Any]] = None,
    user: str = "dashboard",
) -> None:
    """Log an audit event."""
    global _audit_log
    event = {
        "id": f"audit_{int(time.time() * 1000)}",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "action": action,
        "resource": resource,
        "user": user,
        "details": details or {},
        "ip_address": request.remote_addr if request else None,
    }
    _audit_log.insert(0, event)
    # Trim to max size
    if len(_audit_log) > MAX_AUDIT_LOG_ENTRIES:
        _audit_log = _audit_log[:MAX_AUDIT_LOG_ENTRIES]
    logger.info(f"Audit: {action} on {resource}", extra={"audit_event": event})


def _get_dashboard_token() -> Optional[str]:
    """Get dashboard token from environment or config."""
    return os.getenv("DASHBOARD_API_TOKEN")


def require_dashboard_auth(f: Callable) -> Callable:
    """
    Decorator to require dashboard authentication.

    Checks for X-Dashboard-Token header or dashboard_token query param.
    If DASHBOARD_API_TOKEN is not set, authentication is bypassed (dev mode).
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        expected_token = _get_dashboard_token()

        # If no token configured, allow access (dev mode)
        if not expected_token:
            return f(*args, **kwargs)

        # Check header first, then query param
        provided_token = request.headers.get("X-Dashboard-Token")
        if not provided_token:
            provided_token = request.args.get("dashboard_token")

        if not provided_token:
            logger.warning("Dashboard access denied: no token provided")
            return jsonify({"error": "Authentication required"}), 401

        if provided_token != expected_token:
            logger.warning("Dashboard access denied: invalid token")
            return jsonify({"error": "Invalid authentication token"}), 403

        return f(*args, **kwargs)
    return decorated


def create_dashboard_blueprint(
    api_call_tracker=None,
    error_analyzer=None,
    dashboard_data=None,
    failed_sync_tracker=None,
    limiter=None,
    event_manager=None,
    config_manager=None,
    data_manager=None,
    sync_trigger_callback=None,
) -> Blueprint:
    """
    Create the dashboard Blueprint with injected dependencies.

    Args:
        api_call_tracker: ApiCallTracker instance for API call history
        error_analyzer: ErrorAnalyzer instance for error suggestions
        dashboard_data: DashboardData instance for metrics aggregation
        failed_sync_tracker: FailedSyncTracker instance for failed records
        limiter: Flask-Limiter instance for rate limiting (optional)
        event_manager: EventManager instance for notification history
        config_manager: ConfigManager instance for configuration status
        data_manager: DataManager instance for cache operations
        sync_trigger_callback: Callback function to trigger manual sync

    Returns:
        Flask Blueprint with dashboard routes
    """
    bp = Blueprint("dashboard", __name__, url_prefix="/api/dashboard")

    # Apply rate limiting to blueprint if limiter provided
    if limiter:
        limiter.limit(RATE_LIMIT_DEFAULT)(bp)

    # --- Sync Metrics ---

    @bp.route("/sync-metrics", methods=["GET"])
    @require_dashboard_auth
    def get_sync_metrics():
        """
        Get aggregated sync metrics.

        Query params:
            hours: Time window in hours (default: 24)

        Returns:
            JSON with sync metrics
        """
        try:
            hours = _parse_int_param(
                request.args.get("hours"), default=24, min_val=1, max_val=MAX_HOURS
            )

            if not dashboard_data:
                return jsonify(_empty_metrics()), 200

            metrics = dashboard_data.get_sync_metrics(hours=hours)
            return jsonify(metrics), 200

        except Exception as e:
            logger.error(f"Error getting sync metrics: {e}", exc_info=True)
            return jsonify({"error": "Internal server error"}), 500

    # --- API Calls ---

    @bp.route("/api-calls", methods=["GET"])
    @require_dashboard_auth
    def get_api_calls():
        """
        Get recent API calls.

        Query params:
            limit: Maximum number of calls (default: 100)
            service: Filter by service name
            method: Filter by HTTP method
            errors_only: Only return error calls (default: false)

        Returns:
            JSON with list of API calls
        """
        try:
            limit = _parse_int_param(
                request.args.get("limit"), default=100, min_val=1, max_val=MAX_LIMIT
            )
            service = request.args.get("service")
            method = request.args.get("method")
            errors_only = request.args.get("errors_only", "").lower() == "true"

            if not api_call_tracker:
                return jsonify({"calls": [], "total": 0}), 200

            calls = api_call_tracker.get_recent_calls(
                limit=limit,
                service=service,
                method=method,
                errors_only=errors_only,
            )

            return jsonify({
                "calls": calls,
                "total": len(calls),
                "filters": {
                    "limit": limit,
                    "service": service,
                    "method": method,
                    "errors_only": errors_only,
                },
            }), 200

        except Exception as e:
            logger.error(f"Error getting API calls: {e}", exc_info=True)
            return jsonify({"calls": [], "total": 0, "error": "Internal error"}), 200

    # --- API Stats ---

    @bp.route("/api-stats", methods=["GET"])
    @require_dashboard_auth
    def get_api_stats():
        """
        Get API call statistics.

        Query params:
            service: Filter by service name

        Returns:
            JSON with API statistics
        """
        try:
            service = request.args.get("service")

            if not api_call_tracker:
                return jsonify(_empty_api_stats()), 200

            stats = api_call_tracker.get_call_stats(service=service)
            return jsonify(stats), 200

        except Exception as e:
            logger.error(f"Error getting API stats: {e}", exc_info=True)
            return jsonify({"error": "Internal server error"}), 500

    # --- Error Suggestions ---

    @bp.route("/error-suggestions", methods=["GET"])
    @require_dashboard_auth
    def get_error_suggestions():
        """
        Get error analysis suggestions.

        Query params:
            hours: Time window in hours (default: 24)

        Returns:
            JSON with list of suggestions
        """
        try:
            hours = _parse_int_param(
                request.args.get("hours"), default=24, min_val=1, max_val=MAX_HOURS
            )

            if not error_analyzer:
                return jsonify({"suggestions": [], "total": 0}), 200

            suggestions = error_analyzer.analyze(hours=hours)

            return jsonify({
                "suggestions": suggestions,
                "total": len(suggestions),
                "hours": hours,
            }), 200

        except Exception as e:
            logger.error(f"Error getting error suggestions: {e}", exc_info=True)
            return jsonify({"suggestions": [], "total": 0, "error": "Internal error"}), 200

    # --- Sync History ---

    @bp.route("/sync-history", methods=["GET"])
    @require_dashboard_auth
    def get_sync_history():
        """
        Get recent sync session history.

        Query params:
            limit: Maximum number of sessions (default: 10)

        Returns:
            JSON with list of sync sessions
        """
        try:
            limit = _parse_int_param(
                request.args.get("limit"), default=10, min_val=1, max_val=100
            )

            if not dashboard_data:
                return jsonify({"sessions": [], "total": 0}), 200

            sessions = dashboard_data.get_sync_history(limit=limit)

            return jsonify({
                "sessions": sessions,
                "total": len(sessions),
            }), 200

        except Exception as e:
            logger.error(f"Error getting sync history: {e}", exc_info=True)
            return jsonify({"sessions": [], "total": 0, "error": "Internal error"}), 200

    # --- Entity Counts ---

    @bp.route("/entity-counts", methods=["GET"])
    @require_dashboard_auth
    def get_entity_counts():
        """
        Get current entity counts.

        Returns:
            JSON with entity counts
        """
        try:
            if not dashboard_data:
                return jsonify({
                    "employees": 0,
                    "jobs": 0,
                    "departments": 0,
                    "vehicles": 0,
                }), 200

            counts = dashboard_data.get_entity_counts()
            return jsonify(counts), 200

        except Exception as e:
            logger.error(f"Error getting entity counts: {e}", exc_info=True)
            return jsonify({"error": "Internal server error"}), 500

    # --- Cache Stats ---

    @bp.route("/cache-stats", methods=["GET"])
    @require_dashboard_auth
    def get_cache_stats():
        """
        Get cache statistics.

        Returns:
            JSON with cache information
        """
        try:
            if not dashboard_data:
                return jsonify({
                    "redis_connected": False,
                    "cache_ttl_hours": 0,
                    "caches": {},
                }), 200

            stats = dashboard_data.get_cache_stats()
            return jsonify(stats), 200

        except Exception as e:
            logger.error(f"Error getting cache stats: {e}", exc_info=True)
            return jsonify({"error": "Internal server error"}), 500

    # --- Duration Trends ---

    @bp.route("/duration-trends", methods=["GET"])
    @require_dashboard_auth
    def get_duration_trends():
        """
        Get sync duration trends over time.

        Query params:
            hours: Time window in hours (default: 24)

        Returns:
            JSON with duration trend data
        """
        try:
            hours = _parse_int_param(
                request.args.get("hours"), default=24, min_val=1, max_val=MAX_HOURS
            )

            if not dashboard_data:
                return jsonify({"trends": [], "hours": hours}), 200

            trends = dashboard_data.get_sync_duration_trends(hours=hours)

            return jsonify({
                "trends": trends,
                "hours": hours,
            }), 200

        except Exception as e:
            logger.error(f"Error getting duration trends: {e}", exc_info=True)
            return jsonify({"trends": [], "error": "Internal error"}), 200

    # --- Vista Records ---

    @bp.route("/vista-records", methods=["GET"])
    @require_dashboard_auth
    def get_vista_records():
        """
        Get Vista record counts by time range.

        Query params:
            time_range: Time range (1d, 7d, 30d, 6mo, default: 1d)

        Returns:
            JSON with record count data
        """
        try:
            time_range = request.args.get("time_range", "1d")
            valid_ranges = ["1d", "7d", "30d", "6mo"]
            if time_range not in valid_ranges:
                time_range = "1d"

            if not dashboard_data:
                return jsonify({
                    "time_range": time_range,
                    "total_records": 0,
                    "by_entity_type": {},
                    "data_points": [],
                }), 200

            data = dashboard_data.get_records_by_time_range(time_range=time_range)
            return jsonify(data), 200

        except Exception as e:
            logger.error(f"Error getting Vista records: {e}", exc_info=True)
            return jsonify({"time_range": "1d", "error": "Internal error"}), 200

    # --- Live Status ---

    @bp.route("/live-status", methods=["GET"])
    @require_dashboard_auth
    def get_live_status():
        """
        Get current live sync status.

        Returns:
            JSON with current sync state
        """
        try:
            if not dashboard_data:
                return jsonify({
                    "sync_in_progress": False,
                    "last_sync_time": None,
                    "current_operation": None,
                }), 200

            status = dashboard_data.get_live_sync_status()
            return jsonify(status), 200

        except Exception as e:
            logger.error(f"Error getting live status: {e}", exc_info=True)
            return jsonify({"error": "Internal server error"}), 500

    # --- Failed Records ---

    @bp.route("/failed-records", methods=["GET"])
    @require_dashboard_auth
    def get_failed_records():
        """
        Get failed sync record statistics.

        Query params:
            entity_type: Filter by entity type

        Returns:
            JSON with failed record stats
        """
        try:
            entity_type = request.args.get("entity_type")

            if not failed_sync_tracker:
                return jsonify({
                    "stats": {
                        "total": 0,
                        "by_entity_type": {},
                        "by_reason": {},
                    },
                    "records": [],
                }), 200

            stats = failed_sync_tracker.get_failure_stats(entity_type=entity_type)

            return jsonify({
                "stats": stats,
            }), 200

        except Exception as e:
            logger.error(f"Error getting failed records: {e}", exc_info=True)
            return jsonify({"stats": {"total": 0}, "error": "Internal error"}), 200

    # --- Dependency Health ---

    @bp.route("/dependency-health", methods=["GET"])
    @require_dashboard_auth
    def get_dependency_health():
        """
        Get health status of external dependencies.

        Returns:
            JSON with dependency health information
        """
        try:
            if not dashboard_data:
                return jsonify({
                    "database": {"status": "unknown"},
                    "services": {},
                }), 200

            health = dashboard_data.get_dependency_health()
            return jsonify(health), 200

        except Exception as e:
            logger.error(f"Error getting dependency health: {e}", exc_info=True)
            return jsonify({"error": "Internal server error"}), 500

    # --- Failed Records Queue (Feature 1) ---

    @bp.route("/failed-records/list", methods=["GET"])
    @require_dashboard_auth
    def list_failed_records():
        """
        Get detailed list of failed records.

        Query params:
            entity_type: Filter by entity type
            limit: Maximum records to return (default: 50)
            offset: Pagination offset (default: 0)

        Returns:
            JSON with failed records list
        """
        try:
            entity_type = request.args.get("entity_type")
            limit = _parse_int_param(request.args.get("limit"), default=50, min_val=1, max_val=200)
            offset = _parse_int_param(request.args.get("offset"), default=0, min_val=0)

            if not failed_sync_tracker:
                return jsonify({"records": [], "total": 0}), 200

            records = failed_sync_tracker.get_failed_records(
                entity_type=entity_type,
                limit=limit,
                offset=offset,
            )
            total = failed_sync_tracker.get_failed_count(entity_type=entity_type)

            return jsonify({
                "records": records,
                "total": total,
                "limit": limit,
                "offset": offset,
            }), 200

        except Exception as e:
            logger.error(f"Error listing failed records: {e}", exc_info=True)
            return jsonify({"records": [], "total": 0, "error": "Internal error"}), 200

    @bp.route("/failed-records/<record_id>/retry", methods=["POST"])
    @require_dashboard_auth
    def retry_failed_record(record_id: str):
        """Retry a specific failed record."""
        try:
            if not failed_sync_tracker:
                return jsonify({"error": "Failed sync tracker not available"}), 503

            success = failed_sync_tracker.mark_for_retry(record_id)
            _log_audit_event("retry", "failed_record", {"record_id": record_id, "success": success})

            if success:
                return jsonify({"status": "queued", "record_id": record_id}), 200
            return jsonify({"error": "Record not found"}), 404

        except Exception as e:
            logger.error(f"Error retrying failed record: {e}", exc_info=True)
            return jsonify({"error": "Internal server error"}), 500

    @bp.route("/failed-records/<record_id>", methods=["DELETE"])
    @require_dashboard_auth
    def dismiss_failed_record(record_id: str):
        """Dismiss/remove a failed record from the queue."""
        try:
            if not failed_sync_tracker:
                return jsonify({"error": "Failed sync tracker not available"}), 503

            success = failed_sync_tracker.dismiss_record(record_id)
            _log_audit_event("dismiss", "failed_record", {"record_id": record_id, "success": success})

            if success:
                return jsonify({"status": "dismissed", "record_id": record_id}), 200
            return jsonify({"error": "Record not found"}), 404

        except Exception as e:
            logger.error(f"Error dismissing failed record: {e}", exc_info=True)
            return jsonify({"error": "Internal server error"}), 500

    @bp.route("/failed-records/retry-all", methods=["POST"])
    @require_dashboard_auth
    def retry_all_failed_records():
        """Retry all failed records."""
        try:
            entity_type = request.args.get("entity_type")

            if not failed_sync_tracker:
                return jsonify({"error": "Failed sync tracker not available"}), 503

            count = failed_sync_tracker.mark_all_for_retry(entity_type=entity_type)
            _log_audit_event("retry_all", "failed_records", {"entity_type": entity_type, "count": count})

            return jsonify({"status": "queued", "count": count}), 200

        except Exception as e:
            logger.error(f"Error retrying all failed records: {e}", exc_info=True)
            return jsonify({"error": "Internal server error"}), 500

    # --- Cache Management (Feature 2) ---

    @bp.route("/cache/invalidate/<cache_name>", methods=["POST"])
    @require_dashboard_auth
    def invalidate_cache(cache_name: str):
        """Invalidate a specific cache."""
        try:
            if not data_manager:
                return jsonify({"error": "Data manager not available"}), 503

            valid_caches = ["employees", "vehicles", "departments", "jobs", "titles", "all"]
            if cache_name not in valid_caches:
                return jsonify({"error": f"Invalid cache name. Valid: {valid_caches}"}), 400

            if cache_name == "all":
                data_manager.clear_all_caches()
            else:
                data_manager.clear_cache(cache_name)

            _log_audit_event("invalidate", "cache", {"cache_name": cache_name})

            return jsonify({"status": "invalidated", "cache": cache_name}), 200

        except Exception as e:
            logger.error(f"Error invalidating cache: {e}", exc_info=True)
            return jsonify({"error": "Internal server error"}), 500

    @bp.route("/cache/refresh/<cache_name>", methods=["POST"])
    @require_dashboard_auth
    def refresh_cache(cache_name: str):
        """Force refresh a specific cache."""
        try:
            if not data_manager:
                return jsonify({"error": "Data manager not available"}), 503

            valid_caches = ["employees", "vehicles", "departments", "jobs", "titles"]
            if cache_name not in valid_caches:
                return jsonify({"error": f"Invalid cache name. Valid: {valid_caches}"}), 400

            # Invalidate and trigger refetch
            data_manager.clear_cache(cache_name)
            _log_audit_event("refresh", "cache", {"cache_name": cache_name})

            return jsonify({"status": "refresh_initiated", "cache": cache_name}), 200

        except Exception as e:
            logger.error(f"Error refreshing cache: {e}", exc_info=True)
            return jsonify({"error": "Internal server error"}), 500

    # --- Employee Sync Diff Viewer (Feature 3) ---

    @bp.route("/sync-diff/<entity_type>/<entity_id>", methods=["GET"])
    @require_dashboard_auth
    def get_sync_diff(entity_type: str, entity_id: str):
        """
        Get diff between source and target for an entity.

        Args:
            entity_type: Type of entity (employee, vehicle, department, job, title)
            entity_id: ID of the entity

        Returns:
            JSON with source data, target data, and diff
        """
        try:
            valid_types = ["employee", "vehicle", "department", "job", "title"]
            if entity_type not in valid_types:
                return jsonify({"error": f"Invalid entity type. Valid: {valid_types}"}), 400

            if not dashboard_data:
                return jsonify({"error": "Dashboard data not available"}), 503

            diff = dashboard_data.get_entity_diff(entity_type, entity_id)
            return jsonify(diff), 200

        except Exception as e:
            logger.error(f"Error getting sync diff: {e}", exc_info=True)
            return jsonify({"error": "Internal server error"}), 500

    # --- Notification Log (Feature 5) ---

    @bp.route("/notifications", methods=["GET"])
    @require_dashboard_auth
    def get_notification_log():
        """
        Get notification history.

        Query params:
            limit: Maximum notifications (default: 50)
            status: Filter by status (sent, failed, pending)

        Returns:
            JSON with notification history
        """
        try:
            limit = _parse_int_param(request.args.get("limit"), default=50, min_val=1, max_val=200)
            status = request.args.get("status")

            if not event_manager:
                return jsonify({"notifications": [], "total": 0}), 200

            notifications = event_manager.get_notification_history(limit=limit, status=status)

            return jsonify({
                "notifications": notifications,
                "total": len(notifications),
            }), 200

        except Exception as e:
            logger.error(f"Error getting notification log: {e}", exc_info=True)
            return jsonify({"notifications": [], "total": 0, "error": "Internal error"}), 200

    # --- Configuration Status (Feature 6) ---

    @bp.route("/config-status", methods=["GET"])
    @require_dashboard_auth
    def get_config_status():
        """
        Get masked configuration status.

        Returns:
            JSON with configuration status (secrets masked)
        """
        try:
            if not config_manager:
                return jsonify({
                    "valid": False,
                    "error": "Config manager not available",
                }), 200

            status = config_manager.get_configuration_status()

            # Mask any sensitive values
            masked_status = _mask_config_status(status)

            return jsonify(masked_status), 200

        except Exception as e:
            logger.error(f"Error getting config status: {e}", exc_info=True)
            return jsonify({"error": "Internal server error"}), 500

    # --- Export/Download Reports (Feature 7) ---

    @bp.route("/export/<report_type>", methods=["GET"])
    @require_dashboard_auth
    def export_report(report_type: str):
        """
        Export data as CSV or JSON.

        Args:
            report_type: Type of report (api-calls, sync-history, errors, failed-records)

        Query params:
            format: Output format (csv, json, default: json)
            hours: Time window for time-based reports (default: 24)

        Returns:
            File download
        """
        try:
            valid_types = ["api-calls", "sync-history", "errors", "failed-records", "entity-counts"]
            if report_type not in valid_types:
                return jsonify({"error": f"Invalid report type. Valid: {valid_types}"}), 400

            output_format = request.args.get("format", "json").lower()
            if output_format not in ["csv", "json"]:
                output_format = "json"

            hours = _parse_int_param(request.args.get("hours"), default=24, min_val=1, max_val=MAX_HOURS)

            # Get data based on report type
            data = _get_export_data(
                report_type, hours,
                api_call_tracker=api_call_tracker,
                dashboard_data=dashboard_data,
                error_analyzer=error_analyzer,
                failed_sync_tracker=failed_sync_tracker,
            )

            _log_audit_event("export", report_type, {"format": output_format, "hours": hours})

            filename = f"safetyamp_{report_type}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

            if output_format == "csv":
                csv_content = _convert_to_csv(data)
                return Response(
                    csv_content,
                    mimetype="text/csv",
                    headers={"Content-Disposition": f"attachment; filename={filename}.csv"}
                )
            else:
                return Response(
                    json.dumps(data, indent=2, default=str),
                    mimetype="application/json",
                    headers={"Content-Disposition": f"attachment; filename={filename}.json"}
                )

        except Exception as e:
            logger.error(f"Error exporting report: {e}", exc_info=True)
            return jsonify({"error": "Internal server error"}), 500

    # --- Manual Sync Triggers (Feature 8) ---

    @bp.route("/trigger-sync", methods=["POST"])
    @require_dashboard_auth
    def trigger_manual_sync():
        """
        Trigger a manual sync operation.

        Request body:
            sync_type: Type of sync (all, employees, vehicles, departments, jobs, titles)

        Returns:
            JSON with sync status
        """
        try:
            body = request.get_json() or {}
            sync_type = body.get("sync_type", "all")

            valid_types = ["all", "employees", "vehicles", "departments", "jobs", "titles"]
            if sync_type not in valid_types:
                return jsonify({"error": f"Invalid sync type. Valid: {valid_types}"}), 400

            if not sync_trigger_callback:
                return jsonify({"error": "Sync trigger not available"}), 503

            # Trigger the sync
            result = sync_trigger_callback(sync_type)
            _log_audit_event("trigger", "sync", {"sync_type": sync_type, "result": result})

            return jsonify({
                "status": "triggered",
                "sync_type": sync_type,
                "message": f"Manual {sync_type} sync has been triggered",
            }), 200

        except Exception as e:
            logger.error(f"Error triggering sync: {e}", exc_info=True)
            return jsonify({"error": "Internal server error"}), 500

    @bp.route("/sync-status", methods=["GET"])
    @require_dashboard_auth
    def get_sync_trigger_status():
        """Get status of any pending or running manual sync."""
        try:
            if not dashboard_data:
                return jsonify({
                    "pending": False,
                    "running": False,
                    "last_manual_sync": None,
                }), 200

            status = dashboard_data.get_manual_sync_status()
            return jsonify(status), 200

        except Exception as e:
            logger.error(f"Error getting sync status: {e}", exc_info=True)
            return jsonify({"error": "Internal server error"}), 500

    # --- Audit Log (Feature 9) ---

    @bp.route("/audit-log", methods=["GET"])
    @require_dashboard_auth
    def get_audit_log():
        """
        Get audit log of dashboard actions.

        Query params:
            limit: Maximum entries (default: 100)
            action: Filter by action type
            resource: Filter by resource type

        Returns:
            JSON with audit log entries
        """
        try:
            limit = _parse_int_param(request.args.get("limit"), default=100, min_val=1, max_val=500)
            action_filter = request.args.get("action")
            resource_filter = request.args.get("resource")

            filtered_log = _audit_log[:limit]

            if action_filter:
                filtered_log = [e for e in filtered_log if e["action"] == action_filter]
            if resource_filter:
                filtered_log = [e for e in filtered_log if e["resource"] == resource_filter]

            return jsonify({
                "entries": filtered_log[:limit],
                "total": len(filtered_log),
            }), 200

        except Exception as e:
            logger.error(f"Error getting audit log: {e}", exc_info=True)
            return jsonify({"entries": [], "total": 0, "error": "Internal error"}), 200

    return bp


def _parse_int_param(
    value: Optional[str],
    default: int,
    min_val: int = 0,
    max_val: int = 10000,
) -> int:
    """
    Parse an integer query parameter with bounds validation.

    Args:
        value: String value from request
        default: Default value if parsing fails
        min_val: Minimum allowed value
        max_val: Maximum allowed value

    Returns:
        Parsed integer value within bounds
    """
    if value is None:
        return default

    try:
        parsed = int(value)
        # Clamp to bounds
        return max(min_val, min(max_val, parsed))
    except (ValueError, TypeError):
        return default


def _empty_metrics() -> dict:
    """Return empty metrics structure."""
    return {
        "total_syncs": 0,
        "successful_syncs": 0,
        "failed_syncs": 0,
        "total_records_processed": 0,
        "success_rate": 100.0,
        "by_operation": {},
    }


def _empty_api_stats() -> dict:
    """Return empty API stats structure."""
    return {
        "total_calls": 0,
        "by_service": {},
        "error_count": 0,
        "success_rate": 100.0,
        "avg_duration_ms": 0,
    }


def _mask_config_status(status: Dict[str, Any]) -> Dict[str, Any]:
    """Mask sensitive values in configuration status."""
    sensitive_keys = [
        "token", "password", "secret", "key", "credential",
        "api_key", "apikey", "auth", "bearer"
    ]

    def mask_value(key: str, value: Any) -> Any:
        if value is None:
            return None
        key_lower = key.lower()
        for sensitive in sensitive_keys:
            if sensitive in key_lower:
                if isinstance(value, str) and len(value) > 4:
                    return value[:2] + "*" * (len(value) - 4) + value[-2:]
                return "****"
        if isinstance(value, dict):
            return {k: mask_value(k, v) for k, v in value.items()}
        if isinstance(value, list):
            return [mask_value(str(i), v) for i, v in enumerate(value)]
        return value

    return {k: mask_value(k, v) for k, v in status.items()}


def _get_export_data(
    report_type: str,
    hours: int,
    api_call_tracker=None,
    dashboard_data=None,
    error_analyzer=None,
    failed_sync_tracker=None,
) -> List[Dict[str, Any]]:
    """Get data for export based on report type."""
    if report_type == "api-calls":
        if api_call_tracker:
            return api_call_tracker.get_recent_calls(limit=1000)
        return []

    elif report_type == "sync-history":
        if dashboard_data:
            return dashboard_data.get_sync_history(limit=1000)
        return []

    elif report_type == "errors":
        if error_analyzer:
            return error_analyzer.analyze(hours=hours)
        return []

    elif report_type == "failed-records":
        if failed_sync_tracker:
            return failed_sync_tracker.get_failed_records(limit=1000)
        return []

    elif report_type == "entity-counts":
        if dashboard_data:
            counts = dashboard_data.get_entity_counts()
            return [{"entity_type": k, "count": v} for k, v in counts.items()]
        return []

    return []


def _convert_to_csv(data: List[Dict[str, Any]]) -> str:
    """Convert list of dicts to CSV string."""
    if not data:
        return ""

    output = io.StringIO()

    # Get all unique keys from all records
    all_keys = set()
    for record in data:
        if isinstance(record, dict):
            all_keys.update(record.keys())
    fieldnames = sorted(all_keys)

    writer = csv.DictWriter(output, fieldnames=fieldnames, extrasaction="ignore")
    writer.writeheader()

    for record in data:
        if isinstance(record, dict):
            # Flatten nested dicts/lists to strings
            flat_record = {}
            for k, v in record.items():
                if isinstance(v, (dict, list)):
                    flat_record[k] = json.dumps(v)
                else:
                    flat_record[k] = v
            writer.writerow(flat_record)

    return output.getvalue()
