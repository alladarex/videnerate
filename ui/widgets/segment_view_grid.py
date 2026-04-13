"""Grid controller for SegmentView tiles and media selection flow.

This module owns the dynamic tile area inside segment detail view:
- builds/restores base and result tiles
- performs asynchronous media search
- binds tile clicks to segment media selection
- keeps the media preview tile synchronized with model/cache state
"""

import threading
from pathlib import Path

from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtWidgets import QGridLayout, QLabel, QLineEdit, QScrollArea, QWidget

from core.models.media import ImageMedia
from core.models.segment import Segment
from config import PROJECTS_DIR
from ui.widgets.segment_tile import column_count_for_viewport
from services.image_search_ddg import fetch_image_results
from ui.widgets.segment_view_cache import SegmentSearchCache
from ui.widgets.segment_view_base_tiles import build_base_tiles
from ui.widgets.segment_view_result_tiles import ImageTile
from ui.widgets.tile_pixmap import (
    inner_preview_edge,
    load_scaled_pixmap,
    load_scaled_pixmap_from_path,
)


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
            except Exception:
                pass

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
            for url, b in cached.images[:10]:
                sq = ImageTile(size_px=self._tile_size_px, parent=self._grid_host)
                sq.set_image_bytes(b)
                sq.clicked.connect(lambda u=url, tb=b: self._select_media(u, tb))
                self._tiles.append(sq)
                self._result_tiles.append(sq)
                restored += 1
                self._thumb_by_url[url] = b

            if restored and self.search_status is not None:
                self.search_status.setText(f"Showing {restored} cached result(s).")

        # Always reflect current segment.media in the Media tile
        self._sync_media_preview()

    def _set_search_busy(self, busy: bool, status: str = "") -> None:
        if self.search_button is not None:
            self.search_button.setEnabled(not busy)
        if self.search_status is not None:
            self.search_status.setText(status)

    def _clear_results(self) -> None:
        """Remove dynamic result tiles while keeping the 4 base tiles."""
        for w in self._result_tiles:
            try:
                w.hide()
                self._grid.removeWidget(w)
                w.deleteLater()
            except Exception:
                pass
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

        self._clear_results()
        self._set_search_busy(True, f"Searching “{query}”…")

        if self._search_worker is None:
            self._search_worker = SearchWorker(self._grid_host)
            self._search_worker.results_ready.connect(self._on_search_results_ready)

        def run() -> None:
            try:
                imgs = fetch_image_results(query, limit=10)
            except Exception:
                imgs = []
            if self._search_worker is not None:
                self._search_worker.results_ready.emit(imgs)

        threading.Thread(target=run, daemon=True).start()

    def _on_search_results_ready(self, images: list) -> None:
        """Create clickable result tiles from fetched results and cache them."""

        results: list[tuple[str, bytes]] = []
        for item in images:
            if (
                isinstance(item, (tuple, list))
                and len(item) == 2
                and isinstance(item[0], str)
                and isinstance(item[1], (bytes, bytearray))
            ):
                results.append((item[0], bytes(item[1])))
        if not results:
            self._set_search_busy(False, "No results (or blocked). Try another keyword.")
            self.rebuild_grid()
            return

        added = 0
        self._thumb_by_url = {}
        for url, data in results[:10]:
            tile = ImageTile(size_px=self._tile_size_px, parent=self._grid_host)
            tile.set_image_bytes(bytes(data))
            tile.clicked.connect(lambda u=url, b=bytes(data): self._select_media(u, b))
            self._tiles.append(tile)
            self._result_tiles.append(tile)
            added += 1
            self._thumb_by_url[url] = bytes(data)

        if self._segment is not None and self.search_input is not None:
            self._cache.set(self._segment.id, query=self.search_input.text().strip(), images=results[:10])

        self._set_search_busy(False, f"Showing {added} result(s).")
        self.rebuild_grid()

    def _select_media(self, url: str, thumb_bytes: bytes) -> None:
        self._segment.set_media(ImageMedia(url=url))
        self._selected_url = url
        self._on_media_selected(self._segment.id, thumb_bytes)
        self._sync_media_preview(thumb_bytes=thumb_bytes)

    def _resolve_project_media_path(self, rel_or_abs: str) -> Path:
        p = Path(rel_or_abs)
        if p.is_absolute():
            return p
        return (PROJECTS_DIR / self._project_title / p).resolve()

    def _sync_media_preview(self, *, thumb_bytes: bytes | None = None) -> None:
        """Draw the first tile's media preview.

        Priority (first match wins):
        1. Saved file on disk — after Save / load from project.json (`file_path`).
        2. Fresh preview bytes — e.g. just clicked a search result (`thumb_bytes`).
        3. Cached preview bytes — same URL as `seg.media.url`, looked up in `_thumb_by_url`
           (filled when search results were built; avoids re-downloading).
        4. Fallback label — URL selected but no preview bytes available yet.
        """

        seg = self._segment
        if seg.media is None:
            self._media_preview.clear()
            self._media_preview.setText("No media selected")
            return

        # Preview area is roughly the tile minus padding; keep scaling stable across reflows
        target = inner_preview_edge(self._tile_size_px, reserved=48)

        # 1) Persisted media (project folder / relative path in JSON)
        if getattr(seg.media, "file_path", None):
            path = self._resolve_project_media_path(seg.media.file_path)
            pixmap = load_scaled_pixmap_from_path(path, target)
            if pixmap is not None:
                self._media_preview.setPixmap(pixmap)
                self._media_preview.setText("")
                return

        # 2) In-memory preview bytes (e.g. passed right after clicking a result tile)
        # These are usually the same small preview bytes used for the result thumbnails
        if thumb_bytes:
            pixmap = load_scaled_pixmap(thumb_bytes, target)
            if pixmap is not None:
                self._media_preview.setPixmap(pixmap)
                self._media_preview.setText("")
                return

        # 3) Reuse cached preview for this URL (set when search results were created)
        if getattr(seg.media, "url", None) and isinstance(seg.media.url, str):
            b = self._thumb_by_url.get(seg.media.url)
            if b:
                self._sync_media_preview(thumb_bytes=b)
                return

        # 4) Nothing drawable yet
        self._media_preview.clear()
        self._media_preview.setText("Media selected")

