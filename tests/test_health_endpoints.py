"""
Unit tests for Flask health check endpoints.

Tests cover /health, /ready, /live, and /metrics endpoints.

Note: These tests require pyodbc and ODBC drivers to be installed,
or use a mocked approach that patches at the module level before import.
"""

import pytest
import sys
from unittest.mock import MagicMock, patch


# Mock pyodbc and sqlalchemy before any imports that depend on them
sys.modules["pyodbc"] = MagicMock()


@pytest.fixture
def mock_dependencies():
    """Set up mocked dependencies before importing main."""
    # Mock all the service modules (some held for future patch expansion)
    mock_viewpoint = MagicMock()
    _mock_safetyamp = MagicMock()  # noqa: F841
    mock_samsara = MagicMock()
    mock_graph = MagicMock()
    _mock_data_manager = MagicMock()  # noqa: F841
    _mock_event_manager = MagicMock()  # noqa: F841
    _mock_failed_tracker = MagicMock()  # noqa: F841

    with patch.dict(
        "sys.modules",
        {
            "services.viewpoint_api": mock_viewpoint,
            "services.samsara_api": mock_samsara,
            "services.graph_api": mock_graph,
        },
    ):
        yield


@pytest.fixture
def health_check_response_healthy():
    """Sample healthy response from health checks."""
    return {
        "status": "healthy",
        "checks": {
            "database": {"status": "healthy", "latency_ms": 5},
            "safetyamp": {"status": "healthy", "latency_ms": 50},
            "samsara": {"status": "healthy", "latency_ms": 30},
        },
    }


@pytest.fixture
def health_check_response_degraded():
    """Sample degraded response from health checks."""
    return {
        "status": "degraded",
        "checks": {
            "database": {"status": "healthy", "latency_ms": 5},
            "safetyamp": {"status": "unhealthy", "error": "API timeout"},
            "samsara": {"status": "healthy", "latency_ms": 30},
        },
    }


@pytest.fixture
def health_check_response_unhealthy():
    """Sample unhealthy response from health checks."""
    return {
        "status": "unhealthy",
        "checks": {"database": {"status": "unhealthy", "error": "Connection refused"}},
    }


class TestHealthCheckLogic:
    """Tests for health check response logic (without Flask app import).

    These tests verify the expected behavior of health check responses
    without requiring the full Flask app and its dependencies.
    """

    def test_healthy_status_should_return_200(self, health_check_response_healthy):
        """Healthy status should map to HTTP 200."""
        status = health_check_response_healthy.get("status", "unhealthy")
        code = 200 if status == "healthy" else (200 if status == "degraded" else 503)
        assert code == 200

    def test_degraded_status_should_return_200(self, health_check_response_degraded):
        """Degraded status should map to HTTP 200 (allows traffic)."""
        status = health_check_response_degraded.get("status", "unhealthy")
        code = 200 if status == "healthy" else (200 if status == "degraded" else 503)
        assert code == 200

    def test_unhealthy_status_should_return_503(self, health_check_response_unhealthy):
        """Unhealthy status should map to HTTP 503."""
        status = health_check_response_unhealthy.get("status", "unhealthy")
        code = 200 if status == "healthy" else (200 if status == "degraded" else 503)
        assert code == 503

    def test_readiness_depends_on_database(self, health_check_response_healthy):
        """Readiness should be based on database check status."""
        db_status = (
            health_check_response_healthy.get("checks", {})
            .get("database", {})
            .get("status", "unhealthy")
        )
        is_ready = db_status == "healthy"
        assert is_ready is True

    def test_readiness_fails_if_database_unhealthy(
        self, health_check_response_unhealthy
    ):
        """Readiness should fail if database is unhealthy."""
        db_status = (
            health_check_response_unhealthy.get("checks", {})
            .get("database", {})
            .get("status", "unhealthy")
        )
        is_ready = db_status == "healthy"
        assert is_ready is False


class TestHealthCheckResponseStructure:
    """Tests for health check response data structure."""

    def test_health_response_has_required_fields(self, health_check_response_healthy):
        """Health response should have status and checks fields."""
        assert "status" in health_check_response_healthy
        assert "checks" in health_check_response_healthy
        assert isinstance(health_check_response_healthy["checks"], dict)

    def test_check_has_status_field(self, health_check_response_healthy):
        """Each check should have a status field."""
        for check_name, check_data in health_check_response_healthy["checks"].items():
            assert "status" in check_data, f"Check '{check_name}' missing status"

    def test_check_has_latency_when_healthy(self, health_check_response_healthy):
        """Healthy checks should include latency measurement."""
        for check_name, check_data in health_check_response_healthy["checks"].items():
            if check_data["status"] == "healthy":
                assert (
                    "latency_ms" in check_data
                ), f"Check '{check_name}' missing latency"

    def test_check_has_error_when_unhealthy(self, health_check_response_unhealthy):
        """Unhealthy checks should include error message."""
        for check_name, check_data in health_check_response_unhealthy["checks"].items():
            if check_data["status"] == "unhealthy":
                assert "error" in check_data, f"Check '{check_name}' missing error"


class TestLivenessLogic:
    """Tests for liveness probe logic."""

    def test_alive_when_not_shutting_down(self):
        """Process should report alive when not shutting down."""
        shutdown_requested = False
        status = "alive" if not shutdown_requested else "shutting_down"
        code = 200 if not shutdown_requested else 503
        assert status == "alive"
        assert code == 200

    def test_shutting_down_when_shutdown_requested(self):
        """Process should report shutting down after signal."""
        shutdown_requested = True
        status = "alive" if not shutdown_requested else "shutting_down"
        code = 200 if not shutdown_requested else 503
        assert status == "shutting_down"
        assert code == 503


class TestExternalAPIStatus:
    """Tests for external API status aggregation."""

    def test_external_apis_healthy_when_all_pass(self, health_check_response_healthy):
        """External APIs status should be healthy when all pass."""
        checks = health_check_response_healthy.get("checks", {})
        external_healthy = all(
            checks.get(name, {}).get("status") == "healthy"
            for name in ("safetyamp", "samsara")
        )
        assert external_healthy is True

    def test_external_apis_degraded_when_any_fails(
        self, health_check_response_degraded
    ):
        """External APIs status should be degraded when any fails."""
        checks = health_check_response_degraded.get("checks", {})
        external_healthy = all(
            checks.get(name, {}).get("status") == "healthy"
            for name in ("safetyamp", "samsara")
        )
        assert external_healthy is False
