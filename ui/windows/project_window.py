from pathlib import Path

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QCloseEvent
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from config import PROJECTS_DIR
from core.models.project import Project


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
        root = QWidget(self)
        root_layout = QVBoxLayout(root)
        root_layout.setContentsMargins(20, 20, 20, 20)
        root_layout.setSpacing(12)

        header = QLabel("Segments")
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
        root_layout.addLayout(header_row)

        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)

        content = QWidget(scroll)
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(10)

        for seg in self._project.segments:
            label = QLabel(seg.text)
            label.setWordWrap(True)
            label.setStyleSheet(
                "padding: 10px 12px; border: 1px solid #333; border-radius: 8px;"
            )
            content_layout.addWidget(label)

        content_layout.addStretch()
        scroll.setWidget(content)
        root_layout.addWidget(scroll, 1)

        self.setCentralWidget(root)

