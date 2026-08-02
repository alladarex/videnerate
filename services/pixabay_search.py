import urllib.parse
from typing import Any

from config import PIXABAY_API_KEY
from core.models.media import MediaType
from headers import VIDENERATE_HEADERS
from services.search_common import (
    FILTER_HEADROOM,
    VIDEO_MAX_SHORT_EDGE,
    VIDEO_MIN_SHORT_EDGE,
    SearchResult,
    fetch_bytes,
    fetch_json,
    is_valid_http_url,
)

SOURCE = "Pixabay"
_PIXABAY_MIN_PER_PAGE = 3  # Pixabay requires at least 3 results
_PIXABAY_MAX_PER_PAGE = 200
_VIDEO_QUALITIES = ("large", "medium", "small", "tiny")


def _pick_image_urls(result: dict[str, Any]) -> tuple[str | None, str | None]:
    """Return (image_url, thumb_url) for an image search result."""
    image_url = result.get("largeImageURL")
    thumb_url = result.get("webformatURL")
    if not is_valid_http_url(image_url) or not is_valid_http_url(thumb_url):
        return (None, None)
    return (image_url, thumb_url)


def _pick_video_urls(result: dict[str, Any]) -> tuple[str | None, str | None]:
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
        if not is_valid_http_url(link):
            continue
        width = int(stream.get("width") or 0)
        height = int(stream.get("height") or 0)
        if width <= 0 or height <= 0:
            continue
        if VIDEO_MIN_SHORT_EDGE <= min(width, height) <= VIDEO_MAX_SHORT_EDGE:
            video_url = link
            thumb_url = stream.get("thumbnail")
            if not is_valid_http_url(thumb_url):
                thumb_url = None
            break

    if not thumb_url:
        # Pixabay uses Vimeo for delivery, picture_id maps to a Vimeo CDN thumbnail
        picture_id = result.get("picture_id")
        if picture_id is not None:
            thumb_url = f"https://i.vimeocdn.com/video/{picture_id}_295x166.jpg"

    return (video_url, thumb_url)


def fetch_pixabay_image_results(query: str, *, limit: int = 10) -> list[SearchResult]:
    """Search Pixabay for images."""
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
        payload = fetch_json(url, headers=VIDENERATE_HEADERS)
    except Exception as exc:
        print(f"[{SOURCE}] fetch_pixabay_image_results failed for query '{q}': {exc}")
        return []

    out: list[SearchResult] = []
    for result in payload.get("hits") or []:
        if not isinstance(result, dict):
            continue
        image_url, thumb_url = _pick_image_urls(result)
        if not image_url or not thumb_url:
            continue
        thumb_bytes = fetch_bytes(thumb_url, headers=VIDENERATE_HEADERS, log_tag=SOURCE)
        if thumb_bytes:
            out.append(
                SearchResult(
                    media_type=MediaType.IMAGE,
                    url=image_url,
                    thumb_bytes=thumb_bytes,
                    source=SOURCE,
                )
            )
        if len(out) >= limit:
            break
    return out[:limit]


def fetch_pixabay_video_results(
    query: str,
    *,
    limit: int = 10,
    min_duration_s: float,
) -> list[SearchResult]:
    """Search Pixabay for videos at least min_duration_s long."""
    if not PIXABAY_API_KEY:
        return []
    q = query.strip()
    if not q:
        return []

    per_page = max(
        _PIXABAY_MIN_PER_PAGE,
        min(limit * FILTER_HEADROOM, _PIXABAY_MAX_PER_PAGE),
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
        payload = fetch_json(url, headers=VIDENERATE_HEADERS)
    except Exception as exc:
        print(f"[{SOURCE}] fetch_pixabay_video_results failed for query '{q}': {exc}")
        return []

    out: list[SearchResult] = []
    for result in payload.get("hits") or []:
        if not isinstance(result, dict):
            continue
        duration = result.get("duration")
        if not isinstance(duration, (int, float)) or duration < min_duration_s:
            continue
        video_url, thumb_url = _pick_video_urls(result)
        if not video_url or not thumb_url:
            continue
        thumb_bytes = fetch_bytes(thumb_url, headers=VIDENERATE_HEADERS, log_tag=SOURCE)
        if thumb_bytes:
            out.append(
                SearchResult(
                    media_type=MediaType.VIDEO,
                    url=video_url,
                    thumb_bytes=thumb_bytes,
                    source=SOURCE,
                )
            )
        if len(out) >= limit:
            break
    return out[:limit]
