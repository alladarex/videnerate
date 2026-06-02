"""Grid controller for SegmentView tile state and interaction flow.

This module owns the dynamic tile area inside segment detail view:
- builds/restores base and search result tiles
- binds tile clicks to segment media selection
- keeps the media preview tile synchronized with model/cache state
"""

from PySide6.QtCore import QObject
from PySide6.QtWidgets import QGridLayout, QLineEdit, QScrollArea, QWidget

from core.models.media import (
    ALL_MEDIA,
    GIF_MEDIA,
    IMAGE_MEDIA,
    VIDEO_MEDIA,
    GifMedia,
    ImageMedia,
    VideoMedia,
)
from core.models.segment import Segment
from core.models.word_timeline import WordTimeline
from ui.utils.grid_layout import column_count_for_viewport
from ui.cache.segment_search_cache import SegmentSearchCache
from ui.widgets.segment_view_base_tiles import build_base_tiles
from ui.widgets.segment_view_media_tile_sync import sync_media_tile
from ui.cache.segment_preview_cache import SegmentPreviewCache
from ui.widgets.preview_playback import SharedVideoPreviewBackend
from ui.widgets.segment_view_result_tiles import build_result_tile
from ui.widgets.segment_view_search_controller import SegmentViewSearchController


class SegmentViewGridController(QObject):
    """Manage segment view grid state, search lifecycle, and tile preview updates."""

    _BASE_TILE_COUNT = 4

    def __init__(
        self,
        *,
        scroll: QScrollArea,
        grid_host: QWidget,
        grid: QGridLayout,
        tile_size_px: int,
        grid_spacing: int,
        cache: SegmentSearchCache,
        preview_cache: SegmentPreviewCache,
        on_media_selected,
        word_timeline: WordTimeline,
    ) -> None:
        super().__init__(grid_host)
        self._scroll = scroll
        self._grid_host = grid_host
        self._grid = grid
        self._tile_size_px = int(tile_size_px)
        self._grid_spacing = int(grid_spacing)
        self._cache = cache
        self._on_media_selected = on_media_selected

        self._tiles: list[QWidget] = []
        self._segment: Segment

        self.search_input: QLineEdit | None = None
        self.search_button = None
        self.search_status = None
        self._media_preview = None
        self._preview_cache = preview_cache

        self._search = SegmentViewSearchController(
            parent=self,
            cache=self._cache,
            word_timeline=word_timeline,
            get_current_segment_id=lambda: self._segment.id,
            clear_results=self._clear_results,
            set_search_busy=self._set_search_busy,
            apply_search_results=self._apply_search_results,
            rebuild_grid=self.rebuild_grid,
        )

    @staticmethod
    def _dispose_widget_preview(widget: QWidget) -> None:
        dispose = getattr(widget, "dispose", None)
        if callable(dispose):
            dispose()

    def set_segment(self, segment: Segment) -> None:
        """Switch active segment and rebuild visible tiles for that segment."""
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
        self._sync_media_tile()

    def _reset_tiles(self) -> None:
        """Recreate base tiles and restore cached result tiles for active segment."""
        for w in self._tiles:
            try:
                self._dispose_widget_preview(w)
                w.hide()
                self._grid.removeWidget(w)
                w.deleteLater()
            except (RuntimeError, TypeError) as e:
                print(f"[segment_view_grid] tile teardown skipped: {e}")

        self._tiles = []
        self.search_input = None
        self.search_status = None
        # Release backend-held media handles before removing temp cache files.
        SharedVideoPreviewBackend.instance().release_source()

        base = build_base_tiles(
            parent=self._grid_host,
            tile_size_px=self._tile_size_px,
            preview_cache=self._preview_cache,
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
            for item in cached.results:
                media_type = item.type
                url = item.url
                b = bytes(item.thumb_bytes)
                if media_type not in ALL_MEDIA or not url or not b:
                    raise ValueError(f"Invalid cached result: {item!r}")
                tile = build_result_tile(
                    media_type=media_type,
                    url=url,
                    thumb=b,
                    source=item.source,
                    size_px=self._tile_size_px,
                    preview_cache=self._preview_cache,
                    parent=self._grid_host,
                    on_select=self._select_media,
                )
                self._tiles.append(tile)
                restored += 1

            if restored:
                self.search_status.setText(f"Showing {restored} cached result(s).")

        # Always reflect current segment.media in the 'current' Media preview tile
        self._sync_media_tile()

        if self._search.is_segment_searching(self._segment.id):
            self._set_search_busy(True, "Searching…")

    def _set_search_busy(self, busy: bool, status: str = "") -> None:
        self.search_button.setEnabled(not busy)
        self.search_status.setText(status)

    def _apply_search_results(self, results: list) -> int:
        added = 0
        for media_type, url, data, source in results:
            tile = build_result_tile(
                media_type=media_type,
                url=url,
                thumb=bytes(data),
                source=source,
                size_px=self._tile_size_px,
                preview_cache=self._preview_cache,
                parent=self._grid_host,
                on_select=self._select_media,
            )
            self._tiles.append(tile)
            added += 1
        return added

    def _clear_results(self) -> None:
        """Remove dynamic result tiles while keeping the base tiles."""
        for w in self._tiles[self._BASE_TILE_COUNT :]:
            try:
                self._dispose_widget_preview(w)
                w.hide()
                self._grid.removeWidget(w)
                w.deleteLater()
            except (RuntimeError, TypeError) as e:
                print(f"[segment_view_grid] result tile teardown skipped: {e}")
        self._tiles = self._tiles[: self._BASE_TILE_COUNT]
        self._sync_media_tile()

    def release_preview_resources(self) -> None:
        for w in self._tiles:
            self._dispose_widget_preview(w)
        SharedVideoPreviewBackend.instance().release_source()

    def _on_search_clicked(self) -> None:
        self._search.on_search_clicked(
            segment=self._segment,
            search_input=self.search_input,
            search_button=self.search_button,
            search_status=self.search_status,
        )

    def _select_media(
        self,
        url: str,
        thumb_bytes: bytes,
        *,
        media_type: str = IMAGE_MEDIA,
        source: str | None = None,
    ) -> None:
        if media_type == IMAGE_MEDIA:
            self._segment.set_media(ImageMedia(url=url, source=source))
        if media_type == VIDEO_MEDIA:
            self._segment.set_media(VideoMedia(url=url, source=source))
        if media_type == GIF_MEDIA:
            self._segment.set_media(GifMedia(url=url, source=source))
        self._on_media_selected(self._segment.id, thumb_bytes)
        self._sync_media_tile(thumb_bytes)

    def _sync_media_tile(self, thumb_bytes: bytes | None = None) -> None:
        if self._media_preview is None:
            return
        sync_media_tile(
            segment=self._segment,
            media_preview=self._media_preview,
            preview_cache=self._preview_cache,
            tile_size_px=self._tile_size_px,
            search_cache=self._cache,
            thumb_bytes=thumb_bytes,
        )