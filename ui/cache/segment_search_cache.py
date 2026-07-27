from dataclasses import dataclass

from services.search_common import SearchResult


@dataclass
class SegmentSearchState:
    """Cached search query and fetched thumbnail data for one segment."""

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

    def thumb_bytes_for_url(self, segment_id: int, url: str) -> bytes | None:
        """Return cached search thumbnail bytes for a result URL, if any."""
        state = self.get(segment_id)
        if state is None:
            return None
        for result in state.results:
            if result.url == url:
                return bytes(result.thumb_bytes)
        return None