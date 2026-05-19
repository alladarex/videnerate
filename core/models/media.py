from abc import ABC, abstractmethod
from typing import Any

IMAGE_MEDIA = "image"
VIDEO_MEDIA = "video"
GIF_MEDIA = "gif"
ALL_MEDIA = (IMAGE_MEDIA, VIDEO_MEDIA, GIF_MEDIA)


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

    @property
    @abstractmethod
    def media_type(self) -> str:
        pass

    @abstractmethod
    def render_media() -> None:
        pass

class ImageMedia(Media):
    def __init__(self, file_path: str = None, url: str = None):
        super().__init__(file_path, url)

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": IMAGE_MEDIA,
            "file_path": self.file_path,
            "url": self.url,
        }

    @property
    def media_type(self) -> str:
        return IMAGE_MEDIA

    def render_media(self) -> None:
        pass


class VideoMedia(Media):
    def __init__(self, file_path: str = None, url: str = None, start_timestamp: float = 0):
        super().__init__(file_path, url)
        self.start_timestamp = start_timestamp

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": VIDEO_MEDIA,
            "file_path": self.file_path,
            "url": self.url,
            "start_timestamp": self.start_timestamp,
        }

    @property
    def media_type(self) -> str:
        return VIDEO_MEDIA

    def render_media(self) -> None:
        pass


class GifMedia(Media):
    def __init__(self, file_path: str = None, url: str = None):
        super().__init__(file_path, url)

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": GIF_MEDIA,
            "file_path": self.file_path,
            "url": self.url,
        }

    @property
    def media_type(self) -> str:
        return GIF_MEDIA

    def render_media(self) -> None:
        pass


def media_from_dict(data: dict[str, Any]) -> Media:
    if not isinstance(data, dict):
        raise TypeError(f"media_from_dict() expected dict, got {type(data).__name__!r}")
    if not data:
        raise ValueError("media payload is empty")
    kind = data.get("type")
    if kind == IMAGE_MEDIA:
        return ImageMedia(
            file_path=data.get("file_path"),
            url=data.get("url"),
        )
    if kind == VIDEO_MEDIA:
        return VideoMedia(
            file_path=data.get("file_path"),
            url=data.get("url"),
            start_timestamp=float(data.get("start_timestamp", 0)),
        )
    if kind == GIF_MEDIA:
        return GifMedia(
            file_path=data.get("file_path"),
            url=data.get("url"),
        )
    raise ValueError(f"Unknown media type: {kind!r}")
