#!/usr/bin/env python3
"""
Connectivity test script that uses the unified /health endpoint
"""

import os
import sys
import requests

SERVICE_URL = os.getenv("SERVICE_URL", "http://localhost:8080")


def main():
    print("🚀 Checking unified health endpoint...\n")
    try:
        resp = requests.get(f"{SERVICE_URL}/health", timeout=15)
        print(f"HTTP {resp.status_code}")
        data = resp.json()
        print("Status:", data.get("status"))
        checks = data.get("checks", {})
        for name, result in checks.items():
            print(
                f" - {name}: {result.get('status')} ({int(result.get('latency_ms', 0))} ms)"
            )
        # Exit code: 0 if healthy or degraded, 1 if unhealthy
        if data.get("status") == "unhealthy":
            return 1
        return 0
    except Exception as e:
        print(f"❌ Failed to call /health: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
