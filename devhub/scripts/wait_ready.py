"""Bounded readiness wait for CI local services."""

import time
import urllib.request

for attempt in range(30):
    try:
        for url in ("http://localhost:8001/health/ready", "http://localhost:5174"):
            with urllib.request.urlopen(url, timeout=2) as response:
                assert response.status == 200
        break
    except Exception:
        if attempt == 29:
            raise
        time.sleep(1)
