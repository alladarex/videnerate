"""Grid controller for SegmentView tile state and interaction flow.

This module owns the dynamic tile area inside segment detail view:
- builds/restores base and result tiles
- performs asynchronous media search
- binds tile clicks to segment media selection
- keeps the media preview tile synchronized with model/cache state
"""

import threading

from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtWidgets import QGridLayout, QLabel, QLineEdit, QScrollArea, QWidget

from core.models.media import (
    ALL_MEDIA,
    GIF_MEDIA,
    IMAGE_MEDIA,
    GifMedia,
    ImageMedia,
    VIDEO_MEDIA,
    VideoMedia,
)
from core.models.segment import Segment
from ui.widgets.segment_tile import column_count_for_viewport
from ui.widgets.search_settings import search_settings_state
from ui.widgets.segment_view_cache import SegmentSearchCache
from ui.widgets.segment_view_base_tiles import build_base_tiles
from ui.widgets.segment_view_media_preview import refresh_media_preview
from ui.widgets.segment_view_preview_cache import SegmentPreviewTempCache
from ui.widgets.segment_view_search_runner import run_distributed_search
from ui.widgets.segment_view_search_logic import (
    build_source_distribution,
    to_cached_results,
)
from ui.widgets.segment_view_result_tiles import GifTile, ImageTile, VideoTile


# Either this SegmentViewGridController has to inherit QObject
class SearchWorker(QObject):

    results_ready = Signal(list)


