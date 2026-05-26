from PySide6.QtCore import QObject, QUrl, Signal
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer

from core.project_paths import ProjectPaths


class VoiceoverPlaybackController(QObject):
    """Play project voiceover MP3, including per-segment time ranges."""

    state_changed = Signal()

    def __init__(self, parent: QObject | None, paths: ProjectPaths) -> None:
        super().__init__(parent)
        self._paths = paths
        self._media_player = QMediaPlayer(self)
        self._audio_output = QAudioOutput(self)
        self._media_player.setAudioOutput(self._audio_output)
        self._segment_play_end_ms: int | None = None
        self._segment_play_id: int | None = None
        self._pending_start_ms: int | None = None
        self._media_player.playbackStateChanged.connect(self._emit_state_changed)
        self._media_player.positionChanged.connect(self._on_position_changed)
        self._media_player.mediaStatusChanged.connect(self._on_media_status_changed)

    @property
    def is_playing(self) -> bool:
        return self._media_player.playbackState() == QMediaPlayer.PlaybackState.PlayingState

    def is_playing_full(self) -> bool:
        return self.is_playing and self._segment_play_id is None

    def is_playing_segment(self, segment_id: int) -> bool:
        return self.is_playing and self._segment_play_id == segment_id

    def voiceover_tooltip(self) -> str:
        return str(self._paths.voiceover_mp3)

    def full_play_button_text(self) -> str:
        if self.is_playing_full():
            return "Stop playback"
        return "Play voiceover"

    def stop(self) -> None:
        self._pending_start_ms = None
        self._media_player.stop()
        self._segment_play_end_ms = None
        self._segment_play_id = None
        self._emit_state_changed()

    def toggle_full(self) -> None:
        if self.is_playing:
            self.stop()
            return
        self._segment_play_end_ms = None
        self._segment_play_id = None
        self._play_from_ms(0)

    def toggle_segment(self, segment_id: int, start_s: float, end_s: float) -> None:
        if self.is_playing_segment(segment_id):
            self.stop()
            return
        self._segment_play_id = segment_id
        self._segment_play_end_ms = int(end_s * 1000)
        self._play_from_ms(int(start_s * 1000))

    def on_active_segment_changed(self, segment_id: int) -> None:
        if self._segment_play_id is None:
            return
        if segment_id != self._segment_play_id:
            self.stop()

    def _voiceover_url(self) -> QUrl:
        return QUrl.fromLocalFile(str(self._paths.voiceover_mp3))

    def _voiceover_is_loaded(self) -> bool:
        return self._media_player.mediaStatus() in (
            QMediaPlayer.MediaStatus.LoadedMedia,
            QMediaPlayer.MediaStatus.BufferedMedia,
        )

    def _play_from_ms(self, start_ms: int) -> None:
        """Seek and play, wait until media is loaded (setPosition is ignored before that)."""
        url = self._voiceover_url()
        if self._media_player.source().isEmpty():
            self._pending_start_ms = start_ms
            self._media_player.setSource(url)
            return
        if not self._voiceover_is_loaded():
            self._pending_start_ms = start_ms
            return
        self._pending_start_ms = None
        self._media_player.setPosition(start_ms)
        self._media_player.play()

    def _on_media_status_changed(self, status: QMediaPlayer.MediaStatus) -> None:
        if self._pending_start_ms is None:
            return
        if status not in (
            QMediaPlayer.MediaStatus.LoadedMedia,
            QMediaPlayer.MediaStatus.BufferedMedia,
        ):
            return
        start_ms = self._pending_start_ms
        self._pending_start_ms = None
        self._media_player.setPosition(start_ms)
        self._media_player.play()

    def _on_position_changed(self, position: int) -> None:
        if self._segment_play_end_ms is not None and position >= self._segment_play_end_ms:
            self.stop()

    def _emit_state_changed(self, *_args: object) -> None:
        self.state_changed.emit()
