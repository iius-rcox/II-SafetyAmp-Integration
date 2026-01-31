import requests
import time
from ratelimit import limits, sleep_and_retry
from config import config
from utils.logger import get_logger
from utils.data_validator import validator
from services.api_call_tracker import get_api_call_tracker

logger = get_logger("safetyamp")


class SafetyAmpAPI:
    CALLS = 60
    PERIOD = 61  # in seconds
    MAX_RETRY_WAIT = 60

    def __init__(self):
        self.base_url = config.SAFETYAMP_DOMAIN.rstrip("/")
        self.headers = {
            "Authorization": f"Bearer {config.SAFETYAMP_TOKEN}",
            "Fqdn": config.SAFETYAMP_FQDN,
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

    def _preprocess_payload(self, endpoint: str, data: dict, method: str) -> dict:
        """Validate and clean payloads for write operations before sending to SafetyAmp.

        Applies entity-specific validation for POST/PUT/PATCH requests.
        Always returns a cleaned payload; logs validation errors for visibility.
        """
        if not isinstance(data, dict):
            return data

        cleaned_payload = data
        validation_errors = []

        try:
            endpoint_lower = endpoint.lower()
            if endpoint_lower.startswith("/api/users"):
                # Employee payload validation
                emp_id = str(data.get("emp_id", data.get("id", "unknown")))
                full_name = (
                    f"{data.get('first_name', '')} {data.get('last_name', '')}".strip()
                )
                is_valid, errs, cleaned = validator.validate_employee_data(
                    data, emp_id, full_name
                )
                cleaned_payload = cleaned
                validation_errors = errs
            elif endpoint_lower.startswith("/api/assets"):
                # Vehicle/asset payload validation (best-effort)
                asset_id = str(data.get("id", data.get("serial", "unknown")))
                is_valid, errs, cleaned = validator.validate_vehicle_data(
                    data, asset_id
                )
                cleaned_payload = cleaned
                validation_errors = errs
            elif endpoint_lower.startswith("/api/sites") or endpoint_lower.startswith(
                "/api/site_clusters"
            ):
                site_id = str(data.get("id", data.get("external_code", "unknown")))
                is_valid, errs, cleaned = validator.validate_site_data(data, site_id)
                cleaned_payload = cleaned
                validation_errors = errs
        except Exception as e:
            logger.warning(f"Validation preprocessing skipped due to error: {e}")

        if validation_errors:
            logger.warning(
                f"{method} {endpoint}: payload had validation issues: {validation_errors}"
            )
            if method.upper() == "POST":
                has_missing_required = any(
                    str(err).startswith("Missing required field:")
                    for err in validation_errors
                )
                if has_missing_required:
                    raise requests.HTTPError(
                        "Validation failed: missing required fields",
                        response=requests.Response(),
                    )

        return cleaned_payload

    @sleep_and_retry
    @limits(calls=CALLS, period=PERIOD)
    def _rate_limited_request(self, method, url, **kwargs):
        return method(url, headers=self.headers, **kwargs)

    def _exponential_retry(self, func, *args, **kwargs):
        retry = 0
        while True:
            try:
                response = func(*args, **kwargs)
                if response.status_code == 429:
                    raise requests.HTTPError("429 Too Many Requests", response=response)
                return response
            except requests.HTTPError as e:
                if e.response.status_code == 429:
                    wait_time = min(2**retry, self.MAX_RETRY_WAIT)
                    logger.warning(
                        f"Rate limited (429). Retrying in {wait_time} seconds..."
                    )
                    time.sleep(wait_time)
                    retry += 1
                else:
                    raise

    def _handle_response(self, response, method: str, url: str):
        try:
            response.raise_for_status()
            data = response.json().get("data", [])
            logger.debug(f"{method} {url} succeeded")
            return data
        except requests.HTTPError as http_err:
            logger.error(f"{method} {url} HTTP error: {http_err} - {response.text}")
        except ValueError as parse_err:
            logger.error(f"{method} {url} parse error: {parse_err}")
        except Exception as err:
            logger.error(f"{method} {url} unexpected error: {err}")
        return []

    def _track_call(self, method: str, endpoint: str, status_code: int, duration_ms: int, error: str = None):
        """Record API call to tracker if available."""
        tracker = get_api_call_tracker()
        if tracker:
            tracker.record_call(
                service="safetyamp",
                method=method,
                endpoint=endpoint,
                status_code=status_code,
                duration_ms=duration_ms,
                error_message=error,
            )

    def get(self, endpoint, params=None):
        url = f"{self.base_url}{endpoint}"
        start_time = time.time()
        try:
            response = self._exponential_retry(
                self._rate_limited_request, requests.get, url, params=params
            )
            duration_ms = int((time.time() - start_time) * 1000)
            self._track_call("GET", endpoint, response.status_code, duration_ms)
            return self._handle_response(response, "GET", url)
        except requests.RequestException as e:
            duration_ms = int((time.time() - start_time) * 1000)
            self._track_call("GET", endpoint, 0, duration_ms, str(e))
            logger.error(f"GET {url} request failed: {e}")
            return []

    def get_all_paginated(self, endpoint, key_field="id"):
        result_limit = 25
        all_results = {}
        page = 0
        while True:
            params = {"page": page, "limit": result_limit}
            batch = self.get(endpoint, params=params)
            if not batch:
                break
            for item in batch:
                if key_field in item:
                    all_results[str(item[key_field])] = item
            page += 1
        return all_results

    def post(self, endpoint, data):
        url = f"{self.base_url}{endpoint}"
        start_time = time.time()
        try:
            cleaned = self._preprocess_payload(endpoint, data, "POST")
            response = self._exponential_retry(
                self._rate_limited_request, requests.post, url, json=cleaned
            )
            duration_ms = int((time.time() - start_time) * 1000)
            self._track_call("POST", endpoint, response.status_code, duration_ms)
            return self._handle_response(response, "POST", url)
        except requests.RequestException as e:
            duration_ms = int((time.time() - start_time) * 1000)
            self._track_call("POST", endpoint, 0, duration_ms, str(e))
            logger.error(f"POST {url} request failed: {e}")
            return []

    def put(self, endpoint, data):
        url = f"{self.base_url}{endpoint}"
        start_time = time.time()
        try:
            cleaned = self._preprocess_payload(endpoint, data, "PUT")
            response = self._exponential_retry(
                self._rate_limited_request, requests.put, url, json=cleaned
            )
            duration_ms = int((time.time() - start_time) * 1000)
            self._track_call("PUT", endpoint, response.status_code, duration_ms)
            return self._handle_response(response, "PUT", url)
        except requests.RequestException as e:
            duration_ms = int((time.time() - start_time) * 1000)
            self._track_call("PUT", endpoint, 0, duration_ms, str(e))
            logger.error(f"PUT {url} request failed: {e}")
            return []

    def patch(self, endpoint, data):
        url = f"{self.base_url}{endpoint}"
        start_time = time.time()
        try:
            cleaned = self._preprocess_payload(endpoint, data, "PATCH")
            response = self._exponential_retry(
                self._rate_limited_request, requests.patch, url, json=cleaned
            )
            duration_ms = int((time.time() - start_time) * 1000)
            self._track_call("PATCH", endpoint, response.status_code, duration_ms)
            return self._handle_response(response, "PATCH", url)
        except requests.RequestException as e:
            duration_ms = int((time.time() - start_time) * 1000)
            self._track_call("PATCH", endpoint, 0, duration_ms, str(e))
            logger.error(f"PATCH {url} request failed: {e}")
            return []

    def delete(self, endpoint):
        url = f"{self.base_url}{endpoint}"
        start_time = time.time()
        try:
            response = self._exponential_retry(
                self._rate_limited_request, requests.delete, url
            )
            duration_ms = int((time.time() - start_time) * 1000)
            self._track_call("DELETE", endpoint, response.status_code, duration_ms)
            response.raise_for_status()
            logger.debug(f"DELETE {url} succeeded")
            return True
        except requests.RequestException as e:
            duration_ms = int((time.time() - start_time) * 1000)
            self._track_call("DELETE", endpoint, 0, duration_ms, str(e))
            logger.error(f"DELETE {url} failed: {e}")
            return False

    # === Convenience methods ===
    def get_sites(self):
        return self.get_all_paginated("/api/sites", key_field="id")

    def get_site_clusters(self):
        def flatten_clusters(clusters):
            flat = {}
            stack = list(clusters)
            while stack:
                node = stack.pop()
                children = node.pop("children", [])
                if "id" in node:
                    flat[str(node["id"])] = node
                stack.extend(children)
            return flat

        root_clusters = self.get("/api/site_clusters")
        if isinstance(root_clusters, list) and root_clusters:
            return flatten_clusters(root_clusters)
        return {}

    def get_titles(self):
        return self.get_all_paginated("/api/user_titles", key_field="id")

    def get_users(self):
        return self.get_all_paginated("/api/users", key_field="emp_id")

    def get_users_by_id(self):
        """Get users indexed by their user ID instead of employee ID"""
        return self.get_all_paginated("/api/users", key_field="id")

    def get_roles(self):
        return self.get_all_paginated("/api/roles", key_field="id")

    def get_asset_types(self):
        return self.get_all_paginated("/api/asset_types", key_field="id")

    def create_title(self, title_data: dict):
        return self.post("/api/user_titles", title_data)

    def create_site(self, site_data: dict):
        return self.post("/api/sites", site_data)

    def create_cluster(self, cluster_data: dict):
        return self.post("/api/site_clusters", cluster_data)

    def patch_cluster(self, cluster_id: int, cluster_data: dict):
        return self.patch(f"/api/site_clusters/{cluster_id}", cluster_data)

    def create_user(self, user_data: dict):
        return self.post("/api/users", user_data)

    def create_asset(self, asset_data: dict):
        """Create a new asset in SafetyAmp"""
        return self.post("/api/assets", asset_data)

    def update_asset(self, asset_id: str, asset_data: dict):
        """Update an existing asset in SafetyAmp"""
        return self.put(f"/api/assets/{asset_id}", asset_data)
