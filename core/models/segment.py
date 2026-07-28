from __future__ import annotations

from typing import Any

from .media import Media


class Segment:
    def __init__(self, text: str, segment_id: int):
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