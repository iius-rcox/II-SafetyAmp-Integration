from typing import Any, Dict, Optional, Callable
import requests
from utils.logger import get_logger
from utils.data_validator import validator as global_validator
from utils.error_manager import error_manager as global_error_manager
from services.safetyamp_api import SafetyAmpAPI
from services.viewpoint_api import ViewpointAPI


class SyncOperation:
    """Base class for sync operations providing common utilities.

    Features:
    - Standard API clients
    - Unified error/change tracking facade
    - Validation helpers
    - Safe API call wrapper with rich error logging
    - Basic counters and consecutive error guard
    """

    def __init__(
        self,
        sync_type: str,
        entity_type: Optional[str] = None,
        *,
        use_viewpoint: bool = True,
        max_consecutive_errors: int = 10,
    ) -> None:
        self.logger = get_logger(f"sync_{sync_type}")
        self.sync_type = sync_type
        self.entity_type = entity_type or sync_type

        # Shared services
        self.api_client = SafetyAmpAPI()
        self.viewpoint = ViewpointAPI() if use_viewpoint else None

        # Shared managers
        self.error_manager = global_error_manager
        self.validator = global_validator

        # Tracking
        self.counts: Dict[str, int] = {
            "created": 0,
            "updated": 0,
            "skipped": 0,
            "errors": 0,
            "processed": 0,
        }
        self.consecutive_errors = 0
        self.max_consecutive_errors = max_consecutive_errors

    # ----- lifecycle -----
    def start_sync(self) -> None:
        self.error_manager.start_sync(self.sync_type)

    def finish_sync(self) -> Dict[str, Any]:
        return self.error_manager.end_sync()

    # ----- counters -----
    def increment(self, key: str, by: int = 1) -> None:
        if key not in self.counts:
            self.counts[key] = 0
        self.counts[key] += by

    # ----- logging/CT wrappers -----
    def log_creation(self, entity_id: str, data: Dict[str, Any]) -> None:
        self.error_manager.log_creation(self.entity_type, entity_id, data)

    def log_update(
        self,
        entity_id: str,
        changes: Dict[str, Any],
        original_data: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.error_manager.log_update(self.entity_type, entity_id, changes, original_data)

    def log_skip(self, entity_id: str, reason: str) -> None:
        self.error_manager.log_skip(self.entity_type, entity_id, reason)

    def log_error(
        self,
        error_type: str,
        entity_id: str,
        error_message: str,
        *,
        operation: str = "unknown",
        error_details: Optional[Dict[str, Any]] = None,
        source: str = "sync",
    ) -> None:
        self.error_manager.log_error(
            error_type=error_type,
            entity_type=self.entity_type,
            entity_id=entity_id,
            error_message=error_message,
            operation=operation,
            error_details=error_details,
            source=source,
        )

    # ----- validation convenience -----
    def clean_phone(self, phone: Any) -> Optional[str]:
        return self.validator.clean_phone(phone)

    def normalize_gender(self, gender_raw: Any) -> Optional[str]:
        return self.validator.normalize_gender(gender_raw)

    def format_date(self, val: Any) -> Optional[str]:
        return self.validator.format_date(val)

    # ----- safe API call -----
    def safe_call(
        self,
        func: Callable[..., Any],
        *args: Any,
        operation: str,
        entity_id: str,
        error_details: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> Optional[Any]:
        try:
            result = func(*args, **kwargs)
            # Successful call resets consecutive errors
            self.consecutive_errors = 0
            return result
        except requests.HTTPError as http_err:
            self.consecutive_errors += 1
            status = getattr(getattr(http_err, "response", None), "status_code", None)
            details: Dict[str, Any] = {
                "status_code": status,
                "args": args if args else None,
                "kwargs": kwargs if kwargs else None,
            }
            if error_details:
                details.update(error_details)
            try:
                if hasattr(http_err, "response") and http_err.response is not None:
                    details["response_body"] = http_err.response.json()
            except Exception:
                pass

            error_type = "validation_error" if status == 422 else "http_error"
            self.log_error(
                error_type=error_type,
                entity_id=entity_id,
                error_message=f"HTTP error during {operation}: {http_err}",
                operation=operation,
                error_details=details,
                source=f"sync_{operation}",
            )
            self.increment("errors")
            return None
        except Exception as e:
            self.consecutive_errors += 1
            details = {"args": args if args else None, "kwargs": kwargs if kwargs else None}
            if error_details:
                details.update(error_details)
            self.log_error(
                error_type="unexpected_error",
                entity_id=entity_id,
                error_message=f"Unexpected error during {operation}: {e}",
                operation=operation,
                error_details=details,
                source=f"sync_{operation}",
            )
            self.increment("errors")
            return None

    # ----- guard -----
    def should_stop_for_errors(self) -> bool:
        if self.consecutive_errors >= self.max_consecutive_errors:
            self.log_error(
                error_type="safety_stop",
                entity_id="system",
                error_message=f"Stopping sync due to {self.consecutive_errors} consecutive errors",
                operation="safety_stop",
                error_details={
                    "consecutive_errors": self.consecutive_errors,
                    "max_consecutive_errors": self.max_consecutive_errors,
                },
                source="sync_safety",
            )
            return True
        return False