from typing import Any, Dict, Optional

from utils.logger import get_logger
from utils.change_tracker import ChangeTracker
from utils.data_validator import validator
from utils.error_notifier import error_notifier
from services.safetyamp_api import SafetyAmpAPI
from services.viewpoint_api import ViewpointAPI


class SyncOperation:
    """Base class for sync operations providing shared clients, tracking, and error handling.

    Subclasses must implement perform_sync() and may override before_sync() and after_sync().
    """

    def __init__(self, name: str, sync_type: str, entity_type: str):
        self.logger = get_logger(name)
        self.sync_type = sync_type
        self.entity_type = entity_type

        # Common service clients
        safetyamp = SafetyAmpAPI()
        self.api_client = safetyamp  # Backwards-compatible alias used by some syncers
        self.safetyamp_api = safetyamp
        self.viewpoint = ViewpointAPI()

        # Shared utilities
        self.change_tracker = ChangeTracker()
        self.validator = validator
        self.error_notifier = error_notifier

    # --- Lifecycle hooks ---
    def before_sync(self) -> None:
        """Optional hook for subclasses to preload data before sync."""
        return None

    def perform_sync(self) -> Dict[str, Any]:
        """Subclasses must implement the core sync logic and return a result dict.

        Expected keys (defaults applied if missing):
        - processed: int
        - created: int
        - updated: int
        - skipped: int
        - errors: int
        """
        raise NotImplementedError

    def after_sync(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """Optional hook for subclasses to run after successful perform_sync (e.g., cache updates)."""
        return result

    # --- Change tracking helpers ---
    def log_creation(self, entity_id: str, data: Dict[str, Any], source_system: str = "viewpoint", target_system: str = "safetyamp") -> None:
        self.change_tracker.log_creation(self.entity_type, entity_id, data, source_system, target_system)

    def log_update(self, entity_id: str, changes: Dict[str, Any], original_data: Optional[Dict[str, Any]] = None, source_system: str = "viewpoint", target_system: str = "safetyamp") -> None:
        self.change_tracker.log_update(self.entity_type, entity_id, changes, original_data, source_system, target_system)

    def log_skip(self, entity_id: str, reason: str, source_system: str = "viewpoint", target_system: str = "safetyamp") -> None:
        self.change_tracker.log_skip(self.entity_type, entity_id, reason, source_system, target_system)

    def log_error(self, entity_id: str, error: str, operation: str = "unknown", data: Optional[Dict[str, Any]] = None, notify: bool = False, notify_type: Optional[str] = None, notify_details: Optional[Dict[str, Any]] = None, source: Optional[str] = None) -> None:
        self.change_tracker.log_error(self.entity_type, entity_id, error, operation, data)
        if notify:
            try:
                self.error_notifier.log_error(
                    error_type=notify_type or "sync_error",
                    entity_type=self.entity_type,
                    entity_id=entity_id,
                    error_message=error,
                    error_details=notify_details or {},
                    source=source or f"sync_{self.sync_type}",
                )
            except Exception:
                # Never raise from notifier
                pass

    # --- Orchestration ---
    def sync(self) -> Dict[str, Any]:
        self.logger.info(f"Starting {self.sync_type} sync...")
        self.change_tracker.start_sync(self.sync_type)

        result: Dict[str, Any]
        try:
            self.before_sync()
            result = self.perform_sync() or {}
            result = self.after_sync(result) or result
        except Exception as e:
            # Robust error handling to avoid crashing the worker
            err_msg = str(e)
            self.logger.exception(f"Unhandled error during {self.sync_type} sync: {err_msg}")
            self.log_error(entity_id="system", error=err_msg, operation="sync", notify=True, notify_type="unexpected_error")
            result = {"processed": 0, "created": 0, "updated": 0, "skipped": 0, "errors": 1}
        finally:
            session_summary = self.change_tracker.end_sync()

        # Normalize result shape
        result.setdefault("processed", 0)
        result.setdefault("created", 0)
        result.setdefault("updated", 0)
        result.setdefault("skipped", 0)
        result.setdefault("errors", 0)
        result["session_summary"] = session_summary

        self.logger.info(
            f"{self.sync_type.capitalize()} sync completed: "
            f"{result['created']} created, {result['updated']} updated, {result['skipped']} skipped, {result['errors']} errors"
        )
        return result