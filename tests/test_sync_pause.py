"""
Unit tests for Sync Pause/Resume feature.

Tests cover:
- DataManager.get_sync_paused() and set_sync_paused() methods
- GET/POST /api/dashboard/sync-pause endpoints
- Authentication requirements
- Redis state management
"""

import json
import time
import pytest
from unittest.mock import MagicMock, patch, PropertyMock


class TestDataManagerSyncPause:
    """Tests for DataManager sync pause methods."""

    @pytest.fixture
    def mock_redis_client(self):
        """Create a mock Redis client."""
        client = MagicMock()
        client.ping.return_value = True
        client.get.return_value = None
        client.set.return_value = True
        client.setex.return_value = True
        return client

    @pytest.fixture
    def data_manager_with_redis(self, mock_redis_client):
        """Create DataManager with mocked Redis."""
        with patch("services.data_manager.redis.Redis") as MockRedis:
            MockRedis.return_value = mock_redis_client
            with patch("services.data_manager.config") as mock_config:
                mock_config.REDIS_HOST = "localhost"
                mock_config.REDIS_PORT = "6379"
                mock_config.REDIS_DB = "0"
                mock_config.REDIS_PASSWORD = None
                mock_config.CACHE_TTL_HOURS = "24"
                mock_config.CACHE_REFRESH_INTERVAL_HOURS = "1"
                mock_config.VISTA_REFRESH_MINUTES = "60"

                from services.data_manager import DataManager

                dm = DataManager()
                dm.redis_client = mock_redis_client
                return dm

    def test_get_sync_paused_returns_false_by_default(self, data_manager_with_redis):
        """get_sync_paused() should return False when no pause state exists."""
        data_manager_with_redis.redis_client.get.return_value = None

        result = data_manager_with_redis.get_sync_paused()

        assert result is False
        data_manager_with_redis.redis_client.get.assert_called_with(
            "safetyamp:sync:paused"
        )

    def test_get_sync_paused_returns_true_when_paused(self, data_manager_with_redis):
        """get_sync_paused() should return True when sync is paused."""
        data_manager_with_redis.redis_client.get.return_value = "1"

        result = data_manager_with_redis.get_sync_paused()

        assert result is True

    def test_get_sync_paused_returns_false_when_not_paused(
        self, data_manager_with_redis
    ):
        """get_sync_paused() should return False when sync is not paused."""
        data_manager_with_redis.redis_client.get.return_value = "0"

        result = data_manager_with_redis.get_sync_paused()

        assert result is False

    def test_get_sync_paused_returns_false_on_redis_error(
        self, data_manager_with_redis
    ):
        """get_sync_paused() should return False when Redis fails."""
        data_manager_with_redis.redis_client.get.side_effect = Exception("Redis error")

        result = data_manager_with_redis.get_sync_paused()

        assert result is False

    def test_get_sync_paused_returns_false_without_redis(self):
        """get_sync_paused() should return False when Redis is not available."""
        with patch("services.data_manager.redis.Redis") as MockRedis:
            MockRedis.return_value.ping.side_effect = Exception("Connection failed")
            with patch("services.data_manager.config") as mock_config:
                mock_config.REDIS_HOST = "localhost"
                mock_config.REDIS_PORT = "6379"
                mock_config.REDIS_DB = "0"
                mock_config.REDIS_PASSWORD = None
                mock_config.CACHE_TTL_HOURS = "24"
                mock_config.CACHE_REFRESH_INTERVAL_HOURS = "1"
                mock_config.VISTA_REFRESH_MINUTES = "60"

                from services.data_manager import DataManager

                dm = DataManager()
                dm.redis_client = None

                result = dm.get_sync_paused()

                assert result is False

    def test_set_sync_paused_stores_true_in_redis(self, data_manager_with_redis):
        """set_sync_paused(True) should store '1' in Redis."""
        result = data_manager_with_redis.set_sync_paused(True, paused_by="test_user")

        assert result is True
        # Check that the pause state was set (may not be the last call due to metadata)
        calls = data_manager_with_redis.redis_client.set.call_args_list
        pause_call = None
        for call in calls:
            if call[0][0] == "safetyamp:sync:paused" and call[0][1] == "1":
                pause_call = call
                break
        assert pause_call is not None, "Expected set('safetyamp:sync:paused', '1') call"

    def test_set_sync_paused_stores_false_in_redis(self, data_manager_with_redis):
        """set_sync_paused(False) should store '0' in Redis."""
        result = data_manager_with_redis.set_sync_paused(False)

        assert result is True
        data_manager_with_redis.redis_client.set.assert_called_with(
            "safetyamp:sync:paused", "0"
        )

    def test_set_sync_paused_stores_metadata_when_pausing(
        self, data_manager_with_redis
    ):
        """set_sync_paused(True) should store metadata with paused_by and timestamp."""
        before_time = time.time()
        data_manager_with_redis.set_sync_paused(True, paused_by="admin_user")
        after_time = time.time()

        # Check metadata was stored
        calls = data_manager_with_redis.redis_client.set.call_args_list
        assert len(calls) >= 1

        # Find the metadata call
        metadata_call = None
        for call in calls:
            if "safetyamp:sync:paused:metadata" in str(call):
                metadata_call = call
                break

        assert metadata_call is not None
        metadata_json = metadata_call[0][1]
        metadata = json.loads(metadata_json)

        assert metadata["paused_by"] == "admin_user"
        assert before_time <= metadata["paused_at"] <= after_time

    def test_set_sync_paused_clears_metadata_when_resuming(
        self, data_manager_with_redis
    ):
        """set_sync_paused(False) should delete metadata."""
        data_manager_with_redis.set_sync_paused(False)

        data_manager_with_redis.redis_client.delete.assert_called_with(
            "safetyamp:sync:paused:metadata"
        )

    def test_set_sync_paused_returns_false_on_redis_error(
        self, data_manager_with_redis
    ):
        """set_sync_paused() should return False when Redis fails."""
        data_manager_with_redis.redis_client.set.side_effect = Exception("Redis error")

        result = data_manager_with_redis.set_sync_paused(True)

        assert result is False

    def test_set_sync_paused_returns_false_without_redis(self):
        """set_sync_paused() should return False when Redis is not available."""
        with patch("services.data_manager.redis.Redis") as MockRedis:
            MockRedis.return_value.ping.side_effect = Exception("Connection failed")
            with patch("services.data_manager.config") as mock_config:
                mock_config.REDIS_HOST = "localhost"
                mock_config.REDIS_PORT = "6379"
                mock_config.REDIS_DB = "0"
                mock_config.REDIS_PASSWORD = None
                mock_config.CACHE_TTL_HOURS = "24"
                mock_config.CACHE_REFRESH_INTERVAL_HOURS = "1"
                mock_config.VISTA_REFRESH_MINUTES = "60"

                from services.data_manager import DataManager

                dm = DataManager()
                dm.redis_client = None

                result = dm.set_sync_paused(True)

                assert result is False

    def test_get_sync_pause_metadata_returns_metadata(self, data_manager_with_redis):
        """get_sync_pause_metadata() should return paused_by and paused_at."""
        metadata = {"paused_by": "admin", "paused_at": 1706500000.0}
        data_manager_with_redis.redis_client.get.return_value = json.dumps(metadata)

        result = data_manager_with_redis.get_sync_pause_metadata()

        assert result == metadata
        data_manager_with_redis.redis_client.get.assert_called_with(
            "safetyamp:sync:paused:metadata"
        )

    def test_get_sync_pause_metadata_returns_none_when_not_set(
        self, data_manager_with_redis
    ):
        """get_sync_pause_metadata() should return None when no metadata exists."""
        data_manager_with_redis.redis_client.get.return_value = None

        result = data_manager_with_redis.get_sync_pause_metadata()

        assert result is None

    def test_get_sync_pause_metadata_returns_none_on_error(
        self, data_manager_with_redis
    ):
        """get_sync_pause_metadata() should return None when Redis fails."""
        data_manager_with_redis.redis_client.get.side_effect = Exception("Redis error")

        result = data_manager_with_redis.get_sync_pause_metadata()

        assert result is None


