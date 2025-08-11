#!/usr/bin/env python3
"""
Unified DB health check wrapper that relies on the application's /health endpoint.
"""

import sys
import os
import time
import requests
from urllib.parse import urlparse, urlunparse

APP_HOST = os.getenv("APP_HOST", "http://localhost")
APP_PORT = int(os.getenv("HEALTH_CHECK_PORT", os.getenv("APP_PORT", "8080")))
TIMEOUT = int(os.getenv("HEALTH_CHECK_TIMEOUT", "10"))


def build_health_url(app_host: str, port: int) -> str:
    host = app_host.strip()
    if not host:
        host = "http://localhost"

    if not host.startswith(("http://", "https://")):
        host = f"http://{host}"

    parsed = urlparse(host)
    netloc = parsed.netloc or parsed.path

    if ":" in netloc:
        final_netloc = netloc
    else:
        final_netloc = f"{netloc}:{port}"

    final_path = "/health"
    return urlunparse((parsed.scheme or "http", final_netloc, final_path, "", "", ""))


HEALTH_URL = build_health_url(APP_HOST, APP_PORT)


def test_connection():
    print("🔍 Checking /health for database status...")
    start_time = time.time()
    try:
        resp = requests.get(HEALTH_URL, timeout=TIMEOUT)
        duration = time.time() - start_time
        print(f"GET {HEALTH_URL} -> {resp.status_code} in {duration:.2f}s")
        data = resp.json()
        db_status = data.get('database_status') or data.get('details', {}).get('database')
        print(f"Database status: {db_status}")
        return db_status in ("healthy", "degraded") and resp.status_code in (200, 503, 206)
    except Exception as e:
        print(f"❌ Health check failed: {type(e).__name__}: {str(e)}")
        return False


if __name__ == "__main__":
    success = test_connection()
    sys.exit(0 if success else 1) 