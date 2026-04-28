from pathlib import Path
import threading
import urllib.request

from PySide6.QtCore import QEvent, QObject, QSize, QTimer, Qt, QUrl, Signal
from PySide6.QtGui import QEnterEvent, QMouseEvent, QMovie, QPixmap
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer, QVideoFrame, QVideoSink
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QStackedLayout,
    QVBoxLayout,
    QWidget,
)

from ui.styles.qss import MUTED_LABEL
from ui.widgets.tile_frame import TileFrame
from ui.widgets.tile_pixmap import (
    inner_preview_edge,
    load_scaled_pixmap,
    load_scaled_pixmap_from_path,
)


def _icon_path(name: str) -> Path:
    # ui/widgets/segment_view_result_tiles.py -> ui/
    return Path(__file__).resolve().parents[1] / "assets" / "icons" / name


_ICON_PIXMAP_CACHE: dict[str, QPixmap | None] = {}


def _cached_icon_pixmap(icon_filename: str) -> QPixmap | None:
    cached = _ICON_PIXMAP_CACHE.get(icon_filename)
    if cached is not None:
        return cached
    pixmap = load_scaled_pixmap_from_path(_icon_path(icon_filename), 16)
    _ICON_PIXMAP_CACHE[icon_filename] = pixmap
    return pixmap


