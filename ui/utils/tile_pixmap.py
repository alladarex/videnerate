"""Turn images and segment media into pixmaps a tile can draw.

Nothing here decides how big a thumbnail should be. A widget scales its pixmap to
the space it actually has.
"""

from pathlib import Path

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QPixmap

from core.models.media import Media, MediaType
from services.media_thumbnail import extract_video_frame_bytes
from ui.cache.segment_preview_cache import SegmentPreviewCache

# Ceiling on a pixmap a widget keeps to redraw from. Saved media and ffmpeg video
# frames are full resolution, so without this a tile holds megabytes to draw 200px.
MAX_SOURCE_EDGE_PX = 512


def scale_to_fit(pixmap: QPixmap, size: QSize) -> QPixmap:
    """Return 'pixmap' sized to sit inside 'size', keeping its shape."""
    return pixmap.scaled(
        size,
        Qt.AspectRatioMode.KeepAspectRatio,
        Qt.TransformationMode.SmoothTransformation,
    )


def _capped(pixmap: QPixmap) -> QPixmap:
    """Shrink anything bigger than a tile could ever need to draw."""
    if max(pixmap.width(), pixmap.height()) <= MAX_SOURCE_EDGE_PX:
        return pixmap
    return scale_to_fit(pixmap, QSize(MAX_SOURCE_EDGE_PX, MAX_SOURCE_EDGE_PX))


def load_pixmap(image_bytes: bytes) -> QPixmap | None:
    """Decode bytes for display, or None when they are not an image."""
    pixmap = QPixmap()
    if not pixmap.loadFromData(image_bytes) or pixmap.isNull():
        return None
    return _capped(pixmap)


def load_pixmap_from_path(path: Path) -> QPixmap | None:
    """Read an image file for display, or None when it cannot be read."""
    if not path.is_file():
        return None
    pixmap = QPixmap(str(path))
    if pixmap.isNull():
        return None
    return _capped(pixmap)


def load_media_file_thumbnail(
    *,
    media: Media,
    preview_cache: SegmentPreviewCache,
) -> QPixmap | None:
    """Load a segment's saved media file as a pixmap, or None when there is no file.

    A video has no still to read, so its first frame is pulled out with ffmpeg.
    """
    if not media.file_path:
        return None

    path = preview_cache.paths.file(media.file_path)
    if media.media_type is MediaType.VIDEO:
        frame_bytes = extract_video_frame_bytes(path)
        return load_pixmap(frame_bytes) if frame_bytes else None
    return load_pixmap_from_path(path)
