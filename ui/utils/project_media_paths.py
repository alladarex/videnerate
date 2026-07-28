from PySide6.QtGui import QPixmap

from core.models.media import Media, MediaType
from services.media_thumbnail import extract_video_frame_bytes
from ui.cache.segment_preview_cache import SegmentPreviewCache
from ui.utils.tile_pixmap import inner_preview_edge, load_scaled_pixmap, load_scaled_pixmap_from_path


def load_media_file_thumbnail(
    *,
    media: Media,
    tile_size_px: int,
    reserved: int,
    preview_cache: SegmentPreviewCache,
) -> QPixmap | None:
    """Load a thumbnail pixmap from a segment media file on disk."""
    if not media.file_path:
        return None

    target = inner_preview_edge(tile_size_px, reserved=reserved)
    path = preview_cache.paths.file(media.file_path)
    if media.media_type is MediaType.VIDEO:
        frame_bytes = extract_video_frame_bytes(path)
        return load_scaled_pixmap(frame_bytes, target) if frame_bytes else None
    return load_scaled_pixmap_from_path(path, target)