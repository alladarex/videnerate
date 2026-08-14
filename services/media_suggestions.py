"""The auto-search engine: search each planned segment, rank the hits, report back.

Both engine callbacks fire on a worker thread, so a Qt caller has to hand
them to the main thread itself.
"""

import threading
from collections import deque
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass

from core.models.search_plan import PROVIDERS_BY_SOURCE, SearchPlan, SegmentQuery
from services.media_search import run_distributed_search
from services.vision_ranking import Suggestion, rank_candidates

# How many hits one planned search collects for the ranker
SUGGESTION_CANDIDATE_LIMIT = 16
# Segments in flight at once, and the worker pool size
SUGGESTION_LOOKAHEAD = 4


@dataclass(frozen=True)
class SegmentSuggestions:
    """What auto-assign came back with for one segment."""

    segment_id: int
    query: str
    suggestions: list[Suggestion]
    error: str | None


def suggest_for_segment(
    query: SegmentQuery,
    *,
    topic: str,
    tone: str,
    min_duration_s: float,
) -> list[Suggestion]:
    """Run one segment's planned search and rank the hits."""
    results = run_distributed_search(
        query.query,
        limit=SUGGESTION_CANDIDATE_LIMIT,
        providers=PROVIDERS_BY_SOURCE[query.source],
        min_duration_s=min_duration_s,
    )
    if not results:
        return []
    return rank_candidates(results, topic=topic, tone=tone, segment_text=query.text)


class SuggestionEngine:
    """Works through the plan in order, SUGGESTION_LOOKAHEAD segments at a time.

    'on_started' fires when a worker takes a segment and always precedes that
    segment's delivery. A skipped or cancelled segment gets no callback
    once cancel is observed. Cancel is terminal: threads cannot be killed,
    so in-flight work finishes and its result is discarded.
    """

    def __init__(
        self,
        plan: SearchPlan,
        *,
        min_duration_s_by_segment_id: dict[int, float],
        on_started: Callable[[int], None],
        on_suggestions: Callable[[SegmentSuggestions], None],
    ) -> None:
        self._plan = plan
        self._min_duration_s_by_segment_id = min_duration_s_by_segment_id
        self._on_started = on_started
        self._on_suggestions = on_suggestions
        # Plan order, start to finish.
        self._pending: deque[int] = deque(plan.query_by_segment_id)
        self._lock = threading.Lock()
        self._cancelled = False
        self._pool = ThreadPoolExecutor(max_workers=SUGGESTION_LOOKAHEAD)

    def start(self) -> None:
        for _ in range(min(SUGGESTION_LOOKAHEAD, len(self._pending))):
            self._pool.submit(self._work)

    def skip(self, segment_id: int) -> None:
        """Drop one queued segment. A no-op if it is already in flight or done."""
        with self._lock:
            try:
                self._pending.remove(segment_id)
            except ValueError:
                pass

    def cancel(self) -> None:
        """Abandon everything still queued or in flight."""
        self._cancelled = True
        with self._lock:
            self._pending.clear()
        self._pool.shutdown(wait=False)

    def _next_segment_id(self) -> int | None:
        with self._lock:
            if self._cancelled or not self._pending:
                return None
            return self._pending.popleft()

    def _work(self) -> None:
        while True:
            segment_id = self._next_segment_id()
            if segment_id is None:
                self._pool.shutdown(wait=False)
                return
            self._run_segment(segment_id)

    def _run_segment(self, segment_id: int) -> None:
        self._on_started(segment_id)
        planned_query = self._plan.query_by_segment_id[segment_id]
        try:
            suggestions = suggest_for_segment(
                planned_query,
                topic=self._plan.topic,
                tone=self._plan.tone,
                min_duration_s=self._min_duration_s_by_segment_id[segment_id],
            )
            error = None
        except Exception as exc:
            # Catching here is also what frees this worker for the next segment.
            print(f"[media_suggestions] segment {segment_id} failed: {exc}")
            suggestions = []
            error = str(exc)
        if self._cancelled:
            return
        self._on_suggestions(
            SegmentSuggestions(
                segment_id=segment_id,
                query=planned_query.query,
                suggestions=suggestions,
                error=error,
            )
        )
