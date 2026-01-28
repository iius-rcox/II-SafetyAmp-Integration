#!/usr/bin/env python3
"""
Data Validation Utility for SafetyAmp Integration

This module provides comprehensive data validation functions to ensure
that all required fields are present and valid before sending data to APIs.
"""

import re
from typing import Dict, List, Tuple, Any, Optional
from datetime import datetime, date
from utils.logger import get_logger

logger = get_logger("data_validator")


class DataValidator:
    """Comprehensive data validation for SafetyAmp integration"""

    def __init__(self):
        # Required fields for different entity types
        self.required_fields = {
            "employee": {
                "first_name": "First name",
                "last_name": "Last name",
                "email": "Email address",
            },
            "vehicle": {
                "name": "Vehicle name",
                "code": "Vehicle code",
                "site_id": "Site id",
            },
            "site": {"name": "Site name", "external_code": "External code"},
        }

        # Field validation patterns
        self.validation_patterns = {
            "email": r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$",
            # E.164 format: optional '+' followed by country code and subscriber number (max 15 digits)
            # We will emit numbers as strict E.164 (with '+').
            "phone": r"^\+?[1-9]\d{1,14}$",
            "zip_code": r"^\d{5}(-\d{4})?$",
            "date": r"^\d{4}-\d{2}-\d{2}$",
        }

        # No default substitution for required employee fields. Records missing
        # required fields must be skipped rather than populated with placeholders.

    def validate_employee_data(
        self, payload: Dict[str, Any], emp_id: str, full_name: str
    ) -> Tuple[bool, List[str], Dict[str, Any]]:
        """
        Validate employee data before sending to SafetyAmp API.

        Args:
            payload: Employee data payload
            emp_id: Employee ID for logging
            full_name: Employee full name for logging

        Returns:
            Tuple of (is_valid, validation_errors, cleaned_payload)
        """
        validation_errors = []
        cleaned_payload = payload.copy()

        # Check required fields
        for field, field_name in self.required_fields["employee"].items():
            value = cleaned_payload.get(field)
            if not value or str(value).strip() == "":
                validation_errors.append(f"Missing required field: {field_name}")
                # Do not attempt to synthesize placeholders or emails; skip upstream

        # Validate email format if present; remove invalid emails to avoid API 422
        email = cleaned_payload.get("email")
        if email:
            if not self._validate_email(email):
                validation_errors.append(f"Invalid email format: {email}")
                cleaned_payload.pop("email", None)

        # Validate phone numbers if present (emit E.164; default to +1 for 10-digit US numbers)
        for phone_field in ["mobile_phone", "work_phone"]:
            phone = cleaned_payload.get(phone_field)
            if phone:
                cleaned_phone = self._clean_phone(phone)
                if cleaned_phone:
                    cleaned_payload[phone_field] = cleaned_phone
                else:
                    logger.warning(
                        f"Invalid phone format for {phone_field}: {phone} - removing field"
                    )
                    cleaned_payload.pop(phone_field, None)

        # Normalize gender to 1 (male), 0 (female), or None. Remove if invalid
        if "gender" in cleaned_payload:
            normalized_gender = self.normalize_gender(cleaned_payload.get("gender"))
            if normalized_gender in (0, 1):
                cleaned_payload["gender"] = normalized_gender
            else:
                cleaned_payload.pop("gender", None)

        # Ensure all string fields are properly trimmed
        string_fields = [
            "first_name",
            "last_name",
            "email",
            "middle_name",
            "street",
            "city",
            "state",
        ]
        for field in string_fields:
            if field in cleaned_payload and cleaned_payload[field]:
                cleaned_payload[field] = str(cleaned_payload[field]).strip()

        # Remove None values to prevent API validation errors
        cleaned_payload = {k: v for k, v in cleaned_payload.items() if v is not None}

        is_valid = len(validation_errors) == 0

        if not is_valid:
            logger.error(
                f"Validation errors for employee {emp_id} ({full_name}): {validation_errors}"
            )

        return is_valid, validation_errors, cleaned_payload

    def validate_vehicle_data(
        self, payload: Dict[str, Any], vehicle_id: str
    ) -> Tuple[bool, List[str], Dict[str, Any]]:
        """
        Validate vehicle data before sending to SafetyAmp API.

        Args:
            payload: Vehicle data payload
            vehicle_id: Vehicle ID for logging

        Returns:
            Tuple of (is_valid, validation_errors, cleaned_payload)
        """
        validation_errors = []
        cleaned_payload = payload.copy()

        # Check required fields
        for field, field_name in self.required_fields["vehicle"].items():
            value = cleaned_payload.get(field)
            if not value or str(value).strip() == "":
                validation_errors.append(f"Missing required field: {field_name}")
                # Generate default values
                if field == "name":
                    cleaned_payload[field] = (
                        f"Vehicle_{vehicle_id[-4:]}"
                        if vehicle_id
                        else "Unknown_Vehicle"
                    )
                elif field == "code":
                    cleaned_payload[field] = (
                        f"V_{vehicle_id[-4:]}" if vehicle_id else "V_UNKNOWN"
                    )

        # Validate VIN if present
        vin = cleaned_payload.get("vin")
        if vin and not self._validate_vin(vin):
            logger.warning(f"Invalid VIN format: {vin} - removing field")
            cleaned_payload.pop("vin", None)

        # Ensure all string fields are properly trimmed
        string_fields = ["name", "code", "model", "description", "vin"]
        for field in string_fields:
            if field in cleaned_payload and cleaned_payload[field]:
                cleaned_payload[field] = str(cleaned_payload[field]).strip()

        # Remove None values
        cleaned_payload = {k: v for k, v in cleaned_payload.items() if v is not None}

        is_valid = len(validation_errors) == 0

        if not is_valid:
            logger.error(
                f"Validation errors for vehicle {vehicle_id}: {validation_errors}"
            )

        return is_valid, validation_errors, cleaned_payload

    def validate_site_data(
        self, payload: Dict[str, Any], site_id: str
    ) -> Tuple[bool, List[str], Dict[str, Any]]:
        """
        Validate site data before sending to SafetyAmp API.

        Args:
            payload: Site data payload
            site_id: Site ID for logging

        Returns:
            Tuple of (is_valid, validation_errors, cleaned_payload)
        """
        validation_errors = []
        cleaned_payload = payload.copy()

        # Check required fields
        for field, field_name in self.required_fields["site"].items():
            value = cleaned_payload.get(field)
            if not value or str(value).strip() == "":
                validation_errors.append(f"Missing required field: {field_name}")
                # Generate default values
                if field == "name":
                    cleaned_payload[field] = (
                        f"Site_{site_id[-4:]}" if site_id else "Unknown_Site"
                    )
                elif field == "external_code":
                    cleaned_payload[field] = (
                        f"SITE_{site_id[-4:]}" if site_id else "SITE_UNKNOWN"
                    )

        # Ensure all string fields are properly trimmed
        string_fields = ["name", "external_code", "address", "city", "state"]
        for field in string_fields:
            if field in cleaned_payload and cleaned_payload[field]:
                cleaned_payload[field] = str(cleaned_payload[field]).strip()

        # Remove None values
        cleaned_payload = {k: v for k, v in cleaned_payload.items() if v is not None}

        is_valid = len(validation_errors) == 0

        if not is_valid:
            logger.error(f"Validation errors for site {site_id}: {validation_errors}")

        return is_valid, validation_errors, cleaned_payload

    def _generate_email(self, first_name: str, last_name: str) -> Optional[str]:
        """Generate email address from first and last name if both provided; else None"""
        if not first_name or not last_name:
            return None
        clean_first = re.sub(r"[^a-zA-Z]", "", first_name.lower())
        clean_last = re.sub(r"[^a-zA-Z]", "", last_name.lower())
        if not clean_first or not clean_last:
            return None
        return f"{clean_first}.{clean_last}@company.com"

    def _validate_email(self, email: str) -> bool:
        """Validate email format"""
        if not email:
            return False
        return bool(re.match(self.validation_patterns["email"], email))

    def _clean_phone(self, phone: str) -> Optional[str]:
        """Clean and normalize phone to E.164. Defaults to +1 for 10-digit US numbers.

        Rules:
        - If input already includes a '+', normalize to '+' + digits and validate E.164
        - If 10 digits, assume US and return '+1' + digits
        - If 11 digits starting with '1', return '+1' + last 10 (or '+<digits>' where digits start with 1)
        - If 11-15 digits and no leading zero, assume missing '+' and prefix '+'
        - Otherwise, return None
        """
        if not phone:
            return None
        raw = str(phone).strip()
        digits = re.sub(r"\D", "", raw)

        e164_pattern = r"^\+[1-9]\d{1,14}$"

        # Already has '+' → rebuild as '+' + digits and validate
        if raw.startswith("+"):
            candidate = f"+{digits}"
            return candidate if re.match(e164_pattern, candidate) else None

        # 10 digits → default to US +1
        if len(digits) == 10:
            return f"+1{digits}"

        # 11 digits starting with country code 1 → add '+'
        if len(digits) == 11 and digits.startswith("1"):
            candidate = f"+{digits}"
            return candidate if re.match(e164_pattern, candidate) else None

        # 11–15 digits without leading zero → treat as full international number missing '+'
        if 11 <= len(digits) <= 15 and digits[0] != "0":
            candidate = f"+{digits}"
            return candidate if re.match(e164_pattern, candidate) else None

        return None

    def _validate_phone(self, phone: str) -> bool:
        """Validate phone number format (E.164)."""
        if not phone:
            return False
        return bool(re.match(self.validation_patterns["phone"], phone))

    def _validate_vin(self, vin: str) -> bool:
        """Validate VIN format (basic validation)"""
        if not vin:
            return False
        # VIN should be 17 characters and contain only alphanumeric characters
        return len(vin) == 17 and vin.isalnum()

    def _validate_zip_code(self, zip_code: str) -> bool:
        """Validate ZIP code format"""
        if not zip_code:
            return False
        return bool(re.match(self.validation_patterns["zip_code"], str(zip_code)))

    def _validate_date(self, date_str: str) -> bool:
        """Validate date format (YYYY-MM-DD)"""
        if not date_str:
            return False
        return bool(re.match(self.validation_patterns["date"], str(date_str)))

    def clean_phone(self, phone: Any) -> Optional[str]:
        """Public helper to clean and validate phone numbers"""
        return self._clean_phone(phone)

    def normalize_gender(self, gender_raw: Any) -> Optional[int]:
        """Normalize gender to 1 (male), 0 (female), or None."""
        if gender_raw is None:
            return None
        gender = str(gender_raw).strip().lower()
        # Accept common variants
        if gender in {"m", "male", "1", "true", "t"}:
            return 1
        if gender in {"f", "female", "0", "2", "false", "f"}:
            return 0
        return None

    def format_date(self, val: Any) -> Optional[str]:
        """Format various date inputs to ISO YYYY-MM-DD string or return None"""
        if not val:
            return None
        if isinstance(val, datetime):
            return val.date().isoformat()
        if isinstance(val, date):
            return val.isoformat()
        try:
            return datetime.strptime(str(val).split()[0], "%Y-%m-%d").date().isoformat()
        except Exception:
            logger.warning(f"Invalid date format: {val}")
            return None

    def sanitize_string_field(self, value: Any, field_name: str) -> Optional[str]:
        """Sanitize string field value"""
        if value is None:
            return None

        sanitized = str(value).strip()
        return sanitized if sanitized else None

    def remove_duplicate_entries(
        self, data_list: List[Dict[str, Any]], key_field: str
    ) -> List[Dict[str, Any]]:
        """Remove duplicate entries based on a key field"""
        seen = set()
        unique_data = []

        for item in data_list:
            key_value = item.get(key_field)
            if key_value and key_value not in seen:
                seen.add(key_value)
                unique_data.append(item)
            elif not key_value:
                # Keep items without key value but log warning
                logger.warning(f"Item without {key_field}: {item}")
                unique_data.append(item)

        removed_count = len(data_list) - len(unique_data)
        if removed_count > 0:
            logger.info(
                f"Removed {removed_count} duplicate entries based on {key_field}"
            )

        return unique_data

    def validate_bulk_data(
        self, data_list: List[Dict[str, Any]], entity_type: str
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """
        Validate bulk data and separate valid from invalid records.

        Args:
            data_list: List of data records to validate
            entity_type: Type of entity being validated ("employee", "vehicle", "site")

        Returns:
            Tuple of (valid_records, invalid_records_with_errors)
        """
        valid_records = []
        invalid_records = []

        for i, record in enumerate(data_list):
            record_id = record.get("id", f"record_{i}")

            if entity_type == "employee":
                full_name = f"{record.get('first_name', '')} {record.get('last_name', '')}".strip()
                is_valid, errors, cleaned_record = self.validate_employee_data(
                    record, record_id, full_name
                )
            elif entity_type == "vehicle":
                is_valid, errors, cleaned_record = self.validate_vehicle_data(
                    record, record_id
                )
            elif entity_type == "site":
                is_valid, errors, cleaned_record = self.validate_site_data(
                    record, record_id
                )
            else:
                logger.error(f"Unknown entity type: {entity_type}")
                invalid_records.append(
                    {
                        "record": record,
                        "errors": [f"Unknown entity type: {entity_type}"],
                    }
                )
                continue

            if is_valid:
                valid_records.append(cleaned_record)
            else:
                invalid_records.append(
                    {
                        "record": record,
                        "errors": errors,
                        "cleaned_record": cleaned_record,
                    }
                )

        logger.info(
            f"Bulk validation complete: {len(valid_records)} valid, {len(invalid_records)} invalid {entity_type} records"
        )

        return valid_records, invalid_records


# Global validator instance
validator = DataValidator()
