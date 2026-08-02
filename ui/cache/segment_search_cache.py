from dataclasses import dataclass

from services.search_common import SearchResult


@dataclass
class SegmentSearchEntry:
    """The query last searched for one segment and the results it returned."""

    query: str
    results: list[SearchResult]


class SegmentSearchCache:
    """In-memory per-segment cache (lives for program runtime)."""

    def __init__(self) -> None:
        self._entry_by_segment_id: dict[int, SegmentSearchEntry] = {}

    def get(self, segment_id: int) -> SegmentSearchEntry | None:
        return self._entry_by_segment_id.get(segment_id)

    def set(self, segment_id: int, *, query: str, results: list[SearchResult]) -> None:
        self._entry_by_segment_id[segment_id] = SegmentSearchEntry(
            query=query,
            results=list(results),
        )
