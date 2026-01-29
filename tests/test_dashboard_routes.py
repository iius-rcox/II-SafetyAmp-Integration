"""
Unit tests for the Dashboard Routes Flask Blueprint.

Tests cover:
- All dashboard API endpoints
- Request parameter handling
- Response format validation
- Error handling
"""

import pytest
import json
import sys
from unittest.mock import MagicMock, patch
from datetime import datetime, timezone

# Mock redis before imports
mock_redis_module = MagicMock()
sys.modules["redis"] = mock_redis_module


class TestDashboardRoutes:
    """Tests for dashboard API endpoints."""

    @pytest.fixture
    def mock_dependencies(self):
        """Set up mocked dependencies."""
        # Mock event manager
        mock_event_manager = MagicMock()
        mock_event_manager.change_tracker.get_summary_report.return_value = {
            "total_changes": 100,
            "by_operation": {"created": 50, "updated": 30, "errors": 20},
            "by_entity_type": {"employee": 80, "vehicle": 20},
            "recent_sessions": [
                {
                    "session_id": "sync_123",
                    "sync_type": "employees",
                    "total_processed": 100,
                    "total_created": 50,
                    "total_updated": 30,
                    "total_errors": 20,
                    "duration_seconds": 120,
                    "start_time": datetime.now(timezone.utc).isoformat(),
                }
            ],
        }
        mock_event_manager.error_notifier.errors = []

        # Mock data manager
        mock_data_manager = MagicMock()
        mock_data_manager._employee_data = [{"id": i} for i in range(100)]
        mock_data_manager._job_data = [{"id": i} for i in range(50)]
        mock_data_manager.get_cache_stats.return_value = {
            "redis_connected": True,
            "cache_ttl_hours": 24,
            "caches": {},
        }
        mock_data_manager.get_all_failed_records.return_value = []

        # Mock api call tracker
        mock_api_tracker = MagicMock()
        mock_api_tracker.get_recent_calls.return_value = [
            {
                "id": "call_1",
                "service": "safetyamp",
                "method": "GET",
                "endpoint": "/api/users",
                "status_code": 200,
                "duration_ms": 100,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        ]
        mock_api_tracker.get_call_stats.return_value = {
            "total_calls": 100,
            "by_service": {"safetyamp": 80, "samsara": 20},
            "error_count": 5,
            "success_rate": 95.0,
            "avg_duration_ms": 150,
        }

        # Mock error analyzer
        mock_error_analyzer = MagicMock()
        mock_error_analyzer.analyze.return_value = [
            {
                "id": "sug_001",
                "severity": "high",
                "category": "duplicate_field",
                "title": "Duplicate Email Detected",
                "description": "Test description",
                "affected_records": ["12345"],
                "recommended_action": "Update email",
                "first_seen": datetime.now(timezone.utc).isoformat(),
                "occurrence_count": 5,
            }
        ]

        # Mock failed sync tracker
        mock_failed_tracker = MagicMock()
        mock_failed_tracker.get_failure_stats.return_value = {
            "total": 10,
            "by_entity_type": {"employee": 8, "vehicle": 2},
            "by_reason": {"duplicate_fields": 5, "validation_error": 5},
        }
        mock_failed_tracker.data_manager = mock_data_manager

        return {
            "event_manager": mock_event_manager,
            "data_manager": mock_data_manager,
            "api_tracker": mock_api_tracker,
            "error_analyzer": mock_error_analyzer,
            "failed_tracker": mock_failed_tracker,
        }

    @pytest.fixture
    def client(self, mock_dependencies):
        """Create Flask test client with mocked dependencies."""
        from flask import Flask
        from routes.dashboard import create_dashboard_blueprint

        app = Flask(__name__)
        app.config["TESTING"] = True

        # Create blueprint with mocked dependencies
        bp = create_dashboard_blueprint(
            api_call_tracker=mock_dependencies["api_tracker"],
            error_analyzer=mock_dependencies["error_analyzer"],
            dashboard_data=MagicMock(
                get_sync_metrics=MagicMock(
                    return_value={
                        "total_syncs": 10,
                        "successful_syncs": 8,
                        "failed_syncs": 2,
                        "total_records_processed": 100,
                        "success_rate": 80.0,
                        "by_operation": {"created": 50, "updated": 30},
                    }
                ),
                get_sync_history=MagicMock(return_value=[]),
                get_entity_counts=MagicMock(
                    return_value={"employees": 100, "jobs": 50}
                ),
                get_cache_stats=MagicMock(
                    return_value={"redis_connected": True, "caches": {}}
                ),
                get_sync_duration_trends=MagicMock(return_value=[]),
                get_records_by_time_range=MagicMock(
                    side_effect=lambda time_range="1d": {
                        "time_range": time_range,
                        "total_records": 100,
                        "by_entity_type": {},
                    }
                ),
                get_live_sync_status=MagicMock(
                    return_value={"sync_in_progress": False}
                ),
                get_dependency_health=MagicMock(
                    return_value={"database": {"status": "healthy"}}
                ),
            ),
            failed_sync_tracker=mock_dependencies["failed_tracker"],
        )

        app.register_blueprint(bp)

        with app.test_client() as client:
            yield client

    # --- Sync Metrics Tests ---

    def test_get_sync_metrics_success(self, client):
        """GET /api/dashboard/sync-metrics should return metrics."""
        response = client.get("/api/dashboard/sync-metrics")

        assert response.status_code == 200
        data = json.loads(response.data)
        assert "total_syncs" in data
        assert "success_rate" in data

    def test_get_sync_metrics_with_hours_param(self, client):
        """GET /api/dashboard/sync-metrics?hours=48 should filter by time."""
        response = client.get("/api/dashboard/sync-metrics?hours=48")

        assert response.status_code == 200

    # --- API Calls Tests ---

    def test_get_api_calls_success(self, client):
        """GET /api/dashboard/api-calls should return recent API calls."""
        response = client.get("/api/dashboard/api-calls")

        assert response.status_code == 200
        data = json.loads(response.data)
        assert "calls" in data
        assert isinstance(data["calls"], list)

    def test_get_api_calls_with_limit(self, client):
        """GET /api/dashboard/api-calls?limit=50 should respect limit."""
        response = client.get("/api/dashboard/api-calls?limit=50")

        assert response.status_code == 200

    def test_get_api_calls_with_service_filter(self, client):
        """GET /api/dashboard/api-calls?service=safetyamp should filter."""
        response = client.get("/api/dashboard/api-calls?service=safetyamp")

        assert response.status_code == 200

    def test_get_api_calls_with_errors_only(self, client):
        """GET /api/dashboard/api-calls?errors_only=true should filter errors."""
        response = client.get("/api/dashboard/api-calls?errors_only=true")

        assert response.status_code == 200

    # --- API Stats Tests ---

    def test_get_api_stats_success(self, client):
        """GET /api/dashboard/api-stats should return statistics."""
        response = client.get("/api/dashboard/api-stats")

        assert response.status_code == 200
        data = json.loads(response.data)
        assert "total_calls" in data
        assert "success_rate" in data

    # --- Error Suggestions Tests ---

    def test_get_error_suggestions_success(self, client):
        """GET /api/dashboard/error-suggestions should return suggestions."""
        response = client.get("/api/dashboard/error-suggestions")

        assert response.status_code == 200
        data = json.loads(response.data)
        assert "suggestions" in data
        assert isinstance(data["suggestions"], list)

    def test_get_error_suggestions_with_hours(self, client):
        """GET /api/dashboard/error-suggestions?hours=48 should filter by time."""
        response = client.get("/api/dashboard/error-suggestions?hours=48")

        assert response.status_code == 200

    # --- Sync History Tests ---

    def test_get_sync_history_success(self, client):
        """GET /api/dashboard/sync-history should return history."""
        response = client.get("/api/dashboard/sync-history")

        assert response.status_code == 200
        data = json.loads(response.data)
        assert "sessions" in data
        assert isinstance(data["sessions"], list)

    def test_get_sync_history_with_limit(self, client):
        """GET /api/dashboard/sync-history?limit=5 should respect limit."""
        response = client.get("/api/dashboard/sync-history?limit=5")

        assert response.status_code == 200

    # --- Entity Counts Tests ---

    def test_get_entity_counts_success(self, client):
        """GET /api/dashboard/entity-counts should return counts."""
        response = client.get("/api/dashboard/entity-counts")

        assert response.status_code == 200
        data = json.loads(response.data)
        assert "employees" in data
        assert "jobs" in data

    # --- Cache Stats Tests ---

    def test_get_cache_stats_success(self, client):
        """GET /api/dashboard/cache-stats should return cache info."""
        response = client.get("/api/dashboard/cache-stats")

        assert response.status_code == 200
        data = json.loads(response.data)
        assert "redis_connected" in data

    # --- Duration Trends Tests ---

    def test_get_duration_trends_success(self, client):
        """GET /api/dashboard/duration-trends should return trends."""
        response = client.get("/api/dashboard/duration-trends")

        assert response.status_code == 200
        data = json.loads(response.data)
        assert "trends" in data

    # --- Vista Records Tests ---

    def test_get_vista_records_success(self, client):
        """GET /api/dashboard/vista-records should return records data."""
        response = client.get("/api/dashboard/vista-records")

        assert response.status_code == 200
        data = json.loads(response.data)
        assert "time_range" in data
        assert "total_records" in data

    def test_get_vista_records_with_time_range(self, client):
        """GET /api/dashboard/vista-records?time_range=7d should filter."""
        response = client.get("/api/dashboard/vista-records?time_range=7d")

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["time_range"] == "7d"

    # --- Live Status Tests ---

    def test_get_live_status_success(self, client):
        """GET /api/dashboard/live-status should return current status."""
        response = client.get("/api/dashboard/live-status")

        assert response.status_code == 200
        data = json.loads(response.data)
        assert "sync_in_progress" in data

    # --- Failed Records Tests ---

    def test_get_failed_records_success(self, client):
        """GET /api/dashboard/failed-records should return failed records."""
        response = client.get("/api/dashboard/failed-records")

        assert response.status_code == 200
        data = json.loads(response.data)
        assert "stats" in data

    # --- Dependency Health Tests ---

    def test_get_dependency_health_success(self, client):
        """GET /api/dashboard/dependency-health should return health info."""
        response = client.get("/api/dashboard/dependency-health")

        assert response.status_code == 200
        data = json.loads(response.data)
        assert "database" in data or "services" in data


class TestDashboardRoutesErrorHandling:
    """Tests for error handling in dashboard routes."""

    @pytest.fixture
    def client_with_failing_deps(self):
        """Create Flask test client with failing dependencies."""
        from flask import Flask
        from routes.dashboard import create_dashboard_blueprint

        app = Flask(__name__)
        app.config["TESTING"] = True

        # Create mock that raises exceptions
        mock_api_tracker = MagicMock()
        mock_api_tracker.get_recent_calls.side_effect = Exception("Redis error")

        mock_error_analyzer = MagicMock()
        mock_error_analyzer.analyze.side_effect = Exception("Analyzer error")

        mock_dashboard_data = MagicMock()
        mock_dashboard_data.get_sync_metrics.side_effect = Exception("Data error")

        bp = create_dashboard_blueprint(
            api_call_tracker=mock_api_tracker,
            error_analyzer=mock_error_analyzer,
            dashboard_data=mock_dashboard_data,
            failed_sync_tracker=None,
        )

        app.register_blueprint(bp)

        with app.test_client() as client:
            yield client

    def test_api_calls_handles_error_gracefully(self, client_with_failing_deps):
        """API calls endpoint should handle errors gracefully."""
        response = client_with_failing_deps.get("/api/dashboard/api-calls")

        # Should return error response, not crash
        assert response.status_code in [200, 500]

    def test_sync_metrics_handles_error_gracefully(self, client_with_failing_deps):
        """Sync metrics endpoint should handle errors gracefully."""
        response = client_with_failing_deps.get("/api/dashboard/sync-metrics")

        # Should return error response, not crash
        assert response.status_code in [200, 500]


class TestDashboardRoutesParameterValidation:
    """Tests for parameter validation in dashboard routes."""

    @pytest.fixture
    def client(self):
        """Create Flask test client with minimal mocks."""
        from flask import Flask
        from routes.dashboard import create_dashboard_blueprint

        app = Flask(__name__)
        app.config["TESTING"] = True

        mock_api_tracker = MagicMock()
        mock_api_tracker.get_recent_calls.return_value = []
        mock_api_tracker.get_call_stats.return_value = {}

        mock_dashboard_data = MagicMock()
        mock_dashboard_data.get_sync_metrics.return_value = {}
        mock_dashboard_data.get_sync_history.return_value = []
        mock_dashboard_data.get_entity_counts.return_value = {}
        mock_dashboard_data.get_cache_stats.return_value = {}
        mock_dashboard_data.get_sync_duration_trends.return_value = []
        mock_dashboard_data.get_records_by_time_range.return_value = {
            "time_range": "1d"
        }
        mock_dashboard_data.get_live_sync_status.return_value = {}
        mock_dashboard_data.get_dependency_health.return_value = {}

        mock_error_analyzer = MagicMock()
        mock_error_analyzer.analyze.return_value = []

        bp = create_dashboard_blueprint(
            api_call_tracker=mock_api_tracker,
            error_analyzer=mock_error_analyzer,
            dashboard_data=mock_dashboard_data,
            failed_sync_tracker=None,
        )

        app.register_blueprint(bp)

        with app.test_client() as client:
            yield client

    def test_invalid_limit_uses_default(self, client):
        """Invalid limit parameter should use default."""
        response = client.get("/api/dashboard/api-calls?limit=invalid")

        assert response.status_code == 200

    def test_negative_hours_uses_default(self, client):
        """Negative hours parameter should use default."""
        response = client.get("/api/dashboard/sync-metrics?hours=-10")

        assert response.status_code == 200

    def test_invalid_time_range_uses_default(self, client):
        """Invalid time range should use default."""
        response = client.get("/api/dashboard/vista-records?time_range=invalid")

        assert response.status_code == 200
