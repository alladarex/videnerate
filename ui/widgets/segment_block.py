from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QEvent, QObject, Qt, Signal
from PySide6.QtGui import QColor, QEnterEvent, QMouseEvent, QPixmap
from PySide6.QtWidgets import (
    QFrame,
    QGraphicsDropShadowEffect,
    QLabel,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from core.models.segment import Segment


def _default_plus_icon_path() -> Path:
    # ui/widgets/segment_block.py -> ui/
    return Path(__file__).resolve().parents[1] / "assets" / "icons" / "plus.png"


def column_count_for_viewport(
    viewport_width: int,
    *,
    block_size_px: int,
    grid_spacing: int,
    max_cols: int = 4,
) -> int:
    """How many segment block columns fit in a scroll area viewport (shared by project + segment views)."""
    cell = block_size_px + grid_spacing
    cols = max(1, (max(1, viewport_width) + grid_spacing) // max(1, cell))
    return min(max_cols, cols)


class SegmentBlock(QFrame):
    clicked = Signal()

    def __init__(self, segment: Segment, *, size_px: int = 180, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._segment = segment
        self._size_px = int(size_px)

        self.setObjectName("SegmentBlock")
        self.setFixedSize(self._size_px, self._size_px)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        root = QVBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(10)

        header_scroll = QScrollArea(self)
        header_scroll.setObjectName("SegmentBlockHeaderScroll")
        header_scroll.setWidgetResizable(True)
        header_scroll.setFrameShape(QFrame.Shape.NoFrame)
        header_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        header_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        header_scroll.setFixedHeight(28)
        header_scroll.setStyleSheet(
            """
            QScrollBar:horizontal { height: 0px; }
            QScrollBar:vertical { width: 0px; }
            """
        )

        header_label = QLabel(segment.text)
        header_label.setObjectName("SegmentBlockHeaderLabel")
        header_label.setWordWrap(False)
        header_label.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignHCenter)
        header_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        header_scroll.setWidget(header_label)
        root.addWidget(header_scroll)

        media_label = QLabel(self)
        media_label.setObjectName("SegmentBlockMediaPlaceholder")
        media_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        media_label.setMinimumHeight(1)

        if segment.media is None:
            icon_path = _default_plus_icon_path()
            pixmap = QPixmap(str(icon_path)) if icon_path.is_file() else QPixmap()
            if not pixmap.isNull():
                target = max(1, self._size_px - 20 - header_scroll.height() - root.spacing() - 20)
                target = max(1, int(target * 0.35))
                scaled = pixmap.scaled(
                    target,
                    target,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
                media_label.setPixmap(scaled)
            else:
                media_label.setText("+")
        else:
            # Media rendering will be implemented later.
            media_label.setText("Media")

        root.addWidget(media_label, 1)

        for w in (header_scroll, header_label, media_label):
            w.installEventFilter(self)

        self._shadow = QGraphicsDropShadowEffect(self)
        self._shadow.setBlurRadius(22)
        self._shadow.setOffset(0, 4)
        self._shadow.setColor(QColor(0, 0, 0, 85))
        self.setGraphicsEffect(self._shadow)

        self.setStyleSheet(
            """
            QFrame#SegmentBlock {
              border-radius: 10px;
              background: #141414;
            }
            QScrollArea#SegmentBlockHeaderScroll {
              background: transparent;
            }
            QLabel#SegmentBlockHeaderLabel {
              font-size: 14px;
              font-weight: 600;
              color: #eaeaea;
              background: transparent;
            }
            """
            # QLabel#SegmentBlockMediaPlaceholder {
            #   border: 1px dashed #444;
            #   border-radius: 8px;
            #   color: #888;
            # }
            # """
        )

    def enterEvent(self, event: QEnterEvent) -> None:
        super().enterEvent(event)
        self._shadow.setColor(QColor(0, 0, 0, 165))

    def leaveEvent(self, event) -> None:
        super().leaveEvent(event)
        self._shadow.setColor(QColor(0, 0, 0, 85))

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


class EmptySegmentSquare(QFrame):
    """Same outer size and chrome as SegmentBlock, empty interior (placeholder grid cells)."""

    def __init__(self, *, size_px: int = 180, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._size_px = int(size_px)
        self.setObjectName("SegmentBlock")
        self.setFixedSize(self._size_px, self._size_px)

        self._shadow = QGraphicsDropShadowEffect(self)
        self._shadow.setBlurRadius(22)
        self._shadow.setOffset(0, 4)
        self._shadow.setColor(QColor(0, 0, 0, 85))
        self.setGraphicsEffect(self._shadow)

        self.setStyleSheet(
            """
            QFrame#SegmentBlock {
              border-radius: 10px;
              background: #141414;
            }
            """
        )

    def enterEvent(self, event: QEnterEvent) -> None:
        super().enterEvent(event)
        self._shadow.setColor(QColor(0, 0, 0, 165))

    def leaveEvent(self, event) -> None:
        super().leaveEvent(event)
        self._shadow.setColor(QColor(0, 0, 0, 85))

