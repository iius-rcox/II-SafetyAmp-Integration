"""
Unit tests for the API Call Tracker service.

Tests cover:
- Recording API calls to Redis ring buffer
- Retrieving recent API calls
- Filtering by service, method, status
- Ring buffer eviction when exceeding max size
- Handling Redis unavailability gracefully
"""

import pytest
import json
import sys
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch


@pytest.fixture(scope="module", autouse=True)
def mock_redis_globally():
    """Mock redis module for this test module."""
    mock_redis = MagicMock()
    original_redis = sys.modules.get("redis")
    sys.modules["redis"] = mock_redis

    yield mock_redis

    # Restore original if it existed
    if original_redis is not None:
        sys.modules["redis"] = original_redis
    elif "redis" in sys.modules:
        del sys.modules["redis"]


class TestApiCallTracker:
    """Tests for ApiCallTracker class."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mock_redis_globally):
        """Set up mocks before each test."""
        # Clear cached module to ensure fresh import
        if "services.api_call_tracker" in sys.modules:
            del sys.modules["services.api_call_tracker"]

        # Create fresh mock client
        self.mock_redis_client = MagicMock()
        self.mock_redis_client.ping.return_value = True
        self.mock_redis_client.lpush.return_value = 1
        self.mock_redis_client.ltrim.return_value = True
        self.mock_redis_client.lrange.return_value = []
        self.mock_redis_client.llen.return_value = 0
        self.mock_redis_client.delete.return_value = 1

        mock_redis_globally.Redis.return_value = self.mock_redis_client

    @pytest.fixture
    def tracker(self, setup_mocks, mock_redis_globally):
        """Create an ApiCallTracker with mocked Redis."""
        from services.api_call_tracker import ApiCallTracker

        tracker = ApiCallTracker(
            redis_host="localhost",
            redis_port=6379,
            redis_db=0,
            max_entries=100,
        )
        return tracker

    def test_record_api_call_stores_in_redis(self, tracker):
        """API calls should be stored in Redis list."""
        tracker.record_call(
            service="safetyamp",
            method="GET",
            endpoint="/api/users",
            status_code=200,
            duration_ms=145,
            correlation_id="sync_12345",
        )

        self.mock_redis_client.lpush.assert_called_once()
        call_args = self.mock_redis_client.lpush.call_args
        assert call_args[0][0] == "safetyamp:api_calls"

        # Verify the stored JSON structure
        stored_json = call_args[0][1]
        stored_data = json.loads(stored_json)
        assert stored_data["service"] == "safetyamp"
        assert stored_data["method"] == "GET"
        assert stored_data["endpoint"] == "/api/users"
        assert stored_data["status_code"] == 200
        assert stored_data["duration_ms"] == 145
        assert stored_data["correlation_id"] == "sync_12345"
        assert "id" in stored_data
        assert "timestamp" in stored_data

    def test_record_api_call_with_error(self, tracker):
        """Error messages should be stored with failed API calls."""
        tracker.record_call(
            service="samsara",
            method="POST",
            endpoint="/api/vehicles",
            status_code=500,
            duration_ms=2500,
            error_message="Internal server error",
        )

        call_args = self.mock_redis_client.lpush.call_args
        stored_data = json.loads(call_args[0][1])
        assert stored_data["status_code"] == 500
        assert stored_data["error_message"] == "Internal server error"

    def test_record_api_call_trims_to_max_entries(self, tracker):
        """Ring buffer should be trimmed to max_entries after each insert."""
        tracker.record_call(
            service="safetyamp",
            method="GET",
            endpoint="/api/users",
            status_code=200,
            duration_ms=100,
        )

        # Verify ltrim is called with correct range (0 to max_entries-1)
        self.mock_redis_client.ltrim.assert_called_once_with(
            "safetyamp:api_calls", 0, 99
        )

    def test_get_recent_calls_returns_list(self, tracker):
        """get_recent_calls should return list of API call records."""
        self.mock_redis_client.lrange.return_value = [
            json.dumps(
                {
                    "id": "call_1",
                    "timestamp": "2024-01-28T10:30:00Z",
                    "service": "safetyamp",
                    "method": "GET",
                    "endpoint": "/api/users",
                    "status_code": 200,
                    "duration_ms": 145,
                }
            ),
            json.dumps(
                {
                    "id": "call_2",
                    "timestamp": "2024-01-28T10:29:00Z",
                    "service": "samsara",
                    "method": "POST",
                    "endpoint": "/api/vehicles",
                    "status_code": 201,
                    "duration_ms": 230,
                }
            ),
        ]

        calls = tracker.get_recent_calls(limit=10)

        assert len(calls) == 2
        assert calls[0]["service"] == "safetyamp"
        assert calls[1]["service"] == "samsara"
        self.mock_redis_client.lrange.assert_called_once_with(
            "safetyamp:api_calls", 0, 29
        )

    def test_get_recent_calls_with_service_filter(self, tracker):
        """get_recent_calls should filter by service when specified."""
        self.mock_redis_client.lrange.return_value = [
            json.dumps({"service": "safetyamp", "status_code": 200}),
            json.dumps({"service": "samsara", "status_code": 200}),
            json.dumps({"service": "safetyamp", "status_code": 201}),
        ]

        calls = tracker.get_recent_calls(limit=100, service="safetyamp")

        assert len(calls) == 2
        assert all(c["service"] == "safetyamp" for c in calls)

    def test_get_recent_calls_with_status_filter(self, tracker):
        """get_recent_calls should filter by status code when specified."""
        self.mock_redis_client.lrange.return_value = [
            json.dumps({"service": "safetyamp", "status_code": 200}),
            json.dumps({"service": "samsara", "status_code": 500}),
            json.dumps({"service": "msgraph", "status_code": 200}),
        ]

        # Filter for errors only (status >= 400)
        calls = tracker.get_recent_calls(limit=100, errors_only=True)

        assert len(calls) == 1
        assert calls[0]["status_code"] == 500

    def test_get_recent_calls_with_method_filter(self, tracker):
        """get_recent_calls should filter by HTTP method when specified."""
        self.mock_redis_client.lrange.return_value = [
            json.dumps({"service": "safetyamp", "method": "GET", "status_code": 200}),
            json.dumps({"service": "safetyamp", "method": "POST", "status_code": 201}),
            json.dumps({"service": "safetyamp", "method": "GET", "status_code": 200}),
        ]

        calls = tracker.get_recent_calls(limit=100, method="POST")

        assert len(calls) == 1
        assert calls[0]["method"] == "POST"

    def test_get_call_stats_returns_summary(self, tracker):
        """get_call_stats should return aggregated statistics."""
        self.mock_redis_client.lrange.return_value = [
            json.dumps(
                {"service": "safetyamp", "status_code": 200, "duration_ms": 100}
            ),
            json.dumps(
                {"service": "safetyamp", "status_code": 200, "duration_ms": 200}
            ),
            json.dumps({"service": "safetyamp", "status_code": 500, "duration_ms": 50}),
            json.dumps({"service": "samsara", "status_code": 200, "duration_ms": 150}),
        ]

        stats = tracker.get_call_stats()

        assert stats["total_calls"] == 4
        assert stats["by_service"]["safetyamp"] == 3
        assert stats["by_service"]["samsara"] == 1
        assert stats["error_count"] == 1
        assert stats["success_rate"] == 75.0
        assert "avg_duration_ms" in stats

    def test_get_call_stats_by_service(self, tracker):
        """get_call_stats should support filtering by service."""
        self.mock_redis_client.lrange.return_value = [
            json.dumps(
                {"service": "safetyamp", "status_code": 200, "duration_ms": 100}
            ),
            json.dumps({"service": "samsara", "status_code": 200, "duration_ms": 150}),
        ]

        stats = tracker.get_call_stats(service="safetyamp")

        assert stats["total_calls"] == 1
        assert stats["by_service"]["safetyamp"] == 1
        assert "samsara" not in stats["by_service"]

    def test_record_call_handles_redis_failure_gracefully(self, tracker):
        """Recording should not raise exceptions when Redis fails."""
        self.mock_redis_client.lpush.side_effect = Exception("Redis connection failed")

        # Should not raise
        tracker.record_call(
            service="safetyamp",
            method="GET",
            endpoint="/api/users",
            status_code=200,
            duration_ms=100,
        )

    def test_get_recent_calls_handles_redis_failure(self, tracker):
        """Should return empty list when Redis fails."""
        self.mock_redis_client.lrange.side_effect = Exception("Redis connection failed")

        calls = tracker.get_recent_calls(limit=10)

        assert calls == []

    def test_get_recent_calls_handles_invalid_json(self, tracker):
        """Should skip invalid JSON entries."""
        self.mock_redis_client.lrange.return_value = [
            json.dumps({"service": "safetyamp", "status_code": 200}),
            "invalid json {",
            json.dumps({"service": "samsara", "status_code": 200}),
        ]

        calls = tracker.get_recent_calls(limit=10)

        assert len(calls) == 2

    def test_clear_all_calls(self, tracker):
        """clear_all should delete the Redis list."""
        tracker.clear_all()

        self.mock_redis_client.delete.assert_called_once_with("safetyamp:api_calls")

    def test_get_calls_by_correlation_id(self, tracker):
        """Should be able to filter calls by correlation_id."""
        self.mock_redis_client.lrange.return_value = [
            json.dumps({"service": "safetyamp", "correlation_id": "sync_123"}),
            json.dumps({"service": "safetyamp", "correlation_id": "sync_456"}),
            json.dumps({"service": "samsara", "correlation_id": "sync_123"}),
        ]

        calls = tracker.get_recent_calls(limit=100, correlation_id="sync_123")

        assert len(calls) == 2
        assert all(c["correlation_id"] == "sync_123" for c in calls)


class TestApiCallTrackerWithoutRedis:
    """Tests for ApiCallTracker when Redis is not available."""

    @pytest.fixture(autouse=True)
    def setup_failing_redis(self, mock_redis_globally):
        """Set up Redis mock that fails to connect."""
        if "services.api_call_tracker" in sys.modules:
            del sys.modules["services.api_call_tracker"]

        mock_redis_client = MagicMock()
        mock_redis_client.ping.side_effect = Exception("Connection refused")
        mock_redis_globally.Redis.return_value = mock_redis_client

    def test_tracker_initializes_without_redis(self):
        """Tracker should initialize even if Redis connection fails."""
        from services.api_call_tracker import ApiCallTracker

        tracker = ApiCallTracker(
            redis_host="localhost",
            redis_port=6379,
            redis_db=0,
        )

        assert tracker.redis_client is None

    def test_record_call_without_redis(self):
        """Recording should be no-op when Redis unavailable."""
        from services.api_call_tracker import ApiCallTracker

        tracker = ApiCallTracker(redis_host="localhost", redis_port=6379)

        # Should not raise
        result = tracker.record_call(
            service="safetyamp",
            method="GET",
            endpoint="/api/users",
            status_code=200,
            duration_ms=100,
        )

        assert result is None

    def test_get_recent_calls_without_redis(self):
        """Should return empty list when Redis unavailable."""
        from services.api_call_tracker import ApiCallTracker

        tracker = ApiCallTracker(redis_host="localhost", redis_port=6379)
        calls = tracker.get_recent_calls(limit=10)

        assert calls == []


class TestApiCallTrackerTimestamps:
    """Tests for timestamp handling in API calls."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mock_redis_globally):
        """Set up mocks before each test."""
        if "services.api_call_tracker" in sys.modules:
            del sys.modules["services.api_call_tracker"]

        self.mock_redis_client = MagicMock()
        self.mock_redis_client.ping.return_value = True
        self.mock_redis_client.lpush.return_value = 1
        self.mock_redis_client.ltrim.return_value = True
        mock_redis_globally.Redis.return_value = self.mock_redis_client

    def test_timestamp_is_iso_format(self):
        """Timestamps should be in ISO 8601 format."""
        from services.api_call_tracker import ApiCallTracker

        tracker = ApiCallTracker(redis_host="localhost", redis_port=6379)

        tracker.record_call(
            service="safetyamp",
            method="GET",
            endpoint="/api/users",
            status_code=200,
            duration_ms=100,
        )

        call_args = self.mock_redis_client.lpush.call_args
        stored_data = json.loads(call_args[0][1])
        timestamp = stored_data["timestamp"]

        # Should be parseable as ISO format
        parsed = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        assert parsed is not None


