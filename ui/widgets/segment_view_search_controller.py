"""Segment view search UI: validation, async fetch, cache, and search in-progress segment tracking."""

import threading
from collections.abc import Callable

from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QLineEdit, QLabel, QPushButton

from core.models.segment import Segment
from core.models.word_timeline import WordTimeline, segment_playback_duration
from ui.cache.segment_search_cache import SegmentSearchCache
from ui.widgets.search_settings import search_settings_state
from ui.widgets.segment_view_search_logic import (
    build_source_distribution,
    to_cached_results,
)
from ui.widgets.segment_view_search_runner import run_distributed_search


class SegmentViewSearchController(QObject):
    """Run segment media search off the UI thread and apply results via callbacks."""

    # search_segment_id, search query, list of (media_type, url, thumb_bytes, source)
    results_ready = Signal(int, str, list)

    def __init__(
        self,
        *,
        parent: QObject,
        cache: SegmentSearchCache,
        word_timeline: WordTimeline,
        get_current_segment_id: Callable[[], int],
        clear_results: Callable[[], None],
        set_search_busy: Callable[[bool, str], None],
        apply_search_results: Callable[[list], int],
        rebuild_grid: Callable[[], None],
    ) -> None:
        super().__init__(parent)
        self.results_ready.connect(self._on_results_ready)
        self._cache = cache
        self._word_timeline = word_timeline
        self._get_current_segment_id = get_current_segment_id
        self._clear_results = clear_results
        self._set_search_busy = set_search_busy
        self._apply_search_results = apply_search_results
        self._rebuild_grid = rebuild_grid
        self._searching_segment_ids: set[int] = set()

    def is_segment_searching(self, segment_id: int) -> bool:
        return segment_id in self._searching_segment_ids

    def on_search_clicked(
        self,
        *,
        segment: Segment,
        search_input: QLineEdit | None,
        search_button: QPushButton | None,
        search_status: QLabel | None,
    ) -> None:
        if search_input is None or search_button is None or search_status is None:
            return
        query = search_input.text().strip()
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
        search_segment_id = segment.id
        self._cache.set(search_segment_id, query=query, results=[])
        self._set_search_busy(True, f"Searching “{query}”…")
        self._searching_segment_ids.add(search_segment_id)

        min_video_duration_s = segment_playback_duration(self._word_timeline, segment)

        def run() -> None:
            merged = run_distributed_search(
                query=query,
                limit=limit,
                source_distribution=source_distribution,
                min_video_duration_s=min_video_duration_s,
            )
            self.results_ready.emit(search_segment_id, query, merged)

        threading.Thread(target=run, daemon=True).start()

    def _on_results_ready(
        self, search_segment_id: int, query: str, results: list
    ) -> None:
        try:
            if not results:
                self._cache.set(search_segment_id, query=query, results=[])
                if self._get_current_segment_id() == search_segment_id:
                    self._set_search_busy(
                        False, "No results (or blocked). Try another keyword."
                    )
                    self._rebuild_grid()
                return

            self._cache.set(
                search_segment_id,
                query=query,
                results=to_cached_results(results),
            )
            if self._get_current_segment_id() != search_segment_id:
                return

            self._clear_results()
            added = self._apply_search_results(results)
            self._set_search_busy(
                False,
                f"Showing {added}/{search_settings_state().limit} result(s).",
            )
            self._rebuild_grid()
        finally:
            self._searching_segment_ids.discard(search_segment_id)
