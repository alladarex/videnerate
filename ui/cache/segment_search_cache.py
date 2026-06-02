from dataclasses import dataclass


@dataclass
class SegmentSearchResult:
    type: str
    url: str
    thumb_bytes: bytes
    source: str


@dataclass
class SegmentSearchState:
    """Cached search query and fetched thumbnail data for one segment."""

    query: str
    results: list[SegmentSearchResult]


class SegmentSearchCache:
    """In-memory per-segment cache (lives for program runtime)."""

    def __init__(self) -> None:
        self._by_segment_id: dict[int, SegmentSearchState] = {}

    def get(self, segment_id: int) -> SegmentSearchState | None:
        return self._by_segment_id.get(segment_id)

    def set(
        self, segment_id: int, *, query: str, results: list[SegmentSearchResult]
    ) -> None:
        self._by_segment_id[segment_id] = SegmentSearchState(
            query=query,
            results=list(results),
        )
