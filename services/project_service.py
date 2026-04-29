import json
import re
import hashlib
import shutil
import urllib.parse
import urllib.request
from pathlib import Path

from core.models.project import Project
from core.models.media import GifMedia, ImageMedia, Media, VideoMedia
from core.media_processor import MEDIA_SUBDIR
from core.voiceover import AUDIO_SUBDIR, voiceover_relative_path
from config import PROJECTS_DIR
from services.voiceover_service import write_project_voiceover

PROJECT_JSON_FILENAME = "project.json"
NARRATION_FILENAME = "narration.txt"

INVALID_FOLDER_CHARS = set('<>:"/\\|?*')


def validate_project_title_for_storage(title: str) -> str:
    """Return stripped title for use as the project folder name. Raises ValueError if invalid."""
    normalized = title.strip()
    if not normalized:
        raise ValueError("Project title cannot be empty.")
    if normalized.endswith("."):
        raise ValueError("Project title cannot end with a period.")
    if any(char in INVALID_FOLDER_CHARS for char in normalized):
        raise ValueError(
            "Project title cannot contain invalid path characters: "
            + " ".join(sorted(INVALID_FOLDER_CHARS))
        )
    return normalized


def list_project_titles(projects_dir: Path | None = None) -> list[str]:
    projects_dir = PROJECTS_DIR if projects_dir is None else projects_dir
    if not projects_dir.exists():
        return []

    return sorted([item.name for item in projects_dir.iterdir() if item.is_dir()])


def load_project(title: str, projects_dir: Path | None = None) -> Project:
    """Load a project by title from its JSON file."""
    projects_dir = PROJECTS_DIR if projects_dir is None else projects_dir
    project_dir = projects_dir / title
    json_path = project_dir / PROJECT_JSON_FILENAME
    if not project_dir.is_dir():
        raise FileNotFoundError(f"Project folder not found: {project_dir}")
    if not json_path.is_file():
        raise FileNotFoundError(f"Project file not found: {json_path}")
    raw = json_path.read_text(encoding="utf-8")
    data = json.loads(raw)
    return Project.from_dict(data)


def get_next_project_title(projects_dir: Path | None = None) -> str:
    """Return first available Project_x title based on existing project folders."""
    projects_dir = PROJECTS_DIR if projects_dir is None else projects_dir
    max_index = 0
    pattern = re.compile(r"^Project_(\d+)$")

    if projects_dir.exists():
        for item in projects_dir.iterdir():
            if not item.is_dir():
                continue
            match = pattern.match(item.name)
            if not match:
                continue
            max_index = max(max_index, int(match.group(1)))

    return f"Project_{max_index + 1}"


def create_project_from_segments(
    segments: list[str],
    title: str = "Untitled",
    voiceover_path: str | None = None,
) -> Project:
    """Create a new in-memory Project from segment texts (no saving)."""
    return Project(segments=segments, title=title, voiceover_path=voiceover_path)

def create_and_save_project(
    segments: list[str], title: str = "Untitled", narration: str | None = None
) -> Project:
    """Create a new project and save it to the filesystem."""
    dir_name = validate_project_title_for_storage(title)
    project_dir = PROJECTS_DIR / dir_name
    project_dir.mkdir(parents=True, exist_ok=True)
    (project_dir / MEDIA_SUBDIR).mkdir(parents=True, exist_ok=True)

    voiceover_rel: str | None = None
    if narration is not None:
        (project_dir / NARRATION_FILENAME).write_text(narration, encoding="utf-8")
        if narration.strip():
            audio_dir = project_dir / AUDIO_SUBDIR
            audio_dir.mkdir(parents=True, exist_ok=True)
            write_project_voiceover(narration, audio_dir)
            voiceover_rel = voiceover_relative_path()

    project = create_project_from_segments(segments, title=dir_name, voiceover_path=voiceover_rel)
    json_path = project_dir / PROJECT_JSON_FILENAME
    payload = project.to_dict()
    json_path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return project

def is_project_title_unique(title: str, projects_dir: Path | None = None) -> bool:
    """Return True when no existing project folder has the same name."""
    projects_dir = PROJECTS_DIR if projects_dir is None else projects_dir
    normalized = title.strip().casefold()
    if not normalized or not projects_dir.exists():
        return True

    for item in projects_dir.iterdir():
        if item.is_dir() and item.name.casefold() == normalized:
            return False
    return True


def _guess_ext_from_url(url: str, *, fallback: str) -> str:
    path = urllib.parse.urlparse(url).path
    ext = Path(path).suffix.lower()
    if ext and 1 < len(ext) <= 6:
        return ext
    return fallback


def _download_url_to_path(url: str, dest_path: Path, *, timeout_s: float = 20.0) -> None:
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122 Safari/537.36",
            "Accept-Language": "en-US,en;q=0.9",
        },
    )
    with urllib.request.urlopen(req, timeout=timeout_s) as resp:
        data = resp.read()
    dest_path.write_bytes(data)


def _ensure_media_persisted(project_dir: Path, segment_id: int, media: Media) -> Media:
    """Return a Media with a stable file_path under media/ (downloading/copying if needed)."""
    media_dir = project_dir / MEDIA_SUBDIR
    media_dir.mkdir(parents=True, exist_ok=True)

    # If already a file_path, ensure it's inside media/.
    if media.file_path:
        src = Path(media.file_path)
        if not src.is_absolute():
            # treat as project-relative
            src = (project_dir / src).resolve()
        if src.is_file():
            try:
                src.relative_to(media_dir.resolve())
                # Already in media dir, keep as relative path for portability
                rel = src.relative_to(project_dir).as_posix()
                if isinstance(media, ImageMedia):
                    return ImageMedia(file_path=rel)
                if isinstance(media, GifMedia):
                    return GifMedia(file_path=rel)
                if isinstance(media, VideoMedia):
                    return VideoMedia(file_path=rel, start_timestamp=media.start_timestamp)
            except ValueError:
                pass

            # Copy into media dir
            ext = src.suffix.lower() or (
                ".jpg" if isinstance(media, ImageMedia) else ".gif" if isinstance(media, GifMedia) else ".mp4"
            )
            name = f"{segment_id}_{hashlib.sha256(str(src).encode('utf-8')).hexdigest()[:16]}{ext}"
            dest = media_dir / name
            if not dest.exists():
                shutil.copyfile(src, dest)
            rel = dest.relative_to(project_dir).as_posix()
            if isinstance(media, ImageMedia):
                return ImageMedia(file_path=rel)
            if isinstance(media, GifMedia):
                return GifMedia(file_path=rel)
            if isinstance(media, VideoMedia):
                return VideoMedia(file_path=rel, start_timestamp=media.start_timestamp)

        return media

    # Otherwise, download from URL if present
    if media.url:
        url = media.url
        fallback_ext = ".jpg" if isinstance(media, ImageMedia) else ".gif" if isinstance(media, GifMedia) else ".mp4"
        ext = _guess_ext_from_url(url, fallback=fallback_ext)
        name = f"{segment_id}_{hashlib.sha256(url.encode('utf-8')).hexdigest()[:16]}{ext}"
        dest = media_dir / name
        if not dest.exists():
            _download_url_to_path(url, dest)
        rel = dest.relative_to(project_dir).as_posix()
        if isinstance(media, ImageMedia):
            return ImageMedia(file_path=rel)
        if isinstance(media, GifMedia):
            return GifMedia(file_path=rel)
        if isinstance(media, VideoMedia):
            return VideoMedia(file_path=rel, start_timestamp=media.start_timestamp)

    return media


def _cleanup_unused_project_media(project_dir: Path, project: Project) -> None:
    """Delete unreferenced files in `<project>/media/` based on current segment media."""
    media_dir = project_dir / MEDIA_SUBDIR
    if not media_dir.is_dir():
        return

    referenced_files: set[Path] = set()
    for seg in project.segments:
        media = seg.media
        if media is None or not media.file_path:
            continue

        candidate = Path(media.file_path)
        resolved = (
            candidate.resolve()
            if candidate.is_absolute()
            else (project_dir / candidate).resolve()
        )
        try:
            resolved.relative_to(media_dir.resolve())
        except ValueError:
            # Ignore any path outside this project's media directory.
            continue
        if resolved.is_file():
            referenced_files.add(resolved)

    for media_file in media_dir.iterdir():
        if not media_file.is_file():
            continue
        try:
            resolved_media_file = media_file.resolve()
        except OSError:
            continue
        if resolved_media_file in referenced_files:
            continue
        try:
            media_file.unlink()
        except OSError:
            # Best effort cleanup, do not block save for deletion failures
            continue


def save_project(project: Project, projects_dir: Path | None = None) -> Path:
    """Persist an existing in-memory project to disk.

    - Ensures `<project>/media/` exists.
    - If a segment has media with a URL, downloads it into `media/` and converts to `file_path`.
    - Writes `project.json`.
    - Cleans up unused media files from `<project>/media/`.
    """
    projects_dir = PROJECTS_DIR if projects_dir is None else projects_dir
    dir_name = validate_project_title_for_storage(project.title)
    project_dir = projects_dir / dir_name
    project_dir.mkdir(parents=True, exist_ok=True)
    (project_dir / MEDIA_SUBDIR).mkdir(parents=True, exist_ok=True)

    # Materialize selected media to media/ folder (only for attached media)
    for seg in project.segments:
        if seg.media is None:
            continue
        try:
            seg.media = _ensure_media_persisted(project_dir, seg.id, seg.media)
        except Exception:
            # Don't block saving the rest of the project on a single media failure
            continue

    json_path = project_dir / PROJECT_JSON_FILENAME
    json_path.write_text(
        json.dumps(project.to_dict(), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    _cleanup_unused_project_media(project_dir, project)
    return json_path
