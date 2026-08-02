import math
import urllib.parse
from typing import Any

from config import PEXELS_API_KEY
from core.models.media import MediaType
from headers import pexels_headers
from services.search_common import (
    FILTER_HEADROOM,
    VIDEO_MAX_SHORT_EDGE,
    VIDEO_MIN_SHORT_EDGE,
    SearchResult,
    fetch_bytes,
    fetch_json,
    is_valid_http_url,
)

SOURCE = "Pexels"
_PEXELS_MAX_PER_PAGE = 80


def _pick_image_urls(result: dict[str, Any]) -> tuple[str | None, str | None]:
    """Return (image_url, thumb_url) for an image search result."""
    src = result.get("src") or {}
    if not isinstance(src, dict):
        return (None, None)
    image_url = src.get("original") or src.get("large2x") or src.get("large")
    thumb_url = src.get("medium") or src.get("small") or src.get("tiny")
    if not is_valid_http_url(image_url) or not is_valid_http_url(thumb_url):
        return (None, None)
    return (image_url, thumb_url)


def _pick_video_urls(result: dict[str, Any]) -> tuple[str | None, str | None]:
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
        if not is_valid_http_url(link):
            continue
        width = int(f.get("width") or 0)
        height = int(f.get("height") or 0)
        if width <= 0 or height <= 0:
            continue
        if VIDEO_MIN_SHORT_EDGE <= min(width, height) <= VIDEO_MAX_SHORT_EDGE:
            video_url = link
            break

    for pic in result.get("video_pictures") or []:
        if not isinstance(pic, dict):
            continue
        thumb_url = pic.get("picture")
        if is_valid_http_url(thumb_url):
            break
        thumb_url = None

    return (video_url, thumb_url)


def fetch_pexels_image_results(query: str, *, limit: int = 10) -> list[SearchResult]:
    """Search Pexels for images."""
    if not PEXELS_API_KEY:
        return []
    q = query.strip()
    if not q:
        return []

    per_page = min(limit, _PEXELS_MAX_PER_PAGE)
    url = "https://api.pexels.com/v1/search?" + urllib.parse.urlencode(
        {"query": q, "per_page": per_page}
    )
    try:
        payload = fetch_json(url, headers=pexels_headers())
    except Exception as exc:
        print(f"[{SOURCE}] fetch_pexels_image_results failed for query '{q}': {exc}")
        return []

    out: list[SearchResult] = []
    for result in payload.get("photos") or []:
        if not isinstance(result, dict):
            continue
        image_url, thumb_url = _pick_image_urls(result)
        if not image_url or not thumb_url:
            continue
        thumb_bytes = fetch_bytes(thumb_url, headers=pexels_headers(), log_tag=SOURCE)
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


def fetch_pexels_video_results(
    query: str,
    *,
    limit: int = 10,
    min_duration_s: float,
) -> list[SearchResult]:
    """Search Pexels for videos at least min_duration_s long."""
    if not PEXELS_API_KEY:
        return []
    q = query.strip()
    if not q:
        return []

    per_page = min(limit * FILTER_HEADROOM, _PEXELS_MAX_PER_PAGE)
    params: dict[str, str | int] = {
        "query": q,
        "per_page": per_page,
        "min_duration": math.ceil(min_duration_s),
    }
    url = "https://api.pexels.com/videos/search?" + urllib.parse.urlencode(params)
    try:
        payload = fetch_json(url, headers=pexels_headers())
    except Exception as exc:
        print(f"[{SOURCE}] fetch_pexels_video_results failed for query '{q}': {exc}")
        return []

    out: list[SearchResult] = []
    for result in payload.get("videos") or []:
        if not isinstance(result, dict):
            continue
        video_url, thumb_url = _pick_video_urls(result)
        if not video_url or not thumb_url:
            continue
        thumb_bytes = fetch_bytes(thumb_url, headers=pexels_headers(), log_tag=SOURCE)
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
