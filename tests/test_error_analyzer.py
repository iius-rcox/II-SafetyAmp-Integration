"""
Unit tests for the Error Analyzer service.

Tests cover:
- Pattern detection for common sync errors
- Suggestion generation with actionable recommendations
- Error categorization and severity assignment
- Aggregating errors from multiple sources
"""

import pytest
import json
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock, patch


class TestErrorAnalyzer:
    """Tests for ErrorAnalyzer class."""

    @pytest.fixture
    def mock_event_manager(self):
        """Create a mock event manager."""
        event_manager = MagicMock()
        event_manager.error_notifier.errors = []
        return event_manager

    @pytest.fixture
    def mock_failed_sync_tracker(self):
        """Create a mock failed sync tracker."""
        tracker = MagicMock()
        tracker.data_manager.get_all_failed_records.return_value = []
        return tracker

    @pytest.fixture
    def analyzer(self, mock_event_manager, mock_failed_sync_tracker):
        """Create an ErrorAnalyzer with mocked dependencies."""
        from services.error_analyzer import ErrorAnalyzer

        analyzer = ErrorAnalyzer(
            event_manager=mock_event_manager,
            failed_sync_tracker=mock_failed_sync_tracker,
        )
        return analyzer

    def test_analyze_returns_suggestions_list(self, analyzer):
        """analyze should return a list of suggestions."""
        suggestions = analyzer.analyze()

        assert isinstance(suggestions, list)

    def test_detect_duplicate_email_pattern(self, analyzer, mock_event_manager):
        """Should detect duplicate email errors and generate suggestion."""
        now = datetime.now(timezone.utc)
        mock_event_manager.error_notifier.errors = [
            {
                "timestamp": (now - timedelta(minutes=10)).isoformat(),
                "error_type": "api_error",
                "entity_type": "employee",
                "entity_id": "12345",
                "error_message": "The email has already been taken.",
                "error_details": {"field": "email", "value": "john.doe@example.com"},
            },
            {
                "timestamp": (now - timedelta(minutes=5)).isoformat(),
                "error_type": "api_error",
                "entity_type": "employee",
                "entity_id": "12345",
                "error_message": "The email has already been taken.",
                "error_details": {"field": "email", "value": "john.doe@example.com"},
            },
        ]

        suggestions = analyzer.analyze()

        # Should have at least one suggestion about duplicate email
        duplicate_suggestions = [
            s for s in suggestions if s["category"] == "duplicate_field"
        ]
        assert len(duplicate_suggestions) >= 1
        assert duplicate_suggestions[0]["severity"] in ["high", "medium"]
        assert "email" in duplicate_suggestions[0]["title"].lower()

    def test_detect_duplicate_phone_pattern(self, analyzer, mock_event_manager):
        """Should detect duplicate phone errors."""
        now = datetime.now(timezone.utc)
        mock_event_manager.error_notifier.errors = [
            {
                "timestamp": now.isoformat(),
                "error_type": "api_error",
                "entity_type": "employee",
                "entity_id": "12345",
                "error_message": "The mobile phone has already been taken.",
                "error_details": {"field": "mobile_phone", "value": "+15551234567"},
            }
        ]

        suggestions = analyzer.analyze()

        phone_suggestions = [s for s in suggestions if "phone" in s["title"].lower()]
        assert len(phone_suggestions) >= 1

    def test_detect_validation_error_pattern(self, analyzer, mock_event_manager):
        """Should detect validation errors."""
        now = datetime.now(timezone.utc)
        mock_event_manager.error_notifier.errors = [
            {
                "timestamp": now.isoformat(),
                "error_type": "validation_error",
                "entity_type": "employee",
                "entity_id": "12345",
                "error_message": "Invalid email format: not-an-email",
                "error_details": {"field": "email"},
            }
        ]

        suggestions = analyzer.analyze()

        validation_suggestions = [
            s for s in suggestions if s["category"] == "validation"
        ]
        assert len(validation_suggestions) >= 1

    def test_detect_rate_limit_pattern(self, analyzer, mock_event_manager):
        """Should detect rate limit errors."""
        now = datetime.now(timezone.utc)
        mock_event_manager.error_notifier.errors = [
            {
                "timestamp": now.isoformat(),
                "error_type": "api_error",
                "entity_type": "system",
                "entity_id": "safetyamp",
                "error_message": "Rate limit exceeded. Too many requests.",
                "error_details": {"status_code": 429},
            }
            for _ in range(5)  # Multiple rate limit errors
        ]

        suggestions = analyzer.analyze()

        rate_limit_suggestions = [
            s for s in suggestions if s["category"] == "rate_limit"
        ]
        assert len(rate_limit_suggestions) >= 1
        assert rate_limit_suggestions[0]["severity"] == "high"

    def test_detect_connectivity_pattern(self, analyzer, mock_event_manager):
        """Should detect connectivity/timeout errors."""
        now = datetime.now(timezone.utc)
        mock_event_manager.error_notifier.errors = [
            {
                "timestamp": now.isoformat(),
                "error_type": "connection_error",
                "entity_type": "system",
                "entity_id": "safetyamp",
                "error_message": "Connection timeout after 30 seconds",
                "error_details": {},
            }
        ]

        suggestions = analyzer.analyze()

        connectivity_suggestions = [
            s for s in suggestions if s["category"] == "connectivity"
        ]
        assert len(connectivity_suggestions) >= 1

    def test_detect_missing_required_field(self, analyzer, mock_event_manager):
        """Should detect missing required field errors."""
        now = datetime.now(timezone.utc)
        mock_event_manager.error_notifier.errors = [
            {
                "timestamp": now.isoformat(),
                "error_type": "validation_error",
                "entity_type": "employee",
                "entity_id": "12345",
                "error_message": "Missing required field: Last name",
                "error_details": {"field": "last_name"},
            }
        ]

        suggestions = analyzer.analyze()

        missing_field_suggestions = [
            s for s in suggestions if s["category"] == "missing_field"
        ]
        assert len(missing_field_suggestions) >= 1

    def test_suggestion_includes_affected_records(self, analyzer, mock_event_manager):
        """Suggestions should include list of affected record IDs."""
        now = datetime.now(timezone.utc)
        mock_event_manager.error_notifier.errors = [
            {
                "timestamp": now.isoformat(),
                "error_type": "api_error",
                "entity_type": "employee",
                "entity_id": "12345",
                "error_message": "The email has already been taken.",
                "error_details": {},
            },
            {
                "timestamp": now.isoformat(),
                "error_type": "api_error",
                "entity_type": "employee",
                "entity_id": "67890",
                "error_message": "The email has already been taken.",
                "error_details": {},
            },
        ]

        suggestions = analyzer.analyze()

        # At least one suggestion should have affected records
        suggestions_with_records = [
            s for s in suggestions if len(s.get("affected_records", [])) > 0
        ]
        assert len(suggestions_with_records) >= 1

    def test_suggestion_includes_occurrence_count(self, analyzer, mock_event_manager):
        """Suggestions should include occurrence count."""
        now = datetime.now(timezone.utc)
        mock_event_manager.error_notifier.errors = [
            {
                "timestamp": (now - timedelta(minutes=i)).isoformat(),
                "error_type": "api_error",
                "entity_type": "employee",
                "entity_id": "12345",
                "error_message": "The email has already been taken.",
                "error_details": {},
            }
            for i in range(5)
        ]

        suggestions = analyzer.analyze()

        if suggestions:
            assert "occurrence_count" in suggestions[0]
            assert suggestions[0]["occurrence_count"] >= 1

    def test_suggestion_includes_first_seen_timestamp(
        self, analyzer, mock_event_manager
    ):
        """Suggestions should include when error was first seen."""
        now = datetime.now(timezone.utc)
        first_time = now - timedelta(hours=2)
        mock_event_manager.error_notifier.errors = [
            {
                "timestamp": first_time.isoformat(),
                "error_type": "api_error",
                "entity_type": "employee",
                "entity_id": "12345",
                "error_message": "The email has already been taken.",
                "error_details": {},
            },
            {
                "timestamp": now.isoformat(),
                "error_type": "api_error",
                "entity_type": "employee",
                "entity_id": "12345",
                "error_message": "The email has already been taken.",
                "error_details": {},
            },
        ]

        suggestions = analyzer.analyze()

        if suggestions:
            assert "first_seen" in suggestions[0]

    def test_suggestion_includes_recommended_action(self, analyzer, mock_event_manager):
        """Suggestions should include recommended action."""
        now = datetime.now(timezone.utc)
        mock_event_manager.error_notifier.errors = [
            {
                "timestamp": now.isoformat(),
                "error_type": "api_error",
                "entity_type": "employee",
                "entity_id": "12345",
                "error_message": "The email has already been taken.",
                "error_details": {},
            }
        ]

        suggestions = analyzer.analyze()

        if suggestions:
            assert "recommended_action" in suggestions[0]
            assert len(suggestions[0]["recommended_action"]) > 0

    def test_severity_high_for_repeated_errors(self, analyzer, mock_event_manager):
        """Errors occurring many times should have high severity."""
        now = datetime.now(timezone.utc)
        # Many repeated errors for same entity
        mock_event_manager.error_notifier.errors = [
            {
                "timestamp": (now - timedelta(minutes=i)).isoformat(),
                "error_type": "api_error",
                "entity_type": "employee",
                "entity_id": "12345",
                "error_message": "The email has already been taken.",
                "error_details": {},
            }
            for i in range(10)
        ]

        suggestions = analyzer.analyze()

        high_severity = [s for s in suggestions if s["severity"] == "high"]
        assert len(high_severity) >= 1

    def test_severity_low_for_single_occurrence(self, analyzer, mock_event_manager):
        """Single occurrence errors should have low or medium severity."""
        now = datetime.now(timezone.utc)
        mock_event_manager.error_notifier.errors = [
            {
                "timestamp": now.isoformat(),
                "error_type": "api_error",
                "entity_type": "employee",
                "entity_id": "12345",
                "error_message": "Some random error",
                "error_details": {},
            }
        ]

        suggestions = analyzer.analyze()

        if suggestions:
            assert suggestions[0]["severity"] in ["low", "medium"]

    def test_no_suggestions_when_no_errors(self, analyzer, mock_event_manager):
        """Should return empty list when no errors exist."""
        mock_event_manager.error_notifier.errors = []

        suggestions = analyzer.analyze()

        assert suggestions == []

    def test_integrates_with_failed_sync_tracker(
        self, analyzer, mock_event_manager, mock_failed_sync_tracker
    ):
        """Should also analyze errors from failed sync tracker."""
        mock_event_manager.error_notifier.errors = []
        mock_failed_sync_tracker.data_manager.get_all_failed_records.return_value = [
            {
                "entity_id": "12345",
                "entity_type": "employee",
                "failure_reason": "duplicate_fields",
                "failed_fields": {
                    "email": {"error": "The email has already been taken."}
                },
                "first_failed_at": datetime.now(timezone.utc).isoformat(),
                "attempt_count": 5,
            }
        ]

        suggestions = analyzer.analyze()

        # Should have suggestions from failed sync tracker data
        assert len(suggestions) >= 1

    def test_suggestion_has_unique_id(self, analyzer, mock_event_manager):
        """Each suggestion should have a unique ID."""
        now = datetime.now(timezone.utc)
        mock_event_manager.error_notifier.errors = [
            {
                "timestamp": now.isoformat(),
                "error_type": "api_error",
                "entity_type": "employee",
                "entity_id": "12345",
                "error_message": "The email has already been taken.",
                "error_details": {},
            },
            {
                "timestamp": now.isoformat(),
                "error_type": "api_error",
                "entity_type": "employee",
                "entity_id": "67890",
                "error_message": "Rate limit exceeded",
                "error_details": {},
            },
        ]

        suggestions = analyzer.analyze()

        if len(suggestions) >= 2:
            ids = [s["id"] for s in suggestions]
            assert len(ids) == len(set(ids))  # All IDs are unique


class TestErrorAnalyzerPatternMatching:
    """Tests for specific pattern matching logic."""

    @pytest.fixture
    def analyzer(self):
        """Create analyzer with minimal mocks."""
        from services.error_analyzer import ErrorAnalyzer

        mock_event_manager = MagicMock()
        mock_event_manager.error_notifier.errors = []
        mock_tracker = MagicMock()
        mock_tracker.data_manager.get_all_failed_records.return_value = []

        return ErrorAnalyzer(
            event_manager=mock_event_manager,
            failed_sync_tracker=mock_tracker,
        )

    def test_categorize_duplicate_error(self, analyzer):
        """Should categorize duplicate field errors correctly."""
        category = analyzer._categorize_error(
            "The email has already been taken.", "api_error"
        )
        assert category == "duplicate_field"

    def test_categorize_rate_limit_error(self, analyzer):
        """Should categorize rate limit errors correctly."""
        category = analyzer._categorize_error(
            "Rate limit exceeded. Too many requests.", "api_error"
        )
        assert category == "rate_limit"

        category2 = analyzer._categorize_error("429 Too Many Requests", "api_error")
        assert category2 == "rate_limit"

    def test_categorize_validation_error(self, analyzer):
        """Should categorize validation errors correctly."""
        category = analyzer._categorize_error(
            "Invalid email format", "validation_error"
        )
        assert category == "validation"

    def test_categorize_missing_field_error(self, analyzer):
        """Should categorize missing field errors correctly."""
        category = analyzer._categorize_error(
            "Missing required field: Last name", "validation_error"
        )
        assert category == "missing_field"

    def test_categorize_connectivity_error(self, analyzer):
        """Should categorize connectivity errors correctly."""
        category = analyzer._categorize_error(
            "Connection timeout after 30 seconds", "connection_error"
        )
        assert category == "connectivity"

        category2 = analyzer._categorize_error(
            "Failed to connect to host", "connection_error"
        )
        assert category2 == "connectivity"

    def test_extract_field_from_error(self, analyzer):
        """Should extract field name from error message."""
        field = analyzer._extract_field("The email has already been taken.")
        assert field == "email"

        field2 = analyzer._extract_field("The mobile phone has already been taken.")
        assert field2 == "mobile_phone"

    def test_calculate_severity(self, analyzer):
        """Should calculate severity based on occurrence count."""
        assert analyzer._calculate_severity(1, "duplicate_field") == "low"
        assert analyzer._calculate_severity(5, "duplicate_field") == "medium"
        assert analyzer._calculate_severity(10, "duplicate_field") == "high"

        # Rate limit should be high severity regardless of count
        assert analyzer._calculate_severity(1, "rate_limit") == "high"


class TestErrorAnalyzerTimeFiltering:
    """Tests for time-based error filtering."""

    @pytest.fixture
    def analyzer(self):
        """Create analyzer with minimal mocks."""
        from services.error_analyzer import ErrorAnalyzer

        mock_event_manager = MagicMock()
        mock_event_manager.error_notifier.errors = []
        mock_tracker = MagicMock()
        mock_tracker.data_manager.get_all_failed_records.return_value = []

        return ErrorAnalyzer(
            event_manager=mock_event_manager,
            failed_sync_tracker=mock_tracker,
        )

    def test_analyze_with_hours_filter(self, analyzer):
        """Should filter errors by time window."""
        now = datetime.now(timezone.utc)
        old_error = {
            "timestamp": (now - timedelta(hours=48)).isoformat(),
            "error_type": "api_error",
            "entity_type": "employee",
            "entity_id": "12345",
            "error_message": "Old error",
            "error_details": {},
        }
        recent_error = {
            "timestamp": (now - timedelta(hours=1)).isoformat(),
            "error_type": "api_error",
            "entity_type": "employee",
            "entity_id": "67890",
            "error_message": "The email has already been taken.",
            "error_details": {},
        }

        analyzer.event_manager.error_notifier.errors = [old_error, recent_error]

        # Analyze only last 24 hours
        suggestions = analyzer.analyze(hours=24)

        # Should only include recent error in suggestions
        all_affected = []
        for s in suggestions:
            all_affected.extend(s.get("affected_records", []))

        assert "12345" not in all_affected


class TestErrorAnalyzerSuggestionFormat:
    """Tests for suggestion output format."""

    @pytest.fixture
    def analyzer(self):
        """Create analyzer with minimal mocks."""
        from services.error_analyzer import ErrorAnalyzer

        mock_event_manager = MagicMock()
        mock_event_manager.error_notifier.errors = []
        mock_tracker = MagicMock()
        mock_tracker.data_manager.get_all_failed_records.return_value = []

        return ErrorAnalyzer(
            event_manager=mock_event_manager,
            failed_sync_tracker=mock_tracker,
        )

    def test_suggestion_has_required_fields(self, analyzer):
        """Each suggestion should have all required fields."""
        now = datetime.now(timezone.utc)
        analyzer.event_manager.error_notifier.errors = [
            {
                "timestamp": now.isoformat(),
                "error_type": "api_error",
                "entity_type": "employee",
                "entity_id": "12345",
                "error_message": "The email has already been taken.",
                "error_details": {},
            }
        ]

        suggestions = analyzer.analyze()

        required_fields = [
            "id",
            "severity",
            "category",
            "title",
            "description",
            "affected_records",
            "recommended_action",
            "first_seen",
            "occurrence_count",
        ]

        for suggestion in suggestions:
            for field in required_fields:
                assert field in suggestion, f"Missing field: {field}"

    def test_suggestion_severity_is_valid(self, analyzer):
        """Severity should be one of high, medium, low."""
        now = datetime.now(timezone.utc)
        analyzer.event_manager.error_notifier.errors = [
            {
                "timestamp": now.isoformat(),
                "error_type": "api_error",
                "entity_type": "employee",
                "entity_id": "12345",
                "error_message": "The email has already been taken.",
                "error_details": {},
            }
        ]

        suggestions = analyzer.analyze()

        for suggestion in suggestions:
            assert suggestion["severity"] in ["high", "medium", "low"]

    def test_suggestion_category_is_valid(self, analyzer):
        """Category should be one of the defined categories."""
        now = datetime.now(timezone.utc)
        analyzer.event_manager.error_notifier.errors = [
            {
                "timestamp": now.isoformat(),
                "error_type": "api_error",
                "entity_type": "employee",
                "entity_id": "12345",
                "error_message": "The email has already been taken.",
                "error_details": {},
            }
        ]

        suggestions = analyzer.analyze()

        valid_categories = [
            "duplicate_field",
            "missing_field",
            "rate_limit",
            "validation",
            "connectivity",
            "unknown",
        ]

        for suggestion in suggestions:
            assert suggestion["category"] in valid_categories