class _BaseResultTile(TileFrame):
    def __init__(
        self,
        *,
        size_px: int,
        icon_filename: str,
        placeholder_text: str,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(size_px=size_px, parent=parent, hover_shadow=True)
        self._placeholder_text = placeholder_text
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        root = QVBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(8)

        icon_row = QHBoxLayout()
        icon_row.setContentsMargins(0, 0, 0, 0)
        icon_row.setSpacing(0)

        self._icon_label = QLabel(self)
        self._icon_label.setFixedSize(18, 18)
        self._icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._icon_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        icon = _cached_icon_pixmap(icon_filename)
        if icon is not None:
            self._icon_label.setPixmap(icon)
            self._icon_label.setText("")
        else:
            self._icon_label.setText("•")
        icon_row.addWidget(self._icon_label, 0, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        icon_row.addStretch(1)
        root.addLayout(icon_row, 0)

        self._content_host = QWidget(self)
        self._content_host.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self._content_stack = QStackedLayout(self._content_host)
        self._content_stack.setContentsMargins(0, 0, 0, 0)

        self._label = QLabel(self._content_host)
        self._label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._label.setStyleSheet(MUTED_LABEL)
        self._label.setText(placeholder_text)
        self._label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self._content_stack.addWidget(self._label)
        root.addWidget(self._content_host, 1)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)

    def set_thumbnail_bytes(self, data: bytes) -> None:
        target = inner_preview_edge(self.width(), reserved=40)
        pixmap = load_scaled_pixmap(data, target)
        if pixmap is None:
            self._label.setText(self._placeholder_text)
            return
        self._label.setPixmap(pixmap)
        self._label.setText("")
        self._content_stack.setCurrentWidget(self._label)

    def _add_content_widget(self, widget: QWidget) -> None:
        widget.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self._content_stack.addWidget(widget)

    def _show_thumbnail(self) -> None:
        self._content_stack.setCurrentWidget(self._label)


class _HoverDownloadWorker(QObject):
    ready = Signal(str)
    failed = Signal()

    def download(self, *, url: str, target_path: Path) -> None:
        try:
            target_path.parent.mkdir(parents=True, exist_ok=True)
            if not target_path.exists():
                req = urllib.request.Request(
                    url,
                    headers={
                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
                        "Accept-Language": "en-US,en;q=0.9",
                    },
                )
                with urllib.request.urlopen(req, timeout=20.0) as resp:
                    target_path.write_bytes(resp.read())
            self.ready.emit(str(target_path))
        except Exception:
            self.failed.emit()


class _HoverPlayableTile(_BaseResultTile):
    def __init__(
        self,
        *,
        size_px: int,
        icon_filename: str,
        placeholder_text: str,
        media_url: str,
        cache_path: Path,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(
            size_px=size_px,
            icon_filename=icon_filename,
            placeholder_text=placeholder_text,
            parent=parent,
        )
        self._media_url = media_url
        self._cache_path = cache_path
        self._hovered = False
        self._download_started = False
        self._cached_media_path: str | None = str(cache_path) if cache_path.exists() else None
        self._preview_edge = inner_preview_edge(self.width(), reserved=40)

        self._hover_timer = QTimer(self)
        self._hover_timer.setSingleShot(True)
        self._hover_timer.setInterval(500)
        self._hover_timer.timeout.connect(self._on_hover_delay_elapsed)

        self._loading_overlay = QLabel(self._content_host)
        self._loading_overlay.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self._loading_overlay.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._loading_overlay.setStyleSheet("background: transparent;")
        self._loading_overlay.resize(self._content_host.size())
        self._loading_overlay.hide()
        spinner_path = _icon_path("spinner.gif")
        self._spinner_movie: QMovie | None = None
        if spinner_path.exists():
            self._spinner_movie = QMovie(str(spinner_path))
            self._spinner_movie.setScaledSize(QSize(40, 40))
            self._loading_overlay.setMovie(self._spinner_movie)
        else:
            self._loading_overlay.setText("Loading...")
            self._loading_overlay.setStyleSheet(MUTED_LABEL)

        self._downloader = _HoverDownloadWorker()
        self._downloader.ready.connect(self._on_download_ready)
        self._downloader.failed.connect(self._on_download_failed)

    def _show_loading_overlay(self) -> None:
        self._loading_overlay.resize(self._content_host.size())
        self._loading_overlay.show()
        self._loading_overlay.raise_()
        if self._spinner_movie is not None:
            self._spinner_movie.start()

    def _hide_loading_overlay(self) -> None:
        if self._spinner_movie is not None:
            self._spinner_movie.stop()
        self._loading_overlay.hide()

    def enterEvent(self, event: QEnterEvent) -> None:
        super().enterEvent(event)
        self._hovered = True
        self._hover_timer.start()

    def leaveEvent(self, event: QEvent) -> None:
        super().leaveEvent(event)
        self._hovered = False
        self._hover_timer.stop()
        self._hide_loading_overlay()
        self._stop_preview()
        self._show_thumbnail()

    def _on_hover_delay_elapsed(self) -> None:
        if not self._hovered:
            return
        if self._cached_media_path:
            self._start_preview(self._cached_media_path)
            return
        self._show_loading_overlay()
        if self._download_started:
            return
        self._download_started = True
        threading.Thread(
            target=lambda: self._downloader.download(
                url=self._media_url,
                target_path=self._cache_path,
            ),
            daemon=True,
        ).start()

    def _on_download_ready(self, path: str) -> None:
        self._cached_media_path = path
        if self._hovered:
            self._start_preview(path)
        else:
            self._hide_loading_overlay()
            self._show_thumbnail()

    def _on_download_failed(self) -> None:
        self._download_started = False
        self._hide_loading_overlay()
        self._show_thumbnail()

    # Implemented by subclasses, Qt widgets uses a metaclass that conflicts with abc.ABCMeta
    # so we can't use an abstract method
    def _start_preview(self, path: str) -> None:
        raise NotImplementedError

    def _stop_preview(self) -> None:
        raise NotImplementedError

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._loading_overlay.resize(self._content_host.size())


class ImageTile(_BaseResultTile):

    clicked = Signal()

    def __init__(self, *, size_px: int, parent: QWidget | None = None) -> None:
        super().__init__(
            size_px=size_px,
            icon_filename="image-w.png",
            placeholder_text="Image failed",
            parent=parent,
        )


class VideoTile(_HoverPlayableTile):

    clicked = Signal()

    def __init__(
        self,
        *,
        size_px: int,
        media_url: str,
        cache_path: Path,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(
            size_px=size_px,
            icon_filename="video-w.png",
            placeholder_text="Video failed",
            media_url=media_url,
            cache_path=cache_path,
            parent=parent,
        )

        self._video_label = QLabel(self._content_host)
        self._video_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._add_content_widget(self._video_label)

        # Use QVideoSink so QMediaPlayer gives us decoded frames directly, we then paint
        # them into a normal QLabel. This avoids first-hover blank/offset behavior from
        # QVideoWidget in stacked layouts, where native video surfaces may not be ready
        # until the widget is fully shown
        self._video_sink = QVideoSink(self)
        self._video_sink.videoFrameChanged.connect(self._on_video_frame_changed)

        self._audio_output = QAudioOutput(self)
        self._audio_output.setMuted(True)
        self._player = QMediaPlayer(self)
        self._player.setAudioOutput(self._audio_output)
        self._player.setVideoSink(self._video_sink)
        self._player.mediaStatusChanged.connect(self._on_media_status_changed)
        self._player.errorOccurred.connect(self._on_media_error)

    def _on_media_status_changed(self, status: QMediaPlayer.MediaStatus) -> None:
        if status == QMediaPlayer.MediaStatus.EndOfMedia and self._hovered:
            self._player.setPosition(0)
            self._player.play()

    def _on_media_error(self, *_args) -> None:
        self._show_thumbnail()

    def _on_video_frame_changed(self, frame: QVideoFrame) -> None:
        if not self._hovered:
            return
        if not frame.isValid():
            return
        image = frame.toImage()
        if image.isNull():
            return
        pixmap = QPixmap.fromImage(image).scaled(
            self._preview_edge,
            self._preview_edge,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self._video_label.setPixmap(pixmap)
        self._hide_loading_overlay()
        if self._content_stack.currentWidget() is not self._video_label:
            self._content_stack.setCurrentWidget(self._video_label)

    def _start_preview(self, path: str) -> None:
        self._player.setSource(QUrl.fromLocalFile(path))
        self._player.play()

    def _stop_preview(self) -> None:
        self._player.stop()


class GifTile(_HoverPlayableTile):

    clicked = Signal()

    def __init__(
        self,
        *,
        size_px: int,
        media_url: str,
        cache_path: Path,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(
            size_px=size_px,
            icon_filename="gif-w.png",
            placeholder_text="GIF failed",
            media_url=media_url,
            cache_path=cache_path,
            parent=parent,
        )
        self._gif_label = QLabel(self._content_host)
        self._gif_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._add_content_widget(self._gif_label)
        self._movie: QMovie | None = None

    def _gif_scaled_size(self) -> QSize:
        # Unlike video, QMovie renders frames internally at a fixed output size we
        # specify via setScaledSize. If we pass a square it stretches the GIF,
        # ignoring AR. So we read the GIF's natural size first and compute the
        # AR-preserving dimensions that fit within the preview square.
        natural = self._movie.currentPixmap().size()
        if not natural.isValid() or natural.isEmpty():
            return QSize(self._preview_edge, self._preview_edge)
        return natural.scaled(self._preview_edge, self._preview_edge, Qt.AspectRatioMode.KeepAspectRatio)

    def _start_preview(self, path: str) -> None:
        if self._movie is not None:
            self._movie.stop()
        self._movie = QMovie(path)
        self._movie.setCacheMode(QMovie.CacheMode.CacheAll)
        self._movie.jumpToFrame(0)
        self._movie.setScaledSize(self._gif_scaled_size())
        self._gif_label.setMovie(self._movie)
        self._hide_loading_overlay()
        self._content_stack.setCurrentWidget(self._gif_label)
        self._movie.start()

    def _stop_preview(self) -> None:
        if self._movie is not None:
            self._movie.stop()


