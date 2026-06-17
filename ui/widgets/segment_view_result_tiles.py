from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QMouseEvent, QPixmap
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from collections.abc import Callable

from core.models.media import MediaType
from ui.widgets.hover_media_preview import HoverMediaPreview
from ui.cache.segment_preview_cache import SegmentPreviewCache
from ui.styles.qss import MUTED_LABEL
from ui.widgets.tile_frame import TileFrame
from ui.utils.tile_pixmap import (
    inner_preview_edge,
    load_scaled_pixmap,
    load_scaled_pixmap_from_path,
)
from ui.utils.ui_paths import icon_path


_ICON_PIXMAP_CACHE: dict[str, QPixmap | None] = {}


def _cached_icon_pixmap(icon_filename: str) -> QPixmap | None:
    cached = _ICON_PIXMAP_CACHE.get(icon_filename)
    if cached is not None:
        return cached
    pixmap = load_scaled_pixmap_from_path(icon_path(icon_filename), 16)
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
        self._size_px = size_px
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

        self._content_host = QWidget(self)
        self._content_host.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self._label = QLabel(self._content_host)
        self._label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._label.setStyleSheet(MUTED_LABEL)
        self._label.setText(placeholder_text)
        self._label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self._content_layout = QVBoxLayout(self._content_host)
        self._content_layout.setContentsMargins(0, 0, 0, 0)
        self._content_layout.addWidget(self._label, 1)
        root.addWidget(self._content_host, 1)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)

    def set_thumbnail_bytes(self, data: bytes) -> None:
        target = inner_preview_edge(self._size_px, reserved=40)
        pixmap = load_scaled_pixmap(data, target)
        if pixmap is None:
            self._label.setText(self._placeholder_text)
            return
        self._label.setPixmap(pixmap)
        self._label.setText("")


class _HoverPlayableTile(_BaseResultTile):
    def __init__(
        self,
        *,
        size_px: int,
        icon_filename: str,
        placeholder_text: str,
        media_url: str,
        preview_cache: SegmentPreviewCache,
        media_type: MediaType,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(
            size_px=size_px,
            icon_filename=icon_filename,
            placeholder_text=placeholder_text,
            parent=parent,
        )
        self._media_preview = HoverMediaPreview(
            tile_size_px=size_px,
            reserved=40,
            placeholder_text=placeholder_text,
            cache=preview_cache,
            parent=self._content_host,
        )
        self._media_preview.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self._media_preview.bind_from_search_url(
            media_type=media_type, media_url=media_url
        )
        self._content_layout.removeWidget(self._label)
        self._label.hide()
        self._content_layout.addWidget(self._media_preview, 1)

    def set_thumbnail_bytes(self, data: bytes) -> None:
        self._media_preview.set_thumbnail_bytes(data)

    def enterEvent(self, event) -> None:
        super().enterEvent(event)
        self._media_preview.on_hover_enter()

    def leaveEvent(self, event) -> None:
        super().leaveEvent(event)
        self._media_preview.on_hover_leave()

    def hideEvent(self, event) -> None:
        super().hideEvent(event)
        self._media_preview.on_hover_leave()

    def dispose(self) -> None:
        self._media_preview.dispose()


class ImageTile(_BaseResultTile):

    clicked = Signal()

    def __init__(self, *, size_px: int, parent: QWidget | None = None) -> None:
        super().__init__(
            size_px=size_px,
            icon_filename="image-w.png",
            placeholder_text="Image failed",
            parent=parent,
        )


class VideoTile(_HoverPlayableTile):

    clicked = Signal()

    def __init__(
        self,
        *,
        size_px: int,
        media_url: str,
        preview_cache: SegmentPreviewCache,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(
            size_px=size_px,
            icon_filename="video-w.png",
            placeholder_text="Video failed",
            media_url=media_url,
            preview_cache=preview_cache,
            media_type=MediaType.VIDEO,
            parent=parent,
        )


class GifTile(_HoverPlayableTile):

    clicked = Signal()

    def __init__(
        self,
        *,
        size_px: int,
        media_url: str,
        preview_cache: SegmentPreviewCache,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(
            size_px=size_px,
            icon_filename="gif-w.png",
            placeholder_text="GIF failed",
            media_url=media_url,
            preview_cache=preview_cache,
            media_type=MediaType.GIF,
            parent=parent,
        )


def build_result_tile(
    *,
    media_type: MediaType,
    url: str,
    thumb: bytes,
    source: str | None,
    size_px: int,
    preview_cache: SegmentPreviewCache,
    parent: QWidget,
    on_select: Callable[..., None],
) -> QWidget:
    """Build one search result tile and wire click to on_select(url, thumb, media_type=..., source=...)."""
    if media_type == MediaType.VIDEO:
        tile = VideoTile(
            size_px=size_px,
            media_url=url,
            preview_cache=preview_cache,
            parent=parent,
        )
        tile.set_thumbnail_bytes(thumb)
        tile.clicked.connect(
            lambda u=url, b=bytes(thumb), s=source: on_select(
                u, b, media_type=MediaType.VIDEO, source=s
            )
        )
        return tile
    if media_type == MediaType.IMAGE:
        tile = ImageTile(size_px=size_px, parent=parent)
        tile.set_thumbnail_bytes(thumb)
        tile.clicked.connect(
            lambda u=url, b=bytes(thumb), s=source: on_select(
                u, b, media_type=MediaType.IMAGE, source=s
            )
        )
        return tile
    if media_type == MediaType.GIF:
        tile = GifTile(
            size_px=size_px,
            media_url=url,
            preview_cache=preview_cache,
            parent=parent,
        )
        tile.set_thumbnail_bytes(thumb)
        tile.clicked.connect(
            lambda u=url, b=bytes(thumb), s=source: on_select(
                u, b, media_type=MediaType.GIF, source=s
            )
        )
        return tile
    raise ValueError(f"Unknown media type: {media_type}")