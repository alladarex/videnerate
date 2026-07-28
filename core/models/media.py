from dataclasses import dataclass
from enum import StrEnum
from typing import Any


class MediaType(StrEnum):
    IMAGE = "image"
    VIDEO = "video"
    GIF = "gif"


@dataclass
class Media:
    """One piece of segment media: a project-local file, a remote URL, or both.

    If Media is selected from search results, it starts as a URL-only media 
    and gains 'file_path' when the project is saved.
    If media is uploaded from the user's device, it will only have 'file_path'.
    'file_path' is resolved first and 'url' is used as the fallback.

    'start_timestamp' is only meaningful for videos, it stays at 0.0 for the other
    types and is omitted from 'to_dict' so project.json keeps its existing shape.
    """

    media_type: MediaType
    file_path: str | None = None
    url: str | None = None
    source: str | None = None
    start_timestamp: float = 0.0

    def __post_init__(self) -> None:
        # 'from_dict' hands over the raw 'type' string out of project.json. Normalizing
        # it here is what lets the rest of the app compare with 'is'.
        self.media_type = MediaType(self.media_type)
        if not self.file_path and not self.url:
            raise ValueError("Media needs a 'file_path' or a 'url'.")
        if self.start_timestamp < 0:
            raise ValueError("start_timestamp must be non-negative")
        if self.media_type is not MediaType.VIDEO and self.start_timestamp:
            raise ValueError(
                f"start_timestamp only applies to video media, got {self.media_type}"
            )

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Media":
        return cls(
            media_type=data["type"],
            file_path=data.get("file_path"),
            url=data.get("url"),
            source=data.get("source"),
            start_timestamp=float(data.get("start_timestamp", 0.0)),
        )

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "type": self.media_type,
            "file_path": self.file_path,
            "url": self.url,
        }
        if self.media_type is MediaType.VIDEO:
            payload["start_timestamp"] = self.start_timestamp
        payload["source"] = self.source
        return payload