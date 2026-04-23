import json
import urllib.parse
import urllib.request

from config import GIPHY_API_KEY


def _fetch_json(url: str, *, timeout_s: float) -> dict:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Videnerate",
        },
    )
    with urllib.request.urlopen(req, timeout=timeout_s) as resp:
        payload = resp.read().decode("utf-8", errors="ignore")
    return json.loads(payload)


def _fetch_bytes(url: str, *, timeout_s: float) -> bytes | None:
    try:
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": "Videnerate",
            },
        )
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:
            data = resp.read()
        return data or None
    except Exception as e:
        print(f"[giphy] _fetch_bytes failed for {url}: {e}")
        return None


def _pick_url(images: dict, *names: str) -> str | None:
    for name in names:
        item = images.get(name)
        if not isinstance(item, dict):
            continue
        url = item.get("url")
        if isinstance(url, str) and url.startswith("http"):
            return url
    return None


def fetch_giphy_gif_results(
    query: str, *, limit: int = 10, timeout_s: float = 12.0
) -> list[tuple[str, bytes]]:
    """Fetch (gif_url, thumbnail_bytes) from Giphy search."""
    if not GIPHY_API_KEY:
        return []
    q = (query or "").strip()
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
        payload = _fetch_json(url, timeout_s=timeout_s)
    except Exception as e:
        print(f"[giphy] fetch_giphy_gif_results failed for query '{q}': {e}")
        return []

    items = payload.get("data") or []
    out: list[tuple[str, bytes]] = []
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

        thumb = _fetch_bytes(thumb_url, timeout_s=timeout_s)
        if thumb:
            out.append((gif_url, thumb))
        if len(out) >= limit:
            break

    return out[:limit]
