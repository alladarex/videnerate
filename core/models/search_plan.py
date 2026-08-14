"""The media search the LLM planned for each segment."""

import json
from dataclasses import dataclass
from typing import Any

# Search options the prompt offers the LLM, and the providers each one searches.
# Auto-search searches exactly these.
PROVIDERS_BY_SOURCE: dict[str, set[str]] = {
    "web": {"web"},
    "stock": {"pexels_image", "pexels_video", "pixabay_image", "pixabay_video"},
}


@dataclass(frozen=True)
class SegmentQuery:
    """One planned search: which source to search, what for, and the text it came from.

    Carries its own 'segment_id' because the suggestion engine queues these and gets
    the results back out of order. 'text' is the segment's own narration, kept for
    the ranker. 'reason' is one sentence, shown in the '?' tooltip.
    """

    segment_id: int
    source: str
    query: str
    reason: str
    text: str


@dataclass(frozen=True)
class SearchPlan:
    """One planned search per segment, plus the video's overall topic and tone."""

    topic: str
    tone: str
    # The id appears twice on purpose. As a key it lets the engine find one
    # segment's query when a worker comes back holding nothing but an id. Inside
    # the SegmentQuery it travels with the query itself, which is passed around
    # alone. A dict also keeps the segments in the order they were added, so the
    # engine builds its queue by iterating this and gets plan order for free.
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
                    "text": entry.text,
                }
                for entry in self.query_by_segment_id.values()
            ],
        }


def parse_search_plan(raw: str, *, text_by_segment_id: dict[int, str]) -> SearchPlan:
    """Read the model's reply into a plan covering the given segments.

    Raises unless every segment is planned once (id lists are compared) with a usable query.
    A source we cannot search falls back to web, so a plan never comes back with a segment
    that has a missing search source. 'text' is injected from 'text_by_segment_id',
    never read from the reply, so the prompt does not pay for the model echoing back our input.
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
    if sorted(parsed_ids) != sorted(text_by_segment_id):
        raise ValueError(
            f"Search plan covers ids {sorted(parsed_ids)}, expected {sorted(text_by_segment_id)}."
        )

    query_by_segment_id: dict[int, SegmentQuery] = {}
    for entry in entries:
        segment_id = entry["id"]
        query = str(entry.get("query") or "").strip()
        if not query:
            raise ValueError(f"Search plan has no query for segment {segment_id}.")

        source = str(entry.get("source") or "").strip().lower()
        query_by_segment_id[segment_id] = SegmentQuery(
            segment_id=segment_id,
            # Web is the broadest source, making it the safest fallback
            source=source if source in PROVIDERS_BY_SOURCE else "web",
            query=query,
            # Only ever shown in a tooltip, so an absent one is not worth a raise
            reason=str(entry.get("reason") or "").strip(),
            text=text_by_segment_id[segment_id],
        )

    context = payload.get("context")
    if not isinstance(context, dict):
        context = {}

    return SearchPlan(
        topic=str(context.get("topic") or "").strip(),
        tone=str(context.get("tone") or "").strip(),
        query_by_segment_id=query_by_segment_id,
    )
