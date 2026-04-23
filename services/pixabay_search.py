import json
import urllib.parse
import urllib.request

from config import PIXABAY_API_KEY


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
        print(f"[pixabay] _fetch_bytes failed for {url}: {e}")
        return None


def fetch_pixabay_image_results(
    query: str, *, limit: int = 10, timeout_s: float = 12.0
) -> list[tuple[str, bytes]]:
    if not PIXABAY_API_KEY:
        return []
    q = (query or "").strip()
    if not q:
        return []

    # Pixabay requires per_page >= 3
    per_page = max(3, min(limit, 200))
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
        print(f"[pixabay] fetch_pixabay_image_results failed for query '{q}': {e}")
        return []

    hits = payload.get("hits") or []
    out: list[tuple[str, bytes]] = []
    for hit in hits:
        if not isinstance(hit, dict):
            continue
        source_url = (
            hit.get("largeImageURL")
            or hit.get("webformatURL")
            or hit.get("imageURL")
            or hit.get("previewURL")
        )
        thumb_url = hit.get("webformatURL") or hit.get("previewURL") or source_url
        if not isinstance(source_url, str) or not isinstance(thumb_url, str):
            continue
        if not source_url.startswith("http") or not thumb_url.startswith("http"):
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
    per_page = max(3, min(limit, 200))
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
        print(f"[pixabay] fetch_pixabay_video_results failed for query '{q}': {e}")
        return []

    hits = payload.get("hits") or []
    out: list[tuple[str, bytes]] = []
    for hit in hits:
        if not isinstance(hit, dict):
            continue

        video_url = None
        thumb_url = None
        videos = hit.get("videos") or {}
        if isinstance(videos, dict):
            # Prefer higher-quality stream URLs when available.
            for quality in ("large", "medium", "small", "tiny"):
                stream = videos.get(quality)
                if not isinstance(stream, dict):
                    continue
                link = stream.get("url")
                if isinstance(link, str) and link.startswith("http"):
                    video_url = link
                    t = stream.get("thumbnail")
                    if isinstance(t, str) and t.startswith("http"):
                        thumb_url = t
                    break

            if not thumb_url:
                for stream in videos.values():
                    if not isinstance(stream, dict):
                        continue
                    t = stream.get("thumbnail")
                    if isinstance(t, str) and t.startswith("http"):
                        thumb_url = t
                        break

        if not video_url:
            continue
        if not thumb_url:
            picture_id = hit.get("picture_id")
            if picture_id is not None:
                thumb_url = f"https://i.vimeocdn.com/video/{picture_id}_295x166.jpg"

        if not isinstance(thumb_url, str) or not thumb_url.startswith("http"):
            continue

        b = _fetch_bytes(thumb_url, timeout_s=timeout_s)
        if b:
            out.append((video_url, b))
        if len(out) >= limit:
            break
    return out[:limit]