class SegmentViewGridController:
    """Manage segment view grid state, search lifecycle, and tile preview updates."""

    def __init__(
        self,
        *,
        scroll: QScrollArea,
        grid_host: QWidget,
        grid: QGridLayout,
        tile_size_px: int,
        grid_spacing: int,
        cache: SegmentSearchCache,
        project_title: str,
        on_media_selected,
    ) -> None:
        self._scroll = scroll
        self._grid_host = grid_host
        self._grid = grid
        self._tile_size_px = int(tile_size_px)
        self._grid_spacing = int(grid_spacing)
        self._cache = cache
        self._project_title = project_title
        self._on_media_selected = on_media_selected

        self._tiles: list[QWidget] = []
        self._result_tiles: list[QWidget] = []
        self._search_worker: SearchWorker | None = None
        self._segment: Segment

        self.search_input: QLineEdit | None = None
        self.search_button = None
        self.search_status: QLabel | None = None
        self._media_preview: QLabel | None = None
        self._selected_url: str | None = None
        self._thumb_by_url: dict[str, bytes] = {}
        self._preview_temp_cache = SegmentPreviewTempCache(project_title)

    def set_segment(self, segment: Segment) -> None:
        """Switch active segment and rebuild visible tiles for that segment."""
        self._preview_temp_cache.activate_segment(segment.id)
        self._segment = segment
        self._reset_tiles()
        self.rebuild_grid()

    def rebuild_grid(self) -> None:
        """Re-layout currently built tiles based on viewport width."""
        viewport_width = self._scroll.viewport().width()
        cols = column_count_for_viewport(
            viewport_width,
            tile_size_px=self._tile_size_px,
            grid_spacing=self._grid_spacing,
        )

        while self._grid.count():
            item = self._grid.takeAt(0)
            if item is None:
                break

        for i, tile in enumerate(self._tiles):
            row = i // cols
            col = i % cols
            self._grid.addWidget(tile, row, col)
        # Re-apply preview scaling after rebuilding
        self._sync_media_preview()

    def _reset_tiles(self) -> None:
        """Recreate base tiles and restore cached result tiles for active segment."""
        for w in self._tiles:
            try:
                w.hide()
                self._grid.removeWidget(w)
                # destroy this object safely at the next event-loop turn
                w.deleteLater()
            except (RuntimeError, TypeError) as e:
                print(f"[segment_view_grid] tile teardown skipped: {e}")

        self._tiles = []
        self._result_tiles = []
        self.search_input = None
        self.search_status = None

        base = build_base_tiles(
            parent=self._grid_host,
            tile_size_px=self._tile_size_px,
            segment=self._segment,
            on_search_clicked=self._on_search_clicked,
        )
        self._tiles.extend(base.tiles)
        self.search_input = base.search_input
        self.search_button = base.search_button
        self.search_status = base.search_status
        self._media_preview = base.media_preview


        cached = self._cache.get(self._segment.id)
        if cached is not None:
            if self.search_input is not None:
                self.search_input.setText(cached.query)

            restored = 0
            self._selected_url = None
            self._thumb_by_url = {}
            for item in cached.results:
                media_type = item.type
                url = item.url
                b = bytes(item.thumb_bytes)
                if media_type not in ALL_MEDIA or not url or not b:
                    raise ValueError(f"Invalid cached result: {item!r}")
                tile = self._build_result_tile(media_type=media_type, url=url, thumb=b)
                self._tiles.append(tile)
                self._result_tiles.append(tile)
                restored += 1
                self._thumb_by_url[url] = b

            if restored: #and self.search_status is not None:
                self.search_status.setText(f"Showing {restored} cached result(s).")

        # Always reflect current segment.media in the 'current' Media preview tile
        self._sync_media_preview()

    def _set_search_busy(self, busy: bool, status: str = "") -> None:
        self.search_button.setEnabled(not busy)
        self.search_status.setText(status)

    def _build_result_tile(self, *, media_type: str, url: str, thumb: bytes) -> QWidget:
        seg_id = self._segment.id
        if media_type == VIDEO_MEDIA:
            tile = VideoTile(
                size_px=self._tile_size_px,
                media_url=url,
                cache_path=self._preview_temp_cache.path_for_url(url, seg_id, fallback_ext=".mp4"),
                parent=self._grid_host,
            )
            tile.set_thumbnail_bytes(thumb)
            tile.clicked.connect(
                lambda u=url, b=bytes(thumb): self._select_media(
                    u, b, media_type=VIDEO_MEDIA
                )
            )
            return tile
        if media_type == IMAGE_MEDIA:
            tile = ImageTile(size_px=self._tile_size_px, parent=self._grid_host)
            tile.set_thumbnail_bytes(thumb)
            tile.clicked.connect(
                lambda u=url, b=bytes(thumb): self._select_media(
                    u, b, media_type=IMAGE_MEDIA
                )
            )
            return tile
        if media_type == GIF_MEDIA:
            tile = GifTile(
                size_px=self._tile_size_px,
                media_url=url,
                cache_path=self._preview_temp_cache.path_for_url(url, seg_id, fallback_ext=".gif"),
                parent=self._grid_host,
            )
            tile.set_thumbnail_bytes(thumb)
            tile.clicked.connect(
                lambda u=url, b=bytes(thumb): self._select_media(
                    u, b, media_type=GIF_MEDIA
                )
            )
            return tile
        raise ValueError(f"Unknown media type: {media_type}")

    def _clear_results(self) -> None:
        """Remove dynamic result tiles while keeping the 4 base tiles."""
        for w in self._result_tiles:
            try:
                w.hide()
                self._grid.removeWidget(w)
                w.deleteLater()
            except (RuntimeError, TypeError) as e:
                print(f"[segment_view_grid] result tile teardown skipped: {e}")
        self._result_tiles = []
        self._tiles = self._tiles[:4]
        self._selected_url = None
        self._sync_media_preview()

    def _on_search_clicked(self) -> None:
        if self.search_input is None:
            return
        query = self.search_input.text().strip()
        if not query:
            self._set_search_busy(False, "Type a keyword first.")
            return

        settings = search_settings_state()
        limit = settings.limit
        use_google = settings.google
        use_giphy = settings.giphy
        use_pexels_images = settings.pexels_image
        use_pexels_videos = settings.pexels_video
        use_pixabay_images = settings.pixabay_image
        use_pixabay_videos = settings.pixabay_video

        if not (
            use_google
            or use_giphy
            or use_pexels_images
            or use_pexels_videos
            or use_pixabay_images
            or use_pixabay_videos
        ):
            self._set_search_busy(False, "Enable at least one supported source first.")
            return

        source_distribution = build_source_distribution(
            limit=limit,
            use_google=use_google,
            use_giphy=use_giphy,
            use_pexels_images=use_pexels_images,
            use_pexels_videos=use_pexels_videos,
            use_pixabay_images=use_pixabay_images,
            use_pixabay_videos=use_pixabay_videos,
        )

        self._clear_results()
        self._set_search_busy(True, f"Searching “{query}”…")

        if self._search_worker is None:
            self._search_worker = SearchWorker(self._grid_host)
            self._search_worker.results_ready.connect(self._on_search_results_ready)

        def run() -> None:
            merged = run_distributed_search(
                query=query,
                limit=limit,
                source_distribution=source_distribution,
            )
            self._search_worker.results_ready.emit(merged)

        threading.Thread(target=run, daemon=True).start()

    def _on_search_results_ready(self, results: list) -> None:
        """Create clickable result tiles from fetched results and cache them."""
        if not results:
            self._set_search_busy(False, "No results (or blocked). Try another keyword.")
            self.rebuild_grid()
            return

        added = 0
        self._thumb_by_url = {}
        for media_type, url, data in results:
            tile = self._build_result_tile(
                media_type=media_type, url=url, thumb=bytes(data)
            )
            self._tiles.append(tile)
            self._result_tiles.append(tile)
            added += 1
            self._thumb_by_url[url] = bytes(data)

        self._cache.set(
            self._segment.id,
            query=self.search_input.text().strip(),
            results=to_cached_results(results),
        )

        self._set_search_busy(False, f"Showing {added}/{search_settings_state().limit} result(s).")
        self.rebuild_grid()

    def _select_media(
        self, url: str, thumb_bytes: bytes, *, media_type: str = IMAGE_MEDIA
    ) -> None:
        if media_type == IMAGE_MEDIA:
            self._segment.set_media(ImageMedia(url=url))
        if media_type == VIDEO_MEDIA:
            self._segment.set_media(VideoMedia(url=url))
        if media_type == GIF_MEDIA:
            self._segment.set_media(GifMedia(url=url))
        self._selected_url = url
        self._on_media_selected(self._segment.id, thumb_bytes)
        self._sync_media_preview(thumb_bytes=thumb_bytes)

    def _sync_media_preview(self, *, thumb_bytes: bytes | None = None) -> None:
        refresh_media_preview(
            segment=self._segment,
            media_preview_label=self._media_preview,
            tile_size_px=self._tile_size_px,
            project_title=self._project_title,
            thumb_by_url=self._thumb_by_url,
            thumb_bytes=thumb_bytes,
        )

