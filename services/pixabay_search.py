import json
import urllib.parse
import urllib.request

from config import PIXABAY_API_KEY
from headers import VIDENERATE_HEADERS

SOURCE = "Pixabay"
_VIDEO_MIN_SHORT_EDGE = 720
_VIDEO_MAX_SHORT_EDGE = 1080
_PIXABAY_MIN_PER_PAGE = 3 # Pixabay requires at least 3 results
_PIXABAY_MAX_PER_PAGE = 200
_FILTER_HEADROOM = 3 # Multiplier for limit to ensure we get enough results after filtering
_VIDEO_QUALITIES = ("large", "medium", "small", "tiny")
_TIMEOUT_S = 12.0


def _is_valid_http_url(value: object) -> bool:
    return isinstance(value, str) and value.startswith("http")


def _fetch_json(url: str) -> dict:
    req = urllib.request.Request(url, headers=VIDENERATE_HEADERS)
    with urllib.request.urlopen(req, timeout=_TIMEOUT_S) as resp:
        payload = resp.read().decode("utf-8", errors="ignore")
    return json.loads(payload)


def _fetch_bytes(url: str) -> bytes | None:
    try:
        req = urllib.request.Request(url, headers=VIDENERATE_HEADERS)
        with urllib.request.urlopen(req, timeout=_TIMEOUT_S) as resp:
            data = resp.read()
        return data or None
    except Exception as e:
        print(f"[{SOURCE}] _fetch_bytes failed for {url}: {e}")
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
    query: str, *, limit: int = 10
) -> list[tuple[str, bytes, str]]:
    """Fetch (image_url, thumbnail_bytes, source) through Pixabay image search."""
    if not PIXABAY_API_KEY:
        return []
    q = query.strip()
    if not q:
        return []

    per_page = max(_PIXABAY_MIN_PER_PAGE, min(limit, _PIXABAY_MAX_PER_PAGE))
    url = "https://pixabay.com/api/?" + urllib.parse.urlencode(
        {
            "key": PIXABAY_API_KEY,
            "q": q,
            "per_page": per_page,
            "safesearch": "true",
        }
    )
    try:
        payload = _fetch_json(url)
    except Exception as e:
        print(f"[{SOURCE}] fetch_pixabay_image_results failed for query '{q}': {e}")
        return []

    out: list[tuple[str, bytes, str]] = []
    for result in payload.get("hits") or []:
        if not isinstance(result, dict):
            continue
        media_url, thumb_url = _pick_image_urls(result)
        if not media_url or not thumb_url:
            continue
        b = _fetch_bytes(thumb_url)
        if b:
            out.append((media_url, b, SOURCE))
        if len(out) >= limit:
            break
    return out[:limit]


def fetch_pixabay_video_results(
    query: str,
    *,
    limit: int = 10,
    min_duration_s: float,
) -> list[tuple[str, bytes, str]]:
    """Fetch (video_url, thumbnail_bytes, source) through Pixabay video search."""
    if not PIXABAY_API_KEY:
        return []
    q = query.strip()
    if not q:
        return []

    per_page = max(
        _PIXABAY_MIN_PER_PAGE,
        min(limit * _FILTER_HEADROOM, _PIXABAY_MAX_PER_PAGE),
    )
    url = "https://pixabay.com/api/videos/?" + urllib.parse.urlencode(
        {
            "key": PIXABAY_API_KEY,
            "q": q,
            "per_page": per_page,
            "safesearch": "true",
        }
    )
    try:
        payload = _fetch_json(url)
    except Exception as e:
        print(f"[{SOURCE}] fetch_pixabay_video_results failed for query '{q}': {e}")
        return []

    out: list[tuple[str, bytes, str]] = []
    for result in payload.get("hits") or []:
        if not isinstance(result, dict):
            continue
        duration = result.get("duration")
        if not isinstance(duration, (int, float)) or duration < min_duration_s:
            continue
        video_url, thumb_url = _pick_video_urls(result)
        if not video_url or not thumb_url:
            continue
        b = _fetch_bytes(thumb_url)
        if b:
            out.append((video_url, b, SOURCE))
        if len(out) >= limit:
            break
    return out[:limit]