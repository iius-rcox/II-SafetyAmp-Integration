"""
Error Analyzer for monitoring dashboard.

Analyzes sync errors to detect patterns and generate actionable suggestions
for resolving common issues like duplicate fields, validation errors, and rate limits.
"""

import hashlib
import re
from collections import defaultdict
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Tuple

from utils.logger import get_logger

logger = get_logger("error_analyzer")


# Error categories
CATEGORY_DUPLICATE_FIELD = "duplicate_field"
CATEGORY_MISSING_FIELD = "missing_field"
CATEGORY_RATE_LIMIT = "rate_limit"
CATEGORY_VALIDATION = "validation"
CATEGORY_CONNECTIVITY = "connectivity"
CATEGORY_UNKNOWN = "unknown"

# Severity levels
SEVERITY_HIGH = "high"
SEVERITY_MEDIUM = "medium"
SEVERITY_LOW = "low"

# Pattern matchers for error categorization
DUPLICATE_PATTERNS = [
    r"already been taken",
    r"duplicate",
    r"already exists",
    r"unique constraint",
]

RATE_LIMIT_PATTERNS = [
    r"rate limit",
    r"too many requests",
    r"429",
    r"throttl",
]

MISSING_FIELD_PATTERNS = [
    r"missing required",
    r"is required",
    r"cannot be blank",
    r"cannot be null",
]

VALIDATION_PATTERNS = [
    r"invalid",
    r"validation",
    r"format",
    r"must be",
]

CONNECTIVITY_PATTERNS = [
    r"timeout",
    r"connection",
    r"connect",
    r"unreachable",
    r"refused",
]

# Field extraction patterns
FIELD_PATTERNS = [
    (
        r"the\s+([\w\s]+?)\s+has\s+already",
        1,
    ),  # "The email has already..." or "The mobile phone has already..."
    (r"field:\s+(\w+)", 1),  # "Missing required field: last_name"
    (r"(\w+)\s+is\s+required", 1),  # "email is required"
]

# Recommended actions by category
RECOMMENDED_ACTIONS = {
    CATEGORY_DUPLICATE_FIELD: "Update the duplicate field value in Viewpoint/source system or manually resolve the conflict in SafetyAmp",
    CATEGORY_MISSING_FIELD: "Ensure the required field is populated in the source system (Viewpoint)",
    CATEGORY_RATE_LIMIT: "Consider reducing sync frequency or implementing request batching",
    CATEGORY_VALIDATION: "Review and correct the data format in the source system",
    CATEGORY_CONNECTIVITY: "Check network connectivity and service availability",
    CATEGORY_UNKNOWN: "Investigate the error logs for more details",
}