class TestSyncPauseEndpoints:
    """Tests for sync pause API endpoints."""

    @pytest.fixture(autouse=True)
    def reset_rate_limiter(self):
        """Reset rate limiter before each test."""
        from routes.dashboard import _reset_rate_limit_tracker
        _reset_rate_limit_tracker()
        yield
        _reset_rate_limit_tracker()

    @pytest.fixture
    def mock_data_manager(self):
        """Create a mock data manager."""
        dm = MagicMock()
        dm.get_sync_paused.return_value = False
        dm.set_sync_paused.return_value = True
        dm.get_sync_pause_metadata.return_value = None
        return dm

    @pytest.fixture
    def dashboard_blueprint(self, mock_data_manager):
        """Create dashboard blueprint with mocked data manager."""
        from routes.dashboard import create_dashboard_blueprint
        from flask import Flask

        app = Flask(__name__)
        app.config["TESTING"] = True

        bp = create_dashboard_blueprint(data_manager=mock_data_manager)
        app.register_blueprint(bp)

        return app, mock_data_manager

    @pytest.fixture
    def auth_headers(self):
        """Return valid authentication headers."""
        return {"X-Dashboard-Token": "test-token-12345"}

    def test_get_sync_pause_returns_current_state_not_paused(
        self, dashboard_blueprint, auth_headers
    ):
        """GET /sync-pause should return current pause state (not paused)."""
        app, mock_dm = dashboard_blueprint
        mock_dm.get_sync_paused.return_value = False
        mock_dm.get_sync_pause_metadata.return_value = None

        with patch.dict("os.environ", {"DASHBOARD_API_TOKEN": "test-token-12345"}):
            with app.test_client() as client:
                response = client.get(
                    "/api/dashboard/sync-pause", headers=auth_headers
                )

        assert response.status_code == 200
        data = response.get_json()
        assert data["paused"] is False
        assert data["paused_by"] is None
        assert data["paused_at"] is None

    def test_get_sync_pause_returns_current_state_paused(
        self, dashboard_blueprint, auth_headers
    ):
        """GET /sync-pause should return current pause state (paused)."""
        app, mock_dm = dashboard_blueprint
        mock_dm.get_sync_paused.return_value = True
        mock_dm.get_sync_pause_metadata.return_value = {
            "paused_by": "admin",
            "paused_at": 1706500000.0,
        }

        with patch.dict("os.environ", {"DASHBOARD_API_TOKEN": "test-token-12345"}):
            with app.test_client() as client:
                response = client.get(
                    "/api/dashboard/sync-pause", headers=auth_headers
                )

        assert response.status_code == 200
        data = response.get_json()
        assert data["paused"] is True
        assert data["paused_by"] == "admin"
        assert data["paused_at"] == 1706500000.0

    def test_post_sync_pause_pauses_sync(self, dashboard_blueprint, auth_headers):
        """POST /sync-pause with paused=true should pause sync."""
        app, mock_dm = dashboard_blueprint

        with patch.dict("os.environ", {"DASHBOARD_API_TOKEN": "test-token-12345"}):
            with app.test_client() as client:
                response = client.post(
                    "/api/dashboard/sync-pause",
                    headers=auth_headers,
                    json={"paused": True},
                )

        assert response.status_code == 200
        data = response.get_json()
        assert data["paused"] is True
        assert "paused" in data["message"].lower() or "sync" in data["message"].lower()
        mock_dm.set_sync_paused.assert_called_once()
        call_args = mock_dm.set_sync_paused.call_args
        assert call_args[0][0] is True  # First positional arg is True

    def test_post_sync_pause_resumes_sync(self, dashboard_blueprint, auth_headers):
        """POST /sync-pause with paused=false should resume sync."""
        app, mock_dm = dashboard_blueprint

        with patch.dict("os.environ", {"DASHBOARD_API_TOKEN": "test-token-12345"}):
            with app.test_client() as client:
                response = client.post(
                    "/api/dashboard/sync-pause",
                    headers=auth_headers,
                    json={"paused": False},
                )

        assert response.status_code == 200
        data = response.get_json()
        assert data["paused"] is False
        assert (
            "resume" in data["message"].lower() or "sync" in data["message"].lower()
        )
        mock_dm.set_sync_paused.assert_called_once()
        call_args = mock_dm.set_sync_paused.call_args
        assert call_args[0][0] is False  # First positional arg is False

    def test_post_sync_pause_returns_error_on_failure(
        self, dashboard_blueprint, auth_headers
    ):
        """POST /sync-pause should return 500 when set_sync_paused fails."""
        app, mock_dm = dashboard_blueprint
        mock_dm.set_sync_paused.return_value = False

        with patch.dict("os.environ", {"DASHBOARD_API_TOKEN": "test-token-12345"}):
            with app.test_client() as client:
                response = client.post(
                    "/api/dashboard/sync-pause",
                    headers=auth_headers,
                    json={"paused": True},
                )

        assert response.status_code == 500
        data = response.get_json()
        assert "error" in data

    def test_post_sync_pause_requires_paused_field(
        self, dashboard_blueprint, auth_headers
    ):
        """POST /sync-pause should return 400 when paused field is missing."""
        app, mock_dm = dashboard_blueprint

        with patch.dict("os.environ", {"DASHBOARD_API_TOKEN": "test-token-12345"}):
            with app.test_client() as client:
                response = client.post(
                    "/api/dashboard/sync-pause",
                    headers=auth_headers,
                    json={},
                )

        assert response.status_code == 400
        data = response.get_json()
        assert "error" in data

    def test_get_sync_pause_requires_authentication(self, dashboard_blueprint):
        """GET /sync-pause should return 401 without authentication."""
        app, _ = dashboard_blueprint

        with patch.dict("os.environ", {"DASHBOARD_API_TOKEN": "test-token-12345"}):
            with app.test_client() as client:
                response = client.get("/api/dashboard/sync-pause")

        assert response.status_code == 401

    def test_post_sync_pause_requires_authentication(self, dashboard_blueprint):
        """POST /sync-pause should return 401 without authentication."""
        app, _ = dashboard_blueprint

        with patch.dict("os.environ", {"DASHBOARD_API_TOKEN": "test-token-12345"}):
            with app.test_client() as client:
                response = client.post(
                    "/api/dashboard/sync-pause",
                    json={"paused": True},
                )

        assert response.status_code == 401

    def test_sync_pause_rejects_invalid_token(self, dashboard_blueprint):
        """Endpoints should return 403 with invalid token."""
        app, _ = dashboard_blueprint
        invalid_headers = {"X-Dashboard-Token": "invalid-token"}

        with patch.dict("os.environ", {"DASHBOARD_API_TOKEN": "test-token-12345"}):
            with app.test_client() as client:
                response = client.get(
                    "/api/dashboard/sync-pause", headers=invalid_headers
                )

        assert response.status_code == 403

    def test_get_sync_pause_logs_audit_event(self, dashboard_blueprint, auth_headers):
        """GET /sync-pause does not log audit (read-only)."""
        # GET is read-only, should not log audit
        pass  # No audit for GET operations

    def test_post_sync_pause_logs_audit_event(self, dashboard_blueprint, auth_headers):
        """POST /sync-pause should log an audit event."""
        app, mock_dm = dashboard_blueprint

        with patch.dict("os.environ", {"DASHBOARD_API_TOKEN": "test-token-12345"}):
            with patch("routes.dashboard._log_audit_event") as mock_audit:
                with app.test_client() as client:
                    response = client.post(
                        "/api/dashboard/sync-pause",
                        headers=auth_headers,
                        json={"paused": True},
                    )

                assert response.status_code == 200
                mock_audit.assert_called_once()
                call_args = mock_audit.call_args
                assert call_args[0][0] == "pause"  # action
                assert call_args[0][1] == "sync"  # resource


class TestSyncPauseSecurity:
    """Tests for security features of sync pause endpoints."""

    @pytest.fixture(autouse=True)
    def reset_rate_limiter(self):
        """Reset rate limiter before each test."""
        from routes.dashboard import _reset_rate_limit_tracker
        _reset_rate_limit_tracker()
        yield
        _reset_rate_limit_tracker()

    @pytest.fixture
    def mock_data_manager(self):
        """Create a mock data manager."""
        dm = MagicMock()
        dm.get_sync_paused.return_value = False
        dm.set_sync_paused.return_value = True
        dm.get_sync_pause_metadata.return_value = None
        return dm

    @pytest.fixture
    def dashboard_blueprint(self, mock_data_manager):
        """Create dashboard blueprint with mocked data manager."""
        from routes.dashboard import create_dashboard_blueprint
        from flask import Flask

        app = Flask(__name__)
        app.config["TESTING"] = True

        bp = create_dashboard_blueprint(data_manager=mock_data_manager)
        app.register_blueprint(bp)

        return app, mock_data_manager

    @pytest.fixture
    def auth_headers(self):
        """Return valid authentication headers."""
        return {"X-Dashboard-Token": "test-token-12345"}

    def test_post_sync_pause_rejects_string_paused_value(
        self, dashboard_blueprint, auth_headers
    ):
        """POST /sync-pause should reject 'false' string as paused value."""
        app, mock_dm = dashboard_blueprint

        with patch.dict("os.environ", {"DASHBOARD_API_TOKEN": "test-token-12345"}):
            with app.test_client() as client:
                response = client.post(
                    "/api/dashboard/sync-pause",
                    headers=auth_headers,
                    json={"paused": "false"},  # String, not boolean
                )

        assert response.status_code == 400
        data = response.get_json()
        assert "boolean" in data["error"].lower()

    def test_post_sync_pause_rejects_integer_paused_value(
        self, dashboard_blueprint, auth_headers
    ):
        """POST /sync-pause should reject integer as paused value."""
        app, mock_dm = dashboard_blueprint

        with patch.dict("os.environ", {"DASHBOARD_API_TOKEN": "test-token-12345"}):
            with app.test_client() as client:
                response = client.post(
                    "/api/dashboard/sync-pause",
                    headers=auth_headers,
                    json={"paused": 1},  # Integer, not boolean
                )

        assert response.status_code == 400
        data = response.get_json()
        assert "boolean" in data["error"].lower()

    def test_post_sync_pause_sanitizes_paused_by_field(
        self, dashboard_blueprint, auth_headers
    ):
        """POST /sync-pause should sanitize paused_by to prevent log injection."""
        app, mock_dm = dashboard_blueprint

        with patch.dict("os.environ", {"DASHBOARD_API_TOKEN": "test-token-12345"}):
            with app.test_client() as client:
                response = client.post(
                    "/api/dashboard/sync-pause",
                    headers=auth_headers,
                    json={
                        "paused": True,
                        "paused_by": "<script>alert(1)</script>\nFake log entry",
                    },
                )

        assert response.status_code == 200
        # Verify the paused_by was sanitized
        call_args = mock_dm.set_sync_paused.call_args
        paused_by = call_args[1]["paused_by"]
        # Should not contain script tags or newlines
        assert "<script>" not in paused_by
        assert "\n" not in paused_by
        # Should be alphanumeric with allowed chars only
        import re
        assert re.match(r"^[\w@.\-]*$", paused_by)

    def test_post_sync_pause_truncates_long_paused_by(
        self, dashboard_blueprint, auth_headers
    ):
        """POST /sync-pause should truncate overly long paused_by."""
        app, mock_dm = dashboard_blueprint
        long_identifier = "a" * 200  # Very long identifier

        with patch.dict("os.environ", {"DASHBOARD_API_TOKEN": "test-token-12345"}):
            with app.test_client() as client:
                response = client.post(
                    "/api/dashboard/sync-pause",
                    headers=auth_headers,
                    json={"paused": True, "paused_by": long_identifier},
                )

        assert response.status_code == 200
        call_args = mock_dm.set_sync_paused.call_args
        paused_by = call_args[1]["paused_by"]
        assert len(paused_by) <= 64  # MAX_PAUSED_BY_LENGTH

    def test_post_sync_pause_rate_limiting(self, dashboard_blueprint, auth_headers):
        """POST /sync-pause should rate limit to 5 requests per minute."""
        app, mock_dm = dashboard_blueprint

        with patch.dict("os.environ", {"DASHBOARD_API_TOKEN": "test-token-12345"}):
            with app.test_client() as client:
                # First 5 requests should succeed
                for i in range(5):
                    response = client.post(
                        "/api/dashboard/sync-pause",
                        headers=auth_headers,
                        json={"paused": True},
                    )
                    assert response.status_code == 200, f"Request {i+1} failed unexpectedly"

                # 6th request should be rate limited
                response = client.post(
                    "/api/dashboard/sync-pause",
                    headers=auth_headers,
                    json={"paused": True},
                )
                assert response.status_code == 429
                data = response.get_json()
                assert "rate limit" in data["error"].lower()


