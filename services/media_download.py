"""Download one media file to disk, picking its extension from the response.

Both the project save (media/ folder) and the hover preview (temp cache) need the
same thing: fetch a URL and write it under a name the caller chose. The caller
cannot supply the extension, because what the URL actually serves is only known
once the response arrives. Only the destination differs between the two, so this
is one function taking the destination.
"""

import urllib.request
from pathlib import Path

from core.media_ext import resolve_media_ext
from headers import BROWSER_HEADERS

DOWNLOAD_TIMEOUT_S = 20.0


def download_media(url: str, dest_base: Path) -> Path:
    """Download 'url' and write it to 'dest_base' with an extension appended.

    'dest_base' is an extensionless path. The extension comes from
    'resolve_media_ext', which reads the URL's own suffix first and falls back to the
    response Content-Type, so the returned path is never 'dest_base' itself.

    Errors propagate, including an unrecognized media type, so a caller that can
    carry on without the file catches them.
    """
    dest_base.parent.mkdir(parents=True, exist_ok=True)
    request = urllib.request.Request(url, headers=BROWSER_HEADERS)
    with urllib.request.urlopen(request, timeout=DOWNLOAD_TIMEOUT_S) as response:
        data = response.read()
        ext = resolve_media_ext(url, response.headers.get("Content-Type"))
    dest = dest_base.with_suffix(ext)
    dest.write_bytes(data)
    return dest