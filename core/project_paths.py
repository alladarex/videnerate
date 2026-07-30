from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from config import PROJECTS_DIR

AUDIO_DIR = "audio"
MEDIA_DIR = "media"

PROJECT_JSON_FILENAME = "project.json"
NARRATION_FILENAME = "narration.txt"
WORD_TIMELINE_FILENAME = "word_timeline.json"
SEGMENTS_ANALYZED_FILENAME = "segments-analyzed.json"
VOICEOVER_FILENAME = "voiceover.mp3"
EXPORT_FILENAME = "export.mp4"
EXPORT_TMP_FILENAME = "export.tmp.mp4"
EXPORT_AUDIO_TMP_FILENAME = ".export_audio.m4a"

# Characters Windows rejects in a file or folder name. Kept as one string so the
# code that builds a name and the code that rejects one cannot drift apart.
INVALID_FILENAME_CHARS = '<>:"/\\|?*'


def sanitize_filename(name: str) -> str:
    """Replace every character a filename cannot hold with an underscore.

    Returns an empty string for a blank name, so a caller that needs a name
    regardless supplies its own fallback.
    """
    return "".join(
        "_" if char in INVALID_FILENAME_CHARS else char for char in name.strip()
    )


@dataclass(frozen=True)
class ProjectPaths:
    """Absolute paths under <PROJECTS_DIR>/<project_title>/."""

    root: Path

    @classmethod
    def from_title(cls, title: str) -> ProjectPaths:
        return cls((PROJECTS_DIR / title.strip()).resolve())

    @classmethod
    def from_root(cls, project_root: Path) -> ProjectPaths:
        return cls(project_root.resolve())

    @property
    def project_json(self) -> Path:
        return self.root / PROJECT_JSON_FILENAME

    @property
    def narration_txt(self) -> Path:
        return self.root / NARRATION_FILENAME

    @property
    def word_timeline_json(self) -> Path:
        return self.root / WORD_TIMELINE_FILENAME

    @property
    def segments_analyzed_json(self) -> Path:
        return self.root / SEGMENTS_ANALYZED_FILENAME

    @property
    def media_dir(self) -> Path:
        return self.root / MEDIA_DIR

    @property
    def audio_dir(self) -> Path:
        return self.root / AUDIO_DIR

    @property
    def voiceover_mp3(self) -> Path:
        return self.audio_dir / VOICEOVER_FILENAME

    @property
    def export_mp4(self) -> Path:
        return self.root / EXPORT_FILENAME

    @property
    def export_tmp_mp4(self) -> Path:
        return self.root / EXPORT_TMP_FILENAME

    @property
    def export_audio_m4a(self) -> Path:
        return self.root / EXPORT_AUDIO_TMP_FILENAME

    def file(self, rel_path: str) -> Path:
        """Resolve a project-relative path (e.g. media/foo.jpg)."""
        return (self.root / rel_path).resolve()

    def ensure_layout(self) -> None:
        """Create standard project folders: root, media/, audio/."""
        self.root.mkdir(parents=True, exist_ok=True)
        self.media_dir.mkdir(parents=True, exist_ok=True)
        self.audio_dir.mkdir(parents=True, exist_ok=True)

    def require_existing(self) -> None:
        if not self.root.is_dir():
            raise FileNotFoundError(f"Project folder not found: {self.root}")
        if not self.project_json.is_file():
            raise FileNotFoundError(f"Project file not found: {self.project_json}")
