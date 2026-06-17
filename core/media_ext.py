import urllib.parse
from pathlib import Path

# HTTP Content-Type header value to file extension dictionary
_CONTENT_TYPE_TO_EXT: dict[str, str] = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/gif": ".gif",
    "image/webp": ".webp",
    "video/mp4": ".mp4",
    "video/quicktime": ".mov",
    "video/webm": ".webm",
}


def ext_from_url_path(url: str) -> str:
    """Return a lowercase extension from the URL path, or empty string."""
    path = urllib.parse.urlparse(url).path
    ext = Path(path).suffix.lower()
    if ext and 1 < len(ext) <= 6:
        return ext
    return ""


def ext_from_content_type(content_type: str | None) -> str:
    """Map a Content-Type header to a file extension, or empty string."""
    if not content_type:
        return ""
    header = content_type.split(";", 1)[0].strip().lower()
    return _CONTENT_TYPE_TO_EXT.get(header, "")


def resolve_media_ext(url: str, content_type: str | None = None) -> str:
    """Pick a file extension from URL suffix, then Content-Type.

    Raises ValueError when neither source is recognized.
    """
    ext = ext_from_url_path(url) or ext_from_content_type(content_type)
    if not ext:
        raise ValueError(
            f"Unrecognized media type for {url!r} (Content-Type: {content_type!r})"
        )
    return ext