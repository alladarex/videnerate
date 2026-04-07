from pathlib import Path

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QCloseEvent
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
from PySide6.QtWidgets import (
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QScrollArea,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from config import PROJECTS_DIR
from core.models.project import Project
from core.models.segment import Segment
from ui.widgets.segment_block import SegmentBlock, column_count_for_viewport
from ui.widgets.segment_view import SegmentView


def _resolved_voiceover_path(project: Project) -> Path | None:
    if not project.voiceover_path:
        return None
    path = (PROJECTS_DIR / project.title / project.voiceover_path).resolve()
    return path if path.is_file() else None


class ProjectWindow(QMainWindow):
    def __init__(self, project: Project) -> None:
        super().__init__()
        self._project = project
        self._voiceover_file = _resolved_voiceover_path(project)
        self._voiceover_btn: QPushButton | None = None
        self._stack: QStackedWidget | None = None
        self._project_view: QWidget | None = None
        self._segment_detail_view: SegmentView | None = None

        self._segments_scroll: QScrollArea | None = None
        # QGridLayout must be attached to a QWidget. It cannot attach directly to QScrollArea
        self._segments_grid_host: QWidget | None = None
        self._segments_grid: QGridLayout | None = None
        self._segment_blocks: list[SegmentBlock] = []
        self._block_size_px = 240
        self._grid_spacing = 12
        self.setWindowTitle(f"Videnerate - {project.title}")

        self._media_player = QMediaPlayer(self)
        self._audio_output = QAudioOutput(self)
        self._media_player.setAudioOutput(self._audio_output)
        self._media_player.playbackStateChanged.connect(self._sync_voiceover_button)

        self._build_ui()
        self._sync_voiceover_button()

    def _sync_voiceover_button(self) -> None:
        if self._voiceover_btn is None:
            return
        if self._media_player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self._voiceover_btn.setText("Stop playback")
        else:
            self._voiceover_btn.setText("Play voiceover")

    def _toggle_voiceover(self) -> None:
        if self._voiceover_file is None:
            return
        if self._media_player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self._media_player.stop()
            return
        if self._media_player.source().isEmpty():
            self._media_player.setSource(QUrl.fromLocalFile(str(self._voiceover_file)))
        self._media_player.setPosition(0)
        self._media_player.play()

    def closeEvent(self, event: QCloseEvent) -> None:
        self._media_player.stop()
        super().closeEvent(event)

    def _build_ui(self) -> None:
        self._stack = QStackedWidget(self)
        self.setCentralWidget(self._stack)

        self._project_view = QWidget(self._stack)
        project_layout = QVBoxLayout(self._project_view)
        project_layout.setContentsMargins(20, 20, 20, 20)
        project_layout.setSpacing(12)

        header = QLabel(self._project.title)
        header.setAlignment(Qt.AlignmentFlag.AlignLeft)
        header.setStyleSheet("font-size: 18px; font-weight: 600;")

        header_row = QHBoxLayout()
        header_row.addWidget(header)
        header_row.addStretch()
        self._voiceover_btn = QPushButton("Play voiceover")
        self._voiceover_btn.setEnabled(self._voiceover_file is not None)
        if self._voiceover_file is None:
            self._voiceover_btn.setToolTip("No voiceover file for this project.")
        else:
            self._voiceover_btn.setToolTip(str(self._voiceover_file))
        self._voiceover_btn.clicked.connect(self._toggle_voiceover)
        header_row.addWidget(self._voiceover_btn)
        project_layout.addLayout(header_row)

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

        self._segment_blocks = [
            SegmentBlock(seg, size_px=self._block_size_px, parent=self._segments_grid_host)
            for seg in self._project.segments
        ]
        self._rebuild_segments_grid()
        self._wire_segment_block_clicks()

        self._segments_scroll.setWidget(self._segments_grid_host)
        project_layout.addWidget(self._segments_scroll, 1)

        self._stack.addWidget(self._project_view)

        self._segment_detail_view = SegmentView(
            project=self._project,
            block_size_px=self._block_size_px,
            grid_spacing=self._grid_spacing,
            parent=self._stack,
        )
        self._segment_detail_view.close_requested.connect(self._show_project_view)
        self._stack.addWidget(self._segment_detail_view)

        self._stack.setCurrentIndex(0)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._rebuild_segments_grid()

    def _rebuild_segments_grid(self) -> None:
        if self._segments_scroll is None or self._segments_grid is None:
            return

        # Clear layout items (widgets are kept alive in self._segment_blocks).
        while self._segments_grid.count():
            item = self._segments_grid.takeAt(0)
            if item is None:
                break

        viewport_width = self._segments_scroll.viewport().width()
        cols = column_count_for_viewport(
            viewport_width,
            block_size_px=self._block_size_px,
            grid_spacing=self._grid_spacing,
        )

        for i, block in enumerate(self._segment_blocks):
            row = i // cols
            col = i % cols
            self._segments_grid.addWidget(block, row, col)

    def _wire_segment_block_clicks(self) -> None:
        for block, seg in zip(self._segment_blocks, self._project.segments):
            block.clicked.connect(lambda s=seg: self._open_segment_view(s))

    def _open_segment_view(self, segment: Segment) -> None:
        if self._segment_detail_view is None or self._stack is None:
            return
        self._segment_detail_view.set_segment(segment)
        self._stack.setCurrentIndex(1)

    def _show_project_view(self) -> None:
        if self._stack is not None:
            self._stack.setCurrentIndex(0)


