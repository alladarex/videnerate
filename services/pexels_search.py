import json
import urllib.parse
import urllib.request

from config import PEXELS_API_KEY


def _base_headers() -> dict[str, str]:
    if not PEXELS_API_KEY:
        return {}
    return {
        "Authorization": PEXELS_API_KEY,
        "User-Agent": "Videnerate",
    }


def _fetch_json(url: str, *, timeout_s: float) -> dict:
    req = urllib.request.Request(url, headers=_base_headers())
    with urllib.request.urlopen(req, timeout=timeout_s) as resp:
        payload = resp.read().decode("utf-8", errors="ignore")
    return json.loads(payload)


def _fetch_bytes(url: str, *, timeout_s: float) -> bytes | None:
    try:
        req = urllib.request.Request(url, headers=_base_headers())
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:
            data = resp.read()
        return data or None
    except Exception:
        return None


def fetch_pexels_image_results(
    query: str, *, limit: int = 10, timeout_s: float = 12.0
) -> list[tuple[str, bytes]]:
    if not PEXELS_API_KEY:
        return []
    q = (query or "").strip()
    if not q:
        return []

    per_page = max(1, min(int(limit), 80))
    url = "https://api.pexels.com/v1/search?" + urllib.parse.urlencode(
        {"query": q, "per_page": per_page}
    )
    try:
        payload = _fetch_json(url, timeout_s=timeout_s)
    except Exception:
        return []

    photos = payload.get("photos") or []
    out: list[tuple[str, bytes]] = []
    for p in photos:
        if not isinstance(p, dict):
            continue
        src = p.get("src") or {}
        if not isinstance(src, dict):
            continue
        # Use a direct image asset URL for persistence/download (not the Pexels page URL).
        source_url = src.get("original") or src.get("large2x") or src.get("large")
        thumb_url = src.get("medium") or src.get("small") or src.get("tiny")
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


def fetch_pexels_video_results(
    query: str, *, limit: int = 10, timeout_s: float = 12.0
) -> list[tuple[str, bytes]]:
    if not PEXELS_API_KEY:
        return []
    q = (query or "").strip()
    if not q:
        return []

    per_page = max(1, min(int(limit), 80))
    url = "https://api.pexels.com/videos/search?" + urllib.parse.urlencode(
        {"query": q, "per_page": per_page}
    )
    try:
        payload = _fetch_json(url, timeout_s=timeout_s)
    except Exception:
        return []

    videos = payload.get("videos") or []
    out: list[tuple[str, bytes]] = []
    for v in videos:
        if not isinstance(v, dict):
            continue
        video_url = None
        files = v.get("video_files") or []
        if isinstance(files, list):
            for f in files:
                if not isinstance(f, dict):
                    continue
                link = f.get("link")
                if isinstance(link, str) and link.startswith("http"):
                    video_url = link
                    break

        thumb_url = None
        pictures = v.get("video_pictures") or []
        if isinstance(pictures, list):
            for pic in pictures:
                if not isinstance(pic, dict):
                    continue
                link = pic.get("picture")
                if isinstance(link, str) and link.startswith("http"):
                    thumb_url = link
                    break

        if not video_url or not thumb_url:
            continue
        b = _fetch_bytes(thumb_url, timeout_s=timeout_s)
        if b:
            out.append((video_url, b))
        if len(out) >= limit:
            break
    return out[:limit]
