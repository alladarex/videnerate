"""Download a hover preview once, however many tiles are waiting on the same URL."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from services.media_download import download_media
from ui.cache.segment_preview_cache import cached_file_for_base
from ui.utils.background_task import run_in_thread

# Called with the downloaded file, or None when the download failed.
DownloadWaiter = Callable[[str | None], None]


class UrlDownloadBroker:
    """Download a URL once, notify every waiter on the main thread.

    Plain object rather than a QObject: 'run_in_thread' already carries the result
    back to the main thread, so there is nothing here for a signal to do.
    """

    _instance: UrlDownloadBroker | None = None

    def __init__(self) -> None:
        self._waiters: dict[str, list[DownloadWaiter]] = {}

    @classmethod
    def instance(cls) -> UrlDownloadBroker:
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def request(
        self,
        *,
        url: str,
        target_base: Path,
        on_done: DownloadWaiter,
    ) -> None:
        """Get 'url' onto disk, then hand the finished file to 'on_done'.

        'target_base' is a path with no extension on it. What the URL actually
        serves is only known once it has been fetched, so the extension is added
        then, and 'on_done' receives the real path that was written, or None if the
        download failed.

        'on_done' always runs on the main thread, but its timing varies. If the file
        is already on disk it is called straight away, before this method returns.
        Otherwise it is called later, once the download finishes.

        Asking for the same url more than once downloads it once. The later callers
        wait in a queue and are all answered together.
        """
        cached = cached_file_for_base(target_base)
        if cached is not None:
            on_done(str(cached))
            return

        waiters = self._waiters.setdefault(url, [])
        waiters.append(on_done)
        if len(waiters) > 1:
            return

        run_in_thread(
            lambda: download_media(url, target_base),
            on_success=lambda path: self._notify_waiters(url, str(path)),
            on_error=lambda exc: self._on_download_failed(url, exc),
        )

    def _on_download_failed(self, url: str, exc: Exception) -> None:
        print(f"[preview_download] download failed for {url}: {exc}")
        self._notify_waiters(url, None)

    def _notify_waiters(self, url: str, path: str | None) -> None:
        for on_done in self._waiters.pop(url, []):
            on_done(path)