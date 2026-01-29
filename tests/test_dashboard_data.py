"""
Unit tests for the Dashboard Data module.

Tests cover:
- Sync metrics aggregation
- Vista records count history
- Entity counts
- Cache statistics
- Sync duration trends
"""

import pytest
import json
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock, patch
from pathlib import Path


class TestDashboardData:
    """Tests for DashboardData class."""

    @pytest.fixture
    def mock_event_manager(self):
        """Create a mock event manager."""
        event_manager = MagicMock()
        event_manager.change_tracker._session_files.return_value = []
        event_manager.change_tracker.get_summary_report.return_value = {
            "total_changes": 0,
            "by_operation": {},
            "by_entity_type": {},
            "recent_sessions": [],
        }
        return event_manager

    @pytest.fixture
    def mock_data_manager(self):
        """Create a mock data manager."""
        data_manager = MagicMock()
        data_manager.get_cache_stats.return_value = {
            "redis_connected": True,
            "cache_ttl_hours": 24,
            "caches": {},
        }
        data_manager._employee_data = []
        data_manager._job_data = []
        return data_manager

    @pytest.fixture
    def dashboard_data(self, mock_event_manager, mock_data_manager):
        """Create a DashboardData instance with mocked dependencies."""
        from utils.dashboard_data import DashboardData

        return DashboardData(
            event_manager=mock_event_manager,
            data_manager=mock_data_manager,
        )

    def test_get_sync_metrics_returns_dict(self, dashboard_data):
        """get_sync_metrics should return a dictionary."""
        metrics = dashboard_data.get_sync_metrics()

        assert isinstance(metrics, dict)
        assert "total_syncs" in metrics
        assert "successful_syncs" in metrics
        assert "failed_syncs" in metrics

    def test_get_sync_metrics_with_time_range(self, dashboard_data, mock_event_manager):
        """get_sync_metrics should support time range filtering."""
        mock_event_manager.change_tracker.get_summary_report.return_value = {
            "total_changes": 100,
            "by_operation": {"created": 50, "updated": 30, "errors": 20},
            "by_entity_type": {"employee": 80, "vehicle": 20},
            "recent_sessions": [
                {
                    "session_id": "sync_1",
                    "total_processed": 100,
                    "total_created": 50,
                    "total_updated": 30,
                    "total_errors": 20,
                    "duration_seconds": 120,
                    "start_time": (
                        datetime.now(timezone.utc) - timedelta(hours=1)
                    ).isoformat(),
                }
            ],
        }

        metrics = dashboard_data.get_sync_metrics(hours=24)

        assert metrics["total_syncs"] >= 1
        mock_event_manager.change_tracker.get_summary_report.assert_called_with(24)

    def test_get_sync_metrics_includes_operations_breakdown(
        self, dashboard_data, mock_event_manager
    ):
        """get_sync_metrics should include breakdown by operation type."""
        mock_event_manager.change_tracker.get_summary_report.return_value = {
            "total_changes": 100,
            "by_operation": {"created": 50, "updated": 30, "skipped": 10, "errors": 10},
            "by_entity_type": {},
            "recent_sessions": [],
        }

        metrics = dashboard_data.get_sync_metrics()

        assert "by_operation" in metrics
        assert metrics["by_operation"]["created"] == 50
        assert metrics["by_operation"]["updated"] == 30

    def test_get_sync_history_returns_list(self, dashboard_data):
        """get_sync_history should return a list of sync records."""
        history = dashboard_data.get_sync_history(limit=10)

        assert isinstance(history, list)

    def test_get_sync_history_with_session_data(
        self, dashboard_data, mock_event_manager
    ):
        """get_sync_history should include session data."""
        now = datetime.now(timezone.utc)
        mock_event_manager.change_tracker.get_summary_report.return_value = {
            "total_changes": 100,
            "by_operation": {},
            "by_entity_type": {},
            "recent_sessions": [
                {
                    "session_id": "sync_123",
                    "sync_type": "employees",
                    "total_processed": 100,
                    "total_created": 50,
                    "total_updated": 30,
                    "total_errors": 5,
                    "duration_seconds": 120.5,
                    "start_time": (now - timedelta(hours=1)).isoformat(),
                    "end_time": now.isoformat(),
                }
            ],
        }

        history = dashboard_data.get_sync_history(limit=10)

        assert len(history) >= 1
        assert history[0]["session_id"] == "sync_123"
        assert history[0]["total_created"] == 50

    def test_get_entity_counts_returns_counts(self, dashboard_data, mock_data_manager):
        """get_entity_counts should return counts for each entity type."""
        mock_data_manager._employee_data = [{"id": 1}, {"id": 2}, {"id": 3}]
        mock_data_manager._job_data = [{"id": 1}, {"id": 2}]

        counts = dashboard_data.get_entity_counts()

        assert "employees" in counts
        assert "jobs" in counts
        assert counts["employees"] == 3
        assert counts["jobs"] == 2

    def test_get_cache_stats_returns_cache_info(
        self, dashboard_data, mock_data_manager
    ):
        """get_cache_stats should return cache statistics."""
        mock_data_manager.get_cache_stats.return_value = {
            "redis_connected": True,
            "cache_ttl_hours": 24,
            "caches": {
                "employees": {"size_bytes": 1024, "valid": True},
                "jobs": {"size_bytes": 512, "valid": True},
            },
        }

        stats = dashboard_data.get_cache_stats()

        assert "redis_connected" in stats
        assert stats["redis_connected"] is True
        assert "caches" in stats

    def test_get_sync_duration_trends(self, dashboard_data, mock_event_manager):
        """get_sync_duration_trends should return duration data over time."""
        now = datetime.now(timezone.utc)
        mock_event_manager.change_tracker.get_summary_report.return_value = {
            "total_changes": 0,
            "by_operation": {},
            "by_entity_type": {},
            "recent_sessions": [
                {
                    "session_id": "sync_1",
                    "duration_seconds": 120,
                    "start_time": (now - timedelta(hours=2)).isoformat(),
                },
                {
                    "session_id": "sync_2",
                    "duration_seconds": 90,
                    "start_time": (now - timedelta(hours=1)).isoformat(),
                },
            ],
        }

        trends = dashboard_data.get_sync_duration_trends()

        assert isinstance(trends, list)
        assert len(trends) >= 1
        assert "duration_seconds" in trends[0]
        assert "timestamp" in trends[0]

    def test_get_error_rate_over_time(self, dashboard_data, mock_event_manager):
        """get_error_rate_over_time should return error rate data."""
        now = datetime.now(timezone.utc)
        mock_event_manager.change_tracker.get_summary_report.return_value = {
            "total_changes": 100,
            "by_operation": {"errors": 10},
            "by_entity_type": {},
            "recent_sessions": [
                {
                    "session_id": "sync_1",
                    "total_processed": 100,
                    "total_errors": 10,
                    "start_time": (now - timedelta(hours=1)).isoformat(),
                }
            ],
        }

        error_rates = dashboard_data.get_error_rate_over_time()

        assert isinstance(error_rates, list)

    def test_get_records_by_time_range_1d(self, dashboard_data, mock_event_manager):
        """Should return data points for 1 day range."""
        mock_event_manager.change_tracker.get_summary_report.return_value = {
            "total_changes": 50,
            "by_operation": {},
            "by_entity_type": {"employee": 50},
            "recent_sessions": [],
        }

        data = dashboard_data.get_records_by_time_range(time_range="1d")

        assert isinstance(data, dict)
        assert "total_records" in data
        assert "time_range" in data
        assert data["time_range"] == "1d"

    def test_get_records_by_time_range_7d(self, dashboard_data):
        """Should return data points for 7 day range."""
        data = dashboard_data.get_records_by_time_range(time_range="7d")

        assert data["time_range"] == "7d"

    def test_get_records_by_time_range_30d(self, dashboard_data):
        """Should return data points for 30 day range."""
        data = dashboard_data.get_records_by_time_range(time_range="30d")

        assert data["time_range"] == "30d"

    def test_get_records_by_time_range_6mo(self, dashboard_data):
        """Should return data points for 6 month range."""
        data = dashboard_data.get_records_by_time_range(time_range="6mo")

        assert data["time_range"] == "6mo"

    def test_get_live_sync_status(self, dashboard_data):
        """get_live_sync_status should return current sync state."""
        status = dashboard_data.get_live_sync_status()

        assert isinstance(status, dict)
        assert "sync_in_progress" in status
        assert "last_sync_time" in status

    def test_get_dependency_health(self, dashboard_data):
        """get_dependency_health should return health status of dependencies."""
        health = dashboard_data.get_dependency_health()

        assert isinstance(health, dict)
        assert "database" in health or "services" in health


