#!/usr/bin/env python3
"""
Unified connectivity test that queries the application /health endpoint.
"""

import os
import sys
import time
import requests

APP_HOST = os.getenv("APP_HOST", "http://localhost")
APP_PORT = int(os.getenv("HEALTH_CHECK_PORT", os.getenv("APP_PORT", "8080")))
HEALTH_URL = f"{APP_HOST}:{APP_PORT}/health"
TIMEOUT = int(os.getenv("HEALTH_CHECK_TIMEOUT", "10"))

def main():
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
        return 0 if status in ("healthy", "degraded") else 1
    except Exception as e:
        print(f"❌ Failed to query health endpoint: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main()) 