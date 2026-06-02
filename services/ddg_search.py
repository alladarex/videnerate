"""Best-effort DuckDuckGo image search without API keys."""

import json
import re
import urllib.parse
import urllib.request
from typing import Optional

from headers import BROWSER_HEADERS, ddg_api_headers

_TIMEOUT_S = 12.0


def _ddg_vqd_from_html(html: str) -> Optional[str]:
    """Extract DuckDuckGo vqd token required for image API requests."""
    # DuckDuckGo embeds a vqd token in the HTML/JS. Common patterns:
    # vqd='...'
    # vqd="..."
    m = re.search(r"vqd=['\"]([^'\"]+)['\"]", html)
    if not m:
        return None
    return m.group(1)


def fetch_google_image_results(
    query: str, *, limit: int = 10
) -> list[tuple[str, bytes, str]]:
    """Fetch (image_url, thumbnail_bytes, source_url) through DuckDuckGo image search."""
    q = query.strip()
    if not q:
        return []

    init_url = "https://duckduckgo.com/?" + urllib.parse.urlencode(
        {"q": q, "ia": "images"}
    )
    init_req = urllib.request.Request(init_url, headers=BROWSER_HEADERS)
    with urllib.request.urlopen(init_req, timeout=_TIMEOUT_S) as resp:
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
    api_req = urllib.request.Request(api_url, headers=ddg_api_headers(init_url))

    with urllib.request.urlopen(api_req, timeout=_TIMEOUT_S) as resp:
        data = resp.read().decode("utf-8", errors="ignore")

    try:
        payload = json.loads(data)
    except Exception:
        return []

    results = payload.get("results") or []
    items: list[tuple[str, str, str]] = []
    for r in results:
        if not isinstance(r, dict):
            continue
        image_url = r.get("image")
        thumb = r.get("thumbnail") or r.get("image")
        source_url = r.get("url")
        if not (
            isinstance(image_url, str)
            and image_url.startswith("http")
            and isinstance(thumb, str)
            and thumb.startswith("http")
            and isinstance(source_url, str)
            and source_url.startswith("http")
        ):
            continue
        items.append((image_url, thumb, source_url))
        if len(items) >= limit:
            break

    images: list[tuple[str, bytes, str]] = []
    for image_url, thumb_url, source_url in items[:limit]:
        try:
            img_req = urllib.request.Request(thumb_url, headers=BROWSER_HEADERS)
            with urllib.request.urlopen(img_req, timeout=_TIMEOUT_S) as img_resp:
                b = img_resp.read()
            if b:
                images.append((image_url, b, source_url))
        except Exception:
            continue

    return images[:limit]