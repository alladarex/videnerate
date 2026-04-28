import hashlib
import shutil
import urllib.parse
from pathlib import Path

from config import PROJECTS_DIR


class SegmentPreviewTempCache:
    """Segment-scoped temp cache for hover media previews."""

    def __init__(self, project_title: str) -> None:
        self._root = PROJECTS_DIR / project_title / ".tmp_preview"
        self._active_segment_id: int | None = None
        self._active_dir: Path | None = None

    def activate_segment(self, segment_id: int) -> Path:
        if self._active_segment_id == segment_id and self._active_dir is not None:
            self._active_dir.mkdir(parents=True, exist_ok=True)
            return self._active_dir

        self.clear()
        self._active_segment_id = segment_id
        self._active_dir = self._root / f"segment_{segment_id}"
        self._active_dir.mkdir(parents=True, exist_ok=True)
        return self._active_dir

    def clear(self) -> None:
        self._active_segment_id = None
        self._active_dir = None
        if self._root.exists():
            shutil.rmtree(self._root, ignore_errors=True)

    def path_for_url(self, url: str, segment_id: int, *, fallback_ext: str) -> Path:
        if self._active_dir is None:
            raise RuntimeError("Segment preview cache is not activated.")
        ext = Path(urllib.parse.urlparse(url).path).suffix.lower() or fallback_ext
        name = f"{segment_id}_{hashlib.sha256(url.encode('utf-8')).hexdigest()[:16]}{ext}"
        return self._active_dir / name
