#!/usr/bin/env python3
"""
Data Validation Utility for SafetyAmp Integration

This module provides comprehensive data validation functions to ensure
that all required fields are present and valid before sending data to APIs.
"""

import re
from typing import Dict, List, Tuple, Any, Optional
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
                "email": "Email address"
            },
            "vehicle": {
                "name": "Vehicle name",
                "code": "Vehicle code"
            },
            "site": {
                "name": "Site name",
                "external_code": "External code"
            }
        }
        
        # Field validation patterns
        self.validation_patterns = {
            "email": r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$',
            "phone": r'^\d{10,11}$',
            "zip_code": r'^\d{5}(-\d{4})?$',
            "date": r'^\d{4}-\d{2}-\d{2}$'
        }
        
        # Default values for missing required fields
        self.default_values = {
            "first_name": "Unknown",
            "last_name": "Unknown",
            "email": None,  # Will be generated from name
            "mobile_phone": None,
            "work_phone": None
        }

    def validate_employee_data(self, payload: Dict[str, Any], emp_id: str, full_name: str) -> Tuple[bool, List[str], Dict[str, Any]]:
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
                # Try to generate a default value for missing fields
                if field == "first_name":
                    cleaned_payload[field] = self.default_values["first_name"]
                    logger.warning(f"Generated default first_name '{self.default_values['first_name']}' for employee {emp_id} ({full_name})")
                elif field == "last_name":
                    cleaned_payload[field] = self.default_values["last_name"]
                    logger.warning(f"Generated default last_name '{self.default_values['last_name']}' for employee {emp_id} ({full_name})")
                elif field == "email":
                    # Generate email from name if possible
                    first_name = cleaned_payload.get("first_name", "unknown")
                    last_name = cleaned_payload.get("last_name", "unknown")
                    if first_name != self.default_values["first_name"] and last_name != self.default_values["last_name"]:
                        generated_email = self._generate_email(first_name, last_name)
                        cleaned_payload[field] = generated_email
                        logger.warning(f"Generated email '{generated_email}' for employee {emp_id} ({full_name})")
                    else:
                        validation_errors.append(f"Cannot generate email for employee {emp_id} - missing name data")
        
        # Validate email format if present
        email = cleaned_payload.get("email")
        if email and email != self.default_values["first_name"]:
            if not self._validate_email(email):
                validation_errors.append(f"Invalid email format: {email}")
                # Generate a valid email as fallback
                first_name = cleaned_payload.get("first_name", "unknown")
                last_name = cleaned_payload.get("last_name", "unknown")
                fallback_email = self._generate_email(first_name, last_name)
                cleaned_payload["email"] = fallback_email
                logger.warning(f"Generated fallback email '{fallback_email}' for employee {emp_id} due to invalid email format")
        
        # Validate phone numbers if present
        for phone_field in ["mobile_phone", "work_phone"]:
            phone = cleaned_payload.get(phone_field)
            if phone and phone != self.default_values["first_name"]:
                cleaned_phone = self._clean_phone(phone)
                if cleaned_phone:
                    cleaned_payload[phone_field] = cleaned_phone
                else:
                    logger.warning(f"Invalid phone format for {phone_field}: {phone} - removing field")
                    cleaned_payload.pop(phone_field, None)
        
        # Ensure all string fields are properly trimmed
        string_fields = ["first_name", "last_name", "email", "middle_name", "street", "city", "state"]
        for field in string_fields:
            if field in cleaned_payload and cleaned_payload[field]:
                cleaned_payload[field] = str(cleaned_payload[field]).strip()
        
        # Remove None values to prevent API validation errors
        cleaned_payload = {k: v for k, v in cleaned_payload.items() if v is not None}
        
        is_valid = len(validation_errors) == 0
        
        if not is_valid:
            logger.error(f"Validation errors for employee {emp_id} ({full_name}): {validation_errors}")
        
        return is_valid, validation_errors, cleaned_payload

    def validate_vehicle_data(self, payload: Dict[str, Any], vehicle_id: str) -> Tuple[bool, List[str], Dict[str, Any]]:
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
                    cleaned_payload[field] = f"Vehicle_{vehicle_id[-4:]}" if vehicle_id else "Unknown_Vehicle"
                elif field == "code":
                    cleaned_payload[field] = f"V_{vehicle_id[-4:]}" if vehicle_id else "V_UNKNOWN"
        
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
            logger.error(f"Validation errors for vehicle {vehicle_id}: {validation_errors}")
        
        return is_valid, validation_errors, cleaned_payload

    def validate_site_data(self, payload: Dict[str, Any], site_id: str) -> Tuple[bool, List[str], Dict[str, Any]]:
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
                    cleaned_payload[field] = f"Site_{site_id[-4:]}" if site_id else "Unknown_Site"
                elif field == "external_code":
                    cleaned_payload[field] = f"SITE_{site_id[-4:]}" if site_id else "SITE_UNKNOWN"
        
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

    def _generate_email(self, first_name: str, last_name: str) -> str:
        """Generate email address from first and last name"""
        if not first_name or not last_name:
            return "unknown@company.com"
        
        # Clean names for email generation
        clean_first = re.sub(r'[^a-zA-Z]', '', first_name.lower())
        clean_last = re.sub(r'[^a-zA-Z]', '', last_name.lower())
        
        if not clean_first or not clean_last:
            return "unknown@company.com"
        
        return f"{clean_first}.{clean_last}@company.com"

    def _validate_email(self, email: str) -> bool:
        """Validate email format"""
        if not email:
            return False
        return bool(re.match(self.validation_patterns["email"], email))

    def _clean_phone(self, phone: str) -> Optional[str]:
        """Clean and validate phone number"""
        if not phone:
            return None
        # Remove all non-digit characters
        cleaned = re.sub(r'\D', '', str(phone))
        return cleaned if len(cleaned) >= 10 else None

    def _validate_phone(self, phone: str) -> bool:
        """Validate phone number format"""
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

    def sanitize_string_field(self, value: Any, field_name: str) -> Optional[str]:
        """Sanitize string field value"""
        if value is None:
            return None
        
        sanitized = str(value).strip()
        return sanitized if sanitized else None

    def remove_duplicate_entries(self, data_list: List[Dict[str, Any]], key_field: str) -> List[Dict[str, Any]]:
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
            logger.info(f"Removed {removed_count} duplicate entries based on {key_field}")
        
        return unique_data

    def validate_bulk_data(self, data_list: List[Dict[str, Any]], entity_type: str) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
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
                is_valid, errors, cleaned_record = self.validate_employee_data(record, record_id, full_name)
            elif entity_type == "vehicle":
                is_valid, errors, cleaned_record = self.validate_vehicle_data(record, record_id)
            elif entity_type == "site":
                is_valid, errors, cleaned_record = self.validate_site_data(record, record_id)
            else:
                logger.error(f"Unknown entity type: {entity_type}")
                invalid_records.append({
                    "record": record,
                    "errors": [f"Unknown entity type: {entity_type}"]
                })
                continue
            
            if is_valid:
                valid_records.append(cleaned_record)
            else:
                invalid_records.append({
                    "record": record,
                    "errors": errors,
                    "cleaned_record": cleaned_record
                })
        
        logger.info(f"Bulk validation complete: {len(valid_records)} valid, {len(invalid_records)} invalid {entity_type} records")
        
        return valid_records, invalid_records

# Global validator instance
validator = DataValidator()
