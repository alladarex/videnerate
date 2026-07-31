from dataclasses import dataclass

from services.search_common import SearchResult


@dataclass
class SegmentSearchState:
    """The query last searched for one segment and the results it returned."""

    query: str
    results: list[SearchResult]


class SegmentSearchCache:
    """In-memory per-segment cache (lives for program runtime)."""

    def __init__(self) -> None:
        self._by_segment_id: dict[int, SegmentSearchState] = {}

    def get(self, segment_id: int) -> SegmentSearchState | None:
        return self._by_segment_id.get(segment_id)

    def set(
        self, segment_id: int, *, query: str, results: list[SearchResult]
    ) -> None:
        self._by_segment_id[segment_id] = SegmentSearchState(
            query=query,
            results=list(results),
        )