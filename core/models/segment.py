from __future__ import annotations

from typing import Any

from .media import Media, media_from_dict


class Segment:
    def __init__(self, text: str, id: int):
        self.id = id
        self.text = text
        self.media: Media | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "text": self.text,
            "media": self.media.to_dict() if self.media is not None else None,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Segment:
        seg = cls(text=data["text"], id=data["id"])
        raw = data.get("media")
        if raw is not None:
            seg.set_media(media_from_dict(raw))
        return seg

    def set_media(self, media: Media) -> None:
        """Associate a media object with the segment"""
        if not isinstance(media, Media):
            raise ValueError("Invalid media object.")
        self.media = media
