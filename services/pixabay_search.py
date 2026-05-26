import json
import urllib.parse
import urllib.request

from config import PIXABAY_API_KEY
from headers import VIDENERATE_HEADERS

_LOG_TAG = "pixabay"
_VIDEO_MIN_SHORT_EDGE = 720
_VIDEO_MAX_SHORT_EDGE = 1080
_VIDEO_QUALITIES = ("large", "medium", "small", "tiny")


def _is_valid_http_url(value: object) -> bool:
    return isinstance(value, str) and value.startswith("http")


def _fetch_json(url: str, *, timeout_s: float) -> dict:
    req = urllib.request.Request(url, headers=VIDENERATE_HEADERS)
    with urllib.request.urlopen(req, timeout=timeout_s) as resp:
        payload = resp.read().decode("utf-8", errors="ignore")
    return json.loads(payload)


def _fetch_bytes(url: str, *, timeout_s: float) -> bytes | None:
    try:
        req = urllib.request.Request(url, headers=VIDENERATE_HEADERS)
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:
            data = resp.read()
        return data or None
    except Exception as e:
        print(f"[{_LOG_TAG}] _fetch_bytes failed for {url}: {e}")
        return None


def _pick_image_urls(result: dict) -> tuple[str | None, str | None]:
    """Return (source_url, thumb_url) for an image search result."""
    source_url = result.get("largeImageURL")
    thumb_url = result.get("webformatURL")
    if not _is_valid_http_url(source_url) or not _is_valid_http_url(thumb_url):
        return (None, None)
    return (source_url, thumb_url)


def _pick_video_urls(result: dict) -> tuple[str | None, str | None]:
    """Return (video_url, thumb_url) for a video search result.

    Only picks streams with short edge in [720, 1080], skips videos with no
    such version (e.g. 4K-only uploads).
    """
    videos = result.get("videos")
    if not isinstance(videos, dict):
        return (None, None)

    video_url = None
    thumb_url = None
    for quality in _VIDEO_QUALITIES:
        stream = videos.get(quality)
        if not isinstance(stream, dict):
            continue
        link = stream.get("url")
        if not _is_valid_http_url(link):
            continue
        width = int(stream.get("width") or 0)
        height = int(stream.get("height") or 0)
        if width <= 0 or height <= 0:
            continue
        if _VIDEO_MIN_SHORT_EDGE <= min(width, height) <= _VIDEO_MAX_SHORT_EDGE:
            video_url = link
            thumb_url = stream.get("thumbnail")
            if not _is_valid_http_url(thumb_url):
                thumb_url = None
            break

    if not thumb_url:
        # Pixabay uses Vimeo for delivery, picture_id maps to a Vimeo CDN thumbnail
        picture_id = result.get("picture_id")
        if picture_id is not None:
            thumb_url = f"https://i.vimeocdn.com/video/{picture_id}_295x166.jpg"

    return (video_url, thumb_url)


def fetch_pixabay_image_results(
    query: str, *, limit: int = 10, timeout_s: float = 12.0
) -> list[tuple[str, bytes]]:
    if not PIXABAY_API_KEY:
        return []
    q = (query or "").strip()
    if not q:
        return []

    # Pixabay requires per_page >= 3
    per_page = max(3, min(limit, 80))
    url = "https://pixabay.com/api/?" + urllib.parse.urlencode(
        {
            "key": PIXABAY_API_KEY,
            "q": q,
            "per_page": per_page,
            "safesearch": "true",
        }
    )
    try:
        payload = _fetch_json(url, timeout_s=timeout_s)
    except Exception as e:
        print(f"[{_LOG_TAG}] fetch_pixabay_image_results failed for query '{q}': {e}")
        return []

    out: list[tuple[str, bytes]] = []
    for result in payload.get("hits") or []:
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


def fetch_pixabay_video_results(
    query: str, *, limit: int = 10, timeout_s: float = 12.0
) -> list[tuple[str, bytes]]:
    if not PIXABAY_API_KEY:
        return []
    q = (query or "").strip()
    if not q:
        return []

    # Pixabay requires per_page >= 3
    per_page = max(3, min(limit, 80))
    url = "https://pixabay.com/api/videos/?" + urllib.parse.urlencode(
        {
            "key": PIXABAY_API_KEY,
            "q": q,
            "per_page": per_page,
            "safesearch": "true",
        }
    )
    try:
        payload = _fetch_json(url, timeout_s=timeout_s)
    except Exception as e:
        print(f"[{_LOG_TAG}] fetch_pixabay_video_results failed for query '{q}': {e}")
        return []

    out: list[tuple[str, bytes]] = []
    for result in payload.get("hits") or []:
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
