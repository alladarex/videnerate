from pathlib import Path

from PySide6.QtCore import QEvent, QSize, QTimer, Qt
from PySide6.QtGui import QEnterEvent, QMovie, QPixmap
from PySide6.QtMultimedia import QVideoFrame
from PySide6.QtWidgets import QLabel, QSizePolicy, QStackedLayout, QWidget

from core.models.media import Media, MediaType
from ui.cache.segment_preview_cache import SegmentPreviewCache, cached_file_for_base
from ui.styles.qss import MUTED_LABEL, SMALL_MUTED_LABEL
from ui.widgets.preview_download import UrlDownloadBroker
from ui.widgets.preview_playback import SharedVideoPreviewBackend
from ui.utils.project_media_paths import load_media_file_thumbnail
from ui.utils.tile_pixmap import inner_preview_edge, load_scaled_pixmap
from ui.utils.ui_paths import icon_path

_HOVER_DELAY_MS = 500


class HoverMediaPreview(QWidget):
    """Tile surface: thumbnail by default, video/GIF preview on hover."""

    def __init__(
        self,
        *,
        tile_size_px: int,
        reserved: int,
        placeholder_text: str,
        preview_cache: SegmentPreviewCache,
        parent: QWidget,
    ) -> None:
        super().__init__(parent)
        self.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )
        self._tile_size_px = tile_size_px
        self._reserved = reserved
        self._placeholder_text = placeholder_text
        self._preview_cache = preview_cache

        self._media_type: MediaType | None = None
        self._media_url: str | None = None
        self._playback_path: str | None = None
        self._hovered = False
        self._disposed = False
        self._download_started = False
        self._movie: QMovie | None = None

        self._root = QStackedLayout(self)
        self._root.setContentsMargins(0, 0, 0, 0)

        self._thumbnail = QLabel(self)
        self._thumbnail.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._thumbnail.setWordWrap(True)
        self._thumbnail.setStyleSheet(SMALL_MUTED_LABEL)
        self._root.addWidget(self._thumbnail)

        self._video_label = QLabel(self)
        self._video_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._root.addWidget(self._video_label)

        self._gif_label = QLabel(self)
        self._gif_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._root.addWidget(self._gif_label)

        self._loading_overlay = QLabel(self)
        self._loading_overlay.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._loading_overlay.setStyleSheet("background: transparent;")
        self._loading_overlay.hide()
        spinner_path = icon_path("spinner.gif")
        self._spinner_movie: QMovie | None = None
        if spinner_path.exists():
            self._spinner_movie = QMovie(str(spinner_path))
            self._spinner_movie.setScaledSize(QSize(40, 40))
            self._loading_overlay.setMovie(self._spinner_movie)
        else:
            self._loading_overlay.setText("Loading...")
            self._loading_overlay.setStyleSheet(MUTED_LABEL)

        self._hover_timer = QTimer(self)
        self._hover_timer.setSingleShot(True)
        self._hover_timer.setInterval(_HOVER_DELAY_MS)
        self._hover_timer.timeout.connect(self._on_hover_delay_elapsed)
        self._show_thumbnail()

    def clear_media(self) -> None:
        """Clear bound media when the segment has no selection (placeholder only)."""
        self._bind(media_type=None, media_url=None)
        self._show_thumbnail()

    def show_media(self, media: Media, *, thumb_bytes: bytes | None = None) -> None:
        """Bind 'media' and draw it.

        Priority (first match wins):
        1. Saved file on disk, which exists once the project has been saved.
        2. 'thumb_bytes', the thumbnail from the caller

        If neither source produces an image the tile shows "Thumbnail error".
        """
        # 1) The image file in the project folder, which only exists after a save
        pixmap = load_media_file_thumbnail(
            media=media,
            tile_size_px=self._tile_size_px,
            reserved=self._reserved,
            preview_cache=self._preview_cache,
        )

        # 2) The thumbnail the view saved when this media was picked from search results
        if pixmap is None and thumb_bytes:
            target = inner_preview_edge(self._tile_size_px, reserved=self._reserved)
            pixmap = load_scaled_pixmap(thumb_bytes, target)

        self._bind(
            media_type=media.media_type,
            media_url=media.url,
            file_path=media.file_path,
        )
        if pixmap is None:
            self.set_placeholder_text("Thumbnail error")
        else:
            self.set_thumbnail_pixmap(pixmap)

    def bind_from_search_url(self, *, media_type: MediaType, media_url: str) -> None:
        """Make a search-result tile hoverable.

        Only URL-based hover and download work here, there is no Media model and so
        no local file to fall back on. The thumbnail is not passed in because the
        tile gets it a moment later: 'build_result_tile' hands over the
        'SearchResult.thumb_bytes' that the search provider already downloaded.
        """
        self._bind(media_type=media_type, media_url=media_url)
        self._show_thumbnail()

    def set_placeholder_text(self, text: str) -> None:
        self._placeholder_text = text
        self._thumbnail.setPixmap(QPixmap())
        self._thumbnail.setText(text)
        self._root.setCurrentWidget(self._thumbnail)

    def set_thumbnail_bytes(self, thumbnail_bytes: bytes | None) -> None:
        self._show_thumbnail(thumbnail_bytes=thumbnail_bytes)

    def set_thumbnail_pixmap(self, pixmap: QPixmap | None) -> None:
        self._show_thumbnail(pixmap=pixmap)

    def enterEvent(self, event: QEnterEvent) -> None:
        super().enterEvent(event)
        self.on_hover_enter()

    def leaveEvent(self, event: QEvent) -> None:
        super().leaveEvent(event)
        self.on_hover_leave()

    def on_hover_enter(self) -> None:
        self._hovered = True
        if self._media_type in (MediaType.VIDEO, MediaType.GIF):
            self._hover_timer.start()

    def on_hover_leave(self) -> None:
        self._hovered = False
        self._hover_timer.stop()
        self._stop_preview()
        self._root.setCurrentWidget(self._thumbnail)

    def dispose(self) -> None:
        self._disposed = True
        self._hover_timer.stop()
        self._stop_preview()

    def is_hovered(self) -> bool:
        return self._hovered

    def _bind(
        self,
        *,
        media_type: MediaType | None,
        media_url: str | None,
        file_path: str | None = None,
    ) -> None:
        """Remember which media this tile shows, so hovering knows what to play.

        This only stores values, it never draws. Whoever calls it draws afterwards
        Passing no type and no url leaves the tile showing nothing, 
        which is what 'clear_media' wants.
        """
        self._stop_preview()
        self._media_type = media_type
        self._media_url = media_url
        self._playback_path = self._resolve_playback_path(
            media_url=media_url, file_path=file_path
        )
        self._download_started = False

    def _show_thumbnail(
        self,
        *,
        thumbnail_bytes: bytes | None = None,
        pixmap: QPixmap | None = None,
    ) -> None:
        if thumbnail_bytes:
            target = inner_preview_edge(self._tile_size_px, reserved=self._reserved)
            pixmap = load_scaled_pixmap(thumbnail_bytes, target)
        if pixmap is not None and not pixmap.isNull():
            self._thumbnail.setPixmap(pixmap)
            self._thumbnail.setText("")
        else:
            self._thumbnail.setPixmap(QPixmap())
            self._thumbnail.setText(self._placeholder_text)
        self._root.setCurrentWidget(self._thumbnail)

    def _resolve_playback_path(
        self, *, media_url: str | None, file_path: str | None
    ) -> str | None:
        """Find a local file to play, or None when hovering will have to download one.

        Both inputs are parameters rather than fields, so this cannot read state that
        its caller is halfway through updating.
        """
        if file_path:
            path = self._preview_cache.paths.file(file_path)
            if path.is_file():
                return str(path)
        if media_url:
            cached = cached_file_for_base(
                self._preview_cache.cache_base_for_url(media_url)
            )
            if cached is not None:
                return str(cached)
        return None

    def _stop_preview(self) -> None:
        self._hide_loading_overlay()
        SharedVideoPreviewBackend.instance().stop()
        if self._movie is not None:
            self._movie.stop()
            self._gif_label.setMovie(None)
            self._movie.deleteLater()
            self._movie = None

    def _show_loading_overlay(self) -> None:
        self._loading_overlay.resize(self.size())
        self._loading_overlay.show()
        self._loading_overlay.raise_()
        if self._spinner_movie is not None:
            self._spinner_movie.start()

    def _hide_loading_overlay(self) -> None:
        if self._spinner_movie is not None:
            self._spinner_movie.stop()
        self._loading_overlay.hide()

    def _on_hover_delay_elapsed(self) -> None:
        if not self._hovered or self._media_type not in (MediaType.VIDEO, MediaType.GIF):
            return
        path = self._playback_path
        if path and Path(path).is_file():
            self._start_preview(path)
            return
        if not self._media_url or self._download_started:
            return
        self._show_loading_overlay()
        self._download_started = True
        UrlDownloadBroker.instance().request(
            url=self._media_url,
            target_base=self._preview_cache.cache_base_for_url(self._media_url),
            on_done=self._on_download_finished,
        )

    def _on_download_finished(self, path: str | None) -> None:
        if self._disposed:
            return
        self._download_started = False
        if path is None:
            self._hide_loading_overlay()
            self._root.setCurrentWidget(self._thumbnail)
            return
        self._playback_path = path
        if self._hovered:
            self._start_preview(path)
        else:
            self._hide_loading_overlay()

    def _start_preview(self, path: str) -> None:
        if self._media_type == MediaType.VIDEO:
            SharedVideoPreviewBackend.instance().play_for(self, path)
            return
        if self._media_type == MediaType.GIF:
            if self._movie is not None:
                self._movie.stop()
            self._movie = QMovie(path)
            self._movie.setCacheMode(QMovie.CacheMode.CacheAll)
            self._movie.jumpToFrame(0)
            target = inner_preview_edge(self._tile_size_px, reserved=self._reserved)
            natural = self._movie.currentPixmap().size()
            if natural.isValid() and not natural.isEmpty():
                self._movie.setScaledSize(
                    natural.scaled(target, target, Qt.AspectRatioMode.KeepAspectRatio)
                )
            else:
                self._movie.setScaledSize(QSize(target, target))
            self._gif_label.setMovie(self._movie)
            self._hide_loading_overlay()
            self._root.setCurrentWidget(self._gif_label)
            self._movie.start()

    def on_video_error(self) -> None:
        self._root.setCurrentWidget(self._thumbnail)
        self._hide_loading_overlay()

    def on_video_frame(self, frame: QVideoFrame) -> None:
        if not self._hovered or not frame.isValid():
            return
        image = frame.toImage()
        if image.isNull():
            return
        target = inner_preview_edge(self._tile_size_px, reserved=self._reserved)
        pixmap = QPixmap.fromImage(image).scaled(
            target,
            target,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self._video_label.setPixmap(pixmap)
        self._hide_loading_overlay()
        if self._root.currentWidget() is not self._video_label:
            self._root.setCurrentWidget(self._video_label)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._loading_overlay.resize(self.size())