class TestApiCallTrackerIds:
    """Tests for unique ID generation."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mock_redis_globally):
        """Set up mocks before each test."""
        if "services.api_call_tracker" in sys.modules:
            del sys.modules["services.api_call_tracker"]

        self.mock_redis_client = MagicMock()
        self.mock_redis_client.ping.return_value = True
        self.mock_redis_client.lpush.return_value = 1
        self.mock_redis_client.ltrim.return_value = True
        mock_redis_globally.Redis.return_value = self.mock_redis_client

    def test_each_call_gets_unique_id(self):
        """Each recorded call should have a unique ID."""
        from services.api_call_tracker import ApiCallTracker

        tracker = ApiCallTracker(redis_host="localhost", redis_port=6379)

        # Record two calls
        tracker.record_call(
            service="safetyamp",
            method="GET",
            endpoint="/api/users",
            status_code=200,
            duration_ms=100,
        )
        tracker.record_call(
            service="safetyamp",
            method="GET",
            endpoint="/api/users",
            status_code=200,
            duration_ms=100,
        )

        # Extract IDs from both calls
        call1_data = json.loads(self.mock_redis_client.lpush.call_args_list[0][0][1])
        call2_data = json.loads(self.mock_redis_client.lpush.call_args_list[1][0][1])

        assert call1_data["id"] != call2_data["id"]
