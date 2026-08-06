from PySide6.QtCore import Qt
from PySide6.QtGui import QCloseEvent, QKeySequence, QResizeEvent, QShortcut
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

from core.models.project import Project
from core.models.search_plan import SearchPlan
from core.models.segment import Segment
from core.project_paths import ProjectPaths
from services.project_service import save_project
from ui.cache.segment_preview_cache import SegmentPreviewCache
from ui.dialogs.export_dialog import ExportDialog
from ui.dialogs.missing_media_dialog import MissingMediaDialog
from ui.styles.qss import ACTION_BUTTON, TITLE_LABEL, top_bar_style
from ui.utils.grid_layout import relayout_grid
from ui.widgets.segment_tile import SegmentTile
from ui.widgets.segment_view import SegmentView
from ui.widgets.voiceover_playback import VoiceoverPlaybackController


class ProjectWindow(QMainWindow):
    _BAR_HEIGHT_PX = 56

    def __init__(self, project: Project, *, search_plan: SearchPlan | None = None) -> None:
        super().__init__()
        self._project = project
        self._search_plan = search_plan
        self._paths = ProjectPaths.from_title(project.title)
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
        self._tile_by_segment_id: dict[int, SegmentTile] = {}
        self._tile_size_px = 240
        self._grid_spacing = 12
        self.setWindowTitle(f"Videnerate - {self._project.title}")

        self._voiceover = VoiceoverPlaybackController(self._paths, parent=self)
        self._voiceover.state_changed.connect(self._sync_playback_button)

        self._build_ui()
        self._sync_playback_button()

        # Auto-assign is a segment-by-segment flow, so skip the project grid entirely.
        if self._search_plan is not None and self._project.segments:
            self._open_segment_view(self._project.segments[0])

        save_shortcut = QShortcut(QKeySequence.StandardKey.Save, self)
        save_shortcut.setContext(Qt.ShortcutContext.WindowShortcut)
        save_shortcut.activated.connect(self._save_project)

    def _sync_playback_button(self) -> None:
        """Keep project voiceover play button in sync with playback state."""
        if self._voiceover_btn is not None:
            self._voiceover_btn.setText(self._voiceover.full_play_button_text())

    def _save_project(self) -> None:
        save_project(self._project)

    def _on_export_clicked(self) -> None:
        any_missing = any(seg.media is None for seg in self._project.segments)
        if any_missing:
            warning = MissingMediaDialog(self)
            if warning.exec() != MissingMediaDialog.DialogCode.Accepted:
                return
        ExportDialog(self._project, self).exec()

    def _toggle_voiceover(self) -> None:
        self._voiceover.toggle_full()

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

        export_btn = QPushButton("Export", self._project_view)
        export_btn.setFixedHeight(36)
        export_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        export_btn.setStyleSheet(ACTION_BUTTON)
        export_btn.setToolTip("Export project to video")
        export_btn.clicked.connect(self._on_export_clicked)

        self._voiceover_btn = QPushButton("Play voiceover", self._project_view)
        self._voiceover_btn.setFixedHeight(36)
        self._voiceover_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._voiceover_btn.setStyleSheet(ACTION_BUTTON)
        self._voiceover_btn.setToolTip(self._voiceover.voiceover_tooltip())
        self._voiceover_btn.clicked.connect(self._toggle_voiceover)

        top_row = QFrame(self._project_view)
        top_row.setObjectName("ProjectViewTopBar")
        top_row.setFixedHeight(self._BAR_HEIGHT_PX)
        top_row.setStyleSheet(top_bar_style("ProjectViewTopBar"))
        top_inner = QHBoxLayout(top_row)
        top_inner.setContentsMargins(14, 8, 10, 8)
        top_inner.setSpacing(12)
        top_inner.addWidget(header, 1)
        top_inner.addWidget(
            save_btn, 0, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
        top_inner.addWidget(
            export_btn, 0, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
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
        self._tile_by_segment_id = {
            seg.id: tile for seg, tile in zip(self._project.segments, self._segment_tiles)
        }
        self._relayout_segments_grid()
        self._wire_segment_tile_clicks()

        self._segments_scroll.setWidget(self._segments_grid_host)
        project_layout.addWidget(self._segments_scroll, 1)

        self._stack.addWidget(self._project_view)

        self._segment_view = SegmentView(
            project=self._project,
            paths=self._paths,
            tile_size_px=self._tile_size_px,
            grid_spacing=self._grid_spacing,
            preview_cache=self._preview_cache,
            voiceover=self._voiceover,
            parent=self._stack,
        )
        self._segment_view.close_requested.connect(self._show_project_view)
        self._segment_view.media_selected.connect(self._on_media_selected)
        self._stack.addWidget(self._segment_view)

        self._stack.setCurrentIndex(0)

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        self._relayout_segments_grid()

    def _relayout_segments_grid(self) -> None:
        if self._segments_scroll is None or self._segments_grid is None:
            return
        relayout_grid(
            self._segment_tiles,
            scroll=self._segments_scroll,
            grid=self._segments_grid,
            tile_size_px=self._tile_size_px,
            grid_spacing=self._grid_spacing,
        )

    def _wire_segment_tile_clicks(self) -> None:
        """Connect each segment tile click to opening detail view."""
        for tile, seg in zip(self._segment_tiles, self._project.segments):
            tile.clicked.connect(lambda seg=seg: self._open_segment_view(seg))

    def _open_segment_view(self, segment: Segment) -> None:
        self._segment_view.set_segment(segment)
        self._stack.setCurrentIndex(1)
        self._sync_playback_button()

    def _show_project_view(self) -> None:
        """Return to project grid (tile previews update on media selection, not here)."""
        self._voiceover.stop()
        self._segment_view.release_preview_resources()
        self._preview_cache.clear()
        self._stack.setCurrentIndex(0)
        # A stacked widget only lays out the page it is showing, so any resize that
        # happened while the segment view was up left this grid's viewport stale
        self._relayout_segments_grid()

    def _on_media_selected(self, segment_id: int, thumb_bytes: bytes) -> None:
        """Update matching project tile thumbnail after media selection in detail view."""
        tile = self._tile_by_segment_id.get(segment_id)
        if tile is not None:
            tile.set_thumbnail_bytes(thumb_bytes)
