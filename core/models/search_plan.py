"""The media search the LLM planned for each segment.

'parse_search_plan' is the only way to build a 'SearchPlan', and it raises unless the
reply covers exactly the segments it was asked about (compared by id lists).
"""

import json
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

# Search options the prompt offers the LLM, and the providers each one searches.
# Auto-assign searches exactly these. The search settings menu governs manual search
# only, so it can neither narrow nor widen them.
PROVIDERS_BY_SOURCE: dict[str, set[str]] = {
    "web": {"web"},
    "stock": {"pexels_image", "pexels_video", "pixabay_image", "pixabay_video"},
}


@dataclass(frozen=True)
class SegmentQuery:
    """One planned search: which source to search, and what for.

    Carries its own 'segment_id' because the suggestion engine queues these and gets
    the results back out of order.
    """

    segment_id: int
    source: str
    query: str
    reason: str


@dataclass(frozen=True)
class SearchPlan:
    """One planned search per segment, plus the video's overall topic and tone."""

    topic: str
    tone: str
    query_by_segment_id: dict[int, SegmentQuery]

    def to_dict(self) -> dict[str, Any]:
        return {
            "context": {"topic": self.topic, "tone": self.tone},
            "segments": [
                {
                    "id": entry.segment_id,
                    "source": entry.source,
                    "query": entry.query,
                    "reason": entry.reason,
                }
                for entry in self.query_by_segment_id.values()
            ],
        }


def parse_search_plan(raw: str, *, segment_ids: Sequence[int]) -> SearchPlan:
    """Read the model's reply into a plan covering exactly 'segment_ids'.

    Raises unless every segment is planned once with a usable query. A source we
    cannot search falls back to web, so a plan never comes back with a segment
    missing from it.
    """
    payload = json.loads(raw)
    entries = payload.get("segments")
    if not isinstance(entries, list):
        raise ValueError("Search plan has no 'segments' list.")

    parsed_ids: list[int] = []
    for entry in entries:
        if not isinstance(entry, dict) or not isinstance(entry.get("id"), int):
            raise ValueError("Search plan entry has no integer 'id'.")
        parsed_ids.append(entry["id"])
    if sorted(parsed_ids) != sorted(segment_ids):
        raise ValueError(
            f"Search plan covers ids {sorted(parsed_ids)}, expected {sorted(segment_ids)}."
        )

    query_by_segment_id: dict[int, SegmentQuery] = {}
    for entry in entries:
        segment_id = entry["id"]
        query = str(entry.get("query", "")).strip()
        if not query:
            raise ValueError(f"Search plan has no query for segment {segment_id}.")

        source = str(entry.get("source", "")).strip().lower()
        query_by_segment_id[segment_id] = SegmentQuery(
            segment_id=segment_id,
            # Web is the broader of the two, so it is the safer guess.
            source=source if source in PROVIDERS_BY_SOURCE else "web",
            query=query,
            # Only ever shown in a tooltip, so an absent one is not worth a raise.
            reason=str(entry.get("reason", "")).strip(),
        )

    context = payload.get("context")
    if not isinstance(context, dict):
        context = {}

    return SearchPlan(
        topic=str(context.get("topic", "")).strip(),
        tone=str(context.get("tone", "")).strip(),
        query_by_segment_id=query_by_segment_id,
    )
