"""
Unit tests for the DataValidator class.

Tests cover phone normalization, email validation, gender normalization,
date formatting, and entity validation (employee, vehicle, site).
"""

import pytest
from datetime import datetime, date
from utils.data_validator import DataValidator, validator


class TestPhoneNormalization:
    """Tests for phone number cleaning and E.164 normalization."""

    def test_clean_phone_10_digit_us(self):
        """10-digit numbers should be prefixed with +1 (US)."""
        v = DataValidator()
        assert v.clean_phone("5551234567") == "+15551234567"
        assert v.clean_phone("555-123-4567") == "+15551234567"
        assert v.clean_phone("(555) 123-4567") == "+15551234567"
        assert v.clean_phone("555.123.4567") == "+15551234567"

    def test_clean_phone_11_digit_with_country_code(self):
        """11-digit numbers starting with 1 should get + prefix."""
        v = DataValidator()
        assert v.clean_phone("15551234567") == "+15551234567"
        assert v.clean_phone("1-555-123-4567") == "+15551234567"

    def test_clean_phone_already_e164(self):
        """Numbers already in E.164 format should be preserved."""
        v = DataValidator()
        assert v.clean_phone("+15551234567") == "+15551234567"
        assert v.clean_phone("+442071234567") == "+442071234567"

    def test_clean_phone_international(self):
        """International numbers (11-15 digits) should get + prefix."""
        v = DataValidator()
        # UK number (12 digits)
        assert v.clean_phone("442071234567") == "+442071234567"
        # 10-digit numbers default to US +1 (design decision)
        # German number would need explicit + prefix to be recognized
        assert v.clean_phone("+4930123456") == "+4930123456"

    def test_clean_phone_invalid_formats(self):
        """Invalid phone formats should return None."""
        v = DataValidator()
        assert v.clean_phone("") is None
        assert v.clean_phone(None) is None
        assert v.clean_phone("123") is None  # Too short
        assert v.clean_phone("12345678901234567890") is None  # Too long
        assert (
            v.clean_phone("abcdefghij") is None
        )  # Non-numeric (becomes empty after stripping)

    def test_clean_phone_ten_digits_with_leading_zero(self):
        """10-digit numbers with leading zero still get +1 prefix (US assumption)."""
        v = DataValidator()
        # Implementation treats all 10-digit as US - this is documented behavior
        result = v.clean_phone("0123456789")
        assert result == "+10123456789"  # Not ideal but matches implementation


class TestEmailValidation:
    """Tests for email format validation."""

    def test_validate_email_valid(self):
        """Valid email formats should pass."""
        v = DataValidator()
        assert v._validate_email("user@example.com") is True
        assert v._validate_email("user.name@example.com") is True
        assert v._validate_email("user+tag@example.co.uk") is True
        assert v._validate_email("user123@sub.example.org") is True

    def test_validate_email_invalid(self):
        """Invalid email formats should fail."""
        v = DataValidator()
        assert v._validate_email("") is False
        assert v._validate_email(None) is False
        assert v._validate_email("not-an-email") is False
        assert v._validate_email("missing@domain") is False
        assert v._validate_email("@nodomain.com") is False
        assert v._validate_email("spaces in@email.com") is False

    def test_clean_email_removes_spaces(self):
        """Email cleaning should remove internal whitespace."""
        v = DataValidator()
        # Space after @ (like the failed record case)
        assert v._clean_email("user@ gmail.com") == "user@gmail.com"
        # Space before @
        assert v._clean_email("user @gmail.com") == "user@gmail.com"
        # Multiple spaces
        assert v._clean_email("user @ gmail . com") == "user@gmail.com"
        # Leading/trailing spaces
        assert v._clean_email("  user@gmail.com  ") == "user@gmail.com"

    def test_clean_email_lowercases(self):
        """Email cleaning should convert to lowercase."""
        v = DataValidator()
        assert v._clean_email("User@GMAIL.COM") == "user@gmail.com"
        assert v._clean_email("USER@Example.Com") == "user@example.com"

    def test_clean_email_returns_none_for_invalid(self):
        """Email cleaning should return None for unfixable emails."""
        v = DataValidator()
        assert v._clean_email("") is None
        assert v._clean_email(None) is None
        assert v._clean_email("not-an-email") is None
        assert v._clean_email("@nodomain.com") is None


