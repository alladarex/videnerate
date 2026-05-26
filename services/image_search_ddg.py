"""Best-effort DuckDuckGo image search without API keys."""

import json
import re
import urllib.parse
import urllib.request
from typing import Optional

from headers import BROWSER_HEADERS, ddg_api_headers


def _ddg_vqd_from_html(html: str) -> Optional[str]:
    """Extract DuckDuckGo vqd token required for image API requests."""
    # DuckDuckGo embeds a vqd token in the HTML/JS. Common patterns:
    # vqd='...'
    # vqd="..."
    m = re.search(r"vqd=['\"]([^'\"]+)['\"]", html)
    if not m:
        return None
    return m.group(1)


def _fetch_ddg_thumb_results(
    query: str, *, limit: int = 10, timeout_s: float = 12.0
) -> list[tuple[str, bytes]]:
    """Fetch DuckDuckGo image thumbnails and source URLs."""
    q = (query or "").strip()
    if not q:
        return []

    init_url = "https://duckduckgo.com/?" + urllib.parse.urlencode({"q": q, "ia": "images"})
    init_req = urllib.request.Request(init_url, headers=BROWSER_HEADERS)
    with urllib.request.urlopen(init_req, timeout=timeout_s) as resp:
        init_html = resp.read().decode("utf-8", errors="ignore")

    vqd = _ddg_vqd_from_html(init_html)
    if not vqd:
        return []

    api_url = "https://duckduckgo.com/i.js?" + urllib.parse.urlencode(
        {
            "l": "us-en",
            "o": "json",
            "q": q,
            "vqd": vqd,
            "f": "",
        }
    )
    api_req = urllib.request.Request(
        api_url, headers=ddg_api_headers(init_url)
    )

    with urllib.request.urlopen(api_req, timeout=timeout_s) as resp:
        data = resp.read().decode("utf-8", errors="ignore")

    try:
        payload = json.loads(data)
    except Exception:
        return []

    results = payload.get("results") or []
    items: list[tuple[str, str]] = []
    for r in results:
        if not isinstance(r, dict):
            continue
        full = r.get("image")
        thumb = r.get("thumbnail") or r.get("image")
        if isinstance(full, str) and full.startswith("http") and isinstance(thumb, str) and thumb.startswith("http"):
            items.append((full, thumb))
        if len(items) >= limit:
            break

    images: list[tuple[str, bytes]] = []
    for full_url, thumb_url in items[:limit]:
        try:
            img_req = urllib.request.Request(thumb_url, headers=BROWSER_HEADERS)
            with urllib.request.urlopen(img_req, timeout=timeout_s) as img_resp:
                b = img_resp.read()
            if b:
                images.append((full_url, b))
        except Exception:
            continue

    return images[:limit]


def fetch_google_image_results(
    query: str, *, limit: int = 10, timeout_s: float = 12.0
) -> list[tuple[str, bytes]]:
    """Fetch (source_url, thumbnail_bytes) results for a query (DDG only)."""
    imgs = _fetch_ddg_thumb_results(query, limit=limit, timeout_s=timeout_s)
    return imgs[:limit]