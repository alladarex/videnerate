from PySide6.QtCore import QEvent, QObject, QSize, Qt, Signal
from PySide6.QtGui import QEnterEvent, QMouseEvent
from PySide6.QtWidgets import QFrame, QLabel, QScrollArea, QVBoxLayout, QWidget

from core.models.segment import Segment
from ui.cache.segment_preview_cache import SegmentPreviewCache
from ui.styles.qss import HIDE_SCROLLBARS, SEGMENT_TILE_EXTRA, TILE_FRAME
from ui.utils.tile_pixmap import load_pixmap_from_path, scale_to_fit
from ui.utils.ui_paths import icon_path
from ui.widgets.hover_media_preview import HoverMediaPreview
from ui.widgets.tile_frame import TileFrame


class SegmentTile(TileFrame):
    clicked = Signal()

    def __init__(
        self,
        segment: Segment,
        *,
        size_px: int,
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

    def enterEvent(self, event: QEnterEvent) -> None:
        super().enterEvent(event)
        self._media_preview.on_hover_enter()

    def leaveEvent(self, event: QEvent) -> None:
        super().leaveEvent(event)
        self._media_preview.on_hover_leave()

    def dispose(self) -> None:
        self._media_preview.dispose()

    def set_thumbnail_bytes(self, thumb_bytes: bytes | None) -> None:
        self._thumb_bytes = thumb_bytes
        self.refresh_media()

    def refresh_media(self) -> None:
        """Draw this tile's preview from the segment's media.

        Priority (first match wins):
        1. Empty state icon, no media is attached yet.
        2. The media itself, see 'show_media', which draws it or falls back
           to a "Thumbnail error" label.

        The segment view runs the same ladder in 'SegmentViewGridController._sync_media_tile'.
        It has to store its remembered bytes per segment id because it reuses a single
        preview widget for every segment. This view builds one tile per segment,
        so a plain field is enough.
        """

        media = self._segment.media

        # 1) Empty state icon, no media is attached yet
        if media is None:
            self._show_empty_state()
            return

        # 2) The media itself, drawn from disk or from the bytes kept when it was attached
        self._media_preview.show_media(media, thumb_bytes=self._thumb_bytes)

    def _show_empty_state(self) -> None:
        """Show the 'add media' hint: a small plus icon, or a '+' if it will not load.

        Deliberately a fraction of the tile, so it reads as a hint rather than
        filling it the way a thumbnail does.
        """
        self._media_preview.clear_media()
        pixmap = load_pixmap_from_path(icon_path("plus.png"))
        if pixmap is None:
            self._media_preview.set_placeholder_text("+")
            return
        icon_edge = max(1, int(self._size_px * 0.35))
        self._media_preview.set_placeholder_pixmap(
            scale_to_fit(pixmap, QSize(icon_edge, icon_edge))
        )
