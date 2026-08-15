"""Grid controller for SegmentView tile state and interaction flow.

This module owns the dynamic tile area inside segment detail view:
- builds/restores base and search result tiles
- runs media search off the UI thread and turns the results into tiles
- binds tile clicks to segment media selection
- keeps the media preview tile synchronized with the active segment's media
"""

from collections.abc import Callable

from PySide6.QtCore import QObject
from PySide6.QtWidgets import QGridLayout, QLabel, QLineEdit, QPushButton, QScrollArea, QWidget

from core.models.media import Media
from core.models.segment import Segment
from core.models.word_timeline import WordTimeline, segment_playback_duration
from services.media_search import run_distributed_search
from services.search_common import SearchResult
from ui.cache.segment_preview_cache import SegmentPreviewCache
from ui.cache.segment_search_cache import SegmentSearchCache
from ui.utils.background_task import run_in_thread
from ui.utils.grid_layout import relayout_grid
from ui.widgets.hover_media_preview import HoverMediaPreview
from ui.widgets.preview_playback import SharedVideoPreviewBackend
from ui.widgets.search_settings import search_settings_state
from ui.widgets.segment_view_base_tiles import build_base_tiles
from ui.widgets.segment_view_result_tiles import build_result_tile


def attach_media(segment: Segment, result: SearchResult) -> None:
    """Set the result as the segment's media. The file itself downloads at save."""
    segment.media = Media(result.media_type, url=result.url, source=result.source)