class TestDashboardDataAggregation:
    """Tests for data aggregation functions."""

    @pytest.fixture
    def dashboard_data(self):
        """Create a DashboardData instance with minimal mocks."""
        from utils.dashboard_data import DashboardData

        mock_event_manager = MagicMock()
        mock_event_manager.change_tracker.get_summary_report.return_value = {
            "total_changes": 0,
            "by_operation": {},
            "by_entity_type": {},
            "recent_sessions": [],
        }
        mock_data_manager = MagicMock()
        mock_data_manager._employee_data = []
        mock_data_manager._job_data = []
        mock_data_manager.get_cache_stats.return_value = {}

        return DashboardData(
            event_manager=mock_event_manager,
            data_manager=mock_data_manager,
        )

    def test_calculate_success_rate(self, dashboard_data):
        """Should calculate success rate correctly."""
        rate = dashboard_data._calculate_success_rate(total=100, errors=10)

        assert rate == 90.0

    def test_calculate_success_rate_zero_total(self, dashboard_data):
        """Should handle zero total gracefully."""
        rate = dashboard_data._calculate_success_rate(total=0, errors=0)

        assert rate == 100.0

    def test_aggregate_by_hour(self, dashboard_data):
        """Should aggregate data points by hour."""
        now = datetime.now(timezone.utc)
        data_points = [
            {"timestamp": (now - timedelta(minutes=30)).isoformat(), "value": 10},
            {"timestamp": (now - timedelta(minutes=45)).isoformat(), "value": 20},
            {"timestamp": (now - timedelta(hours=1, minutes=15)).isoformat(), "value": 30},
        ]

        aggregated = dashboard_data._aggregate_by_hour(data_points)

        assert isinstance(aggregated, list)


