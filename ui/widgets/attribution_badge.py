"""The provider mark a search result tile shows to credit where it came from.

Pexels and Pixabay both require their API results to be credited with a link back
wherever those results are displayed, so every result tile from either one carries
its mark in the corner and clicking that mark opens the item's page on the
provider's own site.

Clicking the mark is not clicking the tile. The badge consumes the press so the
tile underneath does not read it as picking the media.
"""

from dataclasses import dataclass

from PySide6.QtCore import QSize, Qt, QUrl
from PySide6.QtGui import QDesktopServices, QMouseEvent
from PySide6.QtWidgets import QLabel, QWidget

from ui.utils.tile_pixmap import cached_icon_pixmap

# A bounding box, not the size drawn.
MARK_SIZE = QSize(58, 20)


@dataclass(frozen=True)
class _Provider:
    """A provider that has to be credited: the mark to draw, and its name for the tooltip."""

    icon_filename: str
    label: str


_PROVIDERS: dict[str, _Provider] = {
    "pexels": _Provider("pexels-w.png", "Pexels"),
    "pixabay": _Provider("pixabay-w.png", "Pixabay"),
}


class AttributionBadge(QLabel):
    """A tile corner mark crediting the provider, hidden when there is none to credit."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedSize(MARK_SIZE)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setStyleSheet("background: transparent;")
        self._link: str | None = None
        self.hide()

    def set_source(self, source: str | None, *, page_url: str | None = None) -> None:
        """Show the mark for 'source', or hide the badge when it is not a provider.

        'page_url' is the item's own page on the provider's site, which both Pexels
        and Pixabay always return, and is what clicking the mark opens.
        """
        provider = _PROVIDERS.get((source or "").strip().lower())
        pixmap = cached_icon_pixmap(provider.icon_filename, MARK_SIZE) if provider else None
        if provider is None or pixmap is None:
            self._link = None
            self.clear()
            self.setToolTip("")
            self.setCursor(Qt.CursorShape.ArrowCursor)
            self.hide()
            return

        self._link = page_url
        self.setPixmap(pixmap)
        self.setToolTip(f"View on {provider.label}")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.show()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        # Swallowed rather than passed up, the tile treats a press as picking the media.
        if self._link and event.button() == Qt.MouseButton.LeftButton:
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if self._link and event.button() == Qt.MouseButton.LeftButton:
            QDesktopServices.openUrl(QUrl(self._link))
            event.accept()
            return
        super().mouseReleaseEvent(event)
