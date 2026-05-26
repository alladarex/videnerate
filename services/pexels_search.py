import json
import urllib.parse
import urllib.request

from config import PEXELS_API_KEY
from headers import pexels_headers

_LOG_TAG = "pexels"
_VIDEO_MIN_SHORT_EDGE = 720
_VIDEO_MAX_SHORT_EDGE = 1080


def _is_valid_http_url(value: object) -> bool:
    return isinstance(value, str) and value.startswith("http")


def _fetch_json(url: str, *, timeout_s: float) -> dict:
    req = urllib.request.Request(url, headers=pexels_headers())
    with urllib.request.urlopen(req, timeout=timeout_s) as resp:
        payload = resp.read().decode("utf-8", errors="ignore")
    return json.loads(payload)


def _fetch_bytes(url: str, *, timeout_s: float) -> bytes | None:
    try:
        req = urllib.request.Request(url, headers=pexels_headers())
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:
            data = resp.read()
        return data or None
    except Exception as e:
        print(f"[{_LOG_TAG}] _fetch_bytes failed for {url}: {e}")
        return None


def _pick_image_urls(result: dict) -> tuple[str | None, str | None]:
    """Return (source_url, thumb_url) for an image search result."""
    src = result.get("src") or {}
    if not isinstance(src, dict):
        return (None, None)
    source_url = src.get("original") or src.get("large2x") or src.get("large")
    thumb_url = src.get("medium") or src.get("small") or src.get("tiny")
    if not _is_valid_http_url(source_url) or not _is_valid_http_url(thumb_url):
        return (None, None)
    return (source_url, thumb_url)


def _pick_video_urls(result: dict) -> tuple[str | None, str | None]:
    """Return (video_url, thumb_url) for a video search result.

    Only picks streams with short edge in [720, 1080], skips videos with no
    such version (e.g. 4K-only uploads).
    """
    video_url = None
    thumb_url = None
    for f in result.get("video_files") or []:
        if not isinstance(f, dict):
            continue
        link = f.get("link")
        if not _is_valid_http_url(link):
            continue
        width = int(f.get("width") or 0)
        height = int(f.get("height") or 0)
        if width <= 0 or height <= 0:
            continue
        if _VIDEO_MIN_SHORT_EDGE <= min(width, height) <= _VIDEO_MAX_SHORT_EDGE:
            video_url = link
            break

    for pic in result.get("video_pictures") or []:
        if not isinstance(pic, dict):
            continue
        thumb_url = pic.get("picture")
        if _is_valid_http_url(thumb_url):
            break
        thumb_url = None

    return (video_url, thumb_url)


def fetch_pexels_image_results(
    query: str, *, limit: int = 10, timeout_s: float = 12.0
) -> list[tuple[str, bytes]]:
    if not PEXELS_API_KEY:
        return []
    q = (query or "").strip()
    if not q:
        return []

    per_page = max(1, min(limit, 80))
    url = "https://api.pexels.com/v1/search?" + urllib.parse.urlencode(
        {"query": q, "per_page": per_page}
    )
    try:
        payload = _fetch_json(url, timeout_s=timeout_s)
    except Exception as e:
        print(f"[{_LOG_TAG}] fetch_pexels_image_results failed for query '{q}': {e}")
        return []

    out: list[tuple[str, bytes]] = []
    for result in payload.get("photos") or []:
        if not isinstance(result, dict):
            continue
        source_url, thumb_url = _pick_image_urls(result)
        if not source_url or not thumb_url:
            continue
        b = _fetch_bytes(thumb_url, timeout_s=timeout_s)
        if b:
            out.append((source_url, b))
        if len(out) >= limit:
            break
    return out[:limit]


def fetch_pexels_video_results(
    query: str, *, limit: int = 10, timeout_s: float = 12.0
) -> list[tuple[str, bytes]]:
    if not PEXELS_API_KEY:
        return []
    q = (query or "").strip()
    if not q:
        return []

    per_page = max(1, min(limit, 80))
    url = "https://api.pexels.com/videos/search?" + urllib.parse.urlencode(
        {"query": q, "per_page": per_page}
    )
    try:
        payload = _fetch_json(url, timeout_s=timeout_s)
    except Exception as e:
        print(f"[{_LOG_TAG}] fetch_pexels_video_results failed for query '{q}': {e}")
        return []

    out: list[tuple[str, bytes]] = []
    for result in payload.get("videos") or []:
        if not isinstance(result, dict):
            continue
        video_url, thumb_url = _pick_video_urls(result)
        if not video_url or not thumb_url:
            continue
        b = _fetch_bytes(thumb_url, timeout_s=timeout_s)
        if b:
            out.append((video_url, b))
        if len(out) >= limit:
            break
    return out[:limit]