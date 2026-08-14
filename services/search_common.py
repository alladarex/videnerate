"""The search result type, HTTP helpers, and tuning constants shared by every provider.

The providers differ only in their request headers and in how they read each API's
payload, so the request/download code lives here and each provider passes its own
'headers'.
"""

import json
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import Any

from core.models.media import MediaType

HTTP_TIMEOUT_S = 12.0

# Accepted video stream resolution, measured on the short edge.
VIDEO_MIN_SHORT_EDGE = 720
VIDEO_MAX_SHORT_EDGE = 1080

# Multiplier for limit to ensure we get enough results after filtering
FILTER_HEADROOM = 3


@dataclass
class SearchResult:
    """One media result found for a search query.

    The same object travels from the provider that found it through the search runner
    and the cache to the result tile, nothing converts it along the way.

    'url' points at the full-size media, 'thumb_bytes' is the already-downloaded
    preview image shown on the tile, and 'source' is the credit displayed for the
    media and burned into the exported video: the provider name for stock media
    (Pexels, Pixabay, Giphy), or the page it was found on for web results.

    'page_url' is where this item lives on the provider's own site. Pexels and
    Pixabay both require their results to be credited with a link back, so the
    result tile turns their mark into a link to this.
    """

    media_type: MediaType
    url: str
    thumb_bytes: bytes
    source: str
    page_url: str | None = None


def is_valid_http_url(value: object) -> bool:
    return isinstance(value, str) and value.startswith("http")


def fetch_json(url: str, *, headers: dict[str, str]) -> dict[str, Any]:
    """Fetch and parse a JSON API response. Network and parse errors propagate."""
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT_S) as resp:
        payload = resp.read().decode("utf-8", errors="ignore")
    return json.loads(payload)


def fetch_bytes(url: str, *, headers: dict[str, str], log_tag: str) -> bytes | None:
    """Download raw bytes (thumbnails). Returns None on failure."""
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT_S) as resp:
            data = resp.read()
        return data or None
    except Exception as exc:
        print(f"[{log_tag}] fetch_bytes failed for {url}: {exc}")
        return None


# One pool for every thumbnail download in the app. Provider calls run in
# 'run_distributed_search's own pool and block on these fetches, which is what
# keeps this one safe: nothing inside it waits on it, so it cannot fill up with
# threads waiting for threads. Never shut down, so a long fetch  can delay app exit
# by at most HTTP_TIMEOUT_S.
_THUMBNAIL_POOL = ThreadPoolExecutor(max_workers=8)


def fetch_bytes_parallel(
    urls: list[str], *, headers: dict[str, str], log_tag: str
) -> list[bytes | None]:
    """Download every url at once, keeping order. None where a fetch failed."""
    futures = [
        _THUMBNAIL_POOL.submit(fetch_bytes, url, headers=headers, log_tag=log_tag) for url in urls
    ]
    return [future.result() for future in futures]
