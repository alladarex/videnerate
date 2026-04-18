from pathlib import Path

from PySide6.QtWidgets import QLabel

from config import PROJECTS_DIR
from core.models.media import Media, VideoMedia, ImageMedia
from core.models.segment import Segment
from services.media_thumbnail import extract_video_frame_bytes
from ui.widgets.tile_pixmap import (
    inner_preview_edge,
    load_scaled_pixmap,
    load_scaled_pixmap_from_path,
)


def resolve_media_path(*, rel_or_abs: str, project_title: str) -> Path:
    p = Path(rel_or_abs)
    if p.is_absolute():
        return p
    return (PROJECTS_DIR / project_title / p).resolve()


def load_persisted_media_pixmap(
    *,
    media: Media,
    tile_size_px: int,
    reserved: int,
    project_title: str,
):
    """Load a pixmap from persisted media file."""
    file_path = getattr(media, "file_path", None)
    if not file_path:
        return None

    target = inner_preview_edge(tile_size_px, reserved=reserved)
    path = resolve_media_path(rel_or_abs=file_path, project_title=project_title)
    pixmap = None
    if isinstance(media, VideoMedia):
        frame_bytes = extract_video_frame_bytes(path)
        if frame_bytes:
            pixmap = load_scaled_pixmap(frame_bytes, target)
    if isinstance(media, ImageMedia):
        pixmap = load_scaled_pixmap_from_path(path, target)
    return pixmap


def refresh_media_preview(
    *,
    segment: Segment,
    media_preview_label: QLabel,
    tile_size_px: int,
    project_title: str,
    thumb_by_url: dict[str, bytes],
    thumb_bytes: bytes | None = None,
) -> None:
    """Draw the first tile's media preview.

        Priority (first match wins):
        1. Empty state text - no media is selected yet.
        2. Saved file on disk - media persisted in project.json (`file_path`).
        3. Fresh preview bytes - e.g. right after clicking a result (`thumb_bytes`).
        4. Cached preview bytes - same URL as `segment.media.url`, looked up in
           `thumb_by_url` (filled when search results were built; avoids re-downloading).
        5. Fallback label - media exists but no drawable preview is available yet.
    """
    # 1) Empty state text when nothing is selected yet
    if segment.media is None:
        media_preview_label.clear()
        media_preview_label.setText("No media selected")
        return

    # Preview area is roughly the tile minus padding, keep scaling stable across reflows
    target = inner_preview_edge(tile_size_px, reserved=48)

    # 2) Persisted media (project folder / relative path in project.json)
    if getattr(segment.media, "file_path", None):
        pixmap = load_persisted_media_pixmap(
            media=segment.media,
            tile_size_px=tile_size_px,
            reserved=48,
            project_title=project_title,
        )
        if pixmap is not None:
            media_preview_label.setPixmap(pixmap)
            media_preview_label.setText("")
            return

    # 3) In-memory preview bytes (e.g. passed right after clicking a result tile)
    # These are the same small preview bytes used for the result thumbnails
    if thumb_bytes:
        pixmap = load_scaled_pixmap(thumb_bytes, target)
        if pixmap is not None:
            media_preview_label.setPixmap(pixmap)
            media_preview_label.setText("")
            return

    # 4) Reuse cached preview for this URL (set when search results were created and cached)
    if getattr(segment.media, "url", None):
        cached_thumb = thumb_by_url.get(segment.media.url)
        if cached_thumb:
            pixmap = load_scaled_pixmap(cached_thumb, target)
            if pixmap is not None:
                media_preview_label.setPixmap(pixmap)
                media_preview_label.setText("")
                return

    # 5) Nothing drawable yet, show a fallback label
    media_preview_label.clear()
    media_preview_label.setText("Media selected")
