from utils.logger import get_logger
from services.safetyamp_api import SafetyAmpAPI
from services.viewpoint_api import ViewpointAPI
from services.graph_api import MSGraphAPI
from services.data_manager import data_manager
from .base_sync import BaseSyncOperation

import requests

logger = get_logger("sync_employees")

class EmployeeSyncer(BaseSyncOperation):
    def __init__(self):
        super().__init__(sync_type="employees", logger_name="sync_employees")
        self.viewpoint = ViewpointAPI()
        self.msgraph = MSGraphAPI()
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

        sites_dict = data_manager.get_cached_data_with_fallback(
            "safetyamp_sites",
            lambda: self.api_client.get_all_paginated("/api/sites", key_field="id"),
            max_age_hours=1,
        )
        for site in sites_dict.values():
            ext_id = site.get("external_code")
            if ext_id and ext_id not in cluster_map:
                cluster_map[ext_id] = site.get("id")

        logger.info(f"Cluster map built with {len(cluster_map)} entries.")
        return cluster_map

    def _build_role_map(self):
        roles = data_manager.get_cached_data_with_fallback(
            "safetyamp_roles",
            lambda: self.api_client.get_all_paginated("/api/roles", key_field="id"),
            max_age_hours=1,
        )
        role_map = {
            r["name"].strip(): r["id"]
            for r in roles.values()
            if "name" in r and "id" in r
        }
        logger.info(f"Role map built with {len(role_map)} entries.")
        return role_map

    def _build_title_map(self):
        titles = data_manager.get_cached_data_with_fallback(
            "safetyamp_titles",
            lambda: self.api_client.get_all_paginated("/api/user_titles", key_field="id"),
            max_age_hours=1,
        )
        title_map = {
            t["name"].strip(): t["id"]
            for t in titles.values()
            if "name" in t and "id" in t
        }
        logger.info(f"Title map built with {len(title_map)} entries.")
        return title_map

    def _build_user_map(self):
        users = data_manager.get_cached_data_with_fallback(
            "safetyamp_users_by_id",
            lambda: self.api_client.get_all_paginated("/api/users", key_field="id"),
            max_age_hours=1,
        )
        user_map = {user["emp_id"]: user for user in users.values() if user.get("emp_id")}
        logger.info(f"User map built with {len(user_map)} entries.")
        return user_map

    def _build_home_office_map(self):
        sites = data_manager.get_cached_data_with_fallback(
            "safetyamp_sites",
            lambda: self.api_client.get_all_paginated("/api/sites", key_field="id"),
            max_age_hours=1,
        )
        home_office_map = {site["cluster_id"]: site["id"] for site in sites.values() if site.get("cluster_id") and site.get("id")}
        logger.info(f"Home office map built with {len(home_office_map)} entries.")
        return home_office_map

    def clean_phone(self, phone):
        return self.validator.clean_phone(phone)

    def normalize_gender(self, gender_raw):
        return self.validator.normalize_gender(gender_raw)

    def format_date(self, val):
        return self.validator.format_date(val)

    def validate_required_fields(self, payload, emp_id, full_name):
        """
        Validate that all required fields are present and valid before sending to API.
        Returns (is_valid, validation_errors, cleaned_payload)
        """
        return self.validator.validate_employee_data(payload, emp_id, full_name)

    def get_updated_fields(self, existing_user, new_data):
        fields_to_check = [
            "first_name", "middle_name", "last_name", "email", "gender",
            "date_of_birth", "current_hire_date", "street", "street2",
            "city", "state", "zip_code", "country",
            "mobile_phone", "work_phone", "home_site_id"
        ]

        updated_fields = {}

        for key in fields_to_check:
            existing_raw = existing_user.get(key)
            new_raw = new_data.get(key)
            if existing_raw is None:
                existing_value = ""
            else:
                existing_value = str(existing_raw).strip()
            if new_raw is None:
                new_value = ""
            else:
                new_value = str(new_raw).strip()

            if key in ["mobile_phone", "work_phone"]:
                existing_value = self.clean_phone(existing_value) or ""
                new_value = self.clean_phone(new_value) or ""
            elif key == "gender":
                existing_value = self.normalize_gender(existing_value) or ""
                new_value = self.normalize_gender(new_value) or ""
            elif key in ["date_of_birth", "current_hire_date"]:
                existing_value = self.format_date(existing_value) or ""
                new_value = self.format_date(new_value) or ""

            if existing_value != new_value and new_value:
                if key in ["mobile_phone", "work_phone"]:
                    updated_fields[key] = self.clean_phone(new_raw)
                elif key == "gender":
                    updated_fields[key] = self.normalize_gender(new_raw)
                elif key in ["date_of_birth", "current_hire_date"]:
                    updated_fields[key] = self.format_date(new_raw)
                else:
                    updated_fields[key] = new_raw if new_raw is not None else ""

        existing_sa = existing_user.get("system_access")
        existing_sa_str = str(existing_sa).strip().lower()
        if existing_sa_str not in ("1", "true"):
            updated_fields["system_access"] = 1

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
            home_office_id = self.home_office_map.get(cluster_id)
            home_site_id = home_office_id

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
            "system_access": 1,
            "text_opt_out": 1,
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
        self.start_sync()

        employees = self.viewpoint.get_employees()
        logger.info(f"Retrieved {len(employees)} employees from Viewpoint.")

        sync_results = {
            "created": 0,
            "updated": 0,
            "skipped": 0,
            "errors": 0,
            "processed_employees": []
        }

        for emp in employees:
            if self.should_abort_for_safety(processed_count=len(sync_results["processed_employees"])):
                break

            emp_id = str(emp["Employee"])
            payload = self.map_employee_to_payload(emp)
            existing_user = self.existing_users.get(emp_id)
            full_name = f"{payload.get('first_name', '')} {payload.get('last_name', '')}".strip()

            if not payload.get("home_site_id"):
                reason = f"No matching site for PRDept {emp.get('PRDept')} or Job {emp.get('Job')}"
                logger.warning(f"Skipping employee {full_name} (ID: {emp_id}): {reason}")
                self.log_skip("employee", emp_id, reason)
                sync_results["skipped"] += 1
                continue

            is_valid, validation_errors, cleaned_payload = self.validate_required_fields(payload, emp_id, full_name)

            if not is_valid:
                self.log_error(
                    error_type="validation_error",
                    entity_type="employee",
                    entity_id=emp_id,
                    error_message=f"Validation errors: {validation_errors}",
                    operation="validation",
                    error_details={
                        "validation_errors": validation_errors,
                        "original_payload": payload,
                        "cleaned_payload": cleaned_payload,
                        "employee_name": full_name
                    },
                    source="sync_validation"
                )
                sync_results["errors"] += 1
                self.record_error()
                continue

            if existing_user:
                updated_fields = self.get_updated_fields(existing_user, cleaned_payload)
                if updated_fields:
                    update_payload = {**existing_user, **updated_fields}
                    is_update_valid, update_validation_errors, cleaned_update_payload = self.validate_required_fields(update_payload, emp_id, full_name)

                    if not is_update_valid:
                        self.log_error(
                            error_type="validation_error",
                            entity_type="employee",
                            entity_id=emp_id,
                            error_message=f"Update validation errors: {update_validation_errors}",
                            operation="update_validation",
                            error_details=updated_fields,
                            source="sync_update"
                        )
                        sync_results["errors"] += 1
                        self.record_error()
                        continue

                    sanitized_update_fields = {k: cleaned_update_payload.get(k) for k in updated_fields.keys() if k in cleaned_update_payload}

                    required_core_fields = {}
                    for core_key in ["first_name", "last_name", "email"]:
                        if existing_user.get(core_key) is not None:
                            required_core_fields[core_key] = existing_user.get(core_key)
                    if sanitized_update_fields.get("system_access") == 1:
                        patch_payload = {**required_core_fields, "system_access": 1}
                    else:
                        patch_payload = {**required_core_fields, **sanitized_update_fields}
                    if not sanitized_update_fields:
                        sync_results["skipped"] += 1
                        self.record_success()
                        continue

                    def do_patch():
                        return self.api_client.patch(f"/api/users/{existing_user['id']}", patch_payload)

                    success, _ = self.execute_with_http_handling(
                        do_patch,
                        entity_type="employee",
                        entity_id=emp_id,
                        operation="update",
                        payload=patch_payload,
                    )
                    if success:
                        logger.info(f"Updated user {full_name} (ID: {emp_id}) with fields: {list(sanitized_update_fields.keys())}")
                        self.log_update("employee", emp_id, patch_payload, existing_user)
                        sync_results["updated"] += 1
                        sync_results["processed_employees"].append({"id": emp_id, "action": "updated", "fields": list(sanitized_update_fields.keys())})
                else:
                    sync_results["skipped"] += 1
            else:
                def do_create():
                    return self.api_client.create_user(cleaned_payload)

                def on_422_create(e: requests.HTTPError):
                    pass

                success, _ = self.execute_with_http_handling(
                    do_create,
                    entity_type="employee",
                    entity_id=emp_id,
                    operation="create",
                    payload=cleaned_payload,
                )
                if success:
                    logger.info(f"Created user {full_name} (ID: {emp_id})")
                    self.log_creation("employee", emp_id, cleaned_payload)
                    sync_results["created"] += 1
                    sync_results["processed_employees"].append({"id": emp_id, "action": "created"})
                else:
                    # Attempt fallback for known validation issues
                    fallback_payload = cleaned_payload.copy()
                    for field in ["email", "mobile_phone", "work_phone"]:
                        fallback_payload.pop(field, None)

                    is_fallback_valid, fallback_validation_errors, cleaned_fallback_payload = self.validate_required_fields(fallback_payload, emp_id, full_name)

                    if not is_fallback_valid:
                        self.log_error(
                            error_type="validation_error",
                            entity_type="employee",
                            entity_id=emp_id,
                            error_message=f"Fallback validation errors: {fallback_validation_errors}",
                            operation="create_fallback_validation",
                            error_details=fallback_payload,
                            source="sync_create_fallback"
                        )
                        sync_results["errors"] += 1
                        continue

                    def do_create_fallback():
                        return self.api_client.create_user(cleaned_fallback_payload)

                    success_fb, _ = self.execute_with_http_handling(
                        do_create_fallback,
                        entity_type="employee",
                        entity_id=emp_id,
                        operation="create_fallback",
                        payload=cleaned_fallback_payload,
                    )
                    if success_fb:
                        logger.info(f"Created user {full_name} (ID: {emp_id}) on fallback attempt without email/phone")
                        self.log_creation("employee", emp_id, cleaned_fallback_payload)
                        sync_results["created"] += 1
                        sync_results["processed_employees"].append({"id": emp_id, "action": "created_fallback"})

        self._update_cache_after_sync(sync_results)

        session_summary = self.end_sync()

        logger.info(f"Employee sync completed: {sync_results['created']} created, {sync_results['updated']} updated, {sync_results['skipped']} skipped, {sync_results['errors']} errors")

        return {
            "processed": len(employees),
            "created": sync_results["created"],
            "updated": sync_results["updated"],
            "skipped": sync_results["skipped"],
            "errors": sync_results["errors"],
            "session_summary": session_summary
        }

    def _update_cache_after_sync(self, sync_results):
        """Update cache after successful sync operations"""
        try:
            if sync_results["created"] > 0 or sync_results["updated"] > 0:
                logger.info("Updating caches after sync...")
                self.existing_users = self._build_user_map()
                logger.info("Cache update completed")
        except Exception as e:
            logger.error(f"Error updating cache after sync: {e}")