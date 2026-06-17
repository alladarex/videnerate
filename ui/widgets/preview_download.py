from __future__ import annotations

import threading
import urllib.request
from pathlib import Path
from typing import Callable

from PySide6.QtCore import QObject, Signal

from core.media_ext import resolve_media_ext
from headers import BROWSER_HEADERS
from ui.cache.segment_preview_cache import cached_file_for_base


def _download_to_base(url: str, target_base: Path) -> tuple[Path, bool]:
    """Download url and append the extension resolved from the response."""
    try:
        req = urllib.request.Request(url, headers=BROWSER_HEADERS)
        with urllib.request.urlopen(req, timeout=20.0) as resp:
            data = resp.read()
            ext = resolve_media_ext(url, resp.headers.get("Content-Type"))
        dest = target_base.with_suffix(ext)
        dest.write_bytes(data)
        return dest, True
    except Exception:
        return target_base, False


class UrlDownloadBroker(QObject):
    """Download a URL once; notify every waiter on the main thread."""

    _instance: UrlDownloadBroker | None = None
    _completed = Signal(str, str, bool)  # url, path, ok

    def __init__(self) -> None:
        super().__init__()
        self._waiters: dict[str, list[Callable[[str, bool], None]]] = {}
        self._completed.connect(self._notify_waiters)

    @classmethod
    def instance(cls) -> UrlDownloadBroker:
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def request(
        self,
        *,
        url: str,
        target_path: Path,
        callback: Callable[[str, bool], None],
    ) -> None:
        target_path.parent.mkdir(parents=True, exist_ok=True)
        cached = cached_file_for_base(target_path)
        if cached is not None:
            callback(str(cached), True)
            return

        waiters = self._waiters.setdefault(url, [])
        waiters.append(callback)
        if len(waiters) > 1:
            return

        threading.Thread(
            target=self._run_download,
            args=(url, target_path),
            daemon=True,
        ).start()

    def _run_download(self, url: str, target_path: Path) -> None:
        path, ok = _download_to_base(url, target_path)
        self._completed.emit(url, str(path), ok)

    def _notify_waiters(self, url: str, path: str, ok: bool) -> None:
        for callback in self._waiters.pop(url, []):
            callback(path, ok)