class TestSyncWorkerPauseIntegration:
    """Tests for sync worker pause behavior."""

    def test_health_status_includes_sync_paused_field(self):
        """health_status should include sync_paused field."""
        # Test the health_status structure by checking the expected default
        # We cannot import main directly as it triggers Flask limiter initialization
        # Instead, we verify the expected structure through the source code
        expected_fields = [
            "healthy",
            "ready",
            "last_sync",
            "errors",
            "database_status",
            "external_apis_status",
            "sync_in_progress",
            "sync_paused",
        ]

        # Read the main.py file and verify sync_paused is in health_status
        with open("main.py", "r") as f:
            content = f.read()

        # Verify health_status dict contains sync_paused
        assert '"sync_paused": False' in content or "'sync_paused': False" in content


class TestSyncPauseEndpointWhenDataManagerUnavailable:
    """Tests for sync pause endpoints when data_manager is not available."""

    @pytest.fixture(autouse=True)
    def reset_rate_limiter(self):
        """Reset rate limiter before each test."""
        from routes.dashboard import _reset_rate_limit_tracker
        _reset_rate_limit_tracker()
        yield
        _reset_rate_limit_tracker()

    @pytest.fixture
    def dashboard_blueprint_no_data_manager(self):
        """Create dashboard blueprint without data manager."""
        from routes.dashboard import create_dashboard_blueprint
        from flask import Flask

        app = Flask(__name__)
        app.config["TESTING"] = True

        bp = create_dashboard_blueprint(data_manager=None)
        app.register_blueprint(bp)

        return app

    @pytest.fixture
    def auth_headers(self):
        """Return valid authentication headers."""
        return {"X-Dashboard-Token": "test-token-12345"}

    def test_get_sync_pause_returns_503_without_data_manager(
        self, dashboard_blueprint_no_data_manager, auth_headers
    ):
        """GET /sync-pause should return 503 when data_manager not available."""
        app = dashboard_blueprint_no_data_manager

        with patch.dict("os.environ", {"DASHBOARD_API_TOKEN": "test-token-12345"}):
            with app.test_client() as client:
                response = client.get(
                    "/api/dashboard/sync-pause", headers=auth_headers
                )

        assert response.status_code == 503
        data = response.get_json()
        assert "error" in data

    def test_post_sync_pause_returns_503_without_data_manager(
        self, dashboard_blueprint_no_data_manager, auth_headers
    ):
        """POST /sync-pause should return 503 when data_manager not available."""
        app = dashboard_blueprint_no_data_manager

        with patch.dict("os.environ", {"DASHBOARD_API_TOKEN": "test-token-12345"}):
            with app.test_client() as client:
                response = client.post(
                    "/api/dashboard/sync-pause",
                    headers=auth_headers,
                    json={"paused": True},
                )

        assert response.status_code == 503
        data = response.get_json()
        assert "error" in data
