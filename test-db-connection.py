#!/usr/bin/env python3
"""
Test database connectivity via the unified /health endpoint
"""

import sys
import os
import requests

SERVICE_URL = os.getenv("SERVICE_URL", "http://localhost:8080")


def main():
    print("🔍 Checking database health via /health\n")
    try:
        resp = requests.get(f"{SERVICE_URL}/health", timeout=15)
        print(f"HTTP {resp.status_code}")
        data = resp.json()
        db = data.get("checks", {}).get("database", {})
        status = db.get("status", "unknown")
        latency = int(db.get("latency_ms", 0))
        print(f"Database: {status} ({latency} ms)")
        return 0 if status == "healthy" else 1
    except Exception as e:
        print(f"❌ Failed to call /health: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
