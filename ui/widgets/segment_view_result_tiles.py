from collections.abc import Callable

from PySide6.QtCore import QEvent, QSize, Qt, Signal
from PySide6.QtGui import QEnterEvent, QHideEvent, QMouseEvent
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from core.models.media import MediaType
from services.search_common import SearchResult
from ui.cache.segment_preview_cache import SegmentPreviewCache
from ui.utils.tile_pixmap import cached_icon_pixmap
from ui.widgets.attribution_badge import AttributionBadge
from ui.widgets.hover_media_preview import HoverMediaPreview
from ui.widgets.tile_frame import TileFrame

_TYPE_ICON_SIZE = QSize(16, 16)

# Per media type: the badge icon, and the text shown when a thumbnail will not decode.
_TILE_LOOK_BY_TYPE: dict[MediaType, tuple[str, str]] = {
    MediaType.IMAGE: ("image-w.png", "Image failed"),
    MediaType.VIDEO: ("video-w.png", "Video failed"),
    MediaType.GIF: ("gif-w.png", "GIF failed"),
}


class _ResultTile(TileFrame):
    """One search result: a media-type badge above a preview of the result itself.

    Images use 'HoverMediaPreview' too, though they have nothing to hover, so all
    three types share one drawing path.

    The top row carries the media-type icon on the left and, for results from a
    provider that has to be credited, its clickable mark on the right.
    """

    clicked = Signal()

    def __init__(
        self,
        *,
        size_px: int,
        icon_filename: str,
        placeholder_text: str,
        url: str,
        preview_cache: SegmentPreviewCache,
        media_type: MediaType,
        source: str,
        page_url: str | None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(size_px=size_px, parent=parent, hover_shadow=True)
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
        icon = cached_icon_pixmap(icon_filename, _TYPE_ICON_SIZE)
        if icon is not None:
            self._icon_label.setPixmap(icon)
            self._icon_label.setText("")
        else:
            self._icon_label.setText("•")
        icon_row.addWidget(
            self._icon_label, 0, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop
        )
        icon_row.addStretch(1)

        self._attribution = AttributionBadge(self)
        self._attribution.set_source(source, page_url=page_url)
        icon_row.addWidget(
            self._attribution, 0, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignTop
        )
        root.addLayout(icon_row, 0)

        content_host = QWidget(self)
        content_host.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self._media_preview = HoverMediaPreview(
            placeholder_text=placeholder_text,
            preview_cache=preview_cache,
            parent=content_host,
        )
        self._media_preview.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self._media_preview.bind_from_search_url(media_type=media_type, media_url=url)
        content_layout = QVBoxLayout(content_host)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.addWidget(self._media_preview, 1)
        root.addWidget(content_host, 1)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)

    def set_thumbnail_bytes(self, thumb_bytes: bytes) -> None:
        self._media_preview.set_thumbnail_bytes(thumb_bytes)

    def enterEvent(self, event: QEnterEvent) -> None:
        super().enterEvent(event)
        self._media_preview.on_hover_enter()

    def leaveEvent(self, event: QEvent) -> None:
        super().leaveEvent(event)
        self._media_preview.on_hover_leave()

    def hideEvent(self, event: QHideEvent) -> None:
        super().hideEvent(event)
        self._media_preview.on_hover_leave()

    def dispose(self) -> None:
        self._media_preview.dispose()


def build_result_tile(
    result: SearchResult,
    *,
    size_px: int,
    preview_cache: SegmentPreviewCache,
    on_select: Callable[[SearchResult], None],
    parent: QWidget,
) -> QWidget:
    """Build one search result tile and wire its click to on_select(result)."""
    icon_filename, placeholder_text = _TILE_LOOK_BY_TYPE[result.media_type]
    tile = _ResultTile(
        size_px=size_px,
        icon_filename=icon_filename,
        placeholder_text=placeholder_text,
        url=result.url,
        preview_cache=preview_cache,
        media_type=result.media_type,
        source=result.source,
        page_url=result.page_url,
        parent=parent,
    )
    tile.set_thumbnail_bytes(result.thumb_bytes)
    tile.clicked.connect(lambda: on_select(result))
    return tile
