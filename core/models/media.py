from abc import ABC, abstractmethod
from enum import StrEnum
from typing import Any


class MediaType(StrEnum):
    IMAGE = "image"
    VIDEO = "video"
    GIF = "gif"


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

    def set_file_path(self, path: str) -> None:
        """Persist media to a local file path (clears url)."""
        self.url = None
        self.file_path = path

    @abstractmethod
    def to_dict(self) -> dict[str, Any]:
        pass

    @classmethod
    @abstractmethod
    def from_dict(cls, data: dict[str, Any]) -> "Media":
        pass

    @property
    @abstractmethod
    def media_type(self) -> MediaType:
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
            "type": MediaType.IMAGE,
            "file_path": self.file_path,
            "url": self.url,
            "source": self.source,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ImageMedia":
        return cls(
            file_path=data.get("file_path"),
            url=data.get("url"),
            source=data.get("source"),
        )

    @property
    def media_type(self) -> MediaType:
        return MediaType.IMAGE


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
            "type": MediaType.VIDEO,
            "file_path": self.file_path,
            "url": self.url,
            "start_timestamp": self.start_timestamp,
            "source": self.source,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "VideoMedia":
        return cls(
            file_path=data.get("file_path"),
            url=data.get("url"),
            start_timestamp=float(data.get("start_timestamp", 0)),
            source=data.get("source"),
        )

    @property
    def media_type(self) -> MediaType:
        return MediaType.VIDEO


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
            "type": MediaType.GIF,
            "file_path": self.file_path,
            "url": self.url,
            "source": self.source,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "GifMedia":
        return cls(
            file_path=data.get("file_path"),
            url=data.get("url"),
            source=data.get("source"),
        )

    @property
    def media_type(self) -> MediaType:
        return MediaType.GIF


_MEDIA_CLASSES: dict[MediaType, type[Media]] = {
    MediaType.IMAGE: ImageMedia,
    MediaType.VIDEO: VideoMedia,
    MediaType.GIF: GifMedia,
}


def media_from_dict(data: dict[str, Any]) -> Media:
    if not isinstance(data, dict):
        raise TypeError(f"media_from_dict() expected dict, got {type(data).__name__!r}")
    if not data:
        raise ValueError("media payload is empty")
    media_type = MediaType(data["type"])
    return _MEDIA_CLASSES[media_type].from_dict(data)


def media_from_url(
    media_type: MediaType, *, url: str, source: str | None = None
) -> Media:
    """Construct a URL-backed Media of the given type (used at selection time)."""
    return _MEDIA_CLASSES[MediaType(media_type)](url=url, source=source)