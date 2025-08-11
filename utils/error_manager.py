#!/usr/bin/env python3
from typing import Optional, Dict, Any
from utils.logger import get_logger
from utils.change_tracker import ChangeTracker
from utils.error_notifier import ErrorNotifier


logger = get_logger("error_manager")


class ErrorManager:
    """Unified manager for errors, change tracking, and notifications."""

    def __init__(self, change_tracker: Optional[ChangeTracker] = None, error_notifier: Optional[ErrorNotifier] = None):
        self.change_tracker = change_tracker or ChangeTracker()
        self.error_notifier = error_notifier or ErrorNotifier()
        self._current_sync_type: Optional[str] = None

    def start_sync(self, sync_type: str) -> None:
        self._current_sync_type = sync_type
        self.change_tracker.start_sync(sync_type)

    def log_creation(self, entity_type: str, entity_id: str, data: Dict[str, Any],
                     source_system: str = "viewpoint", target_system: str = "safetyamp") -> None:
        self.change_tracker.log_creation(entity_type, entity_id, data, source_system, target_system)

    def log_update(self, entity_type: str, entity_id: str, changes: Dict[str, Any],
                   original_data: Optional[Dict[str, Any]] = None,
                   source_system: str = "viewpoint", target_system: str = "safetyamp") -> None:
        self.change_tracker.log_update(entity_type, entity_id, changes, original_data, source_system, target_system)

    def log_deletion(self, entity_type: str, entity_id: str, reason: str = "sync_cleanup",
                     source_system: str = "viewpoint", target_system: str = "safetyamp") -> None:
        self.change_tracker.log_deletion(entity_type, entity_id, reason, source_system, target_system)

    def log_skip(self, entity_type: str, entity_id: str, reason: str,
                 source_system: str = "viewpoint", target_system: str = "safetyamp") -> None:
        self.change_tracker.log_skip(entity_type, entity_id, reason, source_system, target_system)

    def log_error(self,
                  error_type: str,
                  entity_type: str,
                  entity_id: str,
                  error_message: str,
                  operation: str = "unknown",
                  error_details: Optional[Dict[str, Any]] = None,
                  source: str = "sync",
                  source_system: str = "viewpoint",
                  target_system: str = "safetyamp") -> None:
        """Log an error to change tracking and error notifier (single call for unified handling)."""
        # Track error (this also logs via logger)
        self.change_tracker.log_error(
            entity_type=entity_type,
            entity_id=entity_id,
            error=error_message,
            operation=operation,
            data=error_details,
            source_system=source_system,
            target_system=target_system,
        )
        # Notify for aggregated reporting/email
        try:
            self.error_notifier.log_error(
                error_type=error_type,
                entity_type=entity_type,
                entity_id=entity_id,
                error_message=error_message,
                error_details=error_details,
                source=source,
            )
        except Exception as notify_error:
            logger.error(f"Failed to log error to notifier: {notify_error}")

    def end_sync(self) -> Dict[str, Any]:
        summary = self.change_tracker.end_sync()
        self._current_sync_type = None
        return summary

    # Notification helpers
    def send_hourly_notification(self) -> bool:
        return self.error_notifier.send_hourly_notification()

    def cleanup_old_errors(self, days: int = 7) -> None:
        self.error_notifier.cleanup_old_errors(days)

    def get_notification_status(self) -> Dict[str, Any]:
        return self.error_notifier.get_notification_status()


# Global instance
error_manager = ErrorManager()