class TestGenderNormalization:
    """Tests for gender value normalization."""

    def test_normalize_gender_male(self):
        """Male variants should normalize to 1."""
        v = DataValidator()
        assert v.normalize_gender("M") == 1
        assert v.normalize_gender("m") == 1
        assert v.normalize_gender("male") == 1
        assert v.normalize_gender("Male") == 1
        assert v.normalize_gender("MALE") == 1
        assert v.normalize_gender("1") == 1
        assert v.normalize_gender(1) == 1

    def test_normalize_gender_female(self):
        """Female variants should normalize to 0."""
        v = DataValidator()
        assert v.normalize_gender("F") == 0
        assert v.normalize_gender("f") == 0
        assert v.normalize_gender("female") == 0
        assert v.normalize_gender("Female") == 0
        assert v.normalize_gender("0") == 0
        assert v.normalize_gender("2") == 0

    def test_normalize_gender_invalid(self):
        """Invalid or unknown values should return None."""
        v = DataValidator()
        assert v.normalize_gender(None) is None
        assert v.normalize_gender("") is None
        assert v.normalize_gender("unknown") is None
        assert v.normalize_gender("X") is None
        assert v.normalize_gender("other") is None


class TestDateFormatting:
    """Tests for date formatting to ISO format."""

    def test_format_date_datetime_object(self):
        """datetime objects should format to YYYY-MM-DD."""
        v = DataValidator()
        dt = datetime(2023, 6, 15, 10, 30, 0)
        assert v.format_date(dt) == "2023-06-15"

    def test_format_date_date_object(self):
        """date objects should format to YYYY-MM-DD."""
        v = DataValidator()
        d = date(2023, 6, 15)
        assert v.format_date(d) == "2023-06-15"

    def test_format_date_string(self):
        """String dates should parse and format correctly."""
        v = DataValidator()
        assert v.format_date("2023-06-15") == "2023-06-15"
        assert v.format_date("2023-06-15 10:30:00") == "2023-06-15"

    def test_format_date_invalid(self):
        """Invalid dates should return None."""
        v = DataValidator()
        assert v.format_date(None) is None
        assert v.format_date("") is None
        assert v.format_date("not-a-date") is None
        assert v.format_date("06/15/2023") is None  # Wrong format


class TestVINValidation:
    """Tests for VIN (Vehicle Identification Number) validation."""

    def test_validate_vin_valid(self):
        """Valid 17-character alphanumeric VINs should pass."""
        v = DataValidator()
        assert v._validate_vin("1HGBH41JXMN109186") is True
        assert v._validate_vin("WVWZZZ3CZWE123456") is True
        assert v._validate_vin("12345678901234567") is True  # All numeric

    def test_validate_vin_invalid(self):
        """Invalid VINs should fail."""
        v = DataValidator()
        assert v._validate_vin("") is False
        assert v._validate_vin(None) is False
        assert v._validate_vin("1HGBH41J") is False  # Too short
        assert v._validate_vin("1HGBH41JXMN1091867890") is False  # Too long
        assert v._validate_vin("1HGBH41J-MN10918") is False  # Contains hyphen


