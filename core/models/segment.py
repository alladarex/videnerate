from __future__ import annotations

from typing import Any

from .media import Media


class Segment:
    # Not a dataclass, unlike every other model here: that would force either a
    # ctor parameter named 'id', which shadows the builtin, or renaming the
    # attribute and the 'id' key in project.json.
    def __init__(self, text: str, segment_id: int) -> None:
        self.id = segment_id
        self.text = text
        self.media: Media | None = None
        self.word_start: int | None = None
        self.word_end: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "text": self.text,
            "media": self.media.to_dict() if self.media is not None else None,
            "word_start": self.word_start,
            "word_end": self.word_end,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Segment:
        seg = cls(text=data["text"], segment_id=data["id"])
        raw = data.get("media")
        if raw is not None:
            seg.media = Media.from_dict(raw)
        seg.word_start = int(data["word_start"])
        seg.word_end = int(data["word_end"])
        return seg


def describe_media_failure(segments: list[Segment]) -> str:
    """Returns a message for media that could not be downloaded, for the user to read.

    Each segment in the message is represented by its text.
    """
    subject = "this segment" if len(segments) == 1 else "these segments"
    listed = "\n".join(f"  • {seg.text}" for seg in segments)
    return f"Media for {subject} could not be downloaded:\n\n{listed}"
