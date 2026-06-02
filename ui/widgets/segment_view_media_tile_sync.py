from core.models.segment import Segment
from ui.cache.segment_search_cache import SegmentSearchCache
from ui.cache.segment_preview_cache import SegmentPreviewCache
from ui.utils.project_media_paths import load_media_file_thumbnail
from ui.widgets.hover_media_preview import HoverMediaPreview


def sync_media_tile(
    *,
    segment: Segment,
    media_preview: HoverMediaPreview,
    preview_cache: SegmentPreviewCache,
    tile_size_px: int,
    search_cache: SegmentSearchCache,
    thumb_bytes: bytes | None = None,
) -> None:
    """Sync the segment detail view's Media tile with segment.media.

    Priority (first match wins):
    1. Empty state text - no media is selected yet.
    2. Saved file on disk - media persisted in project.json (file_path).
    3. Fresh preview bytes - e.g. right after clicking a result (thumb_bytes).
    4. Cached preview bytes - same URL as segment.media.url, from search cache.
    5. Fallback label - media exists but no drawable preview is available yet.
    """
    # 1) Empty state text when nothing is selected yet
    if segment.media is None:
        media_preview.clear_media()
        media_preview.set_placeholder_text("No media selected")
        return

    # 2) Persisted media (project folder / relative path in project.json)
    if getattr(segment.media, "file_path", None):
        pixmap = load_media_file_thumbnail(
            media=segment.media,
            tile_size_px=tile_size_px,
            reserved=48,
            preview_cache=preview_cache,
        )
        if pixmap is not None:
            media_preview.bind_from_media(media=segment.media)
            media_preview.set_thumbnail_pixmap(pixmap)
            return

    # 3) In-memory preview bytes (e.g. passed right after clicking a result tile)
    if thumb_bytes:
        media_preview.bind_from_media(media=segment.media, thumbnail_bytes=thumb_bytes)
        return

    # 4) Reuse search-cache thumbnail for this URL
    if getattr(segment.media, "url", None):
        cached_thumb = search_cache.thumb_bytes_for_url(segment.id, segment.media.url)
        if cached_thumb:
            media_preview.bind_from_media(
                media=segment.media, thumbnail_bytes=cached_thumb
            )
            return

    # 5) Nothing drawable yet, show a fallback label
    media_preview.bind_from_media(media=segment.media)
    media_preview.set_placeholder_text("Thumbnail error")