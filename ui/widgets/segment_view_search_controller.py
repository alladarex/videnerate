"""Segment view search UI: validation, async fetch, cache, and search in-progress segment tracking."""

import threading
from collections.abc import Callable

from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QLineEdit, QLabel, QPushButton

from core.models.segment import Segment
from core.models.word_timeline import WordTimeline, segment_playback_duration
from services.media_search import run_distributed_search
from services.search_common import SearchResult
from ui.cache.segment_search_cache import SegmentSearchCache
from ui.widgets.search_settings import search_settings_state


class SegmentViewSearchController(QObject):
    """Run segment media search off the UI thread and apply results via callbacks."""

    # segment_id the search was started for, search query, list[SearchResult]
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
        apply_search_results: Callable[[list[SearchResult]], int],
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
        enabled = set(settings.enabled)
        if not enabled:
            self._set_search_busy(False, "Enable at least one supported source first.")
            return

        self._clear_results()
        segment_id = segment.id
        self._cache.set(segment_id, query=query, results=[])
        self._set_search_busy(True, f"Searching “{query}”…")
        self._searching_segment_ids.add(segment_id)

        min_duration_s = segment_playback_duration(self._word_timeline, segment)

        def run() -> None:
            results = run_distributed_search(
                query,
                limit=limit,
                enabled=enabled,
                min_duration_s=min_duration_s,
            )
            self.results_ready.emit(segment_id, query, results)

        threading.Thread(target=run, daemon=True).start()

    def _on_results_ready(
        self, segment_id: int, query: str, results: list[SearchResult]
    ) -> None:
        try:
            self._cache.set(segment_id, query=query, results=results)
            if self._get_current_segment_id() != segment_id:
                return

            if not results:
                self._set_search_busy(
                    False, "No results (or blocked). Try another keyword."
                )
                self._rebuild_grid()
                return

            self._clear_results()
            added = self._apply_search_results(results)
            self._set_search_busy(
                False,
                f"Showing {added}/{search_settings_state().limit} result(s).",
            )
            self._rebuild_grid()
        finally:
            self._searching_segment_ids.discard(segment_id)
