from __future__ import annotations

from datetime import datetime
from typing import Any, List

from .segment import Segment


class Project:
    def __init__(
        self,
        segments: List[str],
        title: str = "Untitled",
    ):
        self.title = title
        self.created_at = datetime.now()
        if segments is None:
            raise ValueError("segments must be a list of strings (got None)")
        segment_list = [Segment(text=text, id=i) for i, text in enumerate(segments)]
        self.segments: List[Segment] = segment_list

    def to_dict(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "created_at": self.created_at.isoformat(),
            "segments": [s.to_dict() for s in self.segments],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Project:
        segments = [Segment.from_dict(s) for s in data["segments"]]
        project = object.__new__(cls)
        project.title = data["title"]
        project.created_at = datetime.fromisoformat(data["created_at"])
        project.segments = segments
        return project