class ErrorAnalyzer:
    """
    Analyzes sync errors and generates actionable suggestions.

    Features:
    - Pattern detection for common error types
    - Severity calculation based on occurrence frequency
    - Aggregation of related errors
    - Integration with event manager and failed sync tracker
    """

    def __init__(
        self,
        event_manager=None,
        failed_sync_tracker=None,
    ):
        """
        Initialize the error analyzer.

        Args:
            event_manager: EventManager instance for accessing error logs
            failed_sync_tracker: FailedSyncTracker instance for failed record data
        """
        self.event_manager = event_manager
        self.failed_sync_tracker = failed_sync_tracker

    def analyze(self, hours: int = 24) -> List[Dict[str, Any]]:
        """
        Analyze recent errors and generate suggestions.

        Args:
            hours: Time window in hours to analyze (default: 24)

        Returns:
            List of suggestion dictionaries
        """
        suggestions = []

        # Get errors from event manager
        errors = self._get_errors_from_event_manager(hours)

        # Get errors from failed sync tracker
        failed_records = self._get_failed_records()

        # Combine and analyze
        error_groups = self._group_errors(errors, failed_records)

        # Generate suggestions for each group
        for group_key, group_data in error_groups.items():
            suggestion = self._generate_suggestion(group_key, group_data)
            if suggestion:
                suggestions.append(suggestion)

        # Sort by severity (high first) then by occurrence count
        severity_order = {SEVERITY_HIGH: 0, SEVERITY_MEDIUM: 1, SEVERITY_LOW: 2}
        suggestions.sort(
            key=lambda s: (
                severity_order.get(s["severity"], 3),
                -s["occurrence_count"],
            )
        )

        return suggestions

    def _get_errors_from_event_manager(self, hours: int) -> List[Dict[str, Any]]:
        """Get errors from the event manager within time window."""
        if not self.event_manager:
            return []

        try:
            errors = self.event_manager.error_notifier.errors
            if not errors:
                return []

            # Filter by time window
            cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
            filtered = []

            for error in errors:
                try:
                    timestamp_str = error.get("timestamp", "")
                    if timestamp_str:
                        timestamp = datetime.fromisoformat(
                            timestamp_str.replace("Z", "+00:00")
                        )
                        if timestamp >= cutoff:
                            filtered.append(error)
                except (ValueError, TypeError):
                    continue

            return filtered

        except Exception as e:
            logger.error(f"Error getting errors from event manager: {e}")
            return []

    def _get_failed_records(self) -> List[Dict[str, Any]]:
        """Get failed records from the failed sync tracker."""
        if not self.failed_sync_tracker:
            return []

        try:
            return self.failed_sync_tracker.data_manager.get_all_failed_records()
        except Exception as e:
            logger.error(f"Error getting failed records: {e}")
            return []

    def _group_errors(
        self,
        errors: List[Dict[str, Any]],
        failed_records: List[Dict[str, Any]],
    ) -> Dict[str, Dict[str, Any]]:
        """
        Group errors by pattern/category for aggregation.

        Returns dict with group key -> group data
        """
        groups: Dict[str, Dict[str, Any]] = defaultdict(
            lambda: {
                "errors": [],
                "affected_records": set(),
                "first_seen": None,
                "last_seen": None,
                "category": None,
                "field": None,
            }
        )

        # Process event manager errors
        for error in errors:
            message = error.get("error_message", "")
            error_type = error.get("error_type", "")
            entity_id = error.get("entity_id", "")
            timestamp_str = error.get("timestamp", "")

            category = self._categorize_error(message, error_type)
            field = self._extract_field(message)

            # Create group key based on category and field
            group_key = f"{category}:{field or 'general'}"

            groups[group_key]["errors"].append(error)
            groups[group_key]["category"] = category
            groups[group_key]["field"] = field

            if entity_id:
                groups[group_key]["affected_records"].add(entity_id)

            # Track timestamps
            try:
                timestamp = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
                if (
                    groups[group_key]["first_seen"] is None
                    or timestamp < groups[group_key]["first_seen"]
                ):
                    groups[group_key]["first_seen"] = timestamp
                if (
                    groups[group_key]["last_seen"] is None
                    or timestamp > groups[group_key]["last_seen"]
                ):
                    groups[group_key]["last_seen"] = timestamp
            except (ValueError, TypeError):
                pass

        # Process failed sync records
        for record in failed_records:
            entity_id = record.get("entity_id", "")
            failure_reason = record.get("failure_reason", "")
            failed_fields = record.get("failed_fields", {})
            first_failed_at = record.get("first_failed_at", "")

            # Map failure reason to category
            category_map = {
                "duplicate_fields": CATEGORY_DUPLICATE_FIELD,
                "missing_required": CATEGORY_MISSING_FIELD,
                "validation_error": CATEGORY_VALIDATION,
            }
            category = category_map.get(failure_reason, CATEGORY_UNKNOWN)

            # Get field from failed_fields
            field = None
            if failed_fields:
                field = list(failed_fields.keys())[0]

            group_key = f"{category}:{field or 'general'}"

            groups[group_key]["category"] = category
            groups[group_key]["field"] = field

            if entity_id:
                groups[group_key]["affected_records"].add(entity_id)

            # Add pseudo-error for counting
            groups[group_key]["errors"].append(record)

            # Track timestamps
            try:
                timestamp = datetime.fromisoformat(
                    first_failed_at.replace("Z", "+00:00")
                )
                if (
                    groups[group_key]["first_seen"] is None
                    or timestamp < groups[group_key]["first_seen"]
                ):
                    groups[group_key]["first_seen"] = timestamp
            except (ValueError, TypeError):
                pass

        return groups

    def _generate_suggestion(
        self, group_key: str, group_data: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Generate a suggestion from a group of errors."""
        if not group_data["errors"]:
            return None

        category = group_data["category"] or CATEGORY_UNKNOWN
        field = group_data["field"]
        occurrence_count = len(group_data["errors"])
        affected_records = list(group_data["affected_records"])

        severity = self._calculate_severity(occurrence_count, category)

        # Generate unique ID for the suggestion
        suggestion_id = self._generate_suggestion_id(group_key, affected_records)

        # Generate title and description
        title = self._generate_title(category, field, occurrence_count)
        description = self._generate_description(
            category, field, occurrence_count, affected_records
        )

        # Get recommended action
        recommended_action = RECOMMENDED_ACTIONS.get(
            category, RECOMMENDED_ACTIONS[CATEGORY_UNKNOWN]
        )

        # Format timestamps
        first_seen = None
        if group_data["first_seen"]:
            first_seen = group_data["first_seen"].isoformat()

        return {
            "id": suggestion_id,
            "severity": severity,
            "category": category,
            "title": title,
            "description": description,
            "affected_records": affected_records[:50],  # Limit to 50 records
            "recommended_action": recommended_action,
            "first_seen": first_seen or datetime.now(timezone.utc).isoformat(),
            "occurrence_count": occurrence_count,
        }

    def _categorize_error(self, message: str, error_type: str) -> str:
        """Categorize an error based on its message and type."""
        message_lower = message.lower()
        error_type_lower = error_type.lower()

        # Check patterns in order of specificity
        for pattern in DUPLICATE_PATTERNS:
            if re.search(pattern, message_lower):
                return CATEGORY_DUPLICATE_FIELD

        for pattern in RATE_LIMIT_PATTERNS:
            if re.search(pattern, message_lower):
                return CATEGORY_RATE_LIMIT

        for pattern in MISSING_FIELD_PATTERNS:
            if re.search(pattern, message_lower):
                return CATEGORY_MISSING_FIELD

        for pattern in CONNECTIVITY_PATTERNS:
            if re.search(pattern, message_lower) or re.search(
                pattern, error_type_lower
            ):
                return CATEGORY_CONNECTIVITY

        for pattern in VALIDATION_PATTERNS:
            if re.search(pattern, message_lower) or "validation" in error_type_lower:
                return CATEGORY_VALIDATION

        return CATEGORY_UNKNOWN

    def _extract_field(self, message: str) -> Optional[str]:
        """Extract field name from error message."""
        message_lower = message.lower()

        for pattern, group_index in FIELD_PATTERNS:
            match = re.search(pattern, message_lower)
            if match:
                return match.group(group_index).replace(" ", "_")

        return None

    def _calculate_severity(self, occurrence_count: int, category: str) -> str:
        """Calculate severity based on occurrence count and category."""
        # Rate limit errors are always high severity
        if category == CATEGORY_RATE_LIMIT:
            return SEVERITY_HIGH

        # Connectivity errors are high severity
        if category == CATEGORY_CONNECTIVITY:
            return SEVERITY_HIGH

        # Duplicate fields with multiple occurrences are at least medium
        if category == CATEGORY_DUPLICATE_FIELD and occurrence_count >= 2:
            return SEVERITY_MEDIUM if occurrence_count < 10 else SEVERITY_HIGH

        # Calculate based on occurrence count
        if occurrence_count >= 10:
            return SEVERITY_HIGH
        elif occurrence_count >= 3:
            return SEVERITY_MEDIUM
        else:
            return SEVERITY_LOW

    def _generate_suggestion_id(
        self, group_key: str, affected_records: List[str]
    ) -> str:
        """Generate a unique ID for a suggestion."""
        # Use hash of group key and first few affected records
        content = f"{group_key}:{','.join(sorted(affected_records[:5]))}"
        hash_val = hashlib.sha256(content.encode()).hexdigest()[:8]
        return f"sug_{hash_val}"

    def _generate_title(self, category: str, field: Optional[str], count: int) -> str:
        """Generate a human-readable title for the suggestion."""
        titles = {
            CATEGORY_DUPLICATE_FIELD: f"Duplicate {field or 'field'} detected",
            CATEGORY_MISSING_FIELD: f"Missing required {field or 'field'}",
            CATEGORY_RATE_LIMIT: "Rate limit exceeded",
            CATEGORY_VALIDATION: f"Validation error for {field or 'field'}",
            CATEGORY_CONNECTIVITY: "Connectivity issues detected",
            CATEGORY_UNKNOWN: "Sync error detected",
        }

        base_title = titles.get(category, titles[CATEGORY_UNKNOWN])

        if count > 1:
            return f"{base_title} ({count} occurrences)"

        return base_title

    def _generate_description(
        self,
        category: str,
        field: Optional[str],
        count: int,
        affected_records: List[str],
    ) -> str:
        """Generate a detailed description for the suggestion."""
        record_count = len(affected_records)

        descriptions = {
            CATEGORY_DUPLICATE_FIELD: (
                f"The {field or 'field'} value is duplicated across {record_count} "
                f"record(s), causing sync failures. This typically happens when the "
                f"same value exists in both the source system and SafetyAmp."
            ),
            CATEGORY_MISSING_FIELD: (
                f"The required field '{field or 'unknown'}' is missing from "
                f"{record_count} record(s) in the source system."
            ),
            CATEGORY_RATE_LIMIT: (
                f"The API rate limit has been exceeded {count} time(s). "
                f"This may slow down sync operations significantly."
            ),
            CATEGORY_VALIDATION: (
                f"Validation errors for {field or 'field'} in {record_count} "
                f"record(s). The data format may not match SafetyAmp requirements."
            ),
            CATEGORY_CONNECTIVITY: (
                f"Network connectivity issues detected with {count} occurrence(s). "
                f"This may indicate network problems or service unavailability."
            ),
            CATEGORY_UNKNOWN: (
                f"An error occurred {count} time(s) affecting {record_count} "
                f"record(s). Review the error logs for more details."
            ),
        }

        return descriptions.get(category, descriptions[CATEGORY_UNKNOWN])


# Global singleton instance
_error_analyzer: Optional[ErrorAnalyzer] = None


def get_error_analyzer() -> Optional[ErrorAnalyzer]:
    """Get the global error analyzer instance."""
    return _error_analyzer


def initialize_error_analyzer(
    event_manager=None,
    failed_sync_tracker=None,
) -> ErrorAnalyzer:
    """
    Initialize the global error analyzer.

    Args:
        event_manager: EventManager instance
        failed_sync_tracker: FailedSyncTracker instance

    Returns:
        The initialized ErrorAnalyzer instance
    """
    global _error_analyzer
    _error_analyzer = ErrorAnalyzer(
        event_manager=event_manager,
        failed_sync_tracker=failed_sync_tracker,
    )
    logger.info("Error analyzer initialized")
    return _error_analyzer
