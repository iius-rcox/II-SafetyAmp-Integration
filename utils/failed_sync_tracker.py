"""Failed sync tracker for intelligent retry logic based on field-level changes."""

import hashlib
import json
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List
from utils.logger import get_logger

logger = get_logger("failed_sync_tracker")


class FailedSyncTracker:
    """
    Tracks failed sync operations and implements change-based retry logic.

    Only retries syncs when the specific problematic fields have changed since
    the last failure, preventing wasted API calls for unchanged data.
    """

    def __init__(self, data_manager, config):
        """
        Initialize tracker with reference to data_manager for Redis operations.

        Args:
            data_manager: DataManager instance for Redis operations
            config: Configuration instance
        """
        self.data_manager = data_manager
        self.config = config
        self.enabled = config.FAILED_SYNC_TRACKER_ENABLED
        self.ttl_days = config.FAILED_SYNC_TTL_DAYS

    def compute_field_hash(self, value: Any) -> str:
        """
        Compute SHA-256 hash of a field value for change detection.

        Args:
            value: Field value to hash (any JSON-serializable type)

        Returns:
            Hexadecimal hash string
        """
        if value is None:
            value = ""

        # Normalize value to string for consistent hashing
        if isinstance(value, (dict, list)):
            normalized = json.dumps(value, sort_keys=True)
        else:
            normalized = str(value).strip()

        return hashlib.sha256(normalized.encode("utf-8")).hexdigest()

    def compute_hash(self, data: Dict[str, Any]) -> str:
        """
        Compute hash of entire payload for full record comparison.

        Args:
            data: Dictionary to hash

        Returns:
            Hexadecimal hash string
        """
        normalized = json.dumps(data, sort_keys=True)
        return hashlib.sha256(normalized.encode("utf-8")).hexdigest()

    def extract_failed_fields_from_error(self, error_response: Any) -> Dict[str, str]:
        """
        Parse SafetyAmp 422 error response to extract field-level errors.

        Example input:
        {
          "message": "The email has already been taken.",
          "errors": {
            "email": ["The email has already been taken."],
            "mobile_phone": ["The mobile phone has already been taken."]
          }
        }

        Args:
            error_response: Error response from SafetyAmp API (dict or JSON string)

        Returns:
            Dictionary mapping field names to error messages
            Example: {"email": "The email has already been taken."}
        """
        failed_fields = {}

        # Handle string responses
        if isinstance(error_response, str):
            try:
                error_response = json.loads(error_response)
            except (json.JSONDecodeError, ValueError):
                logger.warning(
                    f"Could not parse error response as JSON: {error_response}"
                )
                return failed_fields

        if not isinstance(error_response, dict):
            return failed_fields

        # Extract field-level errors from "errors" key
        if "errors" in error_response and isinstance(error_response["errors"], dict):
            for field_name, error_messages in error_response["errors"].items():
                if isinstance(error_messages, list) and error_messages:
                    failed_fields[field_name] = error_messages[0]
                elif isinstance(error_messages, str):
                    failed_fields[field_name] = error_messages

        # If no field-level errors, use general message as fallback
        if not failed_fields and "message" in error_response:
            # Try to infer field from message (e.g., "The email has already been taken.")
            message = error_response["message"]
            for field in ["email", "mobile_phone", "work_phone", "emp_id"]:
                if field.replace("_", " ") in message.lower():
                    failed_fields[field] = message
                    break

            # If no field inferred, use generic error
            if not failed_fields:
                failed_fields["_general"] = message

        return failed_fields

    def should_skip_retry(
        self, entity_id: str, entity_type: str, current_data: Dict[str, Any]
    ) -> bool:
        """
        Determine if a retry should be skipped based on field-level change detection.

        Returns True if the record failed previously and problematic fields are unchanged.
        Returns False if problematic fields have changed or no previous failure exists.

        Args:
            entity_id: Unique identifier for the entity
            entity_type: Type of entity (e.g., "employee", "vehicle")
            current_data: Current payload data to check

        Returns:
            True to skip retry, False to attempt sync
        """
        if not self.enabled:
            return False

        # Get previous failure record
        failure_record = self.data_manager.get_failed_sync_record(
            entity_type, entity_id
        )

        if not failure_record:
            return False  # No previous failure, don't skip

        # Check if any problematic fields have changed
        failed_fields = failure_record.get("failed_fields", {})

        if not failed_fields:
            # No field-level tracking, compare full payload
            current_hash = self.compute_hash(current_data)
            previous_hash = failure_record.get("full_payload_hash", "")

            if current_hash != previous_hash:
                logger.debug(
                    f"Full payload changed for {entity_type} {entity_id}, will retry"
                )
                return False
            else:
                logger.debug(
                    f"Full payload unchanged for {entity_type} {entity_id}, skipping retry"
                )
                return True

        # Field-level comparison
        for field_name, field_info in failed_fields.items():
            current_value = current_data.get(field_name)
            current_hash = self.compute_field_hash(current_value)
            previous_hash = field_info.get("value_hash", "")

            if current_hash != previous_hash:
                logger.debug(
                    f"Field '{field_name}' changed for {entity_type} {entity_id}, will retry"
                )
                return False  # At least one problematic field changed, should retry

        logger.debug(
            f"All problematic fields unchanged for {entity_type} {entity_id}, skipping retry"
        )
        return True  # All problematic fields unchanged, skip retry

    def record_failure(
        self,
        entity_id: str,
        entity_type: str,
        data: Dict[str, Any],
        error_response: Any,
        http_status: int,
        operation: str = "sync",
    ) -> None:
        """
        Record a failed sync operation with field-level error tracking.

        Args:
            entity_id: Unique identifier for the entity
            entity_type: Type of entity (e.g., "employee", "vehicle")
            data: Payload that failed to sync
            error_response: Error response from API
            http_status: HTTP status code of the failure
            operation: Type of operation (create, update, sync)
        """
        if not self.enabled:
            return

        # Extract which fields caused the failure
        failed_fields = self.extract_failed_fields_from_error(error_response)

        # Compute hashes for failed fields
        field_hashes = {}
        for field_name, error_msg in failed_fields.items():
            field_value = data.get(field_name)
            field_hashes[field_name] = {
                "value_hash": self.compute_field_hash(field_value),
                "error": error_msg,
                "value": (
                    str(field_value)[:100] if field_value is not None else None
                ),  # Store truncated value for debugging
            }

        # Get existing record to preserve history
        existing_record = self.data_manager.get_failed_sync_record(
            entity_type, entity_id
        )

        now = datetime.now(timezone.utc).isoformat()

        # Build failure metadata
        failure_metadata = {
            "entity_id": entity_id,
            "entity_type": entity_type,
            "failed_fields": field_hashes,
            "full_payload_hash": self.compute_hash(data),
            "failure_reason": self._categorize_failure(error_response, http_status),
            "first_failed_at": (
                existing_record.get("first_failed_at", now) if existing_record else now
            ),
            "last_failed_at": now,
            "attempt_count": (
                (existing_record.get("attempt_count", 0) + 1) if existing_record else 1
            ),
            "http_status": http_status,
            "operation": operation,
            "last_error_message": str(error_response)[:500],  # Truncate for storage
        }

        # Save to Redis with configured TTL
        success = self.data_manager.save_failed_sync_record(
            entity_type=entity_type,
            entity_id=entity_id,
            metadata=failure_metadata,
            ttl_days=self.ttl_days,
        )

        if success:
            logger.info(
                f"Recorded failure for {entity_type} {entity_id}: "
                f"{len(failed_fields)} field(s), attempt #{failure_metadata['attempt_count']}"
            )
        else:
            logger.warning(f"Failed to record failure for {entity_type} {entity_id}")

    def _categorize_failure(self, error_response: Any, http_status: int) -> str:
        """
        Categorize the type of failure for better tracking.

        Args:
            error_response: Error response from API
            http_status: HTTP status code

        Returns:
            Category string (duplicate_fields, validation_error, missing_required, etc.)
        """
        if http_status != 422:
            return f"http_{http_status}"

        # Parse error response
        if isinstance(error_response, str):
            error_text = error_response.lower()
        elif isinstance(error_response, dict):
            error_text = json.dumps(error_response).lower()
        else:
            error_text = str(error_response).lower()

        # Categorize based on error message patterns
        if "already been taken" in error_text or "duplicate" in error_text:
            return "duplicate_fields"
        elif "required" in error_text or "missing" in error_text:
            return "missing_required"
        elif "invalid" in error_text or "validation" in error_text:
            return "validation_error"
        else:
            return "unknown_422"

    def clear_failure(self, entity_id: str, entity_type: str) -> None:
        """
        Clear a failure record after successful sync.

        Args:
            entity_id: Unique identifier for the entity
            entity_type: Type of entity (e.g., "employee", "vehicle")
        """
        if not self.enabled:
            return

        success = self.data_manager.delete_failed_sync_record(entity_type, entity_id)

        if success:
            logger.debug(f"Cleared failure record for {entity_type} {entity_id}")
        else:
            logger.warning(
                f"Failed to clear failure record for {entity_type} {entity_id}"
            )

    def get_failure_stats(self, entity_type: Optional[str] = None) -> Dict[str, Any]:
        """
        Get statistics about failed sync records.

        Args:
            entity_type: Optional filter by entity type

        Returns:
            Dictionary with stats (total, by_reason, oldest_failure, etc.)
        """
        all_failures = self.data_manager.get_all_failed_records(entity_type=entity_type)

        if not all_failures:
            return {
                "total": 0,
                "by_entity_type": {},
                "by_reason": {},
                "oldest_failure": None,
            }

        by_entity_type = {}
        by_reason = {}
        oldest_timestamp = None

        for failure in all_failures:
            # Count by entity type
            etype = failure.get("entity_type", "unknown")
            by_entity_type[etype] = by_entity_type.get(etype, 0) + 1

            # Count by failure reason
            reason = failure.get("failure_reason", "unknown")
            by_reason[reason] = by_reason.get(reason, 0) + 1

            # Track oldest failure
            first_failed = failure.get("first_failed_at")
            if first_failed:
                if oldest_timestamp is None or first_failed < oldest_timestamp:
                    oldest_timestamp = first_failed

        return {
            "total": len(all_failures),
            "by_entity_type": by_entity_type,
            "by_reason": by_reason,
            "oldest_failure": oldest_timestamp,
        }


# Global singleton instance (will be initialized in main.py with data_manager)
failed_sync_tracker: Optional[FailedSyncTracker] = None


def initialize_tracker(data_manager, config) -> FailedSyncTracker:
    """
    Initialize the global failed sync tracker instance.

    Args:
        data_manager: DataManager instance for Redis operations
        config: Configuration instance

    Returns:
        Initialized FailedSyncTracker instance
    """
    global failed_sync_tracker
    failed_sync_tracker = FailedSyncTracker(data_manager, config)
    enabled_status = "enabled" if config.FAILED_SYNC_TRACKER_ENABLED else "disabled"
    logger.info(
        f"Failed sync tracker initialized ({enabled_status}, TTL: {config.FAILED_SYNC_TTL_DAYS} days)"
    )
    return failed_sync_tracker
