from core.models.segment import Segment
from ui.cache.segment_search_cache import SegmentSearchCache
from ui.widgets.hover_media_preview import HoverMediaPreview


def sync_media_tile(
    *,
    segment: Segment,
    media_preview: HoverMediaPreview,
    search_cache: SegmentSearchCache,
    thumb_bytes: bytes | None = None,
) -> None:
    """Sync the segment detail view's Media tile with segment.media.

    Priority (first match wins):
    1. Empty state text - no media is selected yet.
    2. Saved file on disk, then 'thumb_bytes' if the caller passed any - see 'show_media'.
    3. The search cache, looked up by media url.
    4. Fallback label - media exists but no drawable preview is available yet.

    Steps 2 and 3 usually reach the same image and differ only in how they get it.
    Only the click that attaches media passes 'thumb_bytes' in, because that caller
    already holds the SearchResult. Every later redraw of this tile (resize, result
    clear, segment switch) passes nothing, so step 3 looks the same bytes up again.
    Once the project is saved, 'file_path' is set and step 2 wins outright.

    Step 3 exists here and not in the project grid because only this view has a
    search cache to consult.
    """
    # 1) Empty state text when nothing is selected yet
    if segment.media is None:
        media_preview.clear_media()
        media_preview.set_placeholder_text("No media selected")
        return

    # 2) Persisted media, then the bytes passed right after clicking a result tile
    if media_preview.show_media(segment.media, thumb_bytes=thumb_bytes):
        return

    # 3) Reuse search-cache thumbnail for this URL
    if segment.media.url:
        cached_thumb = search_cache.thumb_bytes_for_url(segment.id, segment.media.url)
        if cached_thumb:
            media_preview.bind_from_media(
                media=segment.media, thumbnail_bytes=cached_thumb
            )
            return

    # 4) Nothing drawable yet, show a fallback label
    media_preview.bind_from_media(media=segment.media)
    media_preview.set_placeholder_text("Thumbnail error")