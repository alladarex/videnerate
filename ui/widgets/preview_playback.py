from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ui.widgets.hover_media_preview import HoverMediaPreview

from PySide6.QtCore import QObject, QUrl
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer, QVideoFrame, QVideoSink


class SharedVideoPreviewBackend(QObject):
    """Single app-wide video backend used by all hover preview widgets."""

    _instance: SharedVideoPreviewBackend | None = None

    def __init__(self) -> None:
        super().__init__()
        self._owner: HoverMediaPreview | None = None
        self._video_sink = QVideoSink(self)
        self._video_sink.videoFrameChanged.connect(self._on_video_frame_changed)
        self._audio_output = QAudioOutput(self)
        self._audio_output.setMuted(True)
        self._player = QMediaPlayer(self)
        self._player.setAudioOutput(self._audio_output)
        self._player.setVideoSink(self._video_sink)
        self._player.mediaStatusChanged.connect(self._on_media_status_changed)
        self._player.errorOccurred.connect(self._on_media_error)

    @classmethod
    def instance(cls) -> SharedVideoPreviewBackend:
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def play_for(self, owner: HoverMediaPreview, path: str) -> None:
        self._owner = owner
        self._player.setSource(QUrl.fromLocalFile(path))
        self._player.play()

    def stop(self) -> None:
        self._player.stop()
        self._owner = None

    def release_source(self) -> None:
        self.stop()
        self._player.setSource(QUrl())

     #QMediaPlayer.errorOccurred typically emits something like (error, error_string)
    def _on_media_error(self, *_) -> None:
        if self._owner is not None:
            self._owner.on_video_error()

    def _on_media_status_changed(self, status: QMediaPlayer.MediaStatus) -> None:
        if (
            status == QMediaPlayer.MediaStatus.EndOfMedia
            and self._owner is not None
            and self._owner.is_hovered()
        ):
            self._player.setPosition(0)
            self._player.play()

    def _on_video_frame_changed(self, frame: QVideoFrame) -> None:
        if self._owner is not None:
            self._owner.on_video_frame(frame)
