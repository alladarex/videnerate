"""Shared pixmap helpers for tile previews."""

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap


def inner_preview_edge(tile_size_px: int, *, reserved: int) -> int:
    """Return the square edge for inner preview rendering.

    Use one reserved constant per layout type (project tile, media body, result tile)
    so spacing choices stay explicit while scaling stays centralized.
    """
    return max(1, int(tile_size_px) - int(reserved))


def load_scaled_pixmap(data: bytes, target_edge: int) -> QPixmap | None:
    """Load bytes and return a smooth pixmap, or None if invalid."""
    pm = QPixmap()
    if not pm.loadFromData(data) or pm.isNull():
        return None
    edge = max(1, int(target_edge))
    return pm.scaled(
        edge,
        edge,
        Qt.AspectRatioMode.KeepAspectRatio,
        Qt.TransformationMode.SmoothTransformation,
    )


def load_scaled_pixmap_from_path(path: Path, target_edge: int) -> QPixmap | None:
    """Load image from disk and return a scaled pixmap, or None."""
    if not path.is_file():
        return None
    pm = QPixmap(str(path))
    if pm.isNull():
        return None
    edge = max(1, int(target_edge))
    return pm.scaled(
        edge,
        edge,
        Qt.AspectRatioMode.KeepAspectRatio,
        Qt.TransformationMode.SmoothTransformation,
    )
