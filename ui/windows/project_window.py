from PySide6.QtCore import Qt
from PySide6.QtGui import QCloseEvent, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from core.models.segment import Segment
from core.models.word_timeline import WordTimeline, segment_playback_bounds
from core.models.project import Project
from core.project_paths import ProjectPaths
from services.alignment_service import load_word_timeline
from services.project_service import save_project
from ui.styles.qss import ACTION_BUTTON, TITLE_LABEL, top_bar_style
from ui.cache.segment_preview_cache import SegmentPreviewCache
from ui.utils.grid_layout import column_count_for_viewport
from ui.widgets.segment_tile import SegmentTile
from ui.widgets.segment_view import SegmentView
from ui.widgets.voiceover_playback import VoiceoverPlaybackController

_PROJECT_VIEW_BAR_HEIGHT_PX = 56


class ProjectWindow(QMainWindow):
    def __init__(self, project: Project) -> None:
        super().__init__()
        self._project = project
        self._paths = ProjectPaths.from_title(project.title)
        self._word_timeline: WordTimeline = load_word_timeline(self._paths)
        self._voiceover_btn: QPushButton | None = None
        self._stack: QStackedWidget | None = None
        self._project_view: QWidget | None = None
        self._segment_view: SegmentView | None = None

        self._segments_scroll: QScrollArea | None = None
        # QGridLayout must be attached to a QWidget. It cannot attach directly to QScrollArea
        self._segments_grid_host: QWidget | None = None
        self._segments_grid: QGridLayout | None = None
        self._segment_tiles: list[SegmentTile] = []
        self._preview_cache = SegmentPreviewCache(self._paths)
        # Store a map of segment id to tile for quick lookup
        self._segment_tile_by_id: dict[int, SegmentTile] = {}
        self._tile_size_px = 240
        self._grid_spacing = 12
        self.setWindowTitle(f"Videnerate - {self._project.title}")

        self._voiceover = VoiceoverPlaybackController(self, self._paths)
        self._voiceover.state_changed.connect(self._sync_playback_buttons)

        self._build_ui()
        self._sync_playback_buttons()

        save_shortcut = QShortcut(QKeySequence.StandardKey.Save, self)
        save_shortcut.setContext(Qt.ShortcutContext.WindowShortcut)
        save_shortcut.activated.connect(self._save_project)

    def _sync_playback_buttons(self) -> None:
        """Keep project and segment play buttons in sync with playback state."""
        if self._voiceover_btn is not None:
            self._voiceover_btn.setText(self._voiceover.full_play_button_text())
        if self._segment_view is not None:
            seg = self._segment_view.current_segment
            self._segment_view.sync_playback_button(
                playing=self._voiceover.is_playing_segment(seg.id),
                bounds=self._segment_playback_bounds(seg),
            )

    def _segment_playback_bounds(self, segment: Segment) -> tuple[float, float]:
        return segment_playback_bounds(self._word_timeline, segment)

    def _save_project(self) -> None:
        save_project(self._project)

    def _toggle_voiceover(self) -> None:
        self._voiceover.toggle_full()

    def _toggle_segment_voiceover(self) -> None:
        if self._segment_view is None:
            return
        seg = self._segment_view.current_segment
        start, end = self._segment_playback_bounds(seg)
        self._voiceover.toggle_segment(seg.id, start, end)

    def closeEvent(self, event: QCloseEvent) -> None:
        self._voiceover.stop()
        self._segment_view.release_preview_resources()
        self._preview_cache.clear()
        super().closeEvent(event)

    def _build_ui(self) -> None:
        self._stack = QStackedWidget(self)
        self.setCentralWidget(self._stack)

        self._project_view = QWidget(self._stack)
        project_layout = QVBoxLayout(self._project_view)
        project_layout.setContentsMargins(20, 20, 20, 20)
        project_layout.setSpacing(12)

        header = QLabel(self._project.title)
        # Align left and vertically center
        header.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        header.setStyleSheet(TITLE_LABEL)
        header.setSizePolicy(
            QSizePolicy.Policy.Expanding, 
            QSizePolicy.Policy.Preferred,
        )

        save_btn = QPushButton("Save")
        save_btn.setFixedHeight(36)
        save_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        save_btn.setToolTip("Save project")
        save_btn.setStyleSheet(ACTION_BUTTON)
        save_btn.clicked.connect(self._save_project)

        self._voiceover_btn = QPushButton("Play voiceover", self._project_view)
        self._voiceover_btn.setFixedHeight(36)
        self._voiceover_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._voiceover_btn.setStyleSheet(ACTION_BUTTON)
        self._voiceover_btn.setToolTip(self._voiceover.voiceover_tooltip())
        self._voiceover_btn.clicked.connect(self._toggle_voiceover)

        top_row = QFrame(self._project_view)
        top_row.setObjectName("ProjectViewTopBar")
        top_row.setFixedHeight(_PROJECT_VIEW_BAR_HEIGHT_PX)
        top_row.setStyleSheet(top_bar_style("ProjectViewTopBar"))
        top_inner = QHBoxLayout(top_row)
        top_inner.setContentsMargins(14, 8, 10, 8)
        top_inner.setSpacing(12)
        top_inner.addWidget(header, 1)
        top_inner.addWidget(
            save_btn, 0, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
        top_inner.addWidget(
            self._voiceover_btn, 0, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
        project_layout.addWidget(top_row)

        self._segments_scroll = QScrollArea(self._project_view)
        self._segments_scroll.setWidgetResizable(True)
        self._segments_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self._segments_grid_host = QWidget(self._segments_scroll)
        self._segments_grid = QGridLayout(self._segments_grid_host)

        self._segments_grid.setContentsMargins(
            self._grid_spacing,
            self._grid_spacing,
            self._grid_spacing,
            self._grid_spacing,
        )

        self._segments_grid.setHorizontalSpacing(self._grid_spacing)
        self._segments_grid.setVerticalSpacing(self._grid_spacing)
        self._segments_grid.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter)

        self._segment_tiles = [
            SegmentTile(
                seg,
                size_px=self._tile_size_px,
                preview_cache=self._preview_cache,
                parent=self._segments_grid_host,
            )
            for seg in self._project.segments
        ]
        self._segment_tile_by_id = {
            seg.id: tile for seg, tile in zip(self._project.segments, self._segment_tiles)
        }
        self._rebuild_segments_grid()
        self._wire_segment_tile_clicks()

        self._segments_scroll.setWidget(self._segments_grid_host)
        project_layout.addWidget(self._segments_scroll, 1)

        self._stack.addWidget(self._project_view)

        self._segment_view = SegmentView(
            project=self._project,
            tile_size_px=self._tile_size_px,
            grid_spacing=self._grid_spacing,
            preview_cache=self._preview_cache,
            parent=self._stack,
        )
        self._segment_view.close_requested.connect(self._show_project_view)
        self._segment_view.media_selected.connect(self._on_media_selected)
        self._segment_view.segment_play_clicked.connect(self._toggle_segment_voiceover)
        self._segment_view.current_segment_changed.connect(self._on_segment_view_changed)
        self._stack.addWidget(self._segment_view)

        self._stack.setCurrentIndex(0)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._rebuild_segments_grid()

    def _rebuild_segments_grid(self) -> None:
        if self._segments_scroll is None or self._segments_grid is None:
            return

        # Clear layout items (widgets are kept alive in self._segment_tiles)
        while self._segments_grid.count():
            item = self._segments_grid.takeAt(0)
            if item is None:
                break

        viewport_width = self._segments_scroll.viewport().width()
        cols = column_count_for_viewport(
            viewport_width,
            tile_size_px=self._tile_size_px,
            grid_spacing=self._grid_spacing,
        )

        for i, tile in enumerate(self._segment_tiles):
            row = i // cols
            col = i % cols
            self._segments_grid.addWidget(tile, row, col)

    def _wire_segment_tile_clicks(self) -> None:
        """Connect each segment tile click to opening detail view."""
        for tile, seg in zip(self._segment_tiles, self._project.segments):
            tile.clicked.connect(lambda s=seg: self._open_segment_view(s))

    def _open_segment_view(self, segment: Segment) -> None:
        self._segment_view.set_segment(segment)
        self._stack.setCurrentIndex(1)
        self._sync_playback_buttons()

    def _on_segment_view_changed(self) -> None:
        if self._segment_view is None:
            return
        self._voiceover.on_active_segment_changed(
            self._segment_view.current_segment.id
        )
        self._sync_playback_buttons()

    def _show_project_view(self) -> None:
        """Return to project grid (tile previews update on media selection, not here)."""
        self._voiceover.stop()
        self._segment_view.release_preview_resources()
        self._preview_cache.clear()
        self._stack.setCurrentIndex(0)

    def _on_media_selected(self, segment_id: int, thumb_bytes: bytes) -> None:
        """Update matching project tile thumbnail after media selection in detail view."""
        tile = self._segment_tile_by_id.get(segment_id)
        if tile is not None:
            tile.set_thumbnail_bytes(thumb_bytes)