class SegmentViewGridController(QObject):
    """Manage segment view grid state, search lifecycle, and tile preview updates."""

    def __init__(
        self,
        *,
        scroll: QScrollArea,
        grid_host: QWidget,
        grid: QGridLayout,
        tile_size_px: int,
        grid_spacing: int,
        search_cache: SegmentSearchCache,
        preview_cache: SegmentPreviewCache,
        on_media_selected: Callable[[int, bytes], None],
        word_timeline: WordTimeline,
        is_segment_running: Callable[[int], bool],
        on_manual_search_started: Callable[[int], None],
        on_results_changed: Callable[[], None],
    ) -> None:
        super().__init__(grid_host)
        self._scroll = scroll
        self._grid_host = grid_host
        self._grid = grid
        self._tile_size_px = int(tile_size_px)
        self._grid_spacing = int(grid_spacing)
        self._search_cache = search_cache
        self._preview_cache = preview_cache
        self._on_media_selected = on_media_selected
        self._word_timeline = word_timeline
        # The view owns this state, the grid only reads and reports it: the first asks
        # whether auto-assign holds a segment, the other two say something changed.
        self._is_segment_running = is_segment_running
        self._on_manual_search_started = on_manual_search_started
        self._on_results_changed = on_results_changed

        self._tiles: list[QWidget] = []
        # Base tiles survive a result clear, so results start at this index.
        self._base_tile_count = 0
        self._segment: Segment
        # A search outlives the segment it was started for, so the spinner can be
        # restored when the user navigates back before the results arrive.
        self._searching_segment_ids: set[int] = set()
        # Thumbnail image of the media attached to each segment, by segment id.
        # Clicking a search result stores only the media's url. The file itself is
        # downloaded when the project is saved, so until then there is nothing on
        # disk to draw and these bytes are the Media tile's only picture.
        # Kept here rather than on the preview widget because the segment view
        # rebuilds that widget every time the user moves to another segment.
        self._thumb_bytes_by_segment_id: dict[int, bytes] = {}

        # Built by '_rebuild_tiles', like '_segment' above.
        self._search_input: QLineEdit
        self._search_btn: QPushButton
        self._search_status: QLabel
        # Assigned by the first '_rebuild_tiles', so None until 'set_segment' runs.
        self._media_preview: HoverMediaPreview | None = None

    @staticmethod
    def _dispose_widget(widget: QWidget) -> None:
        dispose = getattr(widget, "dispose", None)
        if callable(dispose):
            dispose()

    def set_segment(self, segment: Segment) -> None:
        """Switch active segment and rebuild visible tiles for that segment."""
        self._segment = segment
        self.reload()

    def reload(self) -> None:
        """Rebuild the tiles for the segment already set, after its entry changed."""
        self._rebuild_tiles()
        self.relayout_grid()

    def relayout_grid(self) -> None:
        """Rewrap the tiles already built into as many columns as now fit."""
        relayout_grid(
            self._tiles,
            scroll=self._scroll,
            grid=self._grid,
            tile_size_px=self._tile_size_px,
            grid_spacing=self._grid_spacing,
        )
        self.sync_media_tile()

    def _rebuild_tiles(self) -> None:
        """Recreate base tiles and restore cached result tiles for active segment."""
        for tile in self._tiles:
            try:
                self._dispose_widget(tile)
                tile.hide()
                self._grid.removeWidget(tile)
                tile.deleteLater()
            except (RuntimeError, TypeError) as exc:
                print(f"[segment_view_grid] tile teardown skipped: {exc}")

        self._tiles = []

        # Release backend-held media handles before removing temp cache files.
        SharedVideoPreviewBackend.instance().release_source()

        base = build_base_tiles(
            parent=self._grid_host,
            tile_size_px=self._tile_size_px,
            preview_cache=self._preview_cache,
            on_search_clicked=self._on_search_clicked,
        )
        self._tiles.extend(base.tiles)
        self._base_tile_count = len(base.tiles)
        self._search_input = base.search_input
        self._search_btn = base.search_btn
        self._search_status = base.search_status
        self._media_preview = base.media_preview

        cached = self._search_cache.get(self._segment.id)
        if cached is not None:
            self._search_input.setText(cached.query)

            for result in cached.results:
                self._tiles.append(self._build_result_tile(result))

            if cached.error is not None:
                self._search_status.setText("Auto-assign failed, search manually.")
            elif cached.results:
                self._search_status.setText(f"Showing {len(cached.results)} cached result(s).")
            elif cached.suggestions is not None:
                # Auto-assign ran and came back empty, which has to read
                # differently from a segment its queue has not reached yet.
                self._search_status.setText("Auto-assign found nothing, try another keyword.")

        # Always reflect current segment.media in the 'current' Media preview tile
        self.sync_media_tile()

        if self._is_segment_running(self._segment.id):
            self._lock_search("Finding media…")
        elif self._segment.id in self._searching_segment_ids:
            self._set_search_loading(True, "Searching…")

    def _set_search_loading(self, is_loading: bool, status: str = "") -> None:
        self._search_btn.setEnabled(not is_loading)
        self._search_status.setText(status)

    def _lock_search(self, status: str) -> None:
        """Auto-assign owns this segment right now, so the input locks too.

        There is no unlock: delivery, failure and Stop all rebuild the tiles,
        which recreates both widgets enabled.
        """
        self._search_input.setEnabled(False)
        self._search_btn.setEnabled(False)
        self._search_status.setText(status)

    def _build_result_tile(self, result: SearchResult) -> QWidget:
        return build_result_tile(
            result,
            size_px=self._tile_size_px,
            preview_cache=self._preview_cache,
            parent=self._grid_host,
            on_select=self._select_media,
        )

    def _clear_results(self) -> None:
        """Remove dynamic result tiles while keeping the base tiles."""
        for tile in self._tiles[self._base_tile_count :]:
            try:
                self._dispose_widget(tile)
                tile.hide()
                self._grid.removeWidget(tile)
                tile.deleteLater()
            except (RuntimeError, TypeError) as exc:
                print(f"[segment_view_grid] result tile teardown skipped: {exc}")
        self._tiles = self._tiles[: self._base_tile_count]
        self.sync_media_tile()

    def release_preview_resources(self) -> None:
        for tile in self._tiles:
            self._dispose_widget(tile)
        SharedVideoPreviewBackend.instance().release_source()

    def _on_search_clicked(self) -> None:
        """Validate the query, then run the search off the UI thread."""
        query = self._search_input.text().strip()
        if not query:
            self._set_search_loading(False, "Type a keyword first.")
            return

        settings = search_settings_state()
        limit = settings.limit
        providers = set(settings.enabled)

        # Should be unreachable, search settings should always have at least one enabled source
        if not providers:
            self._set_search_loading(False, "Enable at least one supported source first.")
            return

        self._clear_results()
        segment_id = self._segment.id
        # Overwrites any auto-search entry, which drops its proposals and marks
        # the segment as the user's in one call
        self._search_cache.set(segment_id, query=query, results=[])
        self._on_manual_search_started(segment_id)
        self._set_search_loading(True, f"Searching “{query}”…")
        self._searching_segment_ids.add(segment_id)

        # Read off the model here: the thread body must not touch the UI or the model.
        min_duration_s = segment_playback_duration(self._word_timeline, self._segment)

        run_in_thread(
            lambda: run_distributed_search(
                query,
                limit=limit,
                providers=providers,
                min_duration_s=min_duration_s,
            ),
            on_success=lambda results: self._on_search_finished(segment_id, query, results),
            on_error=lambda exc: self._on_search_failed(segment_id, exc),
        )

    def _on_search_finished(self, segment_id: int, query: str, results: list[SearchResult]) -> None:
        self._searching_segment_ids.discard(segment_id)
        self._search_cache.set(segment_id, query=query, results=results)
        # This segment's dot reads its entry, which just changed, and the segment
        # is not necessarily the one on screen.
        self._on_results_changed()
        # The user may have navigated on while the search ran. The cache above keeps
        # the results, so coming back to this segment restores them.
        if self._segment.id != segment_id:
            return

        if not results:
            self._set_search_loading(False, "No results (or blocked). Try another keyword.")
            self.relayout_grid()
            return

        self._clear_results()
        for result in results:
            self._tiles.append(self._build_result_tile(result))
        self._set_search_loading(
            False,
            f"Showing {len(results)}/{search_settings_state().limit} result(s).",
        )
        self.relayout_grid()

    def _on_search_failed(self, segment_id: int, exc: Exception) -> None:
        self._searching_segment_ids.discard(segment_id)
        print(f"[segment_view_grid] search failed: {exc}")
        if self._segment.id != segment_id:
            return
        self._set_search_loading(False, "Search failed. Try again.")

    def _select_media(self, result: SearchResult) -> None:
        attach_media(self._segment, result)
        self._thumb_bytes_by_segment_id[self._segment.id] = result.thumb_bytes
        self._on_media_selected(self._segment.id, result.thumb_bytes)
        self.sync_media_tile()

    def sync_media_tile(self) -> None:
        """Draw the Media tile's preview from the active segment's media.

        Priority (first match wins):
        1. Empty state text, no media is attached yet.
        2. The media itself, see 'show_media', which draws it or falls back
           to a "Thumbnail error" label.

        The project grid runs the same ladder in 'SegmentTile.refresh_media'.
        It can keep its remembered bytes in a plain field because it builds one tile
        per segment. This view reuses a single preview widget for every segment,
        so its bytes have to be stored per segment id instead.
        """
        preview = self._media_preview
        if preview is None:
            return
        media = self._segment.media

        # 1) Empty state text, no media is attached yet
        if media is None:
            preview.clear_media()
            preview.set_placeholder_text("No media selected")
            return

        # 2) The media itself, drawn from disk or from the bytes kept when it was attached
        preview.show_media(media, thumb_bytes=self._thumb_bytes_by_segment_id.get(self._segment.id))
