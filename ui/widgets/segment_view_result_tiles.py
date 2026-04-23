from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QMouseEvent, QPixmap
from PySide6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget

from ui.styles.qss import MUTED_LABEL
from ui.widgets.tile_frame import TileFrame
from ui.widgets.tile_pixmap import (
    inner_preview_edge,
    load_scaled_pixmap,
    load_scaled_pixmap_from_path,
)


def _icon_path(name: str) -> Path:
    # ui/widgets/segment_view_result_tiles.py -> ui/
    return Path(__file__).resolve().parents[1] / "assets" / "icons" / name


_ICON_PIXMAP_CACHE: dict[str, QPixmap | None] = {}


def _cached_icon_pixmap(icon_filename: str) -> QPixmap | None:
    cached = _ICON_PIXMAP_CACHE.get(icon_filename)
    if cached is not None:
        return cached
    pixmap = load_scaled_pixmap_from_path(_icon_path(icon_filename), 16)
    _ICON_PIXMAP_CACHE[icon_filename] = pixmap
    return pixmap


class _BaseResultTile(TileFrame):
    def __init__(
        self,
        *,
        size_px: int,
        icon_filename: str,
        placeholder_text: str,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(size_px=size_px, parent=parent, hover_shadow=True)
        self._placeholder_text = placeholder_text
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        root = QVBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(8)

        icon_row = QHBoxLayout()
        icon_row.setContentsMargins(0, 0, 0, 0)
        icon_row.setSpacing(0)

        self._icon_label = QLabel(self)
        self._icon_label.setFixedSize(18, 18)
        self._icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._icon_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        icon = _cached_icon_pixmap(icon_filename)
        if icon is not None:
            self._icon_label.setPixmap(icon)
            self._icon_label.setText("")
        else:
            self._icon_label.setText("•")
        icon_row.addWidget(self._icon_label, 0, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        icon_row.addStretch(1)
        root.addLayout(icon_row, 0)

        self._label = QLabel(self)
        self._label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._label.setStyleSheet(MUTED_LABEL)
        self._label.setText(placeholder_text)
        self._label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        root.addWidget(self._label, 1)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)

    def set_thumbnail_bytes(self, data: bytes) -> None:
        target = inner_preview_edge(self.width(), reserved=40)
        pixmap = load_scaled_pixmap(data, target)
        if pixmap is None:
            self._label.setText(self._placeholder_text)
            return
        self._label.setPixmap(pixmap)
        self._label.setText("")


class ImageTile(_BaseResultTile):

    clicked = Signal()

    def __init__(self, *, size_px: int, parent: QWidget | None = None) -> None:
        super().__init__(
            size_px=size_px,
            icon_filename="image-w.png",
            placeholder_text="Image failed",
            parent=parent,
        )


class VideoTile(_BaseResultTile):

    clicked = Signal()

    def __init__(self, *, size_px: int, parent: QWidget | None = None) -> None:
        super().__init__(
            size_px=size_px,
            icon_filename="video-w.png",
            placeholder_text="Video failed",
            parent=parent,
        )


class GifTile(_BaseResultTile):

    clicked = Signal()

    def __init__(self, *, size_px: int, parent: QWidget | None = None) -> None:
        super().__init__(
            size_px=size_px,
            icon_filename="gif-w.png",
            placeholder_text="GIF failed",
            parent=parent,
        )