class TestEmployeeValidation:
    """Tests for employee data validation."""

    def test_validate_employee_valid(self, sample_viewpoint_employee):
        """Valid employee data should pass validation."""
        v = DataValidator()
        payload = {
            "first_name": "John",
            "last_name": "Doe",
            "email": "john.doe@example.com",
            "mobile_phone": "5551234567",
            "gender": "M",
        }
        is_valid, errors, cleaned = v.validate_employee_data(
            payload, "12345", "John Doe"
        )

        assert is_valid is True
        assert errors == []
        assert cleaned["first_name"] == "John"
        assert cleaned["last_name"] == "Doe"
        assert cleaned["email"] == "john.doe@example.com"
        assert cleaned["mobile_phone"] == "+15551234567"
        assert cleaned["gender"] == 1

    def test_validate_employee_missing_required(self):
        """Missing required fields should fail validation."""
        v = DataValidator()
        payload = {
            "first_name": "John",
            # Missing last_name and email
        }
        is_valid, errors, cleaned = v.validate_employee_data(payload, "12345", "John")

        assert is_valid is False
        assert len(errors) == 2
        assert "Missing required field: Last name" in errors
        assert "Missing required field: Email address" in errors

    def test_validate_employee_invalid_email_removed(self):
        """Invalid email should be removed from payload."""
        v = DataValidator()
        payload = {"first_name": "John", "last_name": "Doe", "email": "not-valid-email"}
        is_valid, errors, cleaned = v.validate_employee_data(
            payload, "12345", "John Doe"
        )

        # Invalid email makes it invalid AND removes email from cleaned payload
        assert is_valid is False
        assert "Invalid email format: not-valid-email" in errors
        assert "email" not in cleaned

    def test_validate_employee_email_with_space_cleaned(self):
        """Email with internal spaces should be cleaned and kept."""
        v = DataValidator()
        # This is the exact case from the failed record: "saldivarana2017@ gmail.com"
        payload = {
            "first_name": "John",
            "last_name": "Doe",
            "email": "saldivarana2017@ gmail.com",
        }
        is_valid, errors, cleaned = v.validate_employee_data(
            payload, "219268", "John Doe"
        )

        # Email should be cleaned (space removed) and kept
        assert is_valid is True
        assert len(errors) == 0
        assert cleaned.get("email") == "saldivarana2017@gmail.com"

    def test_validate_employee_invalid_phone_removed(self):
        """Invalid phone should be removed from payload."""
        v = DataValidator()
        payload = {
            "first_name": "John",
            "last_name": "Doe",
            "email": "john@example.com",
            "mobile_phone": "123",  # Too short
        }
        is_valid, errors, cleaned = v.validate_employee_data(
            payload, "12345", "John Doe"
        )

        assert is_valid is True
        assert "mobile_phone" not in cleaned

    def test_validate_employee_strips_whitespace(self):
        """String fields should have whitespace trimmed."""
        v = DataValidator()
        payload = {
            "first_name": "  John  ",
            "last_name": "  Doe  ",
            "email": "john@example.com",
            "city": "  Houston  ",
        }
        is_valid, errors, cleaned = v.validate_employee_data(
            payload, "12345", "John Doe"
        )

        assert cleaned["first_name"] == "John"
        assert cleaned["last_name"] == "Doe"
        assert cleaned["city"] == "Houston"

    def test_validate_employee_removes_none_values(self):
        """None values should be removed from cleaned payload."""
        v = DataValidator()
        payload = {
            "first_name": "John",
            "last_name": "Doe",
            "email": "john@example.com",
            "middle_name": None,
            "street": None,
        }
        is_valid, errors, cleaned = v.validate_employee_data(
            payload, "12345", "John Doe"
        )

        assert "middle_name" not in cleaned
        assert "street" not in cleaned


class TestVehicleValidation:
    """Tests for vehicle data validation."""

    def test_validate_vehicle_valid(self, sample_samsara_vehicle):
        """Valid vehicle data should pass validation."""
        v = DataValidator()
        payload = {
            "name": "Truck 42",
            "code": "T42",
            "site_id": 100,
            "vin": "1HGBH41JXMN109186",
        }
        is_valid, errors, cleaned = v.validate_vehicle_data(payload, "vehicle-123")

        assert is_valid is True
        assert errors == []
        assert cleaned["name"] == "Truck 42"
        assert cleaned["vin"] == "1HGBH41JXMN109186"

    def test_validate_vehicle_missing_required_generates_defaults(self):
        """Missing required fields should generate defaults."""
        v = DataValidator()
        payload = {
            "site_id": 100
            # Missing name and code
        }
        is_valid, errors, cleaned = v.validate_vehicle_data(payload, "vehicle-1234")

        assert is_valid is False
        assert len(errors) >= 2
        # Defaults should be generated
        assert cleaned["name"] == "Vehicle_1234"
        assert cleaned["code"] == "V_1234"

    def test_validate_vehicle_invalid_vin_removed(self):
        """Invalid VIN should be removed from payload."""
        v = DataValidator()
        payload = {"name": "Truck 42", "code": "T42", "site_id": 100, "vin": "INVALID"}
        is_valid, errors, cleaned = v.validate_vehicle_data(payload, "vehicle-123")

        assert is_valid is True
        assert "vin" not in cleaned


