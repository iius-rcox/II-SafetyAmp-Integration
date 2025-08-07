from utils.logger import get_logger
from utils.cache_manager import CacheManager
from utils.change_tracker import ChangeTracker
from utils.error_notifier import error_notifier
from services.safetyamp_api import SafetyAmpAPI
from services.viewpoint_api import ViewpointAPI
from services.graph_api import MSGraphAPI

from datetime import datetime, date
import re
import requests

logger = get_logger("sync_employees")

class EmployeeSyncer:
    def __init__(self):
        self.api_client = SafetyAmpAPI()
        self.viewpoint = ViewpointAPI()
        self.msgraph = MSGraphAPI()
        self.cache_manager = CacheManager()
        self.change_tracker = ChangeTracker()
        logger.info("Fetching initial data for sync...")
        self.cluster_map = self._build_cluster_map()
        self.role_map = self._build_role_map()
        self.title_map = self._build_title_map()
        self.existing_users = self._build_user_map()
        self.home_office_map = self._build_home_office_map()
        self.entra_users = self.msgraph.get_active_users()

    def _build_cluster_map(self):
        logger.info("Building cluster map from site clusters and sites...")

        clusters_dict = self.api_client.get_site_clusters()
        cluster_map = {
            cluster["external_code"]: cluster["parent_cluster_id"]
            for cluster in clusters_dict.values()
            if cluster.get("external_code") and cluster.get("parent_cluster_id") is not None
        }

        sites_dict = self.api_client.get_sites_cached(max_age_hours=1)
        for site in sites_dict.values():
            ext_id = site.get("ext_id")
            if ext_id and site.get("id") and not site["name"].endswith(" Office"):
                cluster_map[ext_id.strip()] = site["id"]

        logger.info(f"Cluster map built with {len(cluster_map)} entries.")
        return cluster_map

    def _build_role_map(self):
        logger.info("Fetching roles from SafetyAmp...")
        roles = self.api_client.get_roles_cached(max_age_hours=1)
        role_map = {
            r["name"]: r["id"]
            for r in roles.values()
                if r.get("name") is not None and "id" in r
        }
        logger.info(f"Role map built with {len(role_map)} entries.")
        return role_map

    def _build_title_map(self):
        logger.info("Fetching titles from SafetyAmp...")
        titles = self.api_client.get_titles_cached(max_age_hours=1)
        title_map = {
            t["name"].strip(): t["id"]
            for t in titles.values()
            if "name" in t and "id" in t
        }
        logger.info(f"Title map built with {len(title_map)} entries.")
        return title_map

    def _build_user_map(self):
        logger.info("Fetching existing users from SafetyAmp...")
        users = self.api_client.get_users_cached(max_age_hours=1)
        
        # Handle both list and dict formats from cache
        if isinstance(users, dict):
            user_map = {str(user.get("emp_id")): user for user in users.values() if "emp_id" in user}
        elif isinstance(users, list):
            user_map = {str(user.get("emp_id")): user for user in users if "emp_id" in user}
        else:
            logger.warning(f"Unexpected users data type: {type(users)}. Using empty map.")
            user_map = {}
            
        logger.info(f"User map built with {len(user_map)} entries.")
        return user_map

    def _build_home_office_map(self):
        logger.info("Building home office map from sites...")
        sites = self.api_client.get_sites_cached(max_age_hours=1)
        home_offices = {}
        for site in sites.values():
            if site["name"].endswith(" Office") and site.get("cluster_id") and site.get("id"):
                cluster_id = site["cluster_id"]
                home_offices[cluster_id] = site["id"]
        logger.info(f"Home office map built with {len(home_offices)} entries.")
        return home_offices

    def clean_phone(self, phone):
        if not phone:
            return None
        digits = re.sub(r"\D", "", phone)
        if len(digits) == 10:
            return f"+1{digits}"
        elif len(digits) == 11 and digits.startswith("1"):
            return f"+{digits}"
        return None

    def normalize_gender(self, gender_raw):
        if gender_raw in [0, "0", "F", "f"]:
            return "0"
        if gender_raw in [1, "1", "M", "m"]:
            return "1"
        return None

    def format_date(self, val):
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

    def get_updated_fields(self, existing_user, new_data):
        fields_to_check = [
            "first_name", "middle_name", "last_name", "email", "gender",
            "date_of_birth", "current_hire_date", "street", "street2",
            "city", "state", "zip_code", "country",
            "mobile_phone", "work_phone", "home_site_id"
        ]

        updated_fields = {}

        for key in fields_to_check:
            # Handle None values and normalize to empty string for comparison
            existing_raw = existing_user.get(key)
            new_raw = new_data.get(key)
            
            # Normalize existing value
            if existing_raw is None:
                existing_value = ""
            else:
                existing_value = str(existing_raw).strip()
            
            # Normalize new value
            if new_raw is None:
                new_value = ""
            else:
                new_value = str(new_raw).strip()

            # Apply field-specific normalization
            if key in ["mobile_phone", "work_phone"]:
                existing_value = self.clean_phone(existing_value) or ""
                new_value = self.clean_phone(new_value) or ""
            elif key == "gender":
                existing_value = self.normalize_gender(existing_value) or ""
                new_value = self.normalize_gender(new_value) or ""
            elif key in ["date_of_birth", "current_hire_date"]:
                existing_value = self.format_date(existing_value) or ""
                new_value = self.format_date(new_value) or ""

            # Only include field if values are actually different AND new value is not empty/None
            if existing_value != new_value and new_value:
                # Use the normalized new value for the update to ensure consistency
                if key in ["mobile_phone", "work_phone"]:
                    updated_fields[key] = self.clean_phone(new_raw)
                elif key == "gender":
                    updated_fields[key] = self.normalize_gender(new_raw)
                elif key in ["date_of_birth", "current_hire_date"]:
                    updated_fields[key] = self.format_date(new_raw)
                else:
                    # For other fields, use the original value but ensure it's not None
                    updated_fields[key] = new_raw if new_raw is not None else ""

        return updated_fields

    def map_employee_to_payload(self, emp):
        emp_id = str(emp["Employee"])
        job_code = emp.get("Job")
        dept_code = emp.get("PRDept")
        title_name = emp.get("udEmpTitle")

        home_site_id = None
        if job_code and job_code in self.cluster_map:
            home_site_id = self.cluster_map[job_code]
        elif dept_code and dept_code in self.cluster_map:
            cluster_id = self.cluster_map[dept_code]
            home_site_id = self.home_office_map.get(cluster_id)

        entra_user = self.entra_users.get(emp_id)
        email = entra_user["email"] if entra_user else emp.get("Email")

        return {
            "first_name": emp.get("FirstName"),
            "middle_name": emp.get("MidName"),
            "last_name": emp.get("LastName"),
            "email": email,
            "gender": self.normalize_gender(emp.get("Sex")),
            "date_of_birth": self.format_date(emp.get("BirthDate")),
            "current_hire_date": self.format_date(emp.get("HireDate")),
            "street": emp.get("Address"),
            "street2": None,
            "city": emp.get("City"),
            "state": emp.get("State"),
            "zip_code": str(emp.get("Zip")) if emp.get("Zip") else None,
            "country": "US",
            "mobile_phone": self.clean_phone(emp.get("Phone")),
            "work_phone": self.clean_phone(emp.get("Phone")),
            "home_site_id": home_site_id,
            "system_access": 0,
            "timezone": "America/Chicago",
            "roles": [{"id": self.role_map["Field"]}] if "Field" in self.role_map else [],
            "sites": [],
            "current_title_id": self.title_map.get(title_name),
            "current_department_id": None,
            "current_supervisor_id": None,
            "emp_id": emp_id
        }

    def sync(self):
        logger.info("Starting employee sync...")
        
        # Start change tracking
        self.change_tracker.start_sync("employees")
        
        employees = self.viewpoint.get_employees()
        logger.info(f"Retrieved {len(employees)} employees from Viewpoint.")

        # Track sync results for cache updates
        sync_results = {
            "created": 0,
            "updated": 0,
            "skipped": 0,
            "errors": 0,
            "processed_employees": []
        }

        # Track consecutive errors to prevent infinite error loops
        consecutive_errors = 0
        max_consecutive_errors = 10
        
        for emp in employees:
            # Safety check: stop if too many consecutive errors
            if consecutive_errors >= max_consecutive_errors:
                error_msg = f"Stopping sync due to {consecutive_errors} consecutive errors"
                logger.error(error_msg)
                self.change_tracker.log_error("sync", "system", error_msg, "safety_stop")
                
                # Log to error notifier for email notifications
                error_notifier.log_error(
                    error_type="safety_stop",
                    entity_type="sync",
                    entity_id="system",
                    error_message=error_msg,
                    error_details={
                        "consecutive_errors": consecutive_errors,
                        "max_consecutive_errors": max_consecutive_errors,
                        "processed_count": len(sync_results["processed_employees"])
                    },
                    source="sync_safety"
                )
                break
                
            emp_id = str(emp["Employee"])
            payload = self.map_employee_to_payload(emp)
            existing_user = self.existing_users.get(emp_id)
            full_name = f"{payload.get('first_name', '')} {payload.get('last_name', '')}".strip()

            if not payload.get("home_site_id"):
                reason = f"No matching site for PRDept {emp.get('PRDept')} or Job {emp.get('Job')}"
                logger.warning(f"Skipping employee {full_name} (ID: {emp_id}): {reason}")
                self.change_tracker.log_skip("employee", emp_id, reason)
                sync_results["skipped"] += 1
                continue

            if existing_user:
                updated_fields = self.get_updated_fields(existing_user, payload)
                if updated_fields:
                    try:
                        self.api_client.put(f"/api/users/{existing_user['id']}", updated_fields)
                        logger.info(f"Updated user {full_name} (ID: {emp_id}) with fields: {list(updated_fields.keys())}")
                        self.change_tracker.log_update("employee", emp_id, updated_fields, existing_user)
                        sync_results["updated"] += 1
                        sync_results["processed_employees"].append({"id": emp_id, "action": "updated", "fields": list(updated_fields.keys())})
                        consecutive_errors = 0  # Reset error counter on success
                    except requests.HTTPError as e:
                        consecutive_errors += 1
                        if e.response.status_code == 422:
                            error_response = e.response.json()
                            error_msg = f"Validation error (422): {error_response}"
                            logger.error(f"Validation error updating user {full_name} (ID: {emp_id}): {error_msg}")
                            self.change_tracker.log_error("employee", emp_id, error_msg, "update", payload)
                            
                            # Log to error notifier for email notifications
                            error_notifier.log_error(
                                error_type="validation_error",
                                entity_type="employee",
                                entity_id=emp_id,
                                error_message=error_msg,
                                error_details={
                                    "status_code": 422,
                                    "failed_fields": list(updated_fields.keys()),
                                    "payload": payload,
                                    "employee_name": full_name
                                },
                                source="sync_update"
                            )
                            sync_results["errors"] += 1
                            
                            # Log the problematic fields for debugging
                            logger.error(f"Failed update fields for {full_name}: {updated_fields}")
                        else:
                            error_msg = f"HTTP error {e.response.status_code}: {str(e)}"
                            logger.error(f"Error updating user {full_name} (ID: {emp_id}): {error_msg}")
                            self.change_tracker.log_error("employee", emp_id, error_msg, "update", payload)
                            
                            # Log to error notifier for email notifications
                            error_notifier.log_error(
                                error_type="http_error",
                                entity_type="employee",
                                entity_id=emp_id,
                                error_message=error_msg,
                                error_details={
                                    "status_code": e.response.status_code,
                                    "payload": payload,
                                    "employee_name": full_name
                                },
                                source="sync_update"
                            )
                            sync_results["errors"] += 1
                    except Exception as e:
                        consecutive_errors += 1
                        error_msg = f"Unexpected error updating user: {str(e)}"
                        logger.error(f"Error updating user {full_name} (ID: {emp_id}): {error_msg}")
                        self.change_tracker.log_error("employee", emp_id, error_msg, "update", payload)
                        
                        # Log to error notifier for email notifications
                        error_notifier.log_error(
                            error_type="unexpected_error",
                            entity_type="employee",
                            entity_id=emp_id,
                            error_message=error_msg,
                            error_details={
                                "exception_type": type(e).__name__,
                                "payload": payload,
                                "employee_name": full_name
                            },
                            source="sync_update"
                        )
                        sync_results["errors"] += 1
                else:
                    sync_results["skipped"] += 1
            else:
                try:
                    self.api_client.create_user(payload)
                    logger.info(f"Created user {full_name} (ID: {emp_id})")
                    self.change_tracker.log_creation("employee", emp_id, payload)
                    sync_results["created"] += 1
                    sync_results["processed_employees"].append({"id": emp_id, "action": "created"})
                    consecutive_errors = 0  # Reset error counter on success
                except requests.HTTPError as e:
                    consecutive_errors += 1
                    if e.response.status_code == 422:
                        error_response = e.response.json()
                        error_msg = f"Validation error (422): {error_response}"
                        logger.error(f"Validation error creating user {full_name} (ID: {emp_id}): {error_msg}")
                        
                        # Log to error notifier for email notifications
                        error_notifier.log_error(
                            error_type="validation_error",
                            entity_type="employee",
                            entity_id=emp_id,
                            error_message=error_msg,
                            error_details={
                                "status_code": 422,
                                "payload": payload,
                                "employee_name": full_name,
                                "operation": "create"
                            },
                            source="sync_create"
                        )
                        
                        # Log the problematic payload for debugging
                        logger.error(f"Failed create payload for {full_name}: {payload}")
                        
                        # Attempt fallback for known validation errors
                        fallback_payload = payload.copy()
                        for field in ["email", "mobile_phone", "work_phone"]:
                            fallback_payload.pop(field, None)
                        try:
                            self.api_client.create_user(fallback_payload)
                            logger.info(f"Created user {full_name} (ID: {emp_id}) on fallback attempt without email/phone")
                            self.change_tracker.log_creation("employee", emp_id, fallback_payload)
                            sync_results["created"] += 1
                            sync_results["processed_employees"].append({"id": emp_id, "action": "created_fallback"})
                            consecutive_errors = 0  # Reset on successful fallback
                        except requests.HTTPError as fallback_e:
                            consecutive_errors += 1
                            if fallback_e.response.status_code == 422:
                                fallback_error_response = fallback_e.response.json()
                                fallback_error_msg = f"Fallback validation error (422): {fallback_error_response}"
                                logger.error(f"Fallback failed for {full_name} (ID: {emp_id}): {fallback_error_msg}")
                                self.change_tracker.log_error("employee", emp_id, fallback_error_msg, "create_fallback", fallback_payload)
                                
                                # Log fallback error to notifier
                                error_notifier.log_error(
                                    error_type="fallback_validation_error",
                                    entity_type="employee",
                                    entity_id=emp_id,
                                    error_message=fallback_error_msg,
                                    error_details={
                                        "status_code": 422,
                                        "fallback_payload": fallback_payload,
                                        "original_payload": payload,
                                        "employee_name": full_name
                                    },
                                    source="sync_create_fallback"
                                )
                                sync_results["errors"] += 1
                            else:
                                fallback_error_msg = f"Fallback HTTP error {fallback_e.response.status_code}: {str(fallback_e)}"
                                logger.error(f"Fallback failed for {full_name} (ID: {emp_id}): {fallback_error_msg}")
                                self.change_tracker.log_error("employee", emp_id, fallback_error_msg, "create_fallback", fallback_payload)
                                
                                # Log fallback error to notifier
                                error_notifier.log_error(
                                    error_type="fallback_http_error",
                                    entity_type="employee",
                                    entity_id=emp_id,
                                    error_message=fallback_error_msg,
                                    error_details={
                                        "status_code": fallback_e.response.status_code,
                                        "fallback_payload": fallback_payload,
                                        "original_payload": payload,
                                        "employee_name": full_name
                                    },
                                    source="sync_create_fallback"
                                )
                                sync_results["errors"] += 1
                        except Exception as final_e:
                            consecutive_errors += 1
                            error_msg = f"Unexpected error in fallback: {str(final_e)}"
                            logger.error(f"Unexpected error in fallback for {full_name} (ID: {emp_id}): {error_msg}")
                            self.change_tracker.log_error("employee", emp_id, error_msg, "create_fallback", fallback_payload)
                            
                            # Log fallback error to notifier
                            error_notifier.log_error(
                                error_type="fallback_unexpected_error",
                                entity_type="employee",
                                entity_id=emp_id,
                                error_message=error_msg,
                                error_details={
                                    "exception_type": type(final_e).__name__,
                                    "fallback_payload": fallback_payload,
                                    "original_payload": payload,
                                    "employee_name": full_name
                                },
                                source="sync_create_fallback"
                            )
                            sync_results["errors"] += 1
                    else:
                        consecutive_errors += 1
                        error_msg = f"HTTP error {e.response.status_code}: {str(e)}"
                        logger.error(f"Error creating user {full_name} (ID: {emp_id}): {error_msg}")
                        self.change_tracker.log_error("employee", emp_id, error_msg, "create", payload)
                        
                        # Log to error notifier for email notifications
                        error_notifier.log_error(
                            error_type="http_error",
                            entity_type="employee",
                            entity_id=emp_id,
                            error_message=error_msg,
                            error_details={
                                "status_code": e.response.status_code,
                                "payload": payload,
                                "employee_name": full_name,
                                "operation": "create"
                            },
                            source="sync_create"
                        )
                        sync_results["errors"] += 1

                # Update cache with sync results
        self._update_cache_after_sync(sync_results)

        # End change tracking and get summary
        session_summary = self.change_tracker.end_sync()

        logger.info(f"Employee sync completed: {sync_results['created']} created, {sync_results['updated']} updated, {sync_results['skipped']} skipped, {sync_results['errors']} errors")

        return {
            "processed": len(employees),
            "created": sync_results["created"],
            "updated": sync_results["updated"],
            "skipped": sync_results["skipped"],
            "errors": sync_results["errors"],
            "session_id": session_summary["session_id"],
            "duration_seconds": session_summary["summary"]["duration_seconds"]
        }

    def _update_cache_after_sync(self, sync_results):
        """Update cache directly after sync operations with smart refresh logic"""
        try:
            cache_name = "safetyamp_users"
            
            # Check if it's time for a full cache refresh
            if self.cache_manager.should_refresh_cache(cache_name):
                logger.info("Performing full cache refresh (4-hour interval reached)")
                # Get fresh user data from SafetyAmp API for cache update
                fresh_users = self.api_client.get_users()
                
                if fresh_users:
                    # Update cache directly with fresh data
                    success = self.cache_manager.update_cache_directly(
                        cache_name, 
                        list(fresh_users.values()), 
                        source="sync_employee_full_refresh"
                    )
                    
                    if success:
                        logger.info(f"Successfully performed full cache refresh with {len(fresh_users)} users")
                        # Mark cache as refreshed
                        self.cache_manager.mark_cache_refreshed(cache_name)
                    else:
                        logger.warning("Failed to perform full cache refresh")
                else:
                    logger.warning("No fresh user data available for full cache refresh")
            else:
                # Only update cache if there were actual changes
                if sync_results["created"] > 0 or sync_results["updated"] > 0:
                    logger.info("Performing incremental cache update (changes detected)")
                    fresh_users = self.api_client.get_users()
                    
                    if fresh_users:
                        success = self.cache_manager.update_cache_directly(
                            cache_name, 
                            list(fresh_users.values()), 
                            source="sync_employee_incremental"
                        )
                        
                        if success:
                            logger.info(f"Successfully updated cache incrementally with {len(fresh_users)} users")
                        else:
                            logger.warning("Failed to update cache incrementally")
                    else:
                        logger.warning("No fresh user data available for incremental cache update")
                else:
                    logger.info("No changes detected, skipping cache update")
                
        except Exception as e:
            logger.error(f"Error updating cache after sync: {e}")
            # Don't fail the sync if cache update fails