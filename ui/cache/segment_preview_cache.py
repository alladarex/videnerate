import hashlib
import shutil
import tempfile
import time
from pathlib import Path

from core.project_paths import ProjectPaths


def cached_file_for_base(base: Path) -> Path | None:
    """Return the on-disk cached file for an extensionless cache base, if any."""
    return next((p for p in base.parent.glob(f"{base.name}.*") if p.is_file()), None)


class SegmentPreviewCache:
    """Project-scoped temp cache for hover media previews."""

    def __init__(self, paths: ProjectPaths) -> None:
        self.paths = paths
        self.project_title = paths.root.name
        self._cache_dir = (
            Path(tempfile.gettempdir()) / "videnerate_preview_cache" / self.project_title
        )

    def clear(self) -> None:
        if not self._cache_dir.exists():
            return
        # Windows may hold a short-lived lock on the most recently played file
        for _ in range(6):
            try:
                shutil.rmtree(self._cache_dir)
            except Exception:
                pass
            if not self._cache_dir.exists():
                return
            time.sleep(0.05)
        if self._cache_dir.exists():
            print(f"[segment_preview_cache] cache cleanup incomplete: {self._cache_dir}")

    def cache_base_for_url(self, url: str) -> Path:
        """Return the extensionless download target for a URL, the suffix is added after download."""
        name = hashlib.sha256(url.encode("utf-8")).hexdigest()[:16]
        self._cache_dir.mkdir(parents=True, exist_ok=True)
        return self._cache_dir / name
