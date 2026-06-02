from abc import ABC, abstractmethod
from typing import Any

IMAGE_MEDIA = "image"
VIDEO_MEDIA = "video"
GIF_MEDIA = "gif"
ALL_MEDIA = (IMAGE_MEDIA, VIDEO_MEDIA, GIF_MEDIA)


class Media(ABC):
    def __init__(
        self,
        file_path: str = None,
        url: str = None,
        source: str | None = None,
    ):
        self.file_path = file_path
        self.url = url
        self.source = source

        # Validate that only one of file_path or url is provided
        if self.file_path and self.url:
            raise ValueError("Media can have either a file path or a URL, not both.")
    
    def validate_media(self, key: str, value: str) -> str:
        """Validate media fields"""
        if self.file_path and self.url:
            raise ValueError("Media can have either a file path or a URL, not both.")
        return value

    def set_file_path(self, path: str) -> None:
        """Persist media to a local file path (clears url)."""
        self.url = None
        self.file_path = path

    @abstractmethod
    def to_dict(self) -> dict[str, Any]:
        pass

    @property
    @abstractmethod
    def media_type(self) -> str:
        pass


class ImageMedia(Media):
    def __init__(
        self,
        file_path: str = None,
        url: str = None,
        source: str | None = None,
    ):
        super().__init__(file_path, url, source)

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": IMAGE_MEDIA,
            "file_path": self.file_path,
            "url": self.url,
            "source": self.source,
        }

    @property
    def media_type(self) -> str:
        return IMAGE_MEDIA


class VideoMedia(Media):
    def __init__(
        self,
        file_path: str = None,
        url: str = None,
        start_timestamp: float = 0,
        source: str | None = None,
    ):
        super().__init__(file_path, url, source)
        if start_timestamp < 0:
            raise ValueError("start_timestamp must be non-negative")
        self.start_timestamp = start_timestamp

    def set_start_timestamp(self, start_timestamp: float) -> None:
        if start_timestamp < 0:
            raise ValueError("start_timestamp must be non-negative")
        self.start_timestamp = start_timestamp

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": VIDEO_MEDIA,
            "file_path": self.file_path,
            "url": self.url,
            "start_timestamp": self.start_timestamp,
            "source": self.source,
        }

    @property
    def media_type(self) -> str:
        return VIDEO_MEDIA


class GifMedia(Media):
    def __init__(
        self,
        file_path: str = None,
        url: str = None,
        source: str | None = None,
    ):
        super().__init__(file_path, url, source)

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": GIF_MEDIA,
            "file_path": self.file_path,
            "url": self.url,
            "source": self.source,
        }

    @property
    def media_type(self) -> str:
        return GIF_MEDIA


def media_from_dict(data: dict[str, Any]) -> Media:
    if not isinstance(data, dict):
        raise TypeError(f"media_from_dict() expected dict, got {type(data).__name__!r}")
    if not data:
        raise ValueError("media payload is empty")
    kind = data.get("type")
    source = data.get("source")
    if kind == IMAGE_MEDIA:
        return ImageMedia(
            file_path=data.get("file_path"),
            url=data.get("url"),
            source=source,
        )
    if kind == VIDEO_MEDIA:
        return VideoMedia(
            file_path=data.get("file_path"),
            url=data.get("url"),
            start_timestamp=float(data.get("start_timestamp", 0)),
            source=source,
        )
    if kind == GIF_MEDIA:
        return GifMedia(
            file_path=data.get("file_path"),
            url=data.get("url"),
            source=source,
        )
    raise ValueError(f"Unknown media type: {kind!r}")
