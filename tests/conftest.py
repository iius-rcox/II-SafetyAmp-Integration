"""
Pytest fixtures for SafetyAmp Integration tests.

These fixtures provide mocked dependencies to enable unit testing
without requiring actual database connections or API access.
"""

import pytest
from unittest.mock import MagicMock, patch
import sys
import os

# Ensure the project root is in the path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@pytest.fixture
def mock_config():
    """Mock configuration with test values."""
    config = MagicMock()
    config.SAFETYAMP_DOMAIN = "https://api.safetyamp.test"
    config.SAFETYAMP_FQDN = "test.safetyamp.com"
    config.SAFETYAMP_TOKEN = "test-token-12345"
    config.SAMSARA_DOMAIN = "https://api.samsara.test"
    config.SAMSARA_API_KEY = "test-samsara-key"
    config.SQL_SERVER = "test-sql-server"
    config.SQL_DATABASE = "test-database"
    config.SQL_AUTH_MODE = "sql_auth"
    config.DB_POOL_SIZE = 5
    config.DB_MAX_OVERFLOW = 10
    config.DB_POOL_TIMEOUT = 30
    config.DB_POOL_RECYCLE = 3600
    config.REDIS_HOST = "localhost"
    config.REDIS_PORT = 6379
    config.SYNC_INTERVAL_MINUTES = 15
    config.HTTP_REQUEST_TIMEOUT = 10
    config.MAX_RETRY_ATTEMPTS = 3
    config.FAILED_SYNC_TRACKER_ENABLED = True
    config.FAILED_SYNC_TTL_DAYS = 7
    return config


@pytest.fixture
def sample_viewpoint_employee():
    """Sample employee record from Viewpoint ERP."""
    return {
        "Employee": 12345,
        "FirstName": "John",
        "MidName": "Q",
        "LastName": "Doe",
        "Sex": "M",
        "PRDept": "FIELD",
        "Email": "john.doe@example.com",
        "udEmpTitle": "Foreman",
        "BirthDate": "1985-06-15",
        "HireDate": "2020-01-15",
        "Phone": "(555) 123-4567",
        "Address": "123 Main St",
        "City": "Houston",
        "State": "TX",
        "Zip": "77001",
        "Job": "JOB-001",
    }


@pytest.fixture
def sample_viewpoint_employee_minimal():
    """Minimal employee record with only required fields."""
    return {
        "Employee": 99999,
        "FirstName": "Jane",
        "LastName": "Smith",
        "PRDept": "ADMIN",
        "HireDate": "2023-01-01",
    }


@pytest.fixture
def sample_samsara_vehicle():
    """Sample vehicle record from Samsara API."""
    return {
        "id": "vehicle-123",
        "name": "Truck 42",
        "vin": "1HGBH41JXMN109186",
        "serial": "SN-12345",
        "make": "Ford",
        "model": "F-150",
        "year": 2022,
        "licensePlate": "ABC-1234",
        "externalIds": {"unitNumber": "42"},
    }


@pytest.fixture
def sample_safetyamp_user():
    """Sample user record from SafetyAmp API."""
    return {
        "id": 1001,
        "emp_id": "12345",
        "first_name": "John",
        "middle_name": "Q",
        "last_name": "Doe",
        "email": "john.doe@example.com",
        "gender": "male",
        "date_of_birth": "1985-06-15",
        "current_hire_date": "2020-01-15",
        "mobile_phone": "5551234567",
        "work_phone": "5551234567",
        "home_site_id": 100,
        "system_access": 1,
        "text_opt_out": 1,
    }


@pytest.fixture
def flask_test_client():
    """Flask test client for endpoint testing."""
    # Patch config before importing main
    with patch("config.config") as mock_cfg:
        mock_cfg.DB_POOL_SIZE = 5
        mock_cfg.DB_MAX_OVERFLOW = 10
        mock_cfg.DB_POOL_TIMEOUT = 30
        mock_cfg.SYNC_INTERVAL_MINUTES = 60
        mock_cfg.validate_required_secrets.return_value = True
        mock_cfg.get_configuration_status.return_value = {
            "validation": {"is_valid": True, "missing": []},
            "azure": {"azure_key_vault_enabled": False},
        }

        from main import app

        app.config["TESTING"] = True
        with app.test_client() as client:
            yield client


@pytest.fixture
def mock_safetyamp_api():
    """Mocked SafetyAmp API client."""
    with patch("services.safetyamp_api.SafetyAmpAPI") as MockAPI:
        api = MockAPI.return_value
        api.get.return_value = []
        api.post.return_value = {"id": 1}
        api.patch.return_value = {"id": 1}
        api.get_all_paginated.return_value = {}
        api.get_sites.return_value = {}
        api.get_site_clusters.return_value = {}
        api.get_users.return_value = {}
        api.get_roles.return_value = {}
        api.get_titles.return_value = {}
        yield api


@pytest.fixture
def mock_viewpoint_api():
    """Mocked Viewpoint API client."""
    with patch("services.viewpoint_api.ViewpointAPI") as MockAPI:
        api = MockAPI.return_value
        api.get_employees.return_value = []
        api.get_jobs.return_value = []
        api.get_departments.return_value = []
        api.get_titles.return_value = []
        yield api


@pytest.fixture
def mock_redis():
    """Mocked Redis client for caching tests."""
    with patch("redis.Redis") as MockRedis:
        redis_client = MockRedis.return_value
        redis_client.get.return_value = None
        redis_client.set.return_value = True
        redis_client.delete.return_value = True
        redis_client.exists.return_value = False
        redis_client.ping.return_value = True
        yield redis_client