class TestSiteValidation:
    """Tests for site data validation."""

    def test_validate_site_valid(self):
        """Valid site data should pass validation."""
        v = DataValidator()
        payload = {"name": "Main Office", "external_code": "MAIN-001"}
        is_valid, errors, cleaned = v.validate_site_data(payload, "site-123")

        assert is_valid is True
        assert errors == []
        assert cleaned["name"] == "Main Office"

    def test_validate_site_missing_required_generates_defaults(self):
        """Missing required fields should generate defaults."""
        v = DataValidator()
        payload = {}
        is_valid, errors, cleaned = v.validate_site_data(payload, "site-1234")

        assert is_valid is False
        assert len(errors) == 2
        assert cleaned["name"] == "Site_1234"
        assert cleaned["external_code"] == "SITE_1234"


class TestBulkValidation:
    """Tests for bulk data validation."""

    def test_validate_bulk_employees(self):
        """Bulk employee validation should separate valid/invalid."""
        v = DataValidator()
        records = [
            {"first_name": "John", "last_name": "Doe", "email": "john@example.com"},
            {"first_name": "Jane"},  # Missing required fields
            {"first_name": "Bob", "last_name": "Smith", "email": "bob@example.com"},
        ]

        valid, invalid = v.validate_bulk_data(records, "employee")

        assert len(valid) == 2
        assert len(invalid) == 1
        assert invalid[0]["record"]["first_name"] == "Jane"

    def test_validate_bulk_unknown_type(self):
        """Unknown entity type should be marked invalid."""
        v = DataValidator()
        records = [{"id": "123"}]

        valid, invalid = v.validate_bulk_data(records, "unknown_type")

        assert len(valid) == 0
        assert len(invalid) == 1
        assert "Unknown entity type" in invalid[0]["errors"][0]


class TestHelperMethods:
    """Tests for helper methods."""

    def test_remove_duplicate_entries(self):
        """Duplicate entries should be removed based on key field."""
        v = DataValidator()
        data = [
            {"id": "1", "name": "First"},
            {"id": "2", "name": "Second"},
            {"id": "1", "name": "Duplicate"},
            {"id": "3", "name": "Third"},
        ]

        unique = v.remove_duplicate_entries(data, "id")

        assert len(unique) == 3
        assert unique[0]["name"] == "First"
        assert unique[1]["name"] == "Second"
        assert unique[2]["name"] == "Third"

    def test_remove_duplicates_keeps_items_without_key(self):
        """Items without the key field should be kept."""
        v = DataValidator()
        data = [
            {"id": "1", "name": "First"},
            {"name": "No ID"},
            {"id": "1", "name": "Duplicate"},
        ]

        unique = v.remove_duplicate_entries(data, "id")

        assert len(unique) == 2

    def test_sanitize_string_field(self):
        """String sanitization should trim whitespace."""
        v = DataValidator()
        assert v.sanitize_string_field("  hello  ", "test") == "hello"
        assert v.sanitize_string_field("", "test") is None
        assert v.sanitize_string_field(None, "test") is None
        assert v.sanitize_string_field("   ", "test") is None


class TestGlobalValidatorInstance:
    """Tests for the global validator singleton."""

    def test_global_validator_exists(self):
        """Global validator instance should be available."""
        assert validator is not None
        assert isinstance(validator, DataValidator)

    def test_global_validator_clean_phone(self):
        """Global validator should have working clean_phone method."""
        assert validator.clean_phone("5551234567") == "+15551234567"
