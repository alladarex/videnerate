from PySide6.QtCore import QEvent
from PySide6.QtGui import QColor, QEnterEvent
from PySide6.QtWidgets import QFrame, QGraphicsDropShadowEffect, QWidget

from ui.styles.qss import TILE_FRAME


class TileFrame(QFrame):
    """Base frame for grid tiles."""

    def __init__(
        self,
        *,
        size_px: int,
        stylesheet: str = TILE_FRAME,
        object_name: str = "SegmentTile",
        hover_shadow: bool = False,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName(object_name)
        self.setFixedSize(int(size_px), int(size_px))
        self.setStyleSheet(stylesheet)
        self._hover_shadow = hover_shadow
        self._shadow = QGraphicsDropShadowEffect(self)
        self._shadow.setBlurRadius(22)
        self._shadow.setOffset(0, 4)
        self._shadow_normal = QColor(0, 0, 0, 85)
        self._shadow_hover = QColor(0, 0, 0, 165)
        self._shadow.setColor(self._shadow_normal)
        self.setGraphicsEffect(self._shadow)

    def enterEvent(self, event: QEnterEvent) -> None:
        super().enterEvent(event)
        if self._hover_shadow:
            self._shadow.setColor(self._shadow_hover)

    def leaveEvent(self, event: QEvent) -> None:
        super().leaveEvent(event)
        if self._hover_shadow:
            self._shadow.setColor(self._shadow_normal)
