# Backwards-compatibility shim. The unified DataManager now lives in services/data_manager.py
from services.data_manager import DataManager, data_manager  # noqa: F401

class CacheManager(DataManager):
    """Compatibility wrapper around the unified DataManager.
    Adds legacy helpers expected by deployment scripts.
    """

    def get_employees(self):
        """Return SafetyAmp users as a list for validation scripts.
        Uses cached users-by-id under the hood.
        """
        try:
            from services.safetyamp_api import SafetyAmpAPI
        except Exception:
            SafetyAmpAPI = None  # type: ignore

        fetch = None
        if SafetyAmpAPI is not None:
            api = SafetyAmpAPI()
            fetch = lambda: api.get_all_paginated("/api/users", key_field="id")
        else:
            # If API import fails, fall back to whatever is cached
            fetch = lambda: self.get_cached_data("safetyamp_users_by_id") or {}

        users_by_id = self.get_cached_data_with_fallback(
            "safetyamp_users_by_id",
            fetch,
            max_age_hours=1,
        ) or {}
        # Normalize to list for scripts that iterate sequentially
        try:
            return list(users_by_id.values())
        except Exception:
            return [] 