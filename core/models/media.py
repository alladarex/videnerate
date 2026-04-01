from abc import ABC, abstractmethod
from typing import Any


class Media(ABC):
    def __init__(self, file_path: str = None, url: str = None):
        self.file_path = file_path
        self.url = url
        
        # Validate that only one of file_path or url is provided
        if self.file_path and self.url:
            raise ValueError("Media can have either a file path or a URL, not both.")
    
    def validate_media(self, key: str, value: str) -> str:
        """Validate media fields"""
        if self.file_path and self.url:
            raise ValueError("Media can have either a file path or a URL, not both.")
        return value

    @abstractmethod
    def to_dict(self) -> dict[str, Any]:
        pass

    @abstractmethod
    def render_media() -> None:
        pass

class ImageMedia(Media):
    def __init__(self, file_path: str = None, url: str = None):
        super().__init__(file_path, url)

    def to_dict(self) -> dict[str, Any]:
        return {"type": "image", "file_path": self.file_path, "url": self.url}

    def render_media(self) -> None:
        pass


class VideoMedia(Media):
    def __init__(self, segment_id: int, file_path: str = None, url: str = None, start_timestamp: float = 0):
        super().__init__(file_path, url)
        self.segment_id = segment_id
        self.start_timestamp = start_timestamp

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": "video",
            "segment_id": self.segment_id,
            "file_path": self.file_path,
            "url": self.url,
            "start_timestamp": self.start_timestamp,
        }

    def render_media(self) -> None:
        pass


class GifMedia(Media):
    def __init__(self, segment_id: int, file_path: str = None, url: str = None):
        super().__init__(file_path, url)
        self.segment_id = segment_id

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": "gif",
            "segment_id": self.segment_id,
            "file_path": self.file_path,
            "url": self.url,
        }

    def render_media(self) -> None:
        pass


def media_from_dict(data: dict[str, Any]) -> Media:
    if not isinstance(data, dict):
        raise TypeError(f"media_from_dict() expected dict, got {type(data).__name__!r}")
    if not data:
        raise ValueError("media payload is empty")
    kind = data.get("type")
    if kind == "image":
        return ImageMedia(file_path=data.get("file_path"), url=data.get("url"))
    if kind == "video":
        return VideoMedia(
            segment_id=data["segment_id"],
            file_path=data.get("file_path"),
            url=data.get("url"),
            start_timestamp=float(data.get("start_timestamp", 0)),
        )
    if kind == "gif":
        return GifMedia(
            segment_id=data["segment_id"],
            file_path=data.get("file_path"),
            url=data.get("url"),
        )
    raise ValueError(f"Unknown media type: {kind!r}")
