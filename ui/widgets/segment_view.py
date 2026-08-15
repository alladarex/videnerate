from html import escape

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
from core.models.search_plan import SearchPlan
from core.models.segment import Segment
from core.models.word_timeline import load_word_timeline, segment_playback_bounds
from core.project_paths import ProjectPaths
from services.media_suggestions import SegmentSuggestions, SuggestionEngine
from services.vision_ranking import Suggestion
from ui.cache.segment_preview_cache import SegmentPreviewCache
from ui.cache.segment_search_cache import SegmentSearchCache
from ui.styles.qss import (
    ACTION_BUTTON,
    ICON_CLOSE_BUTTON,
    SECTION_TITLE_LABEL,
    TITLE_LABEL,
    top_bar_style,
)
from ui.widgets.segment_nav_bar import SegmentNavBar
from ui.widgets.segment_view_grid import SegmentViewGridController
from ui.widgets.voiceover_playback import VoiceoverPlaybackController


def _suggestions_tooltip(suggestions: list[Suggestion]) -> str:
    """Text rundown of each proposal: what it shows and why it was picked."""
    rows = [
        f"<b>{i}. {escape(s.description)}</b><br>{escape(s.reason)}"
        for i, s in enumerate(suggestions, start=1)
    ]
    return "<br><br>".join(rows)


