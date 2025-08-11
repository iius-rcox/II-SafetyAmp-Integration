#!/usr/bin/env python3
"""
Unified connectivity test that queries the application /health endpoint and directly validates
external dependencies (SafetyAmp, Samsara, Viewpoint DB, Azure Key Vault).
"""

import os
import sys
import time
import requests
from urllib.parse import urlparse, urlunparse

from services.safetyamp_api import SafetyAmpAPI
from services.samsara_api import SamsaraAPI
from services.viewpoint_api import ViewpointAPI
from sqlalchemy import text
from config.azure_key_vault import AzureKeyVault

APP_HOST = os.getenv("APP_HOST", "http://localhost")
APP_PORT = int(os.getenv("HEALTH_CHECK_PORT", os.getenv("APP_PORT", "8080")))
TIMEOUT = int(os.getenv("HEALTH_CHECK_TIMEOUT", "10"))


def build_health_url(app_host: str, port: int) -> str:
    host = app_host.strip()
    if not host:
        host = "http://localhost"

    # Ensure scheme
    if not host.startswith(("http://", "https://")):
        host = f"http://{host}"

    parsed = urlparse(host)

    # If netloc is empty (e.g., host was just a hostname without scheme earlier), fix it
    netloc = parsed.netloc or parsed.path
    path = parsed.path if parsed.netloc else ""

    # If port already present in host, keep it; else append provided port
    if ":" in netloc:
        final_netloc = netloc
    else:
        final_netloc = f"{netloc}:{port}"

    # Always target '/health'
    final_path = "/health"

    return urlunparse((parsed.scheme or "http", final_netloc, final_path, "", "", ""))


HEALTH_URL = build_health_url(APP_HOST, APP_PORT)


def check_health_endpoint() -> bool:
    print("🚀 Checking unified service health...")
    print("= " * 25)
    try:
        start = time.time()
        resp = requests.get(HEALTH_URL, timeout=TIMEOUT)
        duration = time.time() - start
        print(f"GET {HEALTH_URL} -> {resp.status_code} in {duration:.2f}s")
        data = resp.json()
        status = data.get('status')
        print(f"Status: {status}")
        details = data.get('details', {})
        if details:
            print("Details:")
            for k, v in details.items():
                print(f" - {k}: {v}")
        if data.get('errors'):
            print("Recent errors:")
            for e in data['errors']:
                print(f" - {e}")
        print()
        print("Raw:")
        print(data)
        return status in ("healthy", "degraded") and resp.status_code in (200, 206, 503)
    except Exception as e:
        print(f"❌ Failed to query health endpoint: {e}")
        return False


def check_safetyamp() -> bool:
    print("🔐 Checking SafetyAmp API connectivity...")
    try:
        client = SafetyAmpAPI()
        # Lightweight endpoint; request a small page
        # Using internal 'get' which returns list from 'data'
        start = time.time()
        data = client.get("/api/user_titles", params={"limit": 1})
        duration = time.time() - start
        ok = isinstance(data, list)
        print(f"SafetyAmp /api/user_titles -> ok={ok} in {duration:.2f}s")
        return ok
    except Exception as e:
        print(f"❌ SafetyAmp check failed: {type(e).__name__}: {str(e)}")
        return False


def check_samsara() -> bool:
    print("🚚 Checking Samsara API connectivity...")
    try:
        client = SamsaraAPI()
        endpoint = f"{client.base_url}/fleet/vehicles"
        start = time.time()
        # Exercise rate-limited, retried request path with a small limit
        response = client._exponential_retry(
            client._rate_limited_request, requests.get, endpoint, params={"limit": 1}
        )
        # Handle like the client does
        data = client._handle_response(response, "GET", endpoint)
        duration = time.time() - start
        ok = isinstance(data, dict)
        print(f"Samsara /fleet/vehicles?limit=1 -> ok={ok} in {duration:.2f}s")
        return ok
    except Exception as e:
        print(f"❌ Samsara check failed: {type(e).__name__}: {str(e)}")
        return False


def check_viewpoint_db() -> bool:
    print("🗄️ Checking Viewpoint database connectivity...")
    try:
        vp = ViewpointAPI()
        start = time.time()
        with vp._get_connection() as conn:
            result = conn.exec_driver_sql("SELECT 1").scalar()
        duration = time.time() - start
        ok = result == 1 or result == 1.0
        print(f"Viewpoint SELECT 1 -> ok={ok} in {duration:.2f}s")
        return ok
    except Exception as e:
        print(f"❌ Viewpoint DB check failed: {type(e).__name__}: {str(e)}")
        return False


def check_key_vault() -> bool:
    print("🔑 Checking Azure Key Vault / secrets availability...")
    try:
        kv = AzureKeyVault()
        # If a vault is configured, try to fetch at least one required secret.
        # Otherwise, ensure required secrets exist in environment.
        required = [
            "SAFETYAMP-TOKEN",
            "SAMSARA-API-KEY",
        ]
        if os.getenv("SQL_AUTH_MODE", "managed_identity") == "sql_auth":
            required.extend(["SQL-USERNAME", "VISTA-SQL-PASSWORD"]) 
        # Attempt to read; kv.get_secret falls back to env automatically
        missing = []
        for name in required:
            val = kv.get_secret(name)
            if not val:
                missing.append(name)
        if missing:
            print(f"❌ Missing required secrets: {', '.join(missing)}")
            return False
        print("Azure Key Vault/env secrets -> ok=true")
        return True
    except Exception as e:
        print(f"❌ Key Vault check failed: {type(e).__name__}: {str(e)}")
        return False


def main():
    overall_ok = True

    if not check_health_endpoint():
        overall_ok = False

    # External dependency checks
    if not check_key_vault():
        overall_ok = False
    if not check_viewpoint_db():
        overall_ok = False
    if not check_safetyamp():
        overall_ok = False
    if not check_samsara():
        overall_ok = False

    return 0 if overall_ok else 1


if __name__ == "__main__":
    sys.exit(main()) 