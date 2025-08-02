import requests
import time
from ratelimit import limits, sleep_and_retry
from config import settings
from utils.logger import get_logger

logger = get_logger("samsara")

class SamsaraAPI:
    CALLS = 25  # Vehicle endpoint limit (most restrictive)
    PERIOD = 1   # Per second
    MAX_RETRY_WAIT = 60

    def __init__(self):
        self.base_url = settings.SAMSARA_DOMAIN.rstrip("/")
        self.headers = {
            "Authorization": f"Bearer {settings.SAMSARA_API_KEY}",
            "Accept": "application/json"
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
            logger.debug(f"{method} {url} succeeded")
            return response.json()
        except requests.HTTPError as http_err:
            logger.error(f"{method} {url} HTTP error: {http_err} - {response.text}")
        except ValueError as parse_err:
            logger.error(f"{method} {url} parse error: {parse_err}")
        except Exception as err:
            logger.error(f"{method} {url} unexpected error: {err}")
        return {}

    def get_all_vehicles(self):
        logger.info("Fetching all vehicles from Samsara API...")
        endpoint = f"{self.base_url}/fleet/vehicles"
        params = {"limit": 100}
        vehicles = []
        cursor = None

        while True:
            if cursor:
                params["after"] = cursor

            response = self._exponential_retry(self._rate_limited_request, requests.get, endpoint, params=params)
            data = self._handle_response(response, "GET", endpoint)

            batch = data.get("data", [])
            if not batch:
                break

            vehicles.extend(batch)

            pagination = data.get("pagination", {})
            if pagination.get("hasNextPage"):
                cursor = pagination.get("endCursor")
            else:
                break

        logger.info(f"Retrieved {len(vehicles)} vehicles from Samsara.")
        return vehicles