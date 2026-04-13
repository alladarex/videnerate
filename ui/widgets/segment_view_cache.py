from dataclasses import dataclass


@dataclass
class SegmentSearchState:
    """Cached search query and fetched thumbnail data for one segment."""
    query: str
    images: list[bytes]


class SegmentSearchCache:
    """In-memory per-segment cache (lives for program runtime)."""

    def __init__(self) -> None:
        self._by_segment_id: dict[str, SegmentSearchState] = {}

    def get(self, segment_id: str) -> SegmentSearchState | None:
        return self._by_segment_id.get(segment_id)

    def set(self, segment_id: str, *, query: str, images: list[bytes]) -> None:
        self._by_segment_id[segment_id] = SegmentSearchState(query=query, images=list(images))

