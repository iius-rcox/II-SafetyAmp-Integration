from utils.logger import get_logger
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

        sites_dict = self.api_client.get_sites()
        for site in sites_dict.values():
            ext_id = site.get("ext_id")
            if ext_id and site.get("id") and not site["name"].endswith(" Office"):
                cluster_map[ext_id.strip()] = site["id"]

        logger.info(f"Cluster map built with {len(cluster_map)} entries.")
        return cluster_map

    def _build_role_map(self):
        logger.info("Fetching roles from SafetyAmp...")
        roles = self.api_client.get_roles().values()
        role_map = {
            r["name"]: r["id"]
            for r in roles
                if r.get("name") is not None and "id" in r
        }
        logger.info(f"Role map built with {len(role_map)} entries.")
        return role_map

    def _build_title_map(self):
        logger.info("Fetching titles from SafetyAmp...")
        titles = self.api_client.get_titles()
        title_map = {
            t["name"].strip(): t["id"]
            for t in titles.values()
            if "name" in t and "id" in t
        }
        logger.info(f"Title map built with {len(title_map)} entries.")
        return title_map

    def _build_user_map(self):
        logger.info("Fetching existing users from SafetyAmp...")
        users = self.api_client.get_users().values()
        user_map = {str(user.get("emp_id")): user for user in users if "emp_id" in user}
        logger.info(f"User map built with {len(user_map)} entries.")
        return user_map

    def _build_home_office_map(self):
        logger.info("Building home office map from sites...")
        sites = self.api_client.get_sites().values()
        home_offices = {}
        for site in sites:
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

            # Only include field if values are actually different
            if existing_value != new_value:
                # Use the original new_data value (not normalized) for the update
                updated_fields[key] = new_data.get(key)

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
        employees = self.viewpoint.get_employees()
        logger.info(f"Retrieved {len(employees)} employees from Viewpoint.")

        for emp in employees:
            emp_id = str(emp["Employee"])
            payload = self.map_employee_to_payload(emp)
            existing_user = self.existing_users.get(emp_id)
            full_name = f"{payload.get('first_name', '')} {payload.get('last_name', '')}".strip()

            if not payload.get("home_site_id"):
                logger.warning(f"Skipping employee {full_name} (ID: {emp_id}): No matching site for PRDept {emp.get('PRDept')} or Job {emp.get('Job')}")
                continue

            if existing_user:
                updated_fields = self.get_updated_fields(existing_user, payload)
                if updated_fields:
                    self.api_client.put(f"/api/users/{existing_user['id']}", updated_fields)
                    logger.info(f"Updated user {full_name} (ID: {emp_id}) with fields: {list(updated_fields.keys())}")
                # else:
                    # logger.info(f"No update needed for user {full_name} (ID: {emp_id})")
            else:
                try:
                    self.api_client.create_user(payload)
                    logger.info(f"Created user {full_name} (ID: {emp_id})")
                except requests.HTTPError as e:
                    error_response = e.response.json()
                    logger.warning(
                        f"Initial creation failed for {full_name} (ID: {emp_id}), attempting fallback. Reason: {error_response}")

                    # Fallback logic for known validation errors
                    fallback_payload = payload.copy()
                    for field in ["email", "mobile_phone", "work_phone"]:
                        fallback_payload.pop(field, None)
                    try:
                        self.api_client.create_user(fallback_payload)
                        logger.info(
                            f"Created user {full_name} (ID: {emp_id}) on fallback attempt without email/phone")
                    except Exception as final_e:
                        logger.error(
                            f"Failed to create user {full_name} (ID: {emp_id}) after fallback: {str(final_e)}")