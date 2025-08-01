import requests
import time
from ratelimit import limits, sleep_and_retry
from config import settings
from utils.logger import get_logger

logger = get_logger("safetyamp")

class SafetyAmpAPI:
    CALLS = 60
    PERIOD = 61  # in seconds
    MAX_RETRY_WAIT = 60

    def __init__(self):
        self.base_url = settings.SAFETYAMP_DOMAIN.rstrip("/")
        self.headers = {
            "Authorization": f"Bearer {settings.SAFETYAMP_TOKEN}",
            "Fqdn": settings.SAFETYAMP_FQDN,
            "Accept": "application/json",
            "Content-Type": "application/json"
        }

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
                    wait_time = min(2 ** retry, self.MAX_RETRY_WAIT)
                    logger.warning(f"Rate limited (429). Retrying in {wait_time} seconds...")
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

    def get(self, endpoint, params=None):
        url = f"{self.base_url}{endpoint}"
        try:
            response = self._exponential_retry(self._rate_limited_request, requests.get, url, params=params)
            return self._handle_response(response, "GET", url)
        except requests.RequestException as e:
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
        try:
            response = self._exponential_retry(self._rate_limited_request, requests.post, url, json=data)
            return self._handle_response(response, "POST", url)
        except requests.RequestException as e:
            logger.error(f"POST {url} request failed: {e}")
            return []

    def put(self, endpoint, data):
        url = f"{self.base_url}{endpoint}"
        try:
            response = self._exponential_retry(self._rate_limited_request, requests.put, url, json=data)
            return self._handle_response(response, "PUT", url)
        except requests.RequestException as e:
            logger.error(f"PUT {url} request failed: {e}")
            return []

    def patch(self, endpoint, data):
        url = f"{self.base_url}{endpoint}"
        try:
            response = self._exponential_retry(self._rate_limited_request, requests.patch, url, json=data)
            return self._handle_response(response, "PATCH", url)
        except requests.RequestException as e:
            logger.error(f"PATCH {url} request failed: {e}")
            return []

    def delete(self, endpoint):
        url = f"{self.base_url}{endpoint}"
        try:
            response = self._exponential_retry(self._rate_limited_request, requests.delete, url)
            response.raise_for_status()
            logger.debug(f"DELETE {url} succeeded")
            return True
        except requests.RequestException as e:
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

    def get_user(self, user_id: str):
        return self.get(f"/api/users/{user_id}")

    def get_roles(self):
        return self.get_all_paginated("/api/roles", key_field="id")

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