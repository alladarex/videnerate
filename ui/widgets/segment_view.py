from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QKeySequence, QResizeEvent, QShortcut, QShowEvent
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from core.models.project import Project
from core.models.segment import Segment
from services.project_service import save_project
from ui.styles.qss import (
    ACTION_BUTTON,
    ICON_CLOSE_BUTTON,
    NAV_ARROW_BUTTON,
    NAV_DOT_ACTIVE,
    NAV_DOT_INACTIVE,
    TITLE_LABEL,
    TRANSPARENT_SCROLL,
    top_bar_style,
)
from ui.cache.segment_preview_cache import SegmentPreviewCache
from ui.cache.segment_search_cache import SegmentSearchCache
from ui.widgets.segment_view_grid import SegmentViewGridController




class SegmentView(QWidget):
    """Detail view for one segment: header with text + close, scrollable cell grid, footer nav."""

    close_requested = Signal()
    media_selected = Signal(int, bytes)

    _BAR_HEIGHT_PX = 56
    _DOT_PX = 12
    _DOT_GAP_PX = 5

    def __init__(
        self,
        *,
        project: Project,
        tile_size_px: int,
        grid_spacing: int,
        preview_cache: SegmentPreviewCache,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._project = project
        self._tile_size_px = tile_size_px
        self._grid_spacing = grid_spacing
        self._current_index = 0

        self._scroll: QScrollArea | None = None
        self._grid_host: QWidget | None = None
        self._grid: QGridLayout | None = None
        self._cache = SegmentSearchCache()
        self._grid_controller: SegmentViewGridController

        self._nav_prev: QPushButton | None = None
        self._nav_next: QPushButton | None = None
        self._dots_scroll: QScrollArea | None = None
        self._dot_buttons: list[QPushButton] = []

        # Needed if segment view is accessible without a prior mouse click in project view
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        self._text_label = QLabel(self)
        self._text_label.setWordWrap(True)
        self._text_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self._text_label.setStyleSheet(TITLE_LABEL)
        self._text_label.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Preferred,
        )

        close_btn = QPushButton("×", self)
        close_btn.setFixedSize(36, 36)
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.setToolTip("Back to project")
        close_btn.setStyleSheet(ICON_CLOSE_BUTTON)
        close_btn.clicked.connect(self.close_requested.emit)

        save_btn = QPushButton("Save", self)
        save_btn.setFixedHeight(36)
        save_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        save_btn.setToolTip("Save project")
        save_btn.setStyleSheet(ACTION_BUTTON)
        save_btn.clicked.connect(lambda: save_project(self._project))

        top_row = QFrame(self)
        top_row.setObjectName("SegmentViewTopBar")
        top_row.setFixedHeight(self._BAR_HEIGHT_PX)
        top_row.setStyleSheet(top_bar_style("SegmentViewTopBar"))
        top_inner = QHBoxLayout(top_row)
        top_inner.setContentsMargins(14, 8, 10, 8)
        top_inner.setSpacing(12)
        top_inner.addWidget(self._text_label, 1)
        top_inner.addWidget(save_btn, 0, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        top_inner.addWidget(close_btn, 0, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        self._scroll = QScrollArea(self)
        self._scroll.setWidgetResizable(True)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self._grid_host = QWidget(self._scroll)
        self._grid = QGridLayout(self._grid_host)
        self._grid.setContentsMargins(
            self._grid_spacing,
            self._grid_spacing,
            self._grid_spacing,
            self._grid_spacing,
        )
        self._grid.setHorizontalSpacing(self._grid_spacing)
        self._grid.setVerticalSpacing(self._grid_spacing)
        self._grid.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter)

        self._grid_controller = SegmentViewGridController(
            scroll=self._scroll,
            grid_host=self._grid_host,
            grid=self._grid,
            tile_size_px=self._tile_size_px,
            grid_spacing=self._grid_spacing,
            cache=self._cache,
            preview_cache=preview_cache,
            on_media_selected=lambda seg_id, b: self.media_selected.emit(seg_id, b),
        )
        self._grid_controller.set_segment(self._current_segment())

        self._scroll.setWidget(self._grid_host)
        self._grid_host.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Minimum,
        )

        bottom_row = QFrame(self)
        bottom_row.setObjectName("SegmentViewBottomBar")
        bottom_row.setFixedHeight(self._BAR_HEIGHT_PX)
        bottom_row.setStyleSheet(top_bar_style("SegmentViewBottomBar"))
        bottom_inner = QHBoxLayout(bottom_row)
        bottom_inner.setContentsMargins(10, 8, 10, 8)
        bottom_inner.setSpacing(8)

        self._nav_prev = QPushButton("‹", bottom_row)
        self._nav_prev.setObjectName("SegmentNavArrow")
        self._nav_prev.setFixedSize(36, 36)
        self._nav_prev.setCursor(Qt.CursorShape.PointingHandCursor)
        self._nav_prev.setStyleSheet(NAV_ARROW_BUTTON)
        self._nav_prev.setToolTip("Previous segment")
        self._nav_prev.clicked.connect(self._go_prev)

        self._dots_scroll = QScrollArea(bottom_row)
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

        for i, seg in enumerate(self._project.segments):
            btn = QPushButton(dots_host)
            btn.setObjectName("SegmentNavDot")
            btn.setFixedSize(self._DOT_PX, self._DOT_PX)
            btn.setFlat(True)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setToolTip(seg.text)
            btn.clicked.connect(lambda checked=False, idx=i: self._go_to_index(idx))
            dots_layout.addWidget(btn)
            self._dot_buttons.append(btn)

        dots_layout.addStretch(0)
        self._dots_scroll.setWidget(dots_host)

        self._nav_next = QPushButton("›", bottom_row)
        self._nav_next.setObjectName("SegmentNavArrow")
        self._nav_next.setFixedSize(36, 36)
        self._nav_next.setCursor(Qt.CursorShape.PointingHandCursor)
        self._nav_next.setStyleSheet(NAV_ARROW_BUTTON)
        self._nav_next.setToolTip("Next segment")
        self._nav_next.clicked.connect(self._go_next)

        bottom_inner.addWidget(self._nav_prev)
        bottom_inner.addWidget(self._dots_scroll, 1)
        bottom_inner.addWidget(self._nav_next)

        sc_left = QShortcut(QKeySequence(Qt.Key.Key_Left), self)
        sc_left.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        sc_left.activated.connect(self._go_prev)
        sc_right = QShortcut(QKeySequence(Qt.Key.Key_Right), self)
        sc_right.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        sc_right.activated.connect(self._go_next)

        root = QVBoxLayout(self)
        root.setContentsMargins(20, 20, 20, 20)
        root.setSpacing(12)
        root.addWidget(top_row)
        root.addWidget(self._scroll, 1)
        root.addWidget(bottom_row)

        self._grid_controller.rebuild_grid()
        self._refresh_nav_display()

    def _current_segment(self) -> Segment:
        return self._project.segments[self._current_index]

    def set_segment(self, segment: Segment) -> None:
        for i, s in enumerate(self._project.segments):
            if s.id == segment.id:
                self._current_index = i
                break
        else:
            raise ValueError(f"Segment id {segment.id} not found in project")
        self._grid_controller.set_segment(self._current_segment())
        self._refresh_nav_display()

    def showEvent(self, event: QShowEvent) -> None:
        super().showEvent(event)
        self._grid_controller.rebuild_grid()
        # Needed if segment view is accessible without a prior mouse click in project view
        # self.setFocus(Qt.FocusReason.ActiveWindowFocusReason)

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        self._grid_controller.rebuild_grid()

    def release_preview_resources(self) -> None:
        """Release transient preview resources for segment view."""
        self._grid_controller.release_preview_resources()

    def _go_prev(self) -> None:
        if self._current_index <= 0:
            return
        self._go_to_index(self._current_index - 1)

    def _go_next(self) -> None:
        n = len(self._project.segments)
        if n == 0 or self._current_index >= n - 1:
            return
        self._go_to_index(self._current_index + 1)

    def _go_to_index(self, index: int) -> None:
        """Navigate to a specific segment index and refresh related UI state."""
        n = len(self._project.segments)
        if n == 0 or index < 0 or index >= n:
            return
        if index == self._current_index:
            return
        self._current_index = index
        self._grid_controller.set_segment(self._current_segment())
        self._refresh_nav_display()

    def _refresh_nav_display(self) -> None:
        """Refresh top text, dot highlighting, and nav button enabled states."""
        n = len(self._project.segments)
        seg = self._project.segments[self._current_index] if n else None
        self._text_label.setText("" if seg is None else seg.text)

        for i, btn in enumerate(self._dot_buttons):
            btn.setStyleSheet(NAV_DOT_ACTIVE if i == self._current_index else NAV_DOT_INACTIVE)

        if self._nav_prev is not None:
            self._nav_prev.setEnabled(n > 0 and self._current_index > 0)
        if self._nav_next is not None:
            self._nav_next.setEnabled(n > 0 and self._current_index < n - 1)

        if self._dots_scroll is not None and self._dot_buttons and self._current_index < len(self._dot_buttons):
            self._dots_scroll.ensureWidgetVisible(self._dot_buttons[self._current_index])

