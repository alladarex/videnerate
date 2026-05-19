import hashlib
import shutil
import tempfile
import time
import urllib.parse
from pathlib import Path

from services.project_service import validate_project_title_for_storage


class SegmentPreviewCache:
    """Project-scoped temp cache for hover media previews."""

    def __init__(self, project_title: str) -> None:
        # Use the same title rules as project folder creation
        self.project_title = validate_project_title_for_storage(project_title)
        self._root = Path(tempfile.gettempdir()) / "videnerate_preview_cache" / self.project_title

    def clear(self) -> None:
        if not self._root.exists():
            return
        # Windows may hold a short-lived lock on the most recently played file.
        for _ in range(6):
            try:
                shutil.rmtree(self._root)
            except Exception:
                pass
            if not self._root.exists():
                return
            time.sleep(0.05)
        if self._root.exists():
            print(f"[segment_preview_cache] cache cleanup incomplete: {self._root}")

    def cache_path_for_url(self, url: str, *, fallback_ext: str) -> Path:
        if not fallback_ext.startswith("."):
            fallback_ext = f".{fallback_ext}"
        ext = Path(urllib.parse.urlparse(url).path).suffix.lower() or fallback_ext
        name = f"{hashlib.sha256(url.encode('utf-8')).hexdigest()[:16]}{ext}"
        self._root.mkdir(parents=True, exist_ok=True)
        return self._root / name
