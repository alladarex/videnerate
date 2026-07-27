"""HTTP helpers and tuning constants shared by every media search provider.

The providers differ only in their request headers and in how they read each API's
payload, so the request/download code lives here and each provider passes its own
'headers'.
"""

import json
import urllib.request

HTTP_TIMEOUT_S = 12.0

# Accepted video stream resolution, measured on the short edge.
VIDEO_MIN_SHORT_EDGE = 720
VIDEO_MAX_SHORT_EDGE = 1080

# Multiplier for limit to ensure we get enough results after filtering
FILTER_HEADROOM = 3


def is_valid_http_url(value: object) -> bool:
    return isinstance(value, str) and value.startswith("http")


def fetch_json(url: str, *, headers: dict[str, str]) -> dict:
    """Fetch and parse a JSON API response. Network and parse errors propagate."""
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT_S) as resp:
        payload = resp.read().decode("utf-8", errors="ignore")
    return json.loads(payload)


def fetch_bytes(url: str, *, headers: dict[str, str], source: str) -> bytes | None:
    """Download raw bytes (thumbnails). Returns None on failure; 'source' is the log tag."""
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT_S) as resp:
            data = resp.read()
        return data or None
    except Exception as e:
        print(f"[{source}] fetch_bytes failed for {url}: {e}")
        return None