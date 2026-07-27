import urllib.parse

from config import GIPHY_API_KEY
from headers import VIDENERATE_HEADERS
from services.search_common import fetch_bytes, fetch_json, is_valid_http_url

SOURCE = "Giphy"


def _pick_url(images: dict, *names: str) -> str | None:
    for name in names:
        item = images.get(name)
        if not isinstance(item, dict):
            continue
        url = item.get("url")
        if is_valid_http_url(url):
            return url
    return None


def fetch_giphy_gif_results(
    query: str, *, limit: int = 10
) -> list[tuple[str, bytes, str]]:
    """Fetch (gif_url, thumb_bytes, source) through Giphy search."""
    if not GIPHY_API_KEY:
        return []
    q = query.strip()
    if not q:
        return []

    url = "https://api.giphy.com/v1/gifs/search?" + urllib.parse.urlencode(
        {
            "api_key": GIPHY_API_KEY,
            "q": q,
            "limit": max(1, min(int(limit), 50)),
            "rating": "g",
            "lang": "en",
        }
    )
    try:
        payload = fetch_json(url, headers=VIDENERATE_HEADERS)
    except Exception as e:
        print(f"[{SOURCE}] fetch_giphy_gif_results failed for query '{q}': {e}")
        return []

    items = payload.get("data") or []
    out: list[tuple[str, bytes, str]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        images = item.get("images") or {}
        if not isinstance(images, dict):
            continue

        gif_url = _pick_url(images, "original", "downsized", "fixed_width")
        thumb_url = _pick_url(
            images,
            "fixed_width_small_still",
            "fixed_width_still",
            "preview_gif",
            "fixed_width_small",
        )
        if not gif_url or not thumb_url:
            continue

        thumb_bytes = fetch_bytes(thumb_url, headers=VIDENERATE_HEADERS, source=SOURCE)
        if thumb_bytes:
            out.append((gif_url, thumb_bytes, SOURCE))
        if len(out) >= limit:
            break

    return out[:limit]