class SegmentView(QWidget):
    """Detail view for one segment: header with text + close, scrollable cell grid, footer nav."""

    close_requested = Signal()
    media_selected = Signal(int, bytes)
    save_requested = Signal()

    _BAR_HEIGHT_PX = 56

    def __init__(
        self,
        *,
        project: Project,
        paths: ProjectPaths,
        tile_size_px: int,
        grid_spacing: int,
        preview_cache: SegmentPreviewCache,
        voiceover: VoiceoverPlaybackController,
        search_plan: SearchPlan | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._project = project
        self._word_timeline = load_word_timeline(paths)
        self._voiceover = voiceover
        self._voiceover.state_changed.connect(self._sync_playback_button)
        self._tile_size_px = tile_size_px
        self._grid_spacing = grid_spacing
        self._current_index = 0

        self._search_plan = search_plan
        self._suggestion_engine: SuggestionEngine | None = None
        # Segment ids the engine is working on right now, used by the search locking,
        # the navigation dot, and the "Finding media…" status
        self._auto_searching_segment_ids: set[int] = set()
        # The engine stops the work. This stops rendering events that were already
        # handed to the Qt queue before Stop was clicked
        self._auto_search_stopped = False

        self._scroll: QScrollArea | None = None
        self._grid_host: QWidget | None = None
        self._grid: QGridLayout | None = None
        self._search_cache = SegmentSearchCache()
        self._grid_controller: SegmentViewGridController

        self._nav_bar: SegmentNavBar
        self._play_btn: QPushButton | None = None

        # Prevents activating "Back to project" when clicking space
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
        save_btn.clicked.connect(self.save_requested.emit)

        self._play_btn = QPushButton("Play", self)
        self._play_btn.setFixedHeight(36)
        self._play_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._play_btn.setStyleSheet(ACTION_BUTTON)
        self._play_btn.clicked.connect(self._toggle_segment_voiceover)

        # Visible only while the active segment has suggestions, its tooltip says
        # what each one is and why it was picked
        self._suggestions_hint = QLabel("?", self)
        self._suggestions_hint.setFixedSize(24, 24)
        self._suggestions_hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._suggestions_hint.setStyleSheet(SECTION_TITLE_LABEL)
        self._suggestions_hint.setVisible(False)

        self._stop_auto_search_btn = QPushButton("Stop auto-search", self)
        self._stop_auto_search_btn.setFixedHeight(36)
        self._stop_auto_search_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._stop_auto_search_btn.setToolTip("Abandon the remaining auto-assign searches")
        self._stop_auto_search_btn.setStyleSheet(ACTION_BUTTON)
        self._stop_auto_search_btn.setVisible(False)
        self._stop_auto_search_btn.clicked.connect(self._on_stop_auto_search_clicked)

        top_row = QFrame(self)
        top_row.setObjectName("SegmentViewTopBar")
        top_row.setFixedHeight(self._BAR_HEIGHT_PX)
        top_row.setStyleSheet(top_bar_style("SegmentViewTopBar"))
        top_inner = QHBoxLayout(top_row)
        top_inner.setContentsMargins(14, 8, 10, 8)
        top_inner.setSpacing(12)
        top_inner.addWidget(self._text_label, 1)
        top_inner.addWidget(
            self._suggestions_hint, 0, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
        top_inner.addWidget(
            self._stop_auto_search_btn,
            0,
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
        )
        top_inner.addWidget(
            self._play_btn, 0, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
        top_inner.addWidget(
            save_btn, 0, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
        top_inner.addWidget(
            close_btn, 0, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )

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
            search_cache=self._search_cache,
            preview_cache=preview_cache,
            on_media_selected=self._on_media_selected,
            word_timeline=self._word_timeline,
            is_segment_running=lambda segment_id: segment_id in self._auto_searching_segment_ids,
            on_manual_search_started=self._on_manual_search_started,
            on_results_changed=self._refresh_dots_hint_and_stop_btn,
        )
        self._grid_controller.set_segment(self.current_segment)

        self._scroll.setWidget(self._grid_host)
        self._grid_host.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Minimum,
        )

        self._nav_bar = SegmentNavBar(
            segments=self._project.segments,
            bar_height_px=self._BAR_HEIGHT_PX,
            parent=self,
        )
        self._nav_bar.index_requested.connect(self._go_to_index)

        sc_left = QShortcut(QKeySequence(Qt.Key.Key_Left), self)
        sc_left.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        sc_left.activated.connect(self._nav_bar.go_prev)
        sc_right = QShortcut(QKeySequence(Qt.Key.Key_Right), self)
        sc_right.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        sc_right.activated.connect(self._nav_bar.go_next)

        root = QVBoxLayout(self)
        root.setContentsMargins(20, 20, 20, 20)
        root.setSpacing(12)
        root.addWidget(top_row)
        root.addWidget(self._scroll, 1)
        root.addWidget(self._nav_bar)

        self._grid_controller.relayout_grid()
        self._refresh_nav_display()

    @property
    def current_segment(self) -> Segment:
        return self._project.segments[self._current_index]

    def set_suggestion_engine(self, engine: SuggestionEngine) -> None:
        self._suggestion_engine = engine

    # Both engine callbacks below touch Qt widgets, so they must be called on the main thread.
    # 'ProjectWindow' hands them over with 'call_on_main_thread',
    # so nothing here needs to (whatever 'media_suggestions' says about its workers).

    def suggestions_started(self, segment_id: int) -> None:
        """A worker took this segment."""
        # Two ways this event no longer applies:
        # 1. Stop was pressed
        # 2. The user already run a manual search (segment_id got added to cache)
        # The cache entry is written on click, so point 2 also covers a 'skip'
        # that reached the engine after a manual search worker started a search.
        if self._auto_search_stopped or self._search_cache.get(segment_id) is not None:
            return
        self._auto_searching_segment_ids.add(segment_id)
        self._refresh_dots()
        if segment_id == self.current_segment.id and self.isVisible():
            self._grid_controller.reload()

    def suggestions_ready(self, segment_suggestions: SegmentSuggestions) -> None:
        """Proposals for this segment, or a failure.

        Since the search and vision calls were already paid for,
        suggestions can still arive after Stop is clicked.
        """
        segment_id = segment_suggestions.segment_id
        self._auto_searching_segment_ids.discard(segment_id)
        if self._search_cache.get(segment_id) is None:
            self._search_cache.set(
                segment_id,
                query=segment_suggestions.query,
                results=[s.result for s in segment_suggestions.suggestions],
                suggestions=segment_suggestions.suggestions,
                error=segment_suggestions.error,
            )
        self._refresh_dots_hint_and_stop_btn()
        if segment_id == self.current_segment.id and self.isVisible():
            self._grid_controller.reload()

    def _on_stop_auto_search_clicked(self) -> None:
        self._auto_search_stopped = True
        self._suggestion_engine.cancel()
        self._auto_searching_segment_ids.clear()
        self._refresh_dots_hint_and_stop_btn()
        # Unlocks the current segment if it was being worked on
        self._grid_controller.reload()

    def _on_manual_search_started(self, segment_id: int) -> None:
        """User did a manual search, so the suggestion engine must skip it."""
        if self._suggestion_engine is not None:
            self._suggestion_engine.skip(segment_id)
        self._refresh_dots_hint_and_stop_btn()

    def _on_media_selected(self, segment_id: int, thumb_bytes: bytes) -> None:
        self.media_selected.emit(segment_id, thumb_bytes)
        self._refresh_dots()

    def _segment_playback_bounds(self, segment: Segment) -> tuple[float, float]:
        return segment_playback_bounds(self._word_timeline, segment)

    def _toggle_segment_voiceover(self) -> None:
        seg = self.current_segment
        start, end = self._segment_playback_bounds(seg)
        self._voiceover.toggle_segment(seg.id, start_s=start, end_s=end)

    def _sync_playback_button(self, *_args: object) -> None:
        if self._play_btn is None:
            return
        playing = self._voiceover.is_playing_segment(self.current_segment.id)
        start, end = self._segment_playback_bounds(self.current_segment)
        self._play_btn.setText("Stop" if playing else "Play")
        label = f"{start:.2f}s - {end:.2f}s"
        self._play_btn.setToolTip(
            f"Stop playback ({label})" if playing else f"Play voiceover for this segment ({label})"
        )

    def refresh_media(self) -> None:
        """Redraw the active segment's media, after something outside changed it."""
        self._grid_controller.sync_media_tile()

    def set_segment(self, segment: Segment) -> None:
        for i, seg in enumerate(self._project.segments):
            if seg.id == segment.id:
                self._current_index = i
                break
        else:
            raise ValueError(f"Segment id {segment.id} not found in project")
        self._grid_controller.set_segment(self.current_segment)
        self._refresh_nav_display()

    def showEvent(self, event: QShowEvent) -> None:
        super().showEvent(event)
        self._grid_controller.relayout_grid()

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        self._grid_controller.relayout_grid()

    def release_preview_resources(self) -> None:
        """Release transient preview resources for segment view."""
        self._grid_controller.release_preview_resources()

    def _go_to_index(self, index: int) -> None:
        """Navigate to a specific segment index and refresh related UI state."""
        n = len(self._project.segments)
        if n == 0 or index < 0 or index >= n:
            return
        if index == self._current_index:
            return
        self._current_index = index
        self._grid_controller.set_segment(self.current_segment)
        self._refresh_nav_display()

    def _dot_state(self, segment: Segment) -> str:
        if segment.media is not None:
            return "attached"  # green
        entry = self._search_cache.get(segment.id)
        if entry is not None and entry.results:
            return "ready"  # orange
        if segment.id in self._auto_searching_segment_ids:
            return "working"  # dark gray
        return "idle"  # gray

    def _refresh_dots(self) -> None:
        self._nav_bar.update_dots([self._dot_state(seg) for seg in self._project.segments])

    def _has_auto_work_left(self) -> bool:
        """An entry, delivered or user-made, is what retires a planned segment."""
        if self._search_plan is None or self._auto_search_stopped:
            return False
        return any(
            self._search_cache.get(segment_id) is None
            for segment_id in self._search_plan.query_by_segment_id
        )

    def _refresh_dots_hint_and_stop_btn(self) -> None:
        """Repaint everything outside the grid that reads the search cache."""
        self._refresh_dots()
        entry = self._search_cache.get(self.current_segment.id)
        suggestions = entry.suggestions if entry is not None else None
        self._suggestions_hint.setVisible(bool(suggestions))
        if suggestions:
            self._suggestions_hint.setToolTip(_suggestions_tooltip(suggestions))
        self._stop_auto_search_btn.setVisible(self._has_auto_work_left())

    def _refresh_nav_display(self) -> None:
        """Refresh top text, dot highlighting, and nav button enabled states."""
        n = len(self._project.segments)
        seg = self._project.segments[self._current_index] if n else None
        self._text_label.setText("" if seg is None else seg.text)

        self._nav_bar.set_current_index(self._current_index)
        self._refresh_dots_hint_and_stop_btn()

        self._voiceover.on_active_segment_changed(self.current_segment.id)
        self._sync_playback_button()
