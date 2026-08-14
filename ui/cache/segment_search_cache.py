from dataclasses import dataclass

from services.search_common import SearchResult
from services.vision_ranking import Suggestion


@dataclass
class SegmentSearchEntry:
    """The query last searched for one segment and the results it returned.

    Auto-assign proposals live here too: 'results' then duplicates their
    'SearchResult's, which is what lets every render path stay unchanged.
    """

    query: str
    results: list[SearchResult]
    # None on a manual search. A list, possibly empty, when auto-assign produced this.
    suggestions: list[Suggestion] | None = None
    error: str | None = None


class SegmentSearchCache:
    """In-memory per-segment cache (lives for program runtime)."""

    def __init__(self) -> None:
        self._entry_by_segment_id: dict[int, SegmentSearchEntry] = {}

    def get(self, segment_id: int) -> SegmentSearchEntry | None:
        return self._entry_by_segment_id.get(segment_id)

    def set(
        self,
        segment_id: int,
        *,
        query: str,
        results: list[SearchResult],
        suggestions: list[Suggestion] | None = None,
        error: str | None = None,
    ) -> None:
        self._entry_by_segment_id[segment_id] = SegmentSearchEntry(
            query=query,
            results=list(results),
            suggestions=suggestions,
            error=error,
        )
