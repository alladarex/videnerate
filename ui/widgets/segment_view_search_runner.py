from concurrent.futures import ThreadPoolExecutor
from typing import Callable

from core.models.media import MediaType
from services.giphy_search import fetch_giphy_gif_results
from services.ddg_search import fetch_google_image_results
from services.pexels_search import fetch_pexels_image_results, fetch_pexels_video_results
from services.pixabay_search import fetch_pixabay_image_results, fetch_pixabay_video_results

# Type-hint alias: one provider call (args baked into each lambda) 
# Returns (url, thumb_bytes, source) tuple list

FetchFn = Callable[[], list[tuple[str, bytes, str]]]


def run_distributed_search(
    *,
    query: str,
    limit: int,
    source_distribution: dict[str, int],
    min_video_duration_s: float,
) -> list[tuple[MediaType, str, bytes, str]]:
    """Fetch from enabled sources and return merged (media_type, url, thumb_bytes, source)."""
    merged: list[tuple[MediaType, str, bytes, str]] = []
    seen_urls: set[str] = set()

    def add_items(media_type: MediaType, items: list[tuple[str, bytes, str]]) -> None:
        for url, thumb, source in items:
            if url in seen_urls:
                continue
            seen_urls.add(url)
            merged.append((media_type, url, bytes(thumb), source))
            if len(merged) >= limit:
                return

    # Run one provider, on failure log and return nothing so other sources still run
    def safe_fetch(fn: FetchFn) -> list[tuple[str, bytes, str]]:
        try:
            return fn() or []
        except Exception as e:
            print(f"[search] source fetch failed: {e}")
            return []

    # (media_type, fetch) pairs run concurrently, then merge in list order
    tasks: list[tuple[MediaType, FetchFn]] = []

    google_share = source_distribution.get("google", 0)
    if google_share > 0:
        tasks.append(
            (
                MediaType.IMAGE,
                lambda: fetch_google_image_results(query, limit=google_share),
            )
        )

    giphy_share = source_distribution.get("giphy", 0)
    if giphy_share > 0:
        tasks.append(
            (MediaType.GIF, lambda: fetch_giphy_gif_results(query, limit=giphy_share))
        )

    pexels_image_share = source_distribution.get("pexels_image", 0)
    if pexels_image_share > 0:
        tasks.append(
            (
                MediaType.IMAGE,
                lambda: fetch_pexels_image_results(query, limit=pexels_image_share),
            )
        )

    pexels_video_share = source_distribution.get("pexels_video", 0)
    if pexels_video_share > 0:
        tasks.append(
            (
                MediaType.VIDEO,
                lambda: fetch_pexels_video_results(
                    query,
                    limit=pexels_video_share,
                    min_duration_s=min_video_duration_s,
                )
            )
        )

    pixabay_image_share = source_distribution.get("pixabay_image", 0)
    if pixabay_image_share > 0:
        tasks.append(
            (
                MediaType.IMAGE,
                lambda: fetch_pixabay_image_results(query, limit=pixabay_image_share),
            )
        )

    pixabay_video_share = source_distribution.get("pixabay_video", 0)
    if pixabay_video_share > 0:
        tasks.append(
            (
                MediaType.VIDEO,
                lambda: fetch_pixabay_video_results(
                    query,
                    limit=pixabay_video_share,
                    min_duration_s=min_video_duration_s,
                )
            )
        )

    if not tasks:
        return []

    # Start every enabled source at once, each submit returns a Future (result later)
    with ThreadPoolExecutor(max_workers=len(tasks)) as executor:
        futures = [
            (media_type, executor.submit(safe_fetch, fn)) for media_type, fn in tasks
        ]
        # Wait for each source, then merge in the same order as tasks
        for media_type, future in futures:
            add_items(media_type, future.result())

    return merged[:limit]