class TestDashboardDataFormatting:
    """Tests for data formatting functions."""

    @pytest.fixture
    def dashboard_data(self):
        """Create a DashboardData instance with minimal mocks."""
        from utils.dashboard_data import DashboardData

        mock_event_manager = MagicMock()
        mock_event_manager.change_tracker.get_summary_report.return_value = {
            "total_changes": 0,
            "by_operation": {},
            "by_entity_type": {},
            "recent_sessions": [],
        }
        mock_data_manager = MagicMock()
        mock_data_manager._employee_data = []
        mock_data_manager._job_data = []
        mock_data_manager.get_cache_stats.return_value = {}

        return DashboardData(
            event_manager=mock_event_manager,
            data_manager=mock_data_manager,
        )

    def test_format_duration(self, dashboard_data):
        """Should format duration in human-readable form."""
        formatted = dashboard_data._format_duration(3661)  # 1 hour, 1 minute, 1 second

        assert "1h" in formatted or "hour" in formatted.lower()

    def test_format_duration_seconds_only(self, dashboard_data):
        """Should format short durations correctly."""
        formatted = dashboard_data._format_duration(45)

        assert "45" in formatted and "s" in formatted.lower()

    def test_format_bytes(self, dashboard_data):
        """Should format bytes in human-readable form."""
        formatted = dashboard_data._format_bytes(1048576)  # 1 MB

        assert "MB" in formatted or "1" in formatted


class TestDashboardDataWithoutDependencies:
    """Tests for DashboardData when dependencies are unavailable."""

    def test_handles_missing_event_manager(self):
        """Should handle missing event manager gracefully."""
        from utils.dashboard_data import DashboardData

        mock_data_manager = MagicMock()
        mock_data_manager._employee_data = []
        mock_data_manager._job_data = []
        mock_data_manager.get_cache_stats.return_value = {}

        dashboard = DashboardData(
            event_manager=None,
            data_manager=mock_data_manager,
        )

        metrics = dashboard.get_sync_metrics()

        assert isinstance(metrics, dict)

    def test_handles_missing_data_manager(self):
        """Should handle missing data manager gracefully."""
        from utils.dashboard_data import DashboardData

        mock_event_manager = MagicMock()
        mock_event_manager.change_tracker.get_summary_report.return_value = {
            "total_changes": 0,
            "by_operation": {},
            "by_entity_type": {},
            "recent_sessions": [],
        }

        dashboard = DashboardData(
            event_manager=mock_event_manager,
            data_manager=None,
        )

        counts = dashboard.get_entity_counts()

        assert isinstance(counts, dict)
