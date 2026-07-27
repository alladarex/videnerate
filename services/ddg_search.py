"""Best-effort DuckDuckGo image search without API keys."""

import re
import urllib.parse
import urllib.request

from core.models.media import MediaType
from headers import BROWSER_HEADERS, ddg_api_headers
from services.search_common import (
    HTTP_TIMEOUT_S,
    SearchResult,
    fetch_bytes,
    fetch_json,
)

# Log tag only. Unlike the stock providers, the attribution this module returns per
# result is that result's own page URL, never this constant.
SOURCE = "web"


def _ddg_vqd_from_html(html: str) -> str | None:
    """Extract DuckDuckGo vqd token required for image API requests."""
    # DuckDuckGo embeds a vqd token in the HTML/JS. Common patterns:
    # vqd='...'
    # vqd="..."
    m = re.search(r"vqd=['\"]([^'\"]+)['\"]", html)
    if not m:
        return None
    return m.group(1)


def fetch_web_image_results(query: str, *, limit: int = 10) -> list[SearchResult]:
    """Search the web for images through DuckDuckGo.

    Each result is credited to the page the image was found on.
    """
    q = query.strip()
    if not q:
        return []

    init_url = "https://duckduckgo.com/?" + urllib.parse.urlencode(
        {"q": q, "ia": "images"}
    )
    init_req = urllib.request.Request(init_url, headers=BROWSER_HEADERS)
    with urllib.request.urlopen(init_req, timeout=HTTP_TIMEOUT_S) as resp:
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
    payload = fetch_json(api_url, headers=ddg_api_headers(init_url))

    results = payload.get("results") or []
    items: list[tuple[str, str, str]] = []
    for r in results:
        if not isinstance(r, dict):
            continue
        image_url = r.get("image")
        thumb_url = r.get("thumbnail") or r.get("image")
        source_url = r.get("url")
        if not (
            isinstance(image_url, str)
            and image_url.startswith("http")
            and isinstance(thumb_url, str)
            and thumb_url.startswith("http")
            and isinstance(source_url, str)
            and source_url.startswith("http")
        ):
            continue
        items.append((image_url, thumb_url, source_url))
        if len(items) >= limit:
            break

    out: list[SearchResult] = []
    for image_url, thumb_url, source_url in items:
        thumb_bytes = fetch_bytes(thumb_url, headers=BROWSER_HEADERS, source=SOURCE)
        if thumb_bytes:
            out.append(
                SearchResult(
                    media_type=MediaType.IMAGE,
                    url=image_url,
                    thumb_bytes=thumb_bytes,
                    source=source_url,
                )
            )

    return out[:limit]