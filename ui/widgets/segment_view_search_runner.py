from core.models.media import GIF_MEDIA, IMAGE_MEDIA, VIDEO_MEDIA
from services.giphy_search import fetch_giphy_gif_results
from services.ddg_search import fetch_google_image_results
from services.pexels_search import fetch_pexels_image_results, fetch_pexels_video_results
from services.pixabay_search import fetch_pixabay_image_results, fetch_pixabay_video_results


def run_distributed_search(
    *,
    query: str,
    limit: int,
    source_distribution: dict[str, int],
    min_video_duration_s: float,
) -> list[tuple[str, str, bytes, str]]:
    """Fetch from enabled sources and return merged (media_type, url, thumb_bytes, source)."""
    merged: list[tuple[str, str, bytes, str]] = []
    seen_urls: set[str] = set()

    def add_items(media_type: str, items: list[tuple[str, bytes, str]]) -> None:
        for url, thumb, source in items:
            if url in seen_urls:
                continue
            seen_urls.add(url)
            merged.append((media_type, url, bytes(thumb), source))
            if len(merged) >= limit:
                return

    def safe_fetch(fn):
        try:
            return fn() or []
        except Exception:
            return []

    google_share = source_distribution.get("google", 0)
    if google_share > 0:
        add_items(
            IMAGE_MEDIA,
            safe_fetch(lambda: fetch_google_image_results(query, limit=google_share)),
        )

    giphy_share = source_distribution.get("giphy", 0)
    if giphy_share > 0:
        add_items(
            GIF_MEDIA,
            safe_fetch(lambda: fetch_giphy_gif_results(query, limit=giphy_share)),
        )

    pexels_image_share = source_distribution.get("pexels_image", 0)
    if pexels_image_share > 0:
        add_items(
            IMAGE_MEDIA,
            safe_fetch(lambda: fetch_pexels_image_results(query, limit=pexels_image_share)),
        )

    pexels_video_share = source_distribution.get("pexels_video", 0)
    if pexels_video_share > 0:
        add_items(
            VIDEO_MEDIA,
            safe_fetch(
                lambda: fetch_pexels_video_results(
                    query,
                    limit=pexels_video_share,
                    min_duration_s=min_video_duration_s,
                )
            ),
        )

    pixabay_image_share = source_distribution.get("pixabay_image", 0)
    if pixabay_image_share > 0:
        add_items(
            IMAGE_MEDIA,
            safe_fetch(lambda: fetch_pixabay_image_results(query, limit=pixabay_image_share)),
        )

    pixabay_video_share = source_distribution.get("pixabay_video", 0)
    if pixabay_video_share > 0:
        add_items(
            VIDEO_MEDIA,
            safe_fetch(
                lambda: fetch_pixabay_video_results(
                    query,
                    limit=pixabay_video_share,
                    min_duration_s=min_video_duration_s,
                )
            ),
        )

    return merged[:limit]