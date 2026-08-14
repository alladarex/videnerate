"""Footer navigation bar for the segment detail view.

This module owns the strip below the tile grid:
- previous/next arrows and their enabled state
- one clickable dot per segment, coloured by that segment's search state
- keeping the active dot scrolled into view
"""

from collections.abc import Callable, Sequence

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QFrame, QHBoxLayout, QPushButton, QScrollArea, QWidget

from core.models.segment import Segment
from ui.styles.qss import NAV_ARROW_BUTTON, TRANSPARENT_SCROLL, nav_dot_style, top_bar_style


class SegmentNavBar(QFrame):
    """Arrows and per-segment dots. Asks for a segment, never switches to one itself."""

    index_requested = Signal(int)

    _DOT_PX = 12
    _DOT_GAP_PX = 5

    def __init__(
        self,
        *,
        segments: Sequence[Segment],
        bar_height_px: int,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._segment_count = len(segments)
        self._current_index = 0
        self._dot_buttons: list[QPushButton] = []

        self.setObjectName("SegmentViewBottomBar")
        self.setFixedHeight(bar_height_px)
        self.setStyleSheet(top_bar_style("SegmentViewBottomBar"))

        self._nav_prev = self._build_arrow("‹", "Previous segment", self.go_prev)
        self._nav_next = self._build_arrow("›", "Next segment", self.go_next)

        self._dots_scroll = QScrollArea(self)
        self._dots_scroll.setWidgetResizable(True)
        self._dots_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self._dots_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._dots_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._dots_scroll.setStyleSheet(TRANSPARENT_SCROLL)

        dots_host = QWidget(self._dots_scroll)
        dots_layout = QHBoxLayout(dots_host)
        dots_layout.setContentsMargins(4, 0, 4, 0)
        dots_layout.setSpacing(self._DOT_GAP_PX)
        dots_layout.addStretch(0)

        for i, seg in enumerate(segments):
            btn = QPushButton(dots_host)
            btn.setObjectName("SegmentNavDot")
            btn.setFixedSize(self._DOT_PX, self._DOT_PX)
            btn.setFlat(True)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setToolTip(seg.text)
            btn.clicked.connect(lambda checked=False, idx=i: self.index_requested.emit(idx))
            dots_layout.addWidget(btn)
            self._dot_buttons.append(btn)

        dots_layout.addStretch(0)
        self._dots_scroll.setWidget(dots_host)

        inner = QHBoxLayout(self)
        inner.setContentsMargins(10, 8, 10, 8)
        inner.setSpacing(8)
        inner.addWidget(self._nav_prev)
        inner.addWidget(self._dots_scroll, 1)
        inner.addWidget(self._nav_next)

    def _build_arrow(self, glyph: str, tooltip: str, on_clicked: Callable[[], None]) -> QPushButton:
        btn = QPushButton(glyph, self)
        btn.setObjectName("SegmentNavArrow")
        btn.setFixedSize(36, 36)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setStyleSheet(NAV_ARROW_BUTTON)
        btn.setToolTip(tooltip)
        btn.clicked.connect(on_clicked)
        return btn

    def go_prev(self) -> None:
        """Ask for the segment before the active one, if there is one."""
        if self._current_index <= 0:
            return
        self.index_requested.emit(self._current_index - 1)

    def go_next(self) -> None:
        """Ask for the segment after the active one, if there is one."""
        if self._current_index >= self._segment_count - 1:
            return
        self.index_requested.emit(self._current_index + 1)

    def set_current_index(self, index: int) -> None:
        """Follow the view to a segment: arrow states and the dot scrolled into view.

        Dot colours are left to 'update_dots', which the view calls whenever the
        state behind them changes, not only on navigation.
        """
        self._current_index = index
        self._nav_prev.setEnabled(index > 0)
        self._nav_next.setEnabled(index < self._segment_count - 1)
        if self._dot_buttons and index < len(self._dot_buttons):
            self._dots_scroll.ensureWidgetVisible(self._dot_buttons[index])

    def update_dots(self, states: Sequence[str]) -> None:
        """Repaint every dot from the given states, in segment order."""
        for i, (state, btn) in enumerate(zip(states, self._dot_buttons)):
            btn.setStyleSheet(nav_dot_style(state, is_current=i == self._current_index))
