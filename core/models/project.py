from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from .segment import Segment


@dataclass
class Project:
    title: str
    segments: list[Segment]
    created_at: datetime = field(default_factory=datetime.now)

    @classmethod
    def from_segment_texts(
        cls, segment_texts: list[str], title: str = "Untitled"
    ) -> Project:
        """Create a project with one segment per narration text, in order."""
        return cls(
            title=title,
            segments=[
                Segment(text=text, segment_id=i)
                for i, text in enumerate(segment_texts)
            ],
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "created_at": self.created_at.isoformat(),
            "segments": [seg.to_dict() for seg in self.segments],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Project:
        return cls(
            title=data["title"],
            segments=[Segment.from_dict(s) for s in data["segments"]],
            created_at=datetime.fromisoformat(data["created_at"]),
        )