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
    is_valid_http_url,
)

# Log tag only. Each result is credited to its own page url, never to this.
_LOG_TAG = "web"


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

    init_url = "https://duckduckgo.com/?" + urllib.parse.urlencode({"q": q, "ia": "images"})
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
    for result in results:
        if not isinstance(result, dict):
            continue
        image_url = result.get("image")
        thumb_url = result.get("thumbnail") or result.get("image")
        page_url = result.get("url")
        if not (
            is_valid_http_url(image_url)
            and is_valid_http_url(thumb_url)
            and is_valid_http_url(page_url)
        ):
            continue
        items.append((image_url, thumb_url, page_url))
        if len(items) >= limit:
            break

    out: list[SearchResult] = []
    for image_url, thumb_url, page_url in items:
        thumb_bytes = fetch_bytes(thumb_url, headers=BROWSER_HEADERS, log_tag=_LOG_TAG)
        if thumb_bytes:
            out.append(
                SearchResult(
                    media_type=MediaType.IMAGE,
                    url=image_url,
                    thumb_bytes=thumb_bytes,
                    source=page_url,
                )
            )

    return out[:limit]
