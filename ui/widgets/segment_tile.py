from PySide6.QtCore import QEvent, QObject, Qt, Signal
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QFrame, QLabel, QScrollArea, QVBoxLayout, QWidget

from core.models.segment import Segment
from ui.styles.qss import HIDE_SCROLLBARS, SEGMENT_TILE_EXTRA, TILE_FRAME
from ui.widgets.hover_media_preview import HoverMediaPreview
from ui.cache.segment_preview_cache import SegmentPreviewCache
from ui.widgets.tile_frame import TileFrame
from ui.utils.tile_pixmap import (
    load_scaled_pixmap_from_path,
)
from ui.utils.ui_paths import icon_path


class SegmentTile(TileFrame):

    clicked = Signal()

    def __init__(
        self,
        segment: Segment,
        *,
        size_px: int = 180,
        preview_cache: SegmentPreviewCache,
        parent: QWidget | None = None,
    ) -> None:
        self._segment = segment
        self._size_px = size_px
        self._thumb_bytes: bytes | None = None
        self._media_preview: HoverMediaPreview
        self._preview_cache = preview_cache

        super().__init__(
            size_px=self._size_px,
            parent=parent,
            stylesheet=TILE_FRAME + SEGMENT_TILE_EXTRA,
            hover_shadow=True,
        )
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        root = QVBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(10)

        header_scroll = QScrollArea(self)
        header_scroll.setObjectName("SegmentTileHeaderScroll")
        header_scroll.setWidgetResizable(True)
        header_scroll.setFrameShape(QFrame.Shape.NoFrame)
        header_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        header_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        header_scroll.setFixedHeight(28)
        header_scroll.setStyleSheet(HIDE_SCROLLBARS)

        header_label = QLabel(segment.text)
        header_label.setObjectName("SegmentTileHeaderLabel")
        header_label.setWordWrap(False)
        header_label.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignHCenter)
        header_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        header_scroll.setWidget(header_label)
        root.addWidget(header_scroll)

        self._media_preview = HoverMediaPreview(
            tile_size_px=self._size_px,
            reserved=40,
            placeholder_text="Thumbnail error",
            preview_cache=self._preview_cache,
            parent=self,
        )
        self._media_preview.setObjectName("SegmentTileMediaPlaceholder")
        self._media_preview.setMinimumHeight(1)
        self._media_preview.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        root.addWidget(self._media_preview, 1)
        self.refresh_media()

        for w in (header_scroll, header_label, self._media_preview):
            w.installEventFilter(self)

    # Handle clicks on child elements (header, invisible scroll, media placeholder)
    def eventFilter(self, obj: QObject, event: QEvent) -> bool:
        if event.type() == QEvent.Type.MouseButtonPress:
            me = event
            if isinstance(me, QMouseEvent) and me.button() == Qt.MouseButton.LeftButton:
                self.clicked.emit()
        return super().eventFilter(obj, event)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)

    def enterEvent(self, event) -> None:
        super().enterEvent(event)
        self._media_preview.on_hover_enter()

    def leaveEvent(self, event) -> None:
        super().leaveEvent(event)
        self._media_preview.on_hover_leave()

    def dispose(self) -> None:
        self._media_preview.dispose()

    def set_thumbnail_bytes(self, data: bytes | None) -> None:
        self._thumb_bytes = data
        self.refresh_media()

    def refresh_media(self) -> None:
        """Draw this segment tile's media preview.

        Priority (first match wins):
        1. Empty state icon - segment has no media assigned yet.
        2. Saved file on disk, then 'self._thumb_bytes' - see 'show_media'.
        3. Fallback label - media exists but no drawable preview is available.

        Unlike the segment view, this tile keeps the bytes it was handed when the
        media was attached, so every redraw can reuse them and it never has to ask
        a cache for them back.
        """

        media = self._segment.media

        # 1) Empty state icon - segment has no media assigned yet
        if media is None:
            plus_path = icon_path("plus.png")
            icon_edge = max(1, int(self._size_px * 0.35))
            pixmap = load_scaled_pixmap_from_path(plus_path, icon_edge)
            self._media_preview.clear_media()
            self._media_preview.set_thumbnail_pixmap(pixmap)
            if pixmap is None:
                self._media_preview.set_placeholder_text("+")
            return

        # 2) Saved file on disk, then the bytes from the last runtime selection
        if self._media_preview.show_media(media, thumb_bytes=self._thumb_bytes):
            return

        # 3) Fallback label - media exists but no drawable preview is available
        self._media_preview.bind_from_media(media=media)
        self._media_preview.set_placeholder_text("Thumbnail error")