import time
import requests
from msal import ConfidentialClientApplication
from config import config
from utils.logger import get_logger
from services.api_call_tracker import get_api_call_tracker

logger = get_logger("msgraph_api")


class MSGraphAPI:
    def __init__(self):
        self.client_id = config.MS_GRAPH_CLIENT_ID
        self.client_secret = config.MS_GRAPH_CLIENT_SECRET
        self.tenant_id = config.MS_GRAPH_TENANT_ID
        self.scope = ["https://graph.microsoft.com/.default"]

        self.app = ConfidentialClientApplication(
            self.client_id,
            authority=f"https://login.microsoftonline.com/{self.tenant_id}",
            client_credential=self.client_secret,
        )

    def _get_access_token(self):
        result = self.app.acquire_token_for_client(scopes=self.scope)
        if "access_token" in result:
            return result["access_token"]
        else:
            logger.error(
                f"Failed to acquire access token: {result.get('error_description')}"
            )
            raise Exception("Failed to acquire access token")

    def _track_call(self, method: str, endpoint: str, status_code: int, duration_ms: int, error: str = None):
        """Record API call to tracker if available."""
        tracker = get_api_call_tracker()
        if tracker:
            tracker.record_call(
                service="msgraph",
                method=method,
                endpoint=endpoint,
                status_code=status_code,
                duration_ms=duration_ms,
                error_message=error,
            )

    def get_active_users(self):
        access_token = self._get_access_token()
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json",
        }
        endpoint = "https://graph.microsoft.com/v1.0/users?$filter=accountEnabled eq true&$select=id,employeeId,mail,userPrincipalName"
        users = {}

        while endpoint:
            start_time = time.time()
            response = requests.get(
                endpoint, headers=headers, timeout=config.HTTP_REQUEST_TIMEOUT
            )
            duration_ms = int((time.time() - start_time) * 1000)
            self._track_call("GET", "/v1.0/users", response.status_code, duration_ms)

            if response.status_code == 200:
                data = response.json()
                for user in data.get("value", []):
                    employee_id = user.get("employeeId")
                    email = user.get("mail")
                    if employee_id and email and "onmicrosoft" not in email.lower():
                        users[employee_id] = {
                            "id": user.get("id"),
                            "email": email,
                            "userPrincipalName": user.get("userPrincipalName"),
                        }
                endpoint = data.get("@odata.nextLink", None)
            else:
                logger.error(f"Failed to fetch active users: {response.text}")
                response.raise_for_status()

        logger.info("Fetched active users.")
        return users
