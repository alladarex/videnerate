from pathlib import Path

from PySide6.QtCore import QEvent, QObject, Qt, Signal
from PySide6.QtGui import QMouseEvent, QPixmap
from PySide6.QtWidgets import QFrame, QLabel, QScrollArea, QVBoxLayout, QWidget

from config import PROJECTS_DIR
from core.models.segment import Segment
from ui.styles.qss import HIDE_SCROLLBARS, SEGMENT_TILE_EXTRA, TILE_FRAME
from ui.widgets.tile_frame import TileFrame
from ui.widgets.tile_pixmap import (
    inner_preview_edge,
    load_scaled_pixmap,
    load_scaled_pixmap_from_path,
)


def _default_plus_icon_path() -> Path:
    # ui/widgets/segment_tile.py -> ui/
    return Path(__file__).resolve().parents[1] / "assets" / "icons" / "plus.png"


def column_count_for_viewport(
    viewport_width: int,
    *,
    tile_size_px: int,
    grid_spacing: int,
    max_cols: int = 4,
) -> int:
    """How many segment tiles fit in a scroll area viewport (shared by project + segment views)."""
    cell = tile_size_px + grid_spacing
    cols = max(1, (max(1, viewport_width) + grid_spacing) // max(1, cell))
    return min(max_cols, cols)


class SegmentTile(TileFrame):

    clicked = Signal()

    def __init__(
        self,
        segment: Segment,
        *,
        size_px: int = 180,
        project_title: str | None = None,
        parent: QWidget | None = None,
    ) -> None:
        self._segment = segment
        self._size_px = int(size_px)
        self._project_title = project_title
        self._thumb_bytes: bytes | None = None
        self._media_label: QLabel | None = None

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

        self._media_label = QLabel(self)
        self._media_label.setObjectName("SegmentTileMediaPlaceholder")
        self._media_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._media_label.setMinimumHeight(1)
        root.addWidget(self._media_label, 1)
        self.refresh_media()

        for w in (header_scroll, header_label, self._media_label):
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

    def set_thumbnail_bytes(self, data: bytes | None) -> None:
        self._thumb_bytes = data
        self.refresh_media()

    def _resolve_media_path(self, rel_or_abs: str) -> Path:
        p = Path(rel_or_abs)
        if p.is_absolute():
            return p
        if self._project_title:
            return (PROJECTS_DIR / self._project_title / p).resolve()
        return p.resolve()

    def refresh_media(self) -> None:
        if self._media_label is None:
            return

        # Prefer runtime thumbnail bytes if present
        if self._thumb_bytes:
            target = inner_preview_edge(self._size_px, reserved=40)
            pixmap = load_scaled_pixmap(self._thumb_bytes, target)
            if pixmap is not None:
                self._media_label.setPixmap(pixmap)
                self._media_label.setText("")
                return

        media = self._segment.media
        if media is None:
            icon_path = _default_plus_icon_path()
            icon_edge = max(1, int(self._size_px * 0.35))
            pixmap = load_scaled_pixmap_from_path(icon_path, icon_edge)
            if pixmap is not None:
                self._media_label.setPixmap(pixmap)
                self._media_label.setText("")
            else:
                self._media_label.setText("+")
            return

        # If persisted to file_path, render it.
        if getattr(media, "file_path", None):
            path = self._resolve_media_path(media.file_path)
            target = inner_preview_edge(self._size_px, reserved=40)
            pixmap = load_scaled_pixmap_from_path(path, target)
            if pixmap is not None:
                self._media_label.setPixmap(pixmap)
                self._media_label.setText("")
                return

        # Otherwise (URL-only, video, etc.) show a simple indicator for now
        self._media_label.setPixmap(QPixmap())
        self._media_label.setText("Media")


