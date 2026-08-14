"""Vision ranking: which media search reasults best fit a segment.

'Suggestion' lives here and not in the 'media_suggestions.py' because it
imports 'rank_candidates', so the other direction would be a circular import.
"""

import base64
import json
from dataclasses import dataclass
from typing import Any

from core.prompts import MEDIA_RANKING_SYSTEM_PROMPT
from services.llm_service import generate_media_ranking
from services.search_common import SearchResult


@dataclass(frozen=True)
class Suggestion:
    """One proposed media, with the model's description of it
    and the reason behind the pick.
    """

    result: SearchResult
    description: str
    reason: str


def _image_data_uri(thumb_bytes: bytes) -> str | None:
    """Return the thumbnail as a base64 'data:' URI, or None if unsupported.

    The data URI requires the image's MIME type, the format is identified
    from it's file signature: fixed identifying bytes near the start of the file.

    JPEG, PNG and WebP are supported. Unknown signatures return None rather
    than guessing, since the original bytes are passed to the API unchanged.

    MIME types: https://www.iana.org/assignments/media-types/media-types.xhtml
    File signatures: https://en.wikipedia.org/wiki/List_of_file_signatures
    """

    # JPEG: FF D8 is the Start Of Image (SOI) marker, JPEG markers begin with FF
    if thumb_bytes.startswith(b"\xff\xd8\xff"):
        mime = "image/jpeg"
    # PNG: fixed 8-byte PNG signature: 89 50 4E 47 0D 0A 1A 0A
    elif thumb_bytes.startswith(b"\x89PNG\r\n\x1a\n"):
        mime = "image/png"
    # WebP: RIFF container ("RIFF"), 4-byte size, then "WEBP" form type
    elif thumb_bytes[:4] == b"RIFF" and thumb_bytes[8:12] == b"WEBP":
        mime = "image/webp"
    else:
        return None
    # base64 because a URI is text and these bytes are not
    return f"data:{mime};base64,{base64.b64encode(thumb_bytes).decode('ascii')}"


def rank_candidates(
    candidates: list[SearchResult],
    *,
    topic: str,
    tone: str,
    segment_text: str,
) -> list[Suggestion]:
    """Ask the vision model for the candidates that best illustrate the segment.

    Returned best first. Ids the model invents or repeats are dropped, as is any
    candidate whose thumbnail format the '_image_data_uri' does not recognise. Raises
    on a malformed reply.
    """
    parts: list[dict[str, Any]] = [
        {
            "type": "text",
            "text": json.dumps(
                {"topic": topic, "tone": tone, "segment": segment_text},
                ensure_ascii=False,
            ),
        }
    ]
    # A text part naming each candidate goes right before its image, which is
    # what makes the returned ids map reliably back onto the right result
    result_by_id: dict[int, SearchResult] = {}
    for i, result in enumerate(candidates):
        uri = _image_data_uri(result.thumb_bytes)
        if uri is None:
            continue
        result_by_id[i] = result
        parts.append({"type": "text", "text": f"Candidate {i}:"})
        parts.append({"type": "image_url", "image_url": {"url": uri, "detail": "low"}})

    # Nothing recognisable to look at, so no llm call should be made
    if not result_by_id:
        return []

    raw = generate_media_ranking(
        [
            {"role": "system", "content": MEDIA_RANKING_SYSTEM_PROMPT},
            {"role": "user", "content": parts},
        ]
    )
    return _parse_picks(raw, result_by_id)


def _parse_picks(raw: str, result_by_id: dict[int, SearchResult]) -> list[Suggestion]:
    payload = json.loads(raw)
    picks = payload.get("picks")
    if not isinstance(picks, list):
        raise ValueError("Ranking reply has no 'picks' list.")

    suggestions: list[Suggestion] = []
    seen_ids: set[int] = set()
    for pick in picks:
        if not isinstance(pick, dict):
            continue
        pick_id = pick.get("id")
        if not isinstance(pick_id, int) or pick_id in seen_ids or pick_id not in result_by_id:
            continue
        seen_ids.add(pick_id)
        suggestions.append(
            Suggestion(
                result=result_by_id[pick_id],
                description=str(pick.get("description") or "").strip(),
                reason=str(pick.get("reason") or "").strip(),
            )
        )
    return suggestions
