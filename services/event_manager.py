#!/usr/bin/env python3
from __future__ import annotations

from typing import Dict, Any, Optional
from utils.logger import get_logger
from utils.change_tracker import ChangeTracker
from utils.error_notifier import ErrorNotifier


logger = get_logger("event_manager")


class EventManager:
    """Unified event manager for sessions, change tracking, and notifications.

    Wraps existing `ChangeTracker` and `ErrorNotifier` to provide a stable API
    for emitting creation/update/deletion events, errors, and session lifecycle.
    """

    def __init__(self, change_tracker: Optional[ChangeTracker] = None, error_notifier: Optional[ErrorNotifier] = None) -> None:
        self.change_tracker = change_tracker or ChangeTracker()
        self.error_notifier = error_notifier or ErrorNotifier()
        self._current_session_id: Optional[str] = None

    # ----- Session lifecycle -----
    def start_sync(self, name: str, correlation_id: Optional[str] = None) -> str:
        self.change_tracker.start_sync(name)
        self._current_session_id = self.change_tracker.current_session.get("session_id")
        logger.info("Sync session started", extra={"sync_type": name, "session_id": self._current_session_id, "correlation_id": correlation_id})
        return self._current_session_id or ""

    def end_sync(self, session_id: Optional[str] = None) -> Dict[str, Any]:
        summary = self.change_tracker.end_sync()
        logger.info("Sync session ended", extra={"session_id": session_id or self._current_session_id, "summary": summary.get("summary")})
        self._current_session_id = None
        return summary

    # ----- Change events -----
    def log_creation(self, entity: str, entity_id: str, details: Optional[Dict[str, Any]] = None, session_id: Optional[str] = None) -> None:
        self.change_tracker.log_creation(entity, entity_id, details or {})

    def log_update(self, entity: str, entity_id: str, changes: Optional[Dict[str, Any]] = None, original_data: Optional[Dict[str, Any]] = None, session_id: Optional[str] = None) -> None:
        self.change_tracker.log_update(entity, entity_id, changes or {}, original_data)

    def log_deletion(self, entity: str, entity_id: str, reason: Optional[str] = None, session_id: Optional[str] = None) -> None:
        self.change_tracker.log_deletion(entity, entity_id, reason or "sync_cleanup")

    def log_skip(self, entity: str, entity_id: str, reason: str, session_id: Optional[str] = None) -> None:
        self.change_tracker.log_skip(entity, entity_id, reason)

    # ----- Errors -----
    def log_error(
        self,
        kind: str,
        entity: Optional[str],
        entity_id: Optional[str],
        message: str,
        exc: Optional[BaseException] = None,
        session_id: Optional[str] = None,
        operation: str = "unknown",
        details: Optional[Dict[str, Any]] = None,
        source: str = "sync",
    ) -> None:
        # Bridge to change tracker
        self.change_tracker.log_error(
            entity_type=entity or "system",
            entity_id=entity_id or "unknown",
            error=message,
            operation=operation,
            data=details,
        )
        # Bridge to notifier
        try:
            self.error_notifier.log_error(
                error_type=kind,
                entity_type=entity or "system",
                entity_id=entity_id or "unknown",
                error_message=message,
                error_details=details,
                source=source,
            )
        except Exception as notify_error:
            logger.error(f"Failed to log error to notifier: {notify_error}")

    # ----- Notifications -----
    def send_hourly_notification(self) -> bool:
        return self.error_notifier.send_hourly_notification()


# Global singleton
event_manager = EventManager()



