from core.models.media import GifMedia, ImageMedia, Media, VideoMedia
from services.media_thumbnail import extract_video_frame_bytes
from ui.cache.segment_preview_cache import SegmentPreviewCache
from ui.utils.tile_pixmap import inner_preview_edge, load_scaled_pixmap, load_scaled_pixmap_from_path


def load_media_file_thumbnail(
    *,
    media: Media,
    tile_size_px: int,
    reserved: int,
    preview_cache: SegmentPreviewCache,
):
    """Load a thumbnail pixmap from a segment media file on disk."""
    file_path = getattr(media, "file_path", None)
    if not file_path:
        return None

    target = inner_preview_edge(tile_size_px, reserved=reserved)
    path = preview_cache.paths.file(file_path)
    pixmap = None
    if isinstance(media, VideoMedia):
        frame_bytes = extract_video_frame_bytes(path)
        if frame_bytes:
            pixmap = load_scaled_pixmap(frame_bytes, target)
    if isinstance(media, (ImageMedia, GifMedia)):
        pixmap = load_scaled_pixmap_from_path(path, target)
    return pixmap
