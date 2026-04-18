from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from ui.styles.qss import MUTED_LABEL
from ui.widgets.tile_frame import TileFrame
from ui.widgets.tile_pixmap import inner_preview_edge, load_scaled_pixmap


class ImageTile(TileFrame):

    clicked = Signal()

    def __init__(self, *, size_px: int, parent: QWidget | None = None) -> None:
        super().__init__(size_px=size_px, parent=parent, hover_shadow=True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        root = QVBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(8)

        self._label = QLabel(self)
        self._label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._label.setStyleSheet(MUTED_LABEL)
        self._label.setText("Loading…")
        self._label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        root.addWidget(self._label, 1)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)

    def set_thumbnail_bytes(self, data: bytes) -> None:
        target = inner_preview_edge(self.width(), reserved=20)
        pixmap = load_scaled_pixmap(data, target)
        if pixmap is None:
            self._label.setText("Image failed")
            return
        self._label.setPixmap(pixmap)
        self._label.setText("")


class VideoTile(TileFrame):

    clicked = Signal()

    def __init__(self, *, size_px: int, parent: QWidget | None = None) -> None:
        super().__init__(size_px=size_px, parent=parent, hover_shadow=True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        root = QVBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(8)

        self._label = QLabel(self)
        self._label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._label.setStyleSheet(MUTED_LABEL)
        self._label.setText("Video")
        self._label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        root.addWidget(self._label, 1)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)

    def set_thumbnail_bytes(self, data: bytes) -> None:
        target = inner_preview_edge(self.width(), reserved=20)
        pixmap = load_scaled_pixmap(data, target)
        if pixmap is None:
            self._label.setText("Video failed")
            return
        self._label.setPixmap(pixmap)
        self._label.setText("")

