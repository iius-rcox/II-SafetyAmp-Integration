from typing import Any, Dict, Optional, Tuple, Callable

import requests

from utils.logger import get_logger
from utils.data_validator import validator
from services.event_manager import event_manager
from services.safetyamp_api import SafetyAmpAPI


class BaseSyncOperation:
    """Base class providing common sync functionality.

    - Centralized logger per sync type
    - Shared SafetyAmp API client
    - Unified error/change tracking via EventManager
    - Validation helpers
    - Simple safety-stop error backoff
    """

    def __init__(self, sync_type: str, logger_name: Optional[str] = None) -> None:
        self.sync_type = sync_type
        self.logger = get_logger(logger_name or f"sync_{sync_type}")
        self.api_client = SafetyAmpAPI()
        self.event_manager = event_manager
        self.validator = validator

        # Basic error backoff
        self.consecutive_errors: int = 0
        self.max_consecutive_errors: int = 10

    # ----- Change tracking lifecycle -----
    def start_sync(self) -> None:
        self.event_manager.start_sync(self.sync_type)

    def end_sync(self) -> Dict[str, Any]:
        return self.event_manager.end_sync()

    # ----- Error handling helpers -----
    def record_success(self) -> None:
        self.consecutive_errors = 0

    def record_error(self) -> None:
        self.consecutive_errors += 1

    def should_abort_for_safety(self, processed_count: int = 0) -> bool:
        if self.consecutive_errors >= self.max_consecutive_errors:
            error_msg = (
                f"Stopping sync due to {self.consecutive_errors} consecutive errors"
            )
            self.event_manager.log_error(
                kind="safety_stop",
                entity="sync",
                entity_id="system",
                message=error_msg,
                operation="safety_stop",
                details={
                    "consecutive_errors": self.consecutive_errors,
                    "max_consecutive_errors": self.max_consecutive_errors,
                    "processed_count": processed_count,
                },
                source="sync_safety",
            )
            return True
        return False

    def execute_with_http_handling(
        self,
        func: Callable[..., Any],
        *,
        entity_type: str,
        entity_id: str,
        operation: str,
        payload: Optional[Dict[str, Any]] = None,
        on_422: Optional[Callable[[requests.HTTPError], None]] = None,
    ) -> Tuple[bool, Optional[Any]]:
        """Execute callable and handle HTTP/Unexpected errors consistently.

        Returns (success, result)
        """
        try:
            result = func()
            self.record_success()
            return True, result
        except requests.HTTPError as e:
            self.record_error()
            status = getattr(e.response, "status_code", None)
            if status == 422:
                # Call custom handler if provided
                if on_422 is not None:
                    try:
                        on_422(e)
                    except Exception:
                        pass
                error_response = None
                try:
                    error_response = e.response.json()
                except Exception:
                    error_response = str(e)
                self.event_manager.log_error(
                    kind="validation_error",
                    entity=entity_type,
                    entity_id=entity_id,
                    message=f"Validation error (422): {error_response}",
                    operation=operation,
                    details={
                        "status_code": 422,
                        "payload": payload,
                    },
                    source=f"sync_{operation}",
                )
            else:
                self.event_manager.log_error(
                    kind="http_error",
                    entity=entity_type,
                    entity_id=entity_id,
                    message=f"HTTP error {status}: {str(e)}",
                    operation=operation,
                    details={
                        "status_code": status,
                        "payload": payload,
                    },
                    source=f"sync_{operation}",
                )
            return False, None
        except Exception as e:
            self.record_error()
            self.event_manager.log_error(
                kind="unexpected_error",
                entity=entity_type,
                entity_id=entity_id,
                message=f"Unexpected error: {str(e)}",
                operation=operation,
                details={
                    "exception_type": type(e).__name__,
                    "payload": payload,
                },
                source=f"sync_{operation}",
            )
            return False, None

    # ----- Validation helpers -----
    def validate_entity(
        self,
        entity_type: str,
        payload: Dict[str, Any],
        entity_id: str,
        display_name: Optional[str] = None,
    ) -> Tuple[bool, Any, Dict[str, Any]]:
        """Validate a payload for a known entity type.

        Returns (is_valid, errors, cleaned_payload)
        """
        if entity_type == "employee":
            return self.validator.validate_employee_data(
                payload, entity_id, display_name or ""
            )
        if entity_type == "vehicle":
            return self.validator.validate_vehicle_data(payload, entity_id)
        if entity_type == "site":
            return self.validator.validate_site_data(payload, entity_id)
        # Default: light clean (remove None)
        cleaned = {k: v for k, v in payload.items() if v is not None}
        return True, [], cleaned

    # ----- Change-tracking helpers -----
    def log_creation(
        self, entity_type: str, entity_id: str, data: Dict[str, Any]
    ) -> None:
        self.event_manager.log_creation(entity_type, entity_id, data)

    def log_update(
        self,
        entity_type: str,
        entity_id: str,
        changes: Dict[str, Any],
        original_data: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.event_manager.log_update(entity_type, entity_id, changes, original_data)

    def log_skip(self, entity_type: str, entity_id: str, reason: str) -> None:
        self.event_manager.log_skip(entity_type, entity_id, reason)

    def log_error(
        self,
        error_type: str,
        entity_type: str,
        entity_id: str,
        error_message: str,
        operation: str = "unknown",
        error_details: Optional[Dict[str, Any]] = None,
        source: str = "sync",
    ) -> None:
        self.event_manager.log_error(
            kind=error_type,
            entity=entity_type,
            entity_id=entity_id,
            message=error_message,
            operation=operation,
            details=error_details,
            source